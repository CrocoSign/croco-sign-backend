"""Maps domain exceptions to HTTP responses, keeping HTTP out of the core."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from croco_sign.api.schemas import ErrorResponse
from croco_sign.domain.exceptions import (
    DomainError,
    InvalidLanguageError,
    JobNotFoundError,
    ModelNotFoundError,
    PayloadTooLargeError,
    SegmentNotFoundError,
    SegmentVideoNotFoundError,
    SegmentVideoProcessingError,
    TranslationFailedError,
    UnsupportedMediaError,
)

_STATUS_MAP: dict[type[DomainError], int] = {
    ModelNotFoundError: status.HTTP_404_NOT_FOUND,
    JobNotFoundError: status.HTTP_404_NOT_FOUND,
    UnsupportedMediaError: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    InvalidLanguageError: 422,
    PayloadTooLargeError: 413,
    TranslationFailedError: 422,
    SegmentNotFoundError: status.HTTP_404_NOT_FOUND,
    SegmentVideoNotFoundError: status.HTTP_404_NOT_FOUND,
    SegmentVideoProcessingError: status.HTTP_502_BAD_GATEWAY,
}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        http_status = _STATUS_MAP.get(type(exc), status.HTTP_400_BAD_REQUEST)
        return JSONResponse(
            status_code=http_status,
            content=ErrorResponse(code=exc.code, message=exc.message).model_dump(),
        )
