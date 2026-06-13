"""Application factory and composition root."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from croco_sign.api.errors import register_exception_handlers
from croco_sign.api.routers import jobs, translation
from croco_sign.core.config import Settings, get_settings
from croco_sign.core.logging import configure_logging
from croco_sign.domain.ports import SpokenLanguageTranslator
from croco_sign.infrastructure.storage.memory_job_store import InMemoryJobStore
from croco_sign.infrastructure.storage.video_storage import VideoStorage
from croco_sign.infrastructure.translators.registry import build_default_registry
from croco_sign.services.translation_service import TranslationService
from croco_sign.infrastructure.translators.deepl_translator import DeeplSpokenLanguageTranslator

def create_app(
    settings: Settings | None = None,
    spoken_translator: SpokenLanguageTranslator | None = None,
) -> FastAPI:
    """Build and wire the FastAPI application.

    `spoken_translator` can be injected (e.g. by tests) to avoid loading the
    production model; when omitted, the real NLLB-backed translator is built.
    """
    configure_logging()
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Composition root: instantiate adapters and the service once.
        registry = build_default_registry()
        job_store = InMemoryJobStore()
        video_storage = VideoStorage(max_bytes=settings.max_upload_bytes)
        translator = spoken_translator
        if translator is None:
            translator = DeeplSpokenLanguageTranslator(auth_key=settings.deepl_key)
        
        app.state.video_storage = video_storage
        app.state.translation_service = TranslationService(
            registry=registry,
            job_store=job_store,
            video_storage=video_storage,
            spoken_translator=translator,
        )
        yield

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

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
