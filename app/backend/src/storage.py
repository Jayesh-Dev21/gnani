"""Audio storage in Cloudflare R2.

R2 is the only backend. Audio stays private: nothing is publicly fetchable, and
playback bytes always flow through the authenticated API route so a leaked link
expires instead of becoming a permanent public file. Gnani receives the bytes
over multipart; it cannot fetch from R2.

This module is the only place in the backend allowed to build an object key or
hold bucket credentials. Object metadata lives in the database, which already has
the filename, content type and size.
"""

import asyncio
import subprocess
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
    duration_seconds: float | None = None


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
        duration = await probe_duration(spooled)
        await _put(note_id, filename, content_type, spooled)
    finally:
        spooled.unlink(missing_ok=True)

    return StoredAudio(filename=filename, content_type=content_type, size_bytes=size, duration_seconds=duration)


async def probe_duration(source: Path) -> float | None:
    """Read the real duration with ffprobe, so the browser's guess is not the truth."""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v", "error",
        "-show_format",
        "-select_streams",
        "a:0",
        source,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()
    for line in stdout.decode().splitlines():
        if line.startswith("duration="):
            try:
                value = float(line.partition("=")[2])
            except ValueError:
                return None
            return value if value > 0 else None
    return None


# Containers a browser's <audio> element can actually decode with durations it can
# seek on. ADTS AAC and AMR come through as audio/aac and audio/amr and neither
# plays nor reports duration; they are transcoded on the way out.
BROWSER_READY_CONTENT_TYPES = {
    "audio/mpeg",
    "audio/mp4",
    "audio/mp4a-latm",
    "audio/ogg",
    "audio/webm",
    "audio/wav",
    "audio/x-wav",
    "audio/flac",
}


def needs_transcode(content_type: str) -> bool:
    return content_type not in BROWSER_READY_CONTENT_TYPES


async def transcode_to_mp3(source: Path, destination: Path) -> Path:
    """Convert a stored object into a browser-playable mp3, preserving seek."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-v", "error",
        "-i", str(source),
        "-codec:a", "libmp3lame",
        "-b:a", "192k",
        str(destination),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg: {stderr.decode().strip()}")
    return destination


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


def playback_url(note_id: str, filename: str) -> str:
    """Where the browser reads the audio from.

    The bytes are streamed by the API rather than handed over as a signed link.
    That costs one hop, and it removes three ways for playback to break in the
    browser: a cross-origin request to the bucket, a link that expires mid-session,
    and a fresh signature on every poll restarting the player's buffer.
    """
    return f"/api/notes/{note_id}/audio"


def parse_byte_range(header: str | None, size: int) -> tuple[int, int]:
    """Turn a Range header into inclusive byte offsets, or the whole file."""
    if not header or not header.startswith("bytes=") or size <= 0:
        return 0, max(size - 1, 0)

    raw = header.removeprefix("bytes=").split(",")[0].strip()
    start_text, _, end_text = raw.partition("-")

    try:
        start = int(start_text) if start_text else 0
        end = int(end_text) if end_text else size - 1
    except ValueError:
        return 0, size - 1

    if start < 0:  # a suffix range asks for the last N bytes
        start = max(size + start, 0)
    end = min(end, size - 1)
    if start > end:
        return 0, size - 1
    return start, end


async def fetch_range(
    note_id: str, filename: str, range_header: str | None, size: int
) -> tuple[bytes, int, int, bool]:
    """Return the requested slice of an object as bytes.

    Uploads are capped at ten megabytes, so the slice is read in one piece. That is
    deliberate: it keeps the response path free of streaming edge cases, and a
    streaming variant is only worth it if the upload limit is raised.
    """
    start, end = parse_byte_range(range_header, size)
    partial = bool(range_header) and (start, end) != (0, size - 1)

    async with _client() as client:
        request = {
            "Bucket": settings.r2_bucket,
            "Key": object_key(note_id, filename),
        }
        if partial:
            request["Range"] = f"bytes={start}-{end}"
        response = await client.get_object(**request)
        payload = await response["Body"].read()

    return payload, start, end, partial


async def fetch_to(note_id: str, filename: str, destination: Path) -> Path:
    """Fetch the object to a local file, for the Gnani endpoints that take bytes."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    async with _client() as client:
        await client.download_file(
            Bucket=settings.r2_bucket,
            Key=object_key(note_id, filename),
            Filename=str(destination),
        )
    return destination
