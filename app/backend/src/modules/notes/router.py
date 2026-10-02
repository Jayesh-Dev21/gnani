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
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from src import storage
from src.auth import CurrentUserDep
from src.db.session import get_session
from src.modules.notes import service
from src.modules.notes.range import stream_file
from src.modules.notes.schemas import RenameNote
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
    return await service.to_note(await service.get_for_user(session, user.id, note_id))


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
    note_id: UUID, user: CurrentUserDep, session: SessionDep
) -> dict:
    return await service.retry(session, user.id, note_id)


@router.get("/{note_id}/audio")
async def stream_note_audio(
    note_id: UUID, request: Request, user: CurrentUserDep, session: SessionDep
) -> Response:
    note = await service.get_for_user(session, user.id, note_id)

    if storage.using_r2():
        # The object is private. Hand over a short-lived signed URL and let R2 serve
        # the bytes, which it does with Range support intact.
        url = await storage.presigned_url(str(note_id), note.filename)
        return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    path = storage.local_path(str(note_id), note.filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Audio not found")
    return await run_in_threadpool(
        stream_file, path, request.headers.get("range"), note.content_type
    )


@router.head("/{note_id}/audio", include_in_schema=False)
async def head_note_audio(
    note_id: UUID, request: Request, user: CurrentUserDep, session: SessionDep
) -> Response:
    response = await stream_note_audio(note_id, request, user, session)
    return Response(status_code=response.status_code, headers=dict(response.headers))
