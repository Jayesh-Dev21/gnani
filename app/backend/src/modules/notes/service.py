"""Note persistence. Every query is scoped to the verified user id."""

import math
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src import storage
from src.config import LANGUAGES, UNSUPPORTED_BY_BATCH, settings
from src.db.models import Note, NoteStatus
from src.queue import defer_summarisation, defer_transcription

AUDIO_PATH = f"/api/notes/{{id}}/audio"


# Batch STT accepts recordings of hours, so this is only a sanity bound on what a
# browser will report, not a product limit.
MAX_DURATION_SECONDS = 4 * 60 * 60


def resolve_language_code(language_code: str | None) -> str:
    if not language_code:
        return settings.default_language_code

    codes = [code.strip() for code in language_code.split(",") if code.strip()]
    known = {code for code, _ in LANGUAGES}

    unsupported = [code for code in codes if code in UNSUPPORTED_BY_BATCH]
    if unsupported:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Batch STT does not support {', '.join(unsupported)}. "
                "Use the synchronous endpoint for those."
            ),
        )

    unknown = [code for code in codes if code not in known]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unknown language code: {', '.join(unknown)}. "
                f"Supported: {', '.join(code for code, _ in LANGUAGES)}"
            ),
        )

    if len(codes) > 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At most 3 language codes may be given for identification",
        )

    return ",".join(codes)


async def to_note(note: Note, *, include_content: bool = True) -> dict:
    payload = {
        "id": str(note.id),
        "title": note.title,
        "status": note.status.value,
        "filename": note.filename,
        "content_type": note.content_type,
        "size_bytes": note.size_bytes,
        "duration_seconds": note.duration_seconds,
        "language_code": note.language_code,
        "error": (
            {"code": note.error_code, "message": note.error_message}
            if note.error_code
            else None
        ),
        "created_at": note.created_at.isoformat(),
        "updated_at": note.updated_at.isoformat(),
    }
    if include_content:
        payload["transcript"] = note.transcript
        payload["summary"] = note.summary
        # Local disk is served through the authenticated route; a private bucket is
        # served through a short-lived signed URL. Either way the browser gets one
        # field to play from and never has to know which backend is in use.
        payload["audio_url"] = await storage.playback_url(str(note.id), note.filename)
    return payload


def sanitise_duration(duration_seconds: float | None) -> float | None:
    """Trust the browser's measurement of duration, but not blindly."""
    if duration_seconds is None or not math.isfinite(duration_seconds):
        return None
    if duration_seconds <= 0 or duration_seconds > MAX_DURATION_SECONDS:
        return None
    return round(duration_seconds, 2)


async def create(
    session: AsyncSession,
    user_id: str,
    file: UploadFile,
    title: str | None,
    language: str | None,
    duration_seconds: float | None = None,
) -> dict:
    note = Note(
        user_id=user_id,
        title=(title or "").strip(),
        filename="pending",
        content_type=file.content_type or "",
        size_bytes=0,
        language_code=resolve_language_code(language),
        duration_seconds=sanitise_duration(duration_seconds),
        status=NoteStatus.QUEUED,
    )
    session.add(note)
    await session.flush()

    try:
        stored = await storage.save(str(note.id), file)
    except Exception:
        await session.rollback()
        raise

    note.filename = stored.filename
    note.content_type = stored.content_type
    note.size_bytes = stored.size_bytes
    if not note.title:
        note.title = stored.filename

    await session.commit()
    await session.refresh(note)
    await defer_transcription(str(note.id), str(note.user_id))
    return await to_note(note)


async def list_for_user(session: AsyncSession, user_id: str, limit: int) -> list[dict]:
    result = await session.execute(
        select(Note)
        .where(Note.user_id == user_id)
        .order_by(Note.created_at.desc(), Note.id.desc())
        .limit(limit)
    )
    return [await to_note(note, include_content=False) for note in result.scalars()]


async def get_for_user(
    session: AsyncSession, user_id: str, note_id: UUID
) -> Note:
    note = await session.get(Note, note_id)
    if note is None or note.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Note not found"
        )
    return note


async def rename(
    session: AsyncSession, user_id: str, note_id: UUID, title: str
) -> dict:
    note = await get_for_user(session, user_id, note_id)
    cleaned = title.strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Title cannot be empty"
        )
    note.title = cleaned
    await session.commit()
    await session.refresh(note)
    return await to_note(note)


async def retry(session: AsyncSession, user_id: str, note_id: UUID) -> dict:
    note = await get_for_user(session, user_id, note_id)
    # queued is retryable too: a note whose job died before it was claimed stays
    # queued forever otherwise, and the user is the only one who can ask again.
    if note.status not in (NoteStatus.FAILED, NoteStatus.QUEUED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only failed or queued notes can be retried, this one is {note.status.value}",
        )
    note.status = NoteStatus.QUEUED
    note.error_code = None
    note.error_message = None
    # provider_job_id survives on purpose: if Gnani already accepted this audio,
    # the next attempt resumes that job instead of billing the same file twice.
    note.attempt_id = None
    note.lease_expires_at = None

    # Retry the step that failed. A note with a transcript only needs its summary,
    # so pressing Retry never pays for transcription twice.
    resuming_summary = bool(note.transcript)
    note.status = NoteStatus.SUMMARISING if resuming_summary else NoteStatus.QUEUED

    await session.commit()
    await session.refresh(note)
    if resuming_summary:
        await defer_summarisation(str(note.id), str(note.user_id))
    else:
        await defer_transcription(str(note.id), str(note.user_id))
    return await to_note(note)


async def delete(session: AsyncSession, user_id: str, note_id: UUID) -> None:
    note = await get_for_user(session, user_id, note_id)
    await session.delete(note)
    await session.commit()
    await storage.delete(str(note_id), note.filename)
