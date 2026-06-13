"""Pydantic DTOs for the HTTP API. Kept separate from domain models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from croco_sign.domain.models import Job, JobStatus, Language, ModelInfo, TranslationResult


class ModelInfoResponse(BaseModel):
    name: str

    @classmethod
    def from_domain(cls, info: ModelInfo) -> "ModelInfoResponse":
        return cls(name=info.name)


class TranslationResultResponse(BaseModel):
    text: str
    target_language: Language
    model_name: str

    @classmethod
    def from_domain(cls, result: TranslationResult) -> "TranslationResultResponse":
        return cls(
            text=result.text,
            target_language=result.target_language,
            model_name=result.model_name,
        )


class TranslateAccepted(BaseModel):
    """202 response when a translation job is accepted."""

    job_id: str
    status: JobStatus
    status_url: str = Field(..., description="Poll this URL for the job result.")


class JobStatusResponse(BaseModel):
    job_id: str
    model_name: str
    status: JobStatus
    target_language: Language
    created_at: datetime
    updated_at: datetime
    result: TranslationResultResponse | None = None
    error: str | None = None

    @classmethod
    def from_domain(cls, job: Job) -> "JobStatusResponse":
        return cls(
            job_id=job.id,
            model_name=job.model_name,
            status=job.status,
            target_language=job.target_language,
            created_at=job.created_at,
            updated_at=job.updated_at,
            result=(
                TranslationResultResponse.from_domain(job.result)
                if job.result is not None
                else None
            ),
            error=job.error,
        )


class ErrorResponse(BaseModel):
    code: str
    message: str
