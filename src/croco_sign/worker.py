"""arq worker entrypoint.

Run with: `arq croco_sign.worker.WorkerSettings`.

The worker is a separate process from the API and shares nothing with it except
Redis. It owns its own composition root (registry, translators, stores) so the
heavy translation models load here, once, on startup — keeping the API light.
"""

from __future__ import annotations

import logging
from typing import Any

from arq.connections import RedisSettings
from redis.asyncio import Redis

from croco_sign.core.config import get_settings
from croco_sign.core.logging import configure_logging
from croco_sign.infrastructure.storage.redis_job_store import RedisJobStore
from croco_sign.infrastructure.storage.redis_video_store import RedisVideoStore
from croco_sign.infrastructure.translators.deepl_translator import (
    DeeplSpokenLanguageTranslator,
)
from croco_sign.infrastructure.translators.registry import build_default_registry
from croco_sign.services.translation_service import TranslationService

logger = logging.getLogger(__name__)


async def translate_job(ctx: dict[str, Any], job_id: str) -> None:
    """arq task: run a previously-created translation job to completion."""
    service: TranslationService = ctx["translation_service"]
    await service.process(job_id)


async def on_startup(ctx: dict[str, Any]) -> None:
    configure_logging()
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=False)
    registry = build_default_registry()
    job_store = RedisJobStore(redis, ttl_seconds=settings.job_ttl_seconds)
    video_store = RedisVideoStore(redis, ttl_seconds=settings.video_ttl_seconds)
    translator = DeeplSpokenLanguageTranslator(auth_key=settings.deepl_key)
    ctx["redis_client"] = redis
    ctx["translation_service"] = TranslationService(
        registry=registry,
        job_store=job_store,
        video_store=video_store,
        spoken_translator=translator,
    )
    logger.info("arq worker started; translation service ready")


async def on_shutdown(ctx: dict[str, Any]) -> None:
    redis: Redis = ctx["redis_client"]
    await redis.aclose()


class WorkerSettings:
    """arq configuration (discovered by the `arq` CLI)."""

    functions = [translate_job]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    # Translation inference is GPU/CPU-bound; run one at a time per worker.
    max_jobs = 1
    # Generous: covers model load on a cold worker plus inference.
    job_timeout = 600
