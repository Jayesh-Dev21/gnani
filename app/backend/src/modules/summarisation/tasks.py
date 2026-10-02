"""The summarisation job.

Runs after transcription lands, as its own job, so a provider outage never
disturbs a transcript that already succeeded and a summary can be retried on its
own. Reuses the note's lease columns: a note is only ever transcribing or
summarising, never both, so a second set of lease fields would be a second
concept for the same job.
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select

from src.config import settings
from src.db.models import Note, NoteStatus
from src.db.session import session_factory
from src.modules.summarisation import llm
from src.queue import QUEUE_SUMMARISATION, app

log = logging.getLogger("summarisation")


@app.task(queue=QUEUE_SUMMARISATION, name="summarise_note")
async def summarise_note(note_id: str, user_id: str, attempt_id: str | None = None) -> None:
    """Summarise a transcribed note through the Groq model chain."""
    attempt = UUID(attempt_id) if attempt_id else uuid4()
    if not await _claim(UUID(note_id), user_id, attempt):
        return

    async def heartbeat() -> None:
        async with session_factory() as session:
            await _extend_lease(session, UUID(note_id), attempt)
            await session.commit()

    try:
        async with session_factory() as session:
            note = await session.scalar(
                select(Note).where(Note.id == UUID(note_id), Note.user_id == user_id)
            )
            transcript = note.transcript if note else None

        if not transcript:
            raise llm.LLMError("summary_no_transcript", "There is no transcript to summarise.")

        result = await llm.summarise_transcript(transcript)

        async with session_factory() as session:
            await _write_summary(session, UUID(note_id), user_id, attempt, result.text)

        log.info(
            "note=%s summarised by %s after %d model attempt(s)",
            note_id,
            result.model,
            len(result.attempts),
        )

    except Exception as error:  # noqa: BLE001 - the user must be told what happened
        code = getattr(error, "code", "summary_failed")
        message = getattr(error, "message", None) or str(error)
        log.exception("note=%s summarisation failed", note_id)

        async with session_factory() as session:
            await _write_failure(session, UUID(note_id), user_id, attempt, code, message)

    finally:
        async with session_factory() as session:
            await _release_lease(session, UUID(note_id), attempt)
            await session.commit()


async def _claim(note_id: UUID, user_id: str, attempt: UUID) -> bool:
    """Take ownership, unless another worker legitimately holds the note."""
    async with session_factory() as session:
        note = await session.scalar(
            select(Note).where(Note.id == note_id, Note.user_id == user_id).with_for_update()
        )
        if note is None or not note.transcript:
            return False

        now = datetime.now(UTC)
        if (
            note.status == NoteStatus.SUMMARISING
            and note.lease_expires_at is not None
            and note.lease_expires_at > now
        ):
            log.info("note=%s is already being summarised", note_id)
            return False

        note.status = NoteStatus.SUMMARISING
        note.error_code = None
        note.error_message = None
        note.attempt_id = attempt
        note.lease_expires_at = now + timedelta(seconds=settings.worker_lease_seconds)
        note.updated_at = now
        await session.commit()
        return True


async def _extend_lease(session, note_id: UUID, attempt: UUID) -> None:
    note = await session.scalar(
        select(Note).where(Note.id == note_id, Note.attempt_id == attempt).with_for_update()
    )
    if note is not None:
        note.lease_expires_at = datetime.now(UTC) + timedelta(
            seconds=settings.worker_lease_seconds
        )


async def _write_summary(session, note_id: UUID, user_id: str, attempt: UUID, summary: str) -> None:
    note = await session.scalar(
        select(Note)
        .where(Note.id == note_id, Note.user_id == user_id, Note.attempt_id == attempt)
        .with_for_update()
    )
    if note is None:
        return
    note.summary = summary
    note.status = NoteStatus.READY
    note.error_code = None
    note.error_message = None
    note.updated_at = datetime.now(UTC)
    await session.commit()


async def _write_failure(
    session, note_id: UUID, user_id: str, attempt: UUID, code: str, message: str
) -> None:
    note = await session.scalar(
        select(Note)
        .where(Note.id == note_id, Note.user_id == user_id, Note.attempt_id == attempt)
        .with_for_update()
    )
    if note is None:
        return
    # The transcript stays exactly as it is. Only the summary step is reported as
    # failed, and the message says which one it was.
    note.status = NoteStatus.FAILED
    note.error_code = code
    note.error_message = message
    note.updated_at = datetime.now(UTC)
    await session.commit()


async def _release_lease(session, note_id: UUID, attempt: UUID) -> None:
    note = await session.scalar(
        select(Note).where(Note.id == note_id, Note.attempt_id == attempt).with_for_update()
    )
    if note is not None:
        note.attempt_id = None
        note.lease_expires_at = None
        await session.commit()