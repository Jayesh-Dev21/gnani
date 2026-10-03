"""Gnani speech-to-text client.

Two paths, chosen at runtime rather than by measuring the file: try the
synchronous endpoint first, and escalate to Batch when Gnani says the audio is
too long. See <https://docs.gnani.ai/api/STTBatch/Introduction> for the Batch
sequence and <https://docs.gnani.ai/api/STT/speech-to-text> for REST.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import httpx

from src.config import settings

log = logging.getLogger("gnani")

REST_PATH = "/stt/v3"
BATCH_JOBS_PATH = "/stt/v3/batch/jobs"
TERMINAL_STATUSES = {"COMPLETED", "PARTIAL_FAILURE", "FAILED", "START_FAILED", "CANCELLED"}


class GnaniError(Exception):
    """The provider refused or failed the request in a way the user can act on."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class TooLongForRest(GnaniError):
    """REST caps audio at 60 seconds; the caller should escalate to Batch."""


class JobEndedUnusable(GnaniError):
    """The provider job reached a terminal failed status, so it can never produce a transcript."""


class RateLimited(Exception):
    """Gnani asked us to poll less often. Not a failure: back off and try again."""


@dataclass(frozen=True)
class Segment:
    """One timestamped stretch of a transcript, in seconds from the start."""

    start: float
    end: float | None
    text: str


@dataclass(frozen=True)
class Transcript:
    text: str
    duration_seconds: float | None = None
    segments: tuple[Segment, ...] = ()


def _headers() -> dict[str, str]:
    return {"X-API-Key-ID": settings.gnani_api_key}


def _client(timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.gnani_base_url,
        headers=_headers(),
        timeout=timeout,
    )


def _is_duration_cap(status: int, body: dict) -> bool:
    if status != 400:
        return False
    error = body.get("error") or {}
    text = f"{error.get('type', '')} {error.get('message', '')}".lower()
    return "duration" in text and ("60" in text or "maximum" in text)


async def transcribe_rest(path: Path, language_code: str) -> Transcript:
    """Synchronous transcription. Raises TooLongForRest when the audio is over 60s.

    REST accepts exactly one locale, so a comma separated preference list is
    truncated to its first entry. Batch takes the whole list.
    """
    primary_locale = language_code.split(",")[0].strip()

    async with _client(settings.stt_rest_timeout_seconds) as client:
        with path.open("rb") as audio:
            response = await client.post(
                REST_PATH,
                data={
                    "language_code": primary_locale,
                    "format": "transcribe",
                },
                files={"audio_file": (path.name, audio)},
            )

    body = _json(response)
    if _is_duration_cap(response.status_code, body):
        raise TooLongForRest("audio_too_long", "Audio is longer than the 60 second limit")

    if response.status_code != 200 or not body.get("success", False):
        error = body.get("error") or {}
        raise GnaniError(
            error.get("type", "rest_failed").lower(),
            error.get("message") or f"Synchronous transcription failed ({response.status_code})",
        )

    text = (body.get("transcript") or "").strip()
    if not text:
        raise GnaniError("empty_transcript", "Gnani returned an empty transcript")
    segments = _parse_segments(body)
    if not segments:
        # The synchronous endpoint does not promise per-segment times. One
        # line for the whole clip keeps the UI uniform without inventing any.
        segments = (
            Segment(
                start=0.0,
                end=_as_float(body.get("duration_seconds", body.get("duration"))),
                text=text,
            ),
        )
    return Transcript(text=text, segments=segments)


async def create_batch_job(
    filename: str, language_code: str, audio_path: str, heartbeat=None
) -> str:
    """Submit a Batch job with the audio attached.

    A 429/503 is Gnani asking for a slower pace, not a refusal: the submission
    is retried with backoff, bounded so a worker slot is never held forever. A
    throttled attempt creates no job, so retrying never double-submits.
    """

    config: dict = {
        "model": settings.gnani_model,
        "language_code": language_code,
        "mode": "transcribe",
        "with_diarization": False,
    }

    # The audio is uploaded to Gnani rather than referenced. Gnani's cloud_storage
    # source only accepts its own providers (aws_s3, gcp_gcs, azure_blob); R2 is
    # reachable as aws_s3 and the job is accepted, but Gnani then fails to fetch the
    # object (START_FAILED), so multipart stays the path that actually works.
    # The cost is Gnani's 10MB per-file cap, which the upload limit already matches.
    attempts = 5
    last_status = 0
    for attempt in range(1, attempts + 1):
        async with _client(300) as client:
            with Path(audio_path).open("rb") as audio:
                response = await client.post(
                    BATCH_JOBS_PATH,
                    data={"config": _json_dumps(config)},
                    files={"files": (filename, audio)},
                )
        if response.status_code not in (429, 503):
            break
        last_status = response.status_code
        log.info(
            "submission throttled (%s), waiting %ss (attempt %d/%d)",
            last_status,
            settings.stt_poll_interval_seconds,
            attempt,
            attempts,
        )
        if heartbeat is not None:
            await heartbeat()
        await asyncio.sleep(settings.stt_poll_interval_seconds)
    else:
        raise GnaniError(
            "batch_submit_throttled",
            "Gnani is rate limiting new submissions right now. Nothing was "
            "submitted and you were not charged — wait a minute and press Retry.",
        )

    body = _json(response)
    if response.status_code not in (200, 201):
        error = body.get("error") or {}
        raise GnaniError(
            error.get("type", "batch_create_failed").lower(),
            error.get("message") or f"Batch submission failed ({response.status_code})",
        )

    job_id = body.get("job_id")
    if not job_id:
        raise GnaniError("batch_no_job_id", "Batch submission returned no job id")
    return job_id


