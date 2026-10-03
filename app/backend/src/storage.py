"""Audio storage in Cloudflare R2.

R2 is the only backend. Audio is private: the browser and Gnani both read it with
short-lived presigned URLs, so a leaked link expires instead of becoming a
permanent public file.

This module is the only place in the backend allowed to build an object key or
hold bucket credentials. Object metadata lives in the database, which already has
the filename, content type and size.
"""

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


def object_key(note_id: str, filename: str) -> str:
    """The note id leads, so a bucket listing groups one note's audio together."""
    return f"notes/{note_id}/{filename}"


def r2_endpoint() -> str:
    return f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"


def _client():
    # aioboto3 exposes clients through a session; the module level helper is boto3.
    return aioboto3.Session().client(
        "s3",
        endpoint_url=r2_endpoint(),
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
        await _put(note_id, filename, content_type, spooled)
    finally:
        spooled.unlink(missing_ok=True)

    return StoredAudio(filename=filename, content_type=content_type, size_bytes=size)


def _spool(upload: UploadFile) -> Path:
    """Buffer the upload to a temporary file, refusing anything over the limit.

    The bucket gets a real file to send rather than a buffer held in memory, and
    the size limit still applies while the request body is still arriving.
    """
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


async def _put(note_id: str, filename: str, content_type: str, source: Path) -> None:
    async with _client() as client:
        with source.open("rb") as body:
            await client.put_object(
                Bucket=settings.r2_bucket,
                Key=object_key(note_id, filename),
                ContentType=content_type,
                ContentLength=source.stat().st_size,
                Body=body,
            )


async def delete(note_id: str, filename: str) -> None:
    async with _client() as client:
        await client.delete_object(
            Bucket=settings.r2_bucket, Key=object_key(note_id, filename)
        )


async def presigned_url(note_id: str, filename: str, expires: int | None = None) -> str:
    """A short-lived URL for reading one object: used for playback and for Gnani."""
    async with _client() as client:
        return await client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.r2_bucket, "Key": object_key(note_id, filename)},
            ExpiresIn=expires or settings.r2_presign_expiry_seconds,
        )


async def playback_url(note_id: str, filename: str) -> str:
    """Where the browser reads the audio from."""
    return await presigned_url(note_id, filename)


async def fetch_to(note_id: str, filename: str, destination: Path) -> Path:
    """Fetch the object to a local file, for the synchronous Gnani endpoint."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    async with _client() as client:
        await client.download_file(
            Bucket=settings.r2_bucket,
            Key=object_key(note_id, filename),
            Filename=str(destination),
        )
    return destination