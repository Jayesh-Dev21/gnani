"""Local-disk audio storage — the dev-mode stand-in for object storage.

This module is the only place in the backend allowed to build a filesystem path.
Production replaces the three functions below with object storage plus
short-lived signed URLs; nothing outside this file may assume a local path.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from src.config import settings

CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class StoredAudio:
    note_id: str
    filename: str
    content_type: str
    size_bytes: int

    @property
    def audio_path(self) -> Path:
        return _note_dir(self.note_id) / self.filename

    @property
    def meta_path(self) -> Path:
        return _note_dir(self.note_id) / "meta.json"


def _note_dir(note_id: str) -> Path:
    return settings.uploads_dir / note_id


def save(note_id: str, upload: UploadFile) -> StoredAudio:
    content_type = upload.content_type or ""
    if content_type not in settings.audio_content_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported audio type: {content_type or 'unknown'}",
        )

    note_dir = _note_dir(note_id)
    note_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(upload.filename or "audio").name
    path = note_dir / filename

    size = 0
    with path.open("wb") as handle:
        while chunk := upload.file.read(CHUNK_SIZE):
            size += len(chunk)
            if size > settings.max_upload_bytes:
                handle.close()
                path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=(
                        f"Audio is larger than the "
                        f"{settings.max_upload_bytes // (1024 * 1024)}MB limit"
                    ),
                )
            handle.write(chunk)

    stored = StoredAudio(
        note_id=note_id,
        filename=filename,
        content_type=content_type,
        size_bytes=size,
    )
    stored.meta_path.write_text(json.dumps(asdict(stored)))
    return stored


def read(note_id: str) -> StoredAudio | None:
    meta_path = _note_dir(note_id) / "meta.json"
    if not meta_path.is_file():
        return None
    return StoredAudio(**json.loads(meta_path.read_text()))


def delete(note_id: str) -> None:
    note_dir = _note_dir(note_id)
    for child in note_dir.glob("*"):
        child.unlink(missing_ok=True)
    note_dir.rmdir()