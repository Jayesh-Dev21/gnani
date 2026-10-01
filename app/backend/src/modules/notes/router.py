"""Stub note routes.

Audio is really stored on disk and really streamed back with range support, but
transcripts are still placeholders and nothing is persisted in a database: every
GET returns the same canned note. POST generates a real note id and keeps the
uploaded file. Replaced by src/modules/notes/service.py when persistence lands.
"""

import re
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from src import storage
from src.config import settings

router = APIRouter(prefix="/api/notes", tags=["notes"])

STUB_TRANSCRIPT = "[stub transcript — the Gnani Batch STT client fills this in]"
STUB_SUMMARY = "[stub summary — the LLM step lands after the frontend]"
RANGE_PATTERN = re.compile(r"bytes=(\d*)-(\d*)")
STREAM_CHUNK_SIZE = 1024 * 256


def stub_note(
    note_id: str,
    title: str | None = None,
    filename: str | None = None,
    audio_url: str | None = None,
) -> dict:
    now = datetime.now(UTC).isoformat()
    return {
        "id": note_id,
        "title": title or filename or "Untitled recording",
        "status": "ready",
        "filename": filename or "audio.m4a",
        "content_type": "audio/mp4",
        "size_bytes": 0,
        "duration_seconds": None,
        "language_code": settings.default_language_code,
        "transcript": STUB_TRANSCRIPT,
        "summary": STUB_SUMMARY,
        "error": None,
        "audio_url": audio_url,
        "created_at": now,
        "updated_at": now,
    }


def resolve_language_code(language_code: str | None) -> str:
    if not language_code:
        return settings.default_language_code

    codes = [code.strip() for code in language_code.split(",") if code.strip()]
    unsupported = [code for code in codes if code not in settings.batch_language_codes]
    if unsupported:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Batch STT does not support {', '.join(unsupported)}. "
                f"Supported: {', '.join(settings.batch_language_codes)}"
            ),
        )
    if len(codes) > 3:
        raise HTTPException(
            status_code=400,
            detail="At most 3 language codes may be given for identification",
        )
    return ",".join(codes)


def stream_audio(path: Path, request: Request, content_type: str) -> Response:
    file_size = path.stat().st_size
    range_header = request.headers.get("range")

    if range_header is None:
        return StreamingResponse(
            _chunks(path, 0, file_size - 1),
            media_type=content_type,
            headers={"accept-ranges": "bytes"},
        )

    match = RANGE_PATTERN.fullmatch(range_header.strip())
    if match is None:
        raise HTTPException(status_code=400, detail="Malformed Range header")

    raw_start, raw_end = match.groups()
    if raw_start == "":
        length = int(raw_end)
        start = max(file_size - length, 0)
        end = file_size - 1
    else:
        start = int(raw_start)
        end = int(raw_end) if raw_end else file_size - 1

    end = min(end, file_size - 1)
    if start > end or start >= file_size:
        raise HTTPException(
            status_code=416,
            detail="Requested range not satisfiable",
            headers={"content-range": f"bytes */{file_size}"},
        )

    return StreamingResponse(
        _chunks(path, start, end),
        status_code=206,
        media_type=content_type,
        headers={
            "accept-ranges": "bytes",
            "content-range": f"bytes {start}-{end}/{file_size}",
            "content-length": str(end - start + 1),
        },
    )


def _chunks(path: Path, start: int, end: int) -> Iterator[bytes]:
    with path.open("rb") as handle:
        handle.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = handle.read(min(STREAM_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@router.post("", status_code=201)
async def create_note(
    request: Request,
    file: UploadFile = File(),
    title: str | None = Form(default=None),
    language_code: str | None = Form(default=None),
) -> dict:
    note_id = str(uuid4())
    stored = await _save_upload(note_id, file)
    language = resolve_language_code(language_code)

    note = stub_note(
        note_id,
        title=title,
        filename=stored.filename,
        audio_url=str(request.url_for("stream_note_audio", note_id=note_id)),
    )
    note["content_type"] = stored.content_type
    note["size_bytes"] = stored.size_bytes
    note["language_code"] = language
    return note


@router.get("")
async def list_notes() -> list[dict]:
    return [stub_note(str(uuid4()))]


@router.get("/{note_id}")
async def get_note(note_id: str) -> dict:
    stored = storage.read(note_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Note not found")

    note = stub_note(note_id, filename=stored.filename)
    note["content_type"] = stored.content_type
    note["size_bytes"] = stored.size_bytes
    return note


@router.get("/{note_id}/audio", name="stream_note_audio")
async def stream_note_audio(note_id: str, request: Request) -> Response:
    stored = storage.read(note_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return stream_audio(stored.audio_path, request, stored.content_type)


@router.head("/{note_id}/audio", include_in_schema=False)
async def head_note_audio(note_id: str, request: Request) -> Response:
    response = await stream_note_audio(note_id, request)
    return Response(status_code=response.status_code, headers=dict(response.headers))


@router.delete("/{note_id}", status_code=204)
async def delete_note(note_id: str) -> Response:
    storage.delete(note_id)
    return Response(status_code=204)


@router.post("/{note_id}/retry", status_code=202)
async def retry_note(note_id: str) -> dict:
    return stub_note(note_id)


async def _save_upload(note_id: str, file: UploadFile) -> storage.StoredAudio:
    try:
        return await run_in_threadpool(storage.save, note_id, file)
    finally:
        await file.close()