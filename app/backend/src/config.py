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

LANGUAGES: tuple[tuple[str, str], ...] = (
    ("bn-IN", "Bengali"),
    ("en-IN", "English"),
    ("gu-IN", "Gujarati"),
    ("hi-IN", "Hindi"),
    ("kn-IN", "Kannada"),
    ("ml-IN", "Malayalam"),
    ("mr-IN", "Marathi"),
    ("pa-IN", "Punjabi"),
    ("ta-IN", "Tamil"),
    ("te-IN", "Telugu"),
)

UNSUPPORTED_BY_BATCH = ("gu-IN", "pa-IN")

BATCH_LANGUAGE_CODES = tuple(
    code for code, _ in LANGUAGES if code not in UNSUPPORTED_BY_BATCH
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
    cors_origins: tuple[str, ...] = (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )
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