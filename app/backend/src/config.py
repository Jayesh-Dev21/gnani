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

DEFAULT_LANGUAGE_CODE = "en-IN"

# Fallback order for summarisation. Groq's llama-3.x models were decommissioned on
# free and developer tiers in August 2026, so the chain is built from what their
# model list actually serves today: a flagship, a different vendor so a single
# vendor's outage is survivable, then the cheapest fast model.
DEFAULT_GROQ_MODELS = ("openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        extra="ignore",
    )

    env: str = "development"
    gnani_api_key: str
    groq_api_key: str
    gnani_model: str = "gnani-prisma-v2.5"
    gnani_base_url: str = "https://api.vachana.ai"
    stt_rest_timeout_seconds: float = 90
    stt_poll_interval_seconds: float = 30
    stt_batch_deadline_seconds: float = 900
    auth_jwks_url: str = "http://localhost:3000/api/auth/jwks"
    auth_audience: str = "http://localhost:3000"
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = "gnani-bucket"
    # Long enough for the browser to start playback and for Gnani to fetch a batch
    # source. Gnani's own transcript links expire after an hour, so this matches.
    r2_presign_expiry_seconds: int = 3600
    groq_base_url: str = "https://api.groq.com/openai/v1"
    llm_timeout_seconds: float = 90
    llm_max_output_tokens: int = 700
    # Chunk size in characters. Indic scripts average well under four characters
    # per token, so this stays inside a conservative prompt budget per chunk.
    llm_chunk_chars: int = 24000
    # A model that keeps failing is skipped for this long, so one dead model costs
    # a note one skipped attempt instead of three failed calls per note.
    llm_model_cooldown_seconds: float = 300
    worker_lease_seconds: float = 120
    worker_heartbeat_seconds: float = 30
    # How often the worker reclaims notes abandoned by a dead worker.
    worker_recovery_interval_seconds: float = 60
    worker_queues: str = "transcription,summarisation"
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
    # A plain comma separated string, because that is how it reads in a .env file.
    groq_models: str = ",".join(DEFAULT_GROQ_MODELS)
    llm_reasoning_effort: str = "low"

    @field_validator("gnani_api_key")
    @classmethod
    def gnani_key_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "GNANI_API_KEY is not set. Copy .env.example to .env and paste the key "
                "from the Gnani APIs dashboard."
            )
        return value

    @model_validator(mode="after")
    def r2_credentials_present(self) -> "Settings":
        """Audio lives in R2, so half a set of credentials is worse than none."""
        missing = [
            name
            for name, value in (
                ("R2_ACCOUNT_ID", self.r2_account_id),
                ("R2_ACCESS_KEY_ID", self.r2_access_key_id),
                ("R2_SECRET_ACCESS_KEY", self.r2_secret_access_key),
                ("R2_BUCKET", self.r2_bucket),
            )
            if not value.strip()
        ]
        if missing:
            raise ValueError(
                f"Audio storage needs {', '.join(missing)}. Create a bucket and an R2 "
                "API token with Object Read & Write at "
                "https://dash.cloudflare.com/?to=/:account/r2/api-tokens"
            )
        return self

    @field_validator("groq_api_key")
    @classmethod
    def groq_key_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "GROQ_API_KEY is not set. Copy .env.example to .env and paste the key "
                "from the GroqCloud console at https://console.groq.com/keys."
            )
        return value

    @field_validator("groq_models")
    @classmethod
    def groq_chain_not_empty(cls, value: str) -> str:
        """A chain with nothing in it cannot fail over, so refuse it at startup."""
        if not [model for model in value.split(",") if model.strip()]:
            raise ValueError(
                "GROQ_MODELS is empty. List the models to try in order, for example "
                "openai/gpt-oss-120b,qwen/qwen3.8-27b,openai/gpt-oss-20b."
            )
        return value

    @property
    def groq_model_chain(self) -> tuple[str, ...]:
        """The fallback chain, in the order models should be tried."""
        return tuple(model.strip() for model in self.groq_models.split(",") if model.strip())

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
    def sync_database_url(self) -> str:
        """Procrastinate speaks psycopg3; SQLAlchemy speaks asyncpg. One URL, two drivers."""
        return self.database_url.replace("+asyncpg", "")



@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()