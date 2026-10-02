"""HTTP range streaming for audio files. Single ranges only, which is all a
media element asks for."""

import re
from collections.abc import Iterator
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

RANGE_PATTERN = re.compile(r"bytes=(\d*)-(\d*)")
CHUNK_SIZE = 1024 * 256


def stream_file(path: Path, range_header: str | None, content_type: str) -> StreamingResponse:
    file_size = path.stat().st_size

    if range_header is None:
        return StreamingResponse(
            _chunks(path, 0, file_size - 1),
            media_type=content_type,
            headers={"accept-ranges": "bytes", "content-length": str(file_size)},
        )

    match = RANGE_PATTERN.fullmatch(range_header.strip())
    if match is None:
        raise HTTPException(status_code=400, detail="Malformed Range header")

    raw_start, raw_end = match.groups()
    if raw_start == "":
        start = max(file_size - int(raw_end), 0)
        end = file_size - 1
    else:
        start = int(raw_start)
        end = min(int(raw_end), file_size - 1) if raw_end else file_size - 1

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
            chunk = handle.read(min(CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
