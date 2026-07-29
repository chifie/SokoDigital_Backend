from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


# Absolute path to .env in the project root – prevents pydantic-settings
# from searching parent directories and accidentally loading another .env file.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # App
    APP_NAME: str = "SokoDigital API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development | staging | production

    # API
    API_V1_PREFIX: str = "/api/v1"
    API_LATEST_VERSION: str = "v1"
    API_SUPPORTED_VERSIONS: list[str] = ["v1"]

    # Frontend URL (for email links)
    APP_URL: str = "http://localhost:5173"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/sokodigital_db"

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours

    # File Uploads
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 5 * 1024 * 1024  # 5 MB

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    # Supabase (optional, for maintaining backward compatibility)
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None

    # Email (optional SMTP config)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[str] = None

    # Redis (optional, for distributed rate limiting & caching)
    REDIS_URL: Optional[str] = None

    # Cache (TTL for Redis response cache)
    CACHE_DEFAULT_TTL: int = 60

    # Sentry (optional, for error tracking)
    SENTRY_DSN: Optional[str] = None

    # AI (OpenAI-compatible)
    AI_API_KEY: Optional[str] = None
    AI_API_URL: str = "https://api.openai.com/v1/chat/completions"
    AI_MODEL: str = "gpt-4o-mini"
    AI_MAX_TOKENS: int = 1024

    # Meilisearch (optional, for full-text product search)
    MEILISEARCH_URL: Optional[str] = None
    MEILISEARCH_API_KEY: Optional[str] = None

    # Webhooks
    WEBHOOK_MAX_ATTEMPTS: int = 3
    WEBHOOK_TIMEOUT_SECONDS: int = 10

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
