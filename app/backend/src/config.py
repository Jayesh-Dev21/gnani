from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

AUDIO_CONTENT_TYPES = (
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/ogg",
    "audio/flac",
    "audio/aac",
    "audio/mp4a-latm",
    "audio/webm",
    "audio/amr",
)

BATCH_LANGUAGE_CODES = (
    "bn-IN",
    "en-IN",
    "hi-IN",
    "kn-IN",
    "ml-IN",
    "mr-IN",
    "ta-IN",
    "te-IN",
)

DEFAULT_LANGUAGE_CODE = "hi-IN,en-IN"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    data_dir: Path = Path("data")
    database_url: str = (
        "postgresql+psycopg://audio_notes:audio_notes@localhost:5432/audio_notes"
    )
    max_upload_bytes: int = 10 * 1024 * 1024
    audio_content_types: tuple[str, ...] = AUDIO_CONTENT_TYPES
    batch_language_codes: tuple[str, ...] = BATCH_LANGUAGE_CODES
    default_language_code: str = DEFAULT_LANGUAGE_CODE

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()