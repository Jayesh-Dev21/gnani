"""Note routes: parse input, call the service, map results to status codes."""

from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    Response,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import CurrentUserDep
from src.db.session import get_session
from src.modules.notes import service
from src.modules.notes.schemas import RenameNote, RetryNote
from src.modules.notes.service import to_note

router = APIRouter(prefix="/api/notes", tags=["notes"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("", status_code=201)
async def create_note(
    user: CurrentUserDep,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form()] = None,
    language_code: Annotated[str | None, Form()] = None,
    duration_seconds: Annotated[float | None, Form()] = None,
) -> dict:
    return await service.create(session, user.id, file, title, language_code, duration_seconds)


@router.get("")
async def list_notes(
    user: CurrentUserDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[dict]:
    return await service.list_for_user(session, user.id, limit)


@router.get("/{note_id}")
async def get_note(note_id: UUID, user: CurrentUserDep, session: SessionDep) -> dict:
    note = await service.get_for_user(session, user.id, note_id)
    return await service.with_iterations(session, note)


@router.patch("/{note_id}")
async def rename_note(
    note_id: UUID, user: CurrentUserDep, session: SessionDep, body: RenameNote
) -> dict:
    return await service.rename(session, user.id, note_id, body.title)


@router.delete("/{note_id}", status_code=204)
async def delete_note(
    note_id: UUID, user: CurrentUserDep, session: SessionDep
) -> Response:
    await service.delete(session, user.id, note_id)
    return Response(status_code=204)


@router.post("/{note_id}/retry", status_code=202)
async def retry_note(
    note_id: UUID,
    user: CurrentUserDep,
    session: SessionDep,
    body: RetryNote | None = None,
) -> dict:
    return await service.retry(session, user.id, note_id, body.target if body else None)
