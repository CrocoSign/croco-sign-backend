"""Application configuration loaded from the environment."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from croco_sign.domain.models import Language


class Settings(BaseSettings):
    """Typed application settings. Override any field via env vars (prefix CROCO_)."""

    model_config = SettingsConfigDict(
        env_prefix="CROCO_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "croco-sign-backend"
    default_target_language: Language = Language.POLISH

    # CORS: origins allowed to call the API from a browser (e.g. the frontend).
    # Override via CROCO_CORS_ALLOW_ORIGINS (JSON list).
    cors_allow_origins: tuple[str, ...] = ("*",)

    # Upload constraints.
    max_upload_bytes: int = 100 * 1024 * 1024  # 100 MiB
    allowed_mime_types: tuple[str, ...] = (
        "video/mp4",
        "video/quicktime",
        "video/webm",
        "video/x-matroska",
    )
    
    deepl_key: str

    # Redis: shared job store + pub/sub and the arq task queue broker. Override
    # via CROCO_REDIS_URL (e.g. redis://redis:6379/0 under docker compose).
    redis_url: str = "redis://localhost:6379/0"
    # How long a job's state survives in Redis; refreshed on every update so an
    # actively-watched job never expires mid-flight.
    job_ttl_seconds: int = 24 * 3600
    # How long an uploaded video lingers in Redis before the worker consumes it.
    video_ttl_seconds: int = 3600


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
