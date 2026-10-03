"""The transcription job.

One attempt owns one note at a time. Every transition is written to the database
before the work starts, so a worker that dies leaves a state the UI can explain
rather than a spinner that never resolves.
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select

from src.config import settings
from src.db.models import Note, NoteStatus, TranscriptIteration
from src.db.session import session_factory
from src.modules.transcription import gnani
from src.queue import QUEUE_TRANSCRIPTION, app, defer_summarisation

log = logging.getLogger("transcription")


@app.task(queue=QUEUE_TRANSCRIPTION, name="transcribe_note")
async def transcribe_note(note_id: str, user_id: str, attempt_id: str | None = None) -> None:
    """Transcribe a note, escalating from the synchronous endpoint to Batch when needed.

    Deliberately has no automatic retry. A retry after a crash would re-send audio
    Gnani has already charged for. Recovery reclaims abandoned notes instead, and
    a user can always press Retry themselves.
    """
    attempt = UUID(attempt_id) if attempt_id else uuid4()
    claimed = await _claim(UUID(note_id), user_id, attempt)
    if not claimed:
        return

    async def heartbeat() -> None:
        async with session_factory() as session:
            await _extend_lease(session, UUID(note_id), attempt)
            await session.commit()

    try:
        async with session_factory() as session:
            note = await _load(session, UUID(note_id), user_id)
            assert note is not None
            filename = note.filename
            language_code = note.language_code
            submitted_job_id = note.provider_job_id

        if submitted_job_id:
            # A previous attempt already paid for this job. Resume it rather than
            # submitting the same audio a second time. If that job turned out to
            # be dead, forget it and submit once, which is what pressing Retry means.
            log.info("reattaching note=%s job=%s", note_id, submitted_job_id)
            try:
                transcript = await gnani.wait_for_batch(
                    submitted_job_id,
                    settings.stt_batch_deadline_seconds,
                    heartbeat,
                    ensure_started=True,
                )
            except gnani.JobEndedUnusable:
                log.info("job %s is dead, submitting a fresh one", submitted_job_id)
                await _forget_provider_job(UUID(note_id), user_id, attempt)
                transcript = await _transcribe(
                    UUID(note_id), user_id, attempt, filename, language_code, heartbeat
                )
        else:
            transcript = await _transcribe(
                UUID(note_id), user_id, attempt, filename, language_code, heartbeat
            )

        async with session_factory() as session:
            await _mark_ready(session, UUID(note_id), user_id, attempt, transcript)

        log.info("note=%s ready (%d chars)", note_id, len(transcript.text))
        await defer_summarisation(note_id, user_id)

    except Exception as error:  # noqa: BLE001 - the user must be told what happened
        code = error.code if isinstance(error, gnani.GnaniError) else "transcription_failed"
        message = getattr(error, "message", None) or str(error)
        log.exception("note=%s failed", note_id)

        async with session_factory() as session:
            await _mark_failed(session, UUID(note_id), user_id, attempt, code, message)

    finally:
        async with session_factory() as session:
            await _release_lease(session, UUID(note_id), attempt)
            await session.commit()


async def _transcribe(
    note_id: UUID, user_id: str, attempt: UUID, filename: str, language_code: str, heartbeat
) -> gnani.Transcript:
    from src import storage

    # Both Gnani endpoints take bytes rather than a bucket reference, so the object
    # is fetched once here and released before the job starts polling.
    with tempfile.TemporaryDirectory(prefix=f"transcribe-{str(note_id)[:8]}-") as workdir:
        audio = await storage.fetch_to(str(note_id), filename, Path(workdir) / filename)
        try:
            return await gnani.transcribe_rest(audio, language_code)
        except gnani.TooLongForRest:
            log.info("escalating to batch: %s", filename)

        job_id = await gnani.create_batch_job(filename, language_code, str(audio), heartbeat)
    await _record_submission(note_id, user_id, attempt, job_id)
    await _start_when_allowed(job_id)
    return await gnani.wait_for_batch(job_id, settings.stt_batch_deadline_seconds, heartbeat)


async def _start_when_allowed(job_id: str) -> None:
    """Start a freshly created job, tolerating the throttle Gnani applies to bursts."""
    for _ in range(5):
        try:
            await gnani.start_batch_job(job_id)
            return
        except gnani.RateLimited:
            log.info("start throttled, retrying in %ss", settings.stt_poll_interval_seconds)
            await asyncio.sleep(settings.stt_poll_interval_seconds)
    raise gnani.GnaniError("batch_start_throttled", "Gnani is rate limiting job submissions.")


async def _record_submission(note_id, user_id, attempt, job_id: str) -> None:
    """Mark the note as submitted *before* polling.

    If the worker dies after Gnani accepted the audio but before the transcript
    arrives, the next attempt finds provider_job_id and resumes this job instead
    of billing the same recording twice.
    """
    async with session_factory() as session:
        note = await session.scalar(
            select(Note)
            .where(Note.id == note_id, Note.user_id == user_id, Note.attempt_id == attempt)
            .with_for_update()
        )
        if note is None:
            raise gnani.GnaniError("note_disappeared", "This note no longer exists.")
        now = datetime.now(UTC)
        note.provider_job_id = job_id
        note.provider_submitted_at = now
        note.updated_at = now
        await session.commit()


async def _forget_provider_job(note_id: UUID, user_id: str, attempt: UUID) -> None:
    async with session_factory() as session:
        note = await session.scalar(
            select(Note)
            .where(Note.id == note_id, Note.user_id == user_id, Note.attempt_id == attempt)
            .with_for_update()
        )
        if note is not None:
            note.provider_job_id = None
            note.provider_submitted_at = None
            await session.commit()


async def _load(session, note_id: UUID, user_id: str) -> Note | None:
    return await session.scalar(select(Note).where(Note.id == note_id, Note.user_id == user_id))


async def _claim(note_id: UUID, user_id: str, attempt: UUID) -> bool:
    """Take ownership of a note, unless someone else legitimately holds it."""
    async with session_factory() as session:
        note = await session.scalar(
            select(Note).where(Note.id == note_id, Note.user_id == user_id).with_for_update()
        )
        if note is None or note.status == "ready":
            return False

        now = datetime.now(UTC)
        if (
            note.status == "transcribing"
            and note.lease_expires_at is not None
            and note.lease_expires_at > now
        ):
            log.info("note=%s is already being transcribed", note_id)
            return False

        note.status = "transcribing"
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


async def _mark_ready(session, note_id: UUID, user_id: str, attempt: UUID, transcript) -> None:
    """Store this pass and keep every earlier one.

    A note is ready as soon as one pass worked, so another attempt adds to the
    history instead of replacing it.
    """
    note = await session.scalar(
        select(Note)
        .where(Note.id == note_id, Note.user_id == user_id, Note.attempt_id == attempt)
        .with_for_update()
    )
    if note is None:
        return
    now = datetime.now(UTC)
    session.add(
        TranscriptIteration(
            note_id=note_id,
            transcript=transcript.text,
            status=NoteStatus.READY.value,
            duration_seconds=transcript.duration_seconds,
        )
    )
    note.status = NoteStatus.READY
    note.transcript = transcript.text
    # Gnani sometimes omits the duration; a probed value from upload is better.
    if transcript.duration_seconds is not None:
        note.duration_seconds = transcript.duration_seconds
    note.error_code = None
    note.error_message = None
    # A fresh transcript invalidates any summary written against the old one.
    note.summary = None
    note.updated_at = now
    await session.commit()


async def _mark_failed(
    session, note_id: UUID, user_id: str, attempt: UUID, code: str, message: str
) -> None:
    """Record the failed pass without destroying an earlier successful transcript."""
    note = await session.scalar(
        select(Note)
        .where(Note.id == note_id, Note.user_id == user_id, Note.attempt_id == attempt)
        .with_for_update()
    )
    if note is None:
        return
    now = datetime.now(UTC)
    session.add(
        TranscriptIteration(
            note_id=note_id,
            status=NoteStatus.FAILED.value,
            error_code=code,
            error_message=message,
        )
    )

    if note.transcript:
        # Something good already exists, so the note stays ready and keeps it. The
        # failure is visible in the history rather than by losing the transcript.
        log.warning("note=%s pass failed, keeping the transcript it already has", note_id)
    else:
        note.status = NoteStatus.FAILED
        note.error_code = code
        note.error_message = message

    note.updated_at = now
    await session.commit()


async def _release_lease(session, note_id: UUID, attempt: UUID) -> None:
    """Let the note be claimed again only if it is not already claimed by someone else."""
    note = await session.scalar(
        select(Note).where(Note.id == note_id, Note.attempt_id == attempt).with_for_update()
    )
    if note is not None:
        note.attempt_id = None
        note.lease_expires_at = None
        await session.commit()