async def start_batch_job(job_id: str) -> None:
    """Creating a job does not start it; without this it sits in CREATED forever."""
    async with _client(60) as client:
        response = await client.post(f"{BATCH_JOBS_PATH}/{job_id}/start")

    if response.status_code in (429, 503):
        raise RateLimited(f"start throttled ({response.status_code})")

    if response.status_code not in (200, 202):
        body = _json(response)
        error = body.get("error") or {}
        raise GnaniError(
            error.get("type", "batch_start_failed").lower(),
            error.get("message") or f"Could not start the batch job ({response.status_code})",
        )


async def batch_status(job_id: str) -> str:
    async with _client(60) as client:
        response = await client.get(f"{BATCH_JOBS_PATH}/{job_id}")

    if response.status_code == 429:
        raise RateLimited("Gnani asked for slower polling")
    if response.status_code != 200:
        raise GnaniError("batch_status_failed", f"Could not read job status ({response.status_code})")
    return str(_json(response).get("status", "UNKNOWN"))


async def _throttled(request, attempts: int = 5):
    """Issue a request, waiting Gnani out when it asks for a slower pace.

    A throttled call is never a failure and never an empty result: retrying keeps
    a completed job from being reported as a job that produced nothing.
    """
    last_status = 0
    for _ in range(attempts):
        response = await request()
        if response.status_code not in (429, 503):
            return response
        last_status = response.status_code
        log.info("throttled (%s), waiting %ss", last_status, settings.stt_poll_interval_seconds)
        await asyncio.sleep(settings.stt_poll_interval_seconds)

    raise RateLimited(f"still throttled after {attempts} attempts ({last_status})")


async def batch_transcript(job_id: str) -> Transcript:
    """List completed files, then download the transcript behind transcript_url."""
    async with _client(120) as client:
        files = await _throttled(
            lambda: client.get(
                f"{BATCH_JOBS_PATH}/{job_id}/files", params={"status": "COMPLETED"}
            )
        )
        if files.status_code != 200:
            raise GnaniError(
                "batch_files_failed", f"Could not list the job's files ({files.status_code})"
            )

        # The listing lives under "data", not "files", and pagination is explicit.
        listing = _json(files).get("data") or []
        urls = [entry["transcript_url"] for entry in listing if entry.get("transcript_url")]
        if not urls:
            raise GnaniError("batch_no_transcript", "The batch job produced no transcript")

        downloaded = await _throttled(lambda: client.get(urls[0]))

    body = _json(downloaded)
    if downloaded.status_code != 200:
        raise GnaniError("batch_download_failed", f"Could not download the transcript ({downloaded.status_code})")

    text = (body.get("full_transcript") or "").strip()
    if not text:
        raise GnaniError("empty_transcript", "The batch job returned an empty transcript")
    return Transcript(
        text=text,
        duration_seconds=_as_float(body.get("duration_seconds")),
        segments=_parse_segments(body),
    )


def _parse_segments(body: dict) -> tuple[Segment, ...]:
    """Pull per-segment timestamps out of a transcript payload, tolerantly.

    The Batch download carries segments[] with start_time/end_time in seconds
    and text. Anything unexpected yields no segments rather than a failed
    transcription: times are presentation, the text is the product.
    """
    raw = body.get("segments")
    if not isinstance(raw, list):
        return ()
    segments: list[Segment] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        text = (entry.get("text") or "").strip()
        start = _as_float(entry.get("start_time", entry.get("start")))
        if not text or start is None:
            continue
        segments.append(
            Segment(
                start=start,
                end=_as_float(entry.get("end_time", entry.get("end"))),
                text=text,
            )
        )
    return tuple(segments)


async def wait_for_batch(
    job_id: str, deadline_seconds: float, heartbeat=None, ensure_started: bool = False
) -> Transcript:
    """Poll a Batch job until it reaches a terminal status, then fetch the transcript.

    Gnani asks for no tighter than ten seconds between polls. The deadline stops
    a job that never terminates instead of holding a worker slot forever.
    """
    loop = asyncio.get_running_loop()
    started = loop.time()
    last_beat = started

    while True:
        try:
            status = await batch_status(job_id)
        except RateLimited:
            log.info("rate limited, waiting before polling job=%s again", job_id)
            await asyncio.sleep(settings.stt_poll_interval_seconds)
            if loop.time() - started > deadline_seconds:
                raise GnaniError(
                    "batch_timeout",
                    f"Transcription did not finish within {int(deadline_seconds)} seconds.",
                )
            continue

        elapsed = loop.time() - started

        if heartbeat and loop.time() - last_beat >= settings.worker_heartbeat_seconds:
            await heartbeat()
            last_beat = loop.time()

        log.info("batch_status job=%s status=%s elapsed=%.0fs", job_id, status, elapsed)

        if status == "CREATED" and ensure_started:
            # The job exists but nobody started it, which happens when a worker died
            # between create and start. Starting a job that is already running is not
            # an error, so a refusal here is simply retried on the next tick.
            try:
                await start_batch_job(job_id)
                log.info("started reattached job %s", job_id)
                ensure_started = False
            except RateLimited:
                log.info("start throttled, will retry job=%s", job_id)

        if status == "COMPLETED":
            return await batch_transcript(job_id)

        if status in TERMINAL_STATUSES:
            raise JobEndedUnusable(
                f"batch_{status.lower()}",
                f"Gnani could not transcribe this recording (job {status}). Try a different "
                "language or a cleaner recording.",
            )

        if elapsed > deadline_seconds:
            raise GnaniError(
                "batch_timeout",
                f"Transcription did not finish within {int(deadline_seconds)} seconds.",
            )

        await asyncio.sleep(settings.stt_poll_interval_seconds)


def _as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _json(response: httpx.Response) -> dict:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _json_dumps(value: dict) -> str:
    return json.dumps(value)