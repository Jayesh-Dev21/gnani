"""Summarisation via GroqCloud, with a fallback chain.

Three rules shape this module:

1. **Failover is for transient trouble, not misconfiguration.** A 429, a 5xx, a
   timeout or an empty completion moves to the next model. A 401 or a 400 stops
   immediately, because retrying a wrong key three times just hides the bug.
2. **A failing model is benched, not retried.** After repeated transient failures
   a model is skipped for a cooldown window, so an outage costs one note one
   skipped attempt instead of three failed calls per note.
3. **Length is handled by reducing, not truncating.** A four hour recording is
   summarised chunk by chunk and the chunks are reduced into one answer, so the
   end of a long recording is never silently dropped.
"""

import asyncio
import logging
from dataclasses import dataclass, field

import httpx

from src.config import settings

log = logging.getLogger("llm")

SYSTEM_PROMPT = (
    "You summarise transcripts of recorded audio. Write 3 to 6 short bullet points "
    "covering what was actually said: the main points, decisions, commitments, "
    "questions and action items. Use the language of the transcript. Never add "
    "information that is not in it. If the transcript is empty or unintelligible, "
    "reply with exactly: (no speech detected)"
)

REDUCE_PROMPT = (
    "Below are summaries of consecutive parts of one recording. Merge them into a "
    "single set of 3 to 6 bullet points. Keep every distinct point, decision and "
    "action item, drop repetition, and do not add anything new."
)

TRANSLATE_PROMPT = (
    "Translate the following transcript to English. Preserve what was actually "
    "said, in order, without summarising, condensing or adding anything. If the "
    "text is already in English, return it unchanged."
)


