"""Routes for model discovery and submitting translation jobs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, UploadFile, status

from croco_sign.api.dependencies import (
    get_app_settings,
    get_job_runner,
    get_translation_service,
    get_video_reader,
    get_video_store,
)
from croco_sign.api.schemas import ModelInfoResponse, TranslateAccepted
from croco_sign.core.config import Settings
from croco_sign.domain.exceptions import InvalidLanguageError, UnsupportedMediaError
from croco_sign.domain.models import Language
from croco_sign.domain.ports import JobRunner, VideoStore
from croco_sign.infrastructure.storage.video_storage import VideoStorage
from croco_sign.services.translation_service import TranslationService

router = APIRouter(tags=["translation"])


@router.get("/models", response_model=list[ModelInfoResponse])
async def list_models(
    service: TranslationService = Depends(get_translation_service),
) -> list[ModelInfoResponse]:
    return [ModelInfoResponse.from_domain(m) for m in service.list_models()]


@router.post(
    "/models/{model_name}/translate",
    response_model=TranslateAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def translate(
    model_name: str,
    request: Request,
    video: UploadFile,
    target_language: str = Form(...),
    service: TranslationService = Depends(get_translation_service),
    video_reader: VideoStorage = Depends(get_video_reader),
    video_store: VideoStore = Depends(get_video_store),
    job_runner: JobRunner = Depends(get_job_runner),
    settings: Settings = Depends(get_app_settings),
) -> TranslateAccepted:
    # Resolve target .
    try:
        language = Language.from_code(target_language)
    except ValueError as exc:
        raise InvalidLanguageError(str(exc)) from exc

    # Fail fast on unknown model and unsupported media before reading the upload.
    service.ensure_model_exists(model_name)
    if video.content_type not in settings.allowed_mime_types:
        allowed = ", ".join(settings.allowed_mime_types)
        raise UnsupportedMediaError(
            f"Unsupported content type '{video.content_type}'. Allowed: {allowed}."
        )

    data = await video_reader.read_with_limit(video)
    job = await service.submit(model_name, language)
    # Stash the bytes where the worker can reach them, then enqueue.
    await video_store.put(job.id, data)
    await job_runner.run(job.id)

    status_url = str(request.url_for("get_job", job_id=job.id))
    return TranslateAccepted(job_id=job.id, status=job.status, status_url=status_url)
