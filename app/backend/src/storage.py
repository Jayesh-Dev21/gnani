"""Audio storage.

One interface, two backends: local disk for development, Cloudflare R2 for
production. This module is the only place in the backend allowed to build a
filesystem path or know which backend is in use. Nothing else may assume a local
path, and nothing else may hold bucket credentials.

Object metadata lives in the database, which already has the filename, content
type and size, so neither backend keeps a sidecar file. In R2 the bucket is
private: playback and Gnani both use short-lived presigned URLs.

An upload is spooled to a temporary file first. That keeps the size limit
enforceable while the bytes stream in, and it gives the bucket a real file to
send rather than a buffer held in memory.
"""

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import aioboto3
from fastapi import HTTPException, UploadFile, status

from src.config import settings

CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class StoredAudio:
    filename: str
    content_type: str
    size_bytes: int


def using_r2() -> bool:
    return settings.storage_backend == "r2"


def _key(note_id: str, filename: str) -> str:
    """Object key. The note id leads so a bucket listing groups one note's audio."""
    return f"notes/{note_id}/{filename}"


def _local_path(note_id: str, filename: str) -> Path:
    return settings.uploads_dir / note_id / filename


def _client():
    return aioboto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )


def _too_large() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        detail=(
            f"Audio is larger than the "
            f"{settings.max_upload_bytes // (1024 * 1024)}MB limit"
        ),
    )


async def save(note_id: str, upload: UploadFile) -> StoredAudio:
    """Store the uploaded audio, enforcing the size limit as the bytes arrive."""
    content_type = upload.content_type or ""
    if content_type not in settings.audio_content_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported audio type: {content_type or 'unknown'}",
        )

    filename = Path(upload.filename or "audio").name
    spooled = _spool(upload)
    try:
        size = spooled.stat().st_size
        if using_r2():
            await _put(note_id, filename, content_type, spooled)
        else:
            _put_on_disk(note_id, filename, spooled)
    finally:
        spooled.unlink(missing_ok=True)

    return StoredAudio(filename=filename, content_type=content_type, size_bytes=size)


def _spool(upload: UploadFile) -> Path:
    """Buffer the upload to a temporary file, refusing anything over the limit."""
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=".audio")
    size = 0
    try:
        while chunk := upload.file.read(CHUNK_SIZE):
            size += len(chunk)
            if size > settings.max_upload_bytes:
                handle.close()
                Path(handle.name).unlink(missing_ok=True)
                raise _too_large()
            handle.write(chunk)
    finally:
        handle.close()
    return Path(handle.name)


def _put_on_disk(note_id: str, filename: str, source: Path) -> Path:
    destination = _local_path(note_id, filename)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return destination


async def _put(note_id: str, filename: str, content_type: str, source: Path) -> None:
    async with _client() as client, source.open("rb") as body:
        await client.put_object(
            Bucket=settings.r2_bucket,
            Key=_key(note_id, filename),
            ContentType=content_type,
            ContentLength=source.stat().st_size,
            Body=body,
        )


async def delete(note_id: str, filename: str) -> None:
    if using_r2():
        async with _client() as client:
            await client.delete_object(
                Bucket=settings.r2_bucket, Key=_key(note_id, filename)
            )
        return

    note_dir = settings.uploads_dir / note_id
    for child in note_dir.glob("*"):
        child.unlink(missing_ok=True)
    try:
        note_dir.rmdir()
    except OSError:
        pass


async def presigned_url(note_id: str, filename: str, expires: int | None = None) -> str:
    """A short-lived URL for reading one object: used for playback and for Gnani."""
    async with _client() as client:
        return await client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.r2_bucket, "Key": _key(note_id, filename)},
            ExpiresIn=expires or settings.r2_presign_expiry_seconds,
        )


async def playback_url(note_id: str, filename: str) -> str:
    """Where the browser should read the audio from.

    Local development keeps serving it through the authenticated API route. In R2
    the object is private, so the browser is handed a short-lived signed URL and
    the bytes never travel through the backend.
    """
    if using_r2():
        return await presigned_url(note_id, filename)
    return f"/api/notes/{note_id}/audio"


def local_path(note_id: str, filename: str) -> Path:
    """The on-disk path, for the local backend only.

    The streaming route calls this without knowing the backend; in R2 it redirects
    to a signed URL before ever getting here.
    """
    return _local_path(note_id, filename)


async def fetch_to(note_id: str, filename: str, destination: Path) -> Path:
    """Fetch an object to a local file, for the synchronous Gnani endpoint."""
    if using_r2():
        destination.parent.mkdir(parents=True, exist_ok=True)
        async with _client() as client:
            await client.download_file(
                Bucket=settings.r2_bucket,
                Key=_key(note_id, filename),
                Filename=str(destination),
            )
        return destination

    return shutil.copyfile(_local_path(note_id, filename), destination)