class LLMError(Exception):
    """Summarisation failed for a reason the user can act on."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ModelUnusable(Exception):
    """One model failed. Transient problems are worth trying the next one."""


class ModelMisconfigured(Exception):
    """The provider rejected our request itself. Trying another model is pointless."""


@dataclass
class _ModelState:
    consecutive_failures: int = 0
    benched_until: float = 0.0

    @property
    def benched(self) -> bool:
        return asyncio.get_running_loop().time() < self.benched_until


# Per-process state: a single worker drains the queue, so a shared dict is the
# whole circuit breaker. Keyed by model id, reset when the worker restarts.
_MODEL_STATE: dict[str, _ModelState] = {}


def reset_model_state() -> None:
    """Forget cooldown history. For tests and for a deliberate operator reset."""
    _MODEL_STATE.clear()


@dataclass
class ChainResult:
    text: str
    model: str
    attempts: list[str] = field(default_factory=list)


def _now() -> float:
    return asyncio.get_running_loop().time()


def _available_models() -> list[str]:
    """Models that are not serving a cooldown, in configured order."""
    return [
        model
        for model in settings.groq_model_chain
        if not _state_for(model).benched
    ]


def _state_for(model: str) -> _ModelState:
    return _MODEL_STATE.setdefault(model, _ModelState())


def _record_failure(model: str) -> None:
    state = _state_for(model)
    state.consecutive_failures += 1
    if state.consecutive_failures >= 2:
        state.benched_until = _now() + settings.llm_model_cooldown_seconds
        log.warning(
            "benching model %s for %ss after %d consecutive failures",
            model,
            settings.llm_model_cooldown_seconds,
            state.consecutive_failures,
        )


def _record_success(model: str) -> None:
    _state_for(model).consecutive_failures = 0


async def _complete(model: str, prompt: str, system: str) -> str:
    """One chat completion against one model."""
    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": settings.llm_max_output_tokens,
    }
    # Only the OpenAI open-weight models document this knob; sending it anywhere
    # else risks a 400 we would then report as a configuration error.
    if model.startswith("openai/gpt-oss"):
        payload["reasoning_effort"] = settings.llm_reasoning_effort

    async with httpx.AsyncClient(
        base_url=settings.groq_base_url,
        headers={"Authorization": f"Bearer {settings.groq_api_key}"},
        timeout=settings.llm_timeout_seconds,
    ) as client:
        try:
            response = await client.post("/chat/completions", json=payload)
        except (httpx.TimeoutException, httpx.TransportError) as error:
            raise ModelUnusable(f"{model}: {type(error).__name__}") from error

    if response.status_code in (401, 403):
        raise ModelMisconfigured(
            "Groq rejected the API key. Check GROQ_API_KEY."
        )
    if response.status_code == 400:
        raise ModelMisconfigured(
            f"Groq rejected the request for {model}: {_error_message(response)}"
        )
    if response.status_code == 429:
        raise ModelUnusable(f"{model}: rate limited (429)")
    if response.status_code >= 500:
        raise ModelUnusable(f"{model}: provider error ({response.status_code})")
    if response.status_code != 200:
        raise ModelMisconfigured(
            f"Groq returned {response.status_code} for {model}: {_error_message(response)}"
        )

    content = _first_message(response)
    if not content:
        # A reasoning model that spent its budget thinking has produced nothing.
        raise ModelUnusable(f"{model}: empty completion")
    return content


async def _try_chain(prompt: str, system: str) -> ChainResult:
    chain = _available_models()
    skipped = [model for model in settings.groq_model_chain if model not in chain]
    if not chain:
        raise LLMError(
            "summary_models_cooling_down",
            "Every summarisation model is temporarily unavailable. Try again in a few "
            "minutes.",
        )

    tried: list[str] = []
    reasons: list[str] = []

    for model in chain:
        tried.append(model)
        try:
            text = await _complete(model, prompt, system)
        except ModelUnusable as error:
            _record_failure(model)
            reasons.append(str(error))
            log.warning("model %s unusable, trying the next one: %s", model, error)
            continue
        except ModelMisconfigured:
            raise
        _record_success(model)
        if skipped:
            log.info("skipped benched models: %s", ", ".join(skipped))
        return ChainResult(text=text, model=model, attempts=tried)

    raise LLMError(
        "summary_all_models_failed",
        "Summarisation failed on every model in the chain: " + "; ".join(reasons),
    )


def _chunks(text: str, size: int) -> list[str]:
    """Split on paragraph boundaries so a chunk never cuts mid sentence if it can."""
    blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
    chunks: list[str] = []
    current: list[str] = []
    length = 0

    for block in blocks:
        if current and length + len(block) > size:
            chunks.append("\n\n".join(current))
            current, length = [], 0
        current.append(block)
        length += len(block)

    if current:
        chunks.append("\n\n".join(current))
    return chunks or ([text] if text.strip() else [])


async def summarise_transcript(transcript: str, language_code: str | None = None) -> ChainResult:
    """Summarise a transcript, reducing chunk by chunk when it is long.

    Non-English transcripts are translated to English first through the same
    model chain, then summarised, so every summary reads the same way no
    matter which language was recorded.
    """
    cleaned = (transcript or "").strip()
    if not cleaned:
        return ChainResult(text="(no speech detected)", model="none")

    if _needs_translation(language_code):
        log.info("translating %s transcript to English before summarising", language_code)
        cleaned = await _translate_to_english(cleaned)

    chunks = _chunks(cleaned, settings.llm_chunk_chars)
    if len(chunks) == 1:
        return await _try_chain(chunks[0], SYSTEM_PROMPT)

    log.info("transcript spans %d chunks, summarising then reducing", len(chunks))
    summaries: list[str] = []
    used_model = "none"
    for index, chunk in enumerate(chunks, start=1):
        result = await _try_chain(chunk, SYSTEM_PROMPT)
        used_model = result.model
        summaries.append(f"Part {index}:\n{result.text}")

    return await _try_chain("\n\n".join(summaries), REDUCE_PROMPT)


def _needs_translation(language_code: str | None) -> bool:
    """True unless the recording's primary language is English.

    The code is one locale or up to three comma-separated ones, first being
    the fallback (e.g. "hi-IN" or "hi-IN,en-IN"); only an "en-*" primary
    skips translation. Unknown or missing codes summarise as-is.
    """
    if not language_code:
        return False
    primary = language_code.split(",")[0].strip().lower()
    return bool(primary) and not primary.startswith("en")


async def _translate_to_english(text: str) -> str:
    """Translate chunk by chunk so a long recording is never truncated."""
    chunks = _chunks(text, settings.llm_chunk_chars)
    translated = [ (await _try_chain(chunk, TRANSLATE_PROMPT)).text for chunk in chunks ]
    if len(chunks) > 1:
        log.info("translated %d chunks to English", len(chunks))
    return "\n\n".join(translated)


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]
    error = body.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error)[:300]
    return str(error or body)[:300]


def _first_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return ""
    choices = body.get("choices") or []
    if not choices:
        return ""
    content = (choices[0].get("message") or {}).get("content")
    return content.strip() if isinstance(content, str) else ""