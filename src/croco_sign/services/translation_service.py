"""Application service: orchestrates the async translation use case."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import AsyncIterator
from uuid import uuid4

from croco_sign.domain.models import (
    Job,
    Language,
    ModelInfo,
    SpokenTranslationInput,
    TranslationResult,
)
from croco_sign.domain.ports import JobStore, SpokenLanguageTranslator
from croco_sign.infrastructure.storage.video_storage import VideoStorage
from croco_sign.infrastructure.translators.registry import TranslatorRegistry

logger = logging.getLogger(__name__)


class TranslationService:
    """Coordinates the registry, job store, and storage for translations."""

    def __init__(
        self,
        registry: TranslatorRegistry,
        job_store: JobStore,
        video_storage: VideoStorage,
        spoken_translator: SpokenLanguageTranslator,
    ) -> None:
        self._registry = registry
        self._job_store = job_store
        self._storage = video_storage
        self._spoken_translator = spoken_translator

    def list_models(self) -> list[ModelInfo]:
        return self._registry.list_models()

    def ensure_model_exists(self, model_name: str) -> None:
        """Raise ModelNotFoundError if the model is unknown (fail fast)."""
        self._registry.get(model_name)

    async def submit(self, model_name: str, target_language: Language) -> Job:
        """Validate the model and create a PENDING job. Raises ModelNotFoundError."""
        self._registry.get(model_name)  # validate eagerly -> 404 before accepting
        job = Job(
            id=uuid4().hex,
            model_name=model_name,
            target_language=target_language,
        )
        await self._job_store.create(job)
        return job

    async def get_job(self, job_id: str) -> Job:
        """Return a job by id. Raises JobNotFoundError."""
        return await self._job_store.get(job_id)

    def stream_job(self, job_id: str) -> AsyncIterator[Job]:
        """Stream a job's state changes until it reaches a terminal status."""
        return self._job_store.subscribe(job_id)

    async def process(self, job_id: str, video_path: Path) -> None:
        """Run the translation in the background and persist the outcome.

        Blocking inference and disk reads run in worker threads so the event loop
        stays responsive.
        """
        job = await self._job_store.get(job_id)
        job.mark_running()
        await self._job_store.update(job)

        try:
            pjm = self._registry.get(job.model_name)
            video = await asyncio.to_thread(self._storage.read_bytes, video_path)
            # Stage 1: recognize the sign video into English text.
            recognized = await asyncio.to_thread(pjm.translate, video)
            # Stage 2: translate the English text into the target language.
            translated = await asyncio.to_thread(
                self._spoken_translator.translate,
                SpokenTranslationInput(
                    target_language=job.target_language, text=recognized
                ),
            )
            # Stamp the registered model name; translators don't know their own name.
            job.mark_succeeded(
                TranslationResult(
                    text=translated,
                    target_language=job.target_language,
                    model_name=job.model_name,
                )
            )
        except Exception as exc:  # noqa: BLE001 - surface any failure on the job
            logger.exception("Translation job %s failed", job_id)
            job.mark_failed(str(exc))
        finally:
            self._storage.remove(video_path)

        await self._job_store.update(job)
