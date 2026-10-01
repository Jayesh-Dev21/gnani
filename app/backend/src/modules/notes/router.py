"""Stub note routes.

Placeholder responses only — no database, no auth, no storage, nothing persists.
Every route returns the same canned note so the frontend can be built against the
final shapes. Replaced by src/modules/notes/service.py when persistence lands.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, File, Form, Response, UploadFile

router = APIRouter(prefix="/api/notes", tags=["notes"])

STUB_ID = "00000000-0000-0000-0000-000000000000"
STUB_TRANSCRIPT = "[stub transcript — the Gnani Batch STT client fills this in]"
STUB_SUMMARY = "[stub summary — the LLM step lands after the frontend]"


def stub_note(title: str | None = None, filename: str | None = None) -> dict:
    now = datetime.now(UTC).isoformat()
    return {
        "id": STUB_ID,
        "title": title or filename or "Stub note",
        "status": "ready",
        "filename": filename or "stub.m4a",
        "content_type": "audio/mp4",
        "size_bytes": 0,
        "duration_seconds": 0.0,
        "language_code": "hi-IN,en-IN",
        "transcript": STUB_TRANSCRIPT,
        "summary": STUB_SUMMARY,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }


@router.post("", status_code=201)
async def create_note(
    file: UploadFile = File(),
    title: str | None = Form(default=None),
    language_code: str | None = Form(default=None),
) -> dict:
    return stub_note(title=title, filename=file.filename)


@router.get("")
async def list_notes() -> list[dict]:
    return [stub_note()]


@router.get("/{note_id}")
async def get_note(note_id: str) -> dict:
    return stub_note()


@router.delete("/{note_id}", status_code=204)
async def delete_note(note_id: str) -> Response:
    return Response(status_code=204)


@router.post("/{note_id}/retry", status_code=202)
async def retry_note(note_id: str) -> dict:
    return stub_note()