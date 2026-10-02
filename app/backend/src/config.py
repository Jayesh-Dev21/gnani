from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
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
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        extra="ignore",
    )

    env: str = "development"
    gnani_api_key: str
    gnani_model: str = "gnani-prisma-v2.5"
    stt_rest_timeout_seconds: float = 90
    data_dir: Path = Path("data")
    auth_jwks_url: str = "http://localhost:3000/api/auth/jwks"
    auth_audience: str = "http://localhost:3000"
    enable_dev_auth: bool = False
    dev_user_id: str = "dev-user"
    database_url: str = (
        "postgresql+asyncpg://audio_notes:audio_notes@localhost:5432/audio_notes"
    )
    max_upload_bytes: int = 10 * 1024 * 1024
    cors_origins: tuple[str, ...] = (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )
    audio_content_types: tuple[str, ...] = AUDIO_CONTENT_TYPES
    batch_language_codes: tuple[str, ...] = BATCH_LANGUAGE_CODES
    default_language_code: str = DEFAULT_LANGUAGE_CODE

    @field_validator("gnani_api_key")
    @classmethod
    def gnani_key_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "GNANI_API_KEY is not set. Copy .env.example to .env and paste the key "
                "from the Gnani APIs dashboard."
            )
        return value

    @field_validator("database_url")
    @classmethod
    def use_asyncpg(cls, value: str) -> str:
        """DATABASE_URL is shared with the frontend, which speaks plain
postgresql://. This service needs the async driver."""
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @model_validator(mode="after")
    def refuse_dev_auth_in_production(self) -> "Settings":
        if self.enable_dev_auth and self.env == "production":
            raise ValueError(
                "ENABLE_DEV_AUTH cannot be enabled when ENV=production"
            )
        return self

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()