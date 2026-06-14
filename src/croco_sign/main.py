"""Application factory and composition root."""

from __future__ import annotations

from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from croco_sign.api.errors import register_exception_handlers
from croco_sign.api.routers import jobs, segments, translation
from croco_sign.core.config import Settings, get_settings
from croco_sign.core.logging import configure_logging
from croco_sign.domain.ports import SegmentVideoSource, SpokenLanguageTranslator
from croco_sign.infrastructure.cache.redis_segment_video_cache import RedisSegmentVideoCache
from croco_sign.infrastructure.datasets.hf_segment_video_source import (
    HuggingFaceSegmentVideoSource,
)
from croco_sign.infrastructure.datasets.mp4_remux_segment_video_source import (
    Mp4RemuxingSegmentVideoSource,
)
from croco_sign.infrastructure.storage.memory_job_store import InMemoryJobStore
from croco_sign.infrastructure.storage.memory_video_store import InMemoryVideoStore
from croco_sign.infrastructure.storage.redis_job_store import RedisJobStore
from croco_sign.infrastructure.storage.redis_video_store import RedisVideoStore
from croco_sign.infrastructure.storage.sqlite_segment_repository import (
    SqliteSegmentRepository,
)
from croco_sign.infrastructure.storage.video_storage import VideoStorage
from croco_sign.infrastructure.translators.registry import build_default_registry
from croco_sign.services.job_runner import ArqJobRunner, EagerJobRunner
from croco_sign.services.segment_service import SegmentService
from croco_sign.services.translation_service import TranslationService
from croco_sign.infrastructure.translators.deepl_translator import DeeplSpokenLanguageTranslator

def create_app(
    settings: Settings | None = None,
    spoken_translator: SpokenLanguageTranslator | None = None,
    segment_video_source: SegmentVideoSource | None = None,
    eager_processing: bool = False,
) -> FastAPI:
    """Build and wire the FastAPI application.

    `spoken_translator` can be injected (e.g. by tests) to avoid loading the
    production model; when omitted, the real DeepL-backed translator is built.

    `segment_video_source` can be injected (e.g. by tests) to avoid HuggingFace
    network access; when omitted, the real streaming source is built (and, in
    production, wrapped in a Redis read-through cache).

    `eager_processing` selects the single-process path: in-memory shared state and
    in-process job execution, with no Redis or arq queue. Used by tests and local
    single-process runs; production (the default) uses Redis + the arq worker.
    """
    configure_logging()
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Composition root: instantiate adapters and the service once.
        registry = build_default_registry()
        video_reader = VideoStorage(max_bytes=settings.max_upload_bytes)
        translator = spoken_translator
        if translator is None:
            translator = DeeplSpokenLanguageTranslator(auth_key=settings.deepl_key)

        # Segment catalog (identical in both branches) and clip source. The bare
        # source streams from HuggingFace; production wraps it in a Redis cache.
        segment_repo = SqliteSegmentRepository(db_path=settings.sqlite_db_path)
        if segment_video_source is not None:
            # Injected (tests): used as-is, no remux — fakes return ready bytes.
            video_source = segment_video_source
        else:
            # Real dataset clips are MPEG-TS; remux to MP4 below the cache so each
            # clip is converted at most once and the cached bytes are playable.
            video_source = Mp4RemuxingSegmentVideoSource(
                HuggingFaceSegmentVideoSource(
                    repo_id=settings.hf_segments_repo_id,
                    split=settings.hf_segments_split,
                )
            )

        if eager_processing:
            # In-memory store + pub/sub, jobs run in-process. No Redis/arq.
            job_store = InMemoryJobStore()
            video_store = InMemoryVideoStore()
            service = TranslationService(
                registry=registry,
                job_store=job_store,
                video_store=video_store,
                spoken_translator=translator,
            )
            app.state.video_store = video_store
            app.state.video_reader = video_reader
            app.state.translation_service = service
            app.state.job_runner = EagerJobRunner(service)
            app.state.segment_service = SegmentService(segment_repo, video_source)
            yield
            return

        # Production: shared Redis state + pub/sub, processing on the arq worker.
        redis = Redis.from_url(settings.redis_url, decode_responses=False)
        arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        job_store = RedisJobStore(redis, ttl_seconds=settings.job_ttl_seconds)
        video_store = RedisVideoStore(redis, ttl_seconds=settings.video_ttl_seconds)
        service = TranslationService(
            registry=registry,
            job_store=job_store,
            video_store=video_store,
            spoken_translator=translator,
        )
        cached_video_source = RedisSegmentVideoCache(
            redis, video_source, ttl_seconds=settings.segment_video_ttl_seconds
        )
        app.state.redis = redis
        app.state.arq_pool = arq_pool
        app.state.video_store = video_store
        app.state.video_reader = video_reader
        app.state.translation_service = service
        app.state.job_runner = ArqJobRunner(arq_pool)
        app.state.segment_service = SegmentService(segment_repo, cached_video_source)
        try:
            yield
        finally:
            await arq_pool.aclose()
            await redis.aclose()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        summary="Translate Polish Sign Language (PJM) video into spoken-language text.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allow_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(translation.router)
    app.include_router(jobs.router)
    app.include_router(segments.router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
