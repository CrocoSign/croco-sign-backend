"""FastAPI dependency providers.

Singletons (registry, job store, service) are created once at startup and stored
on `app.state`; these providers expose them to route handlers via `Depends`.
"""

from __future__ import annotations

from fastapi import Depends, Request

from croco_sign.core.config import Settings, get_settings
from croco_sign.infrastructure.storage.video_storage import VideoStorage
from croco_sign.services.translation_service import TranslationService


def get_translation_service(request: Request) -> TranslationService:
    return request.app.state.translation_service


def get_video_storage(request: Request) -> VideoStorage:
    return request.app.state.video_storage


def get_app_settings() -> Settings:
    return get_settings()


__all__ = [
    "get_translation_service",
    "get_video_storage",
    "get_app_settings",
    "Depends",
]
