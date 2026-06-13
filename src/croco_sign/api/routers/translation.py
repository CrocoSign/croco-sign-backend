"""Routes for model discovery and submitting translation jobs."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request, UploadFile, status

from croco_sign.api.dependencies import (
    get_app_settings,
    get_translation_service,
    get_video_storage,
)
from croco_sign.api.schemas import ModelInfoResponse, TranslateAccepted
from croco_sign.core.config import Settings
from croco_sign.domain.exceptions import InvalidLanguageError, UnsupportedMediaError
from croco_sign.domain.models import Language
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
    background_tasks: BackgroundTasks,
    video: UploadFile,
    target_language: str = Form(...),
    service: TranslationService = Depends(get_translation_service),
    storage: VideoStorage = Depends(get_video_storage),
    settings: Settings = Depends(get_app_settings),
) -> TranslateAccepted:
    # Resolve target .
    try:
        language = Language.from_code(target_language)
    except ValueError as exc:
        raise InvalidLanguageError(str(exc)) from exc

    # Fail fast on unknown model and unsupported media before persisting the upload.
    service.ensure_model_exists(model_name)
    if video.content_type not in settings.allowed_mime_types:
        allowed = ", ".join(settings.allowed_mime_types)
        raise UnsupportedMediaError(
            f"Unsupported content type '{video.content_type}'. Allowed: {allowed}."
        )

    video_path = await storage.save(video)
    job = await service.submit(model_name, language)
    background_tasks.add_task(service.process, job.id, video_path)

    status_url = str(request.url_for("get_job", job_id=job.id))
    return TranslateAccepted(job_id=job.id, status=job.status, status_url=status_url)
