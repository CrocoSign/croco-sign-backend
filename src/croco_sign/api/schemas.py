"""Pydantic DTOs for the HTTP API. Kept separate from domain models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from croco_sign.domain.models import (
    BenchmarkModel,
    Experiment,
    ExperimentRow,
    ExperimentScore,
    Job,
    JobStatus,
    Language,
    MetricDefinition,
    MetricsTable,
    ModelInfo,
    Segment,
    SegmentFacets,
    SegmentPage,
    SegmentSummary,
    Signer,
    TranslationResult,
    VideoMetadata,
)


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


# --- Segments ---------------------------------------------------------------
# These DTOs are the single whitelist of what reaches the client. The domain
# `Segment` aggregate stays complete; to change exposed fields, edit the relevant
# `*Response` model (and its `from_domain`) — the domain and SQL are untouched.


class SegmentSummaryResponse(BaseModel):
    id: int
    segment_id: str
    sentence: str
    age: str
    sex: str
    speaker_id: str

    @classmethod
    def from_domain(cls, summary: SegmentSummary) -> "SegmentSummaryResponse":
        return cls(
            id=summary.id,
            segment_id=summary.segment_id,
            sentence=summary.sentence,
            age=summary.age,
            sex=summary.sex,
            speaker_id=summary.speaker_id,
        )


class SegmentFacetsResponse(BaseModel):
    """Distinct values for the list's dropdown filters."""

    ages: list[str]
    sexes: list[str]
    speaker_ids: list[str]

    @classmethod
    def from_domain(cls, facets: SegmentFacets) -> "SegmentFacetsResponse":
        return cls(
            ages=facets.ages,
            sexes=facets.sexes,
            speaker_ids=facets.speaker_ids,
        )


class SegmentPageResponse(BaseModel):
    items: list[SegmentSummaryResponse]
    total: int

    @classmethod
    def from_domain(cls, page: SegmentPage) -> "SegmentPageResponse":
        return cls(
            items=[SegmentSummaryResponse.from_domain(s) for s in page.items],
            total=page.total,
        )


class SignerResponse(BaseModel):
    id: int
    speaker_id: str
    sex: str
    age: str
    special_case: str

    @classmethod
    def from_domain(cls, signer: Signer) -> "SignerResponse":
        return cls(
            id=signer.id,
            speaker_id=signer.speaker_id,
            sex=signer.sex,
            age=signer.age,
            special_case=signer.special_case,
        )


class VideoMetadataResponse(BaseModel):
    id: int
    video_id: int
    video_url: str
    subtitles_url: str
    video_type: str
    task_id: int
    speaker_side: str
    signer: SignerResponse

    @classmethod
    def from_domain(cls, metadata: VideoMetadata) -> "VideoMetadataResponse":
        return cls(
            id=metadata.id,
            video_id=metadata.video_id,
            video_url=metadata.video_url,
            subtitles_url=metadata.subtitles_url,
            video_type=metadata.video_type,
            task_id=metadata.task_id,
            speaker_side=metadata.speaker_side,
            signer=SignerResponse.from_domain(metadata.signer),
        )


class SegmentDetailResponse(BaseModel):
    id: int
    segment_id: str
    sentence: str
    video_metadata: VideoMetadataResponse

    @classmethod
    def from_domain(cls, segment: Segment) -> "SegmentDetailResponse":
        return cls(
            id=segment.id,
            segment_id=segment.segment_id,
            sentence=segment.sentence,
            video_metadata=VideoMetadataResponse.from_domain(segment.video_metadata),
        )


# --- Metrics ----------------------------------------------------------------
# The benchmark matrix (GET /metrics) and per-experiment detail
# (GET /experiments/{id}). The architecture diagram is served as bytes by a
# separate endpoint, so it is not a field here.


class BenchmarkModelResponse(BaseModel):
    id: int
    display_name: str

    @classmethod
    def from_domain(cls, model: BenchmarkModel) -> "BenchmarkModelResponse":
        return cls(id=model.id, display_name=model.display_name)


class MetricDefinitionResponse(BaseModel):
    id: int
    name: str
    description: str

    @classmethod
    def from_domain(cls, metric: MetricDefinition) -> "MetricDefinitionResponse":
        return cls(id=metric.id, name=metric.name, description=metric.description)


class ExperimentRowResponse(BaseModel):
    id: int
    model: BenchmarkModelResponse
    transfer_source: str
    split: str
    scores: dict[str, float]

    @classmethod
    def from_domain(cls, row: ExperimentRow) -> "ExperimentRowResponse":
        return cls(
            id=row.id,
            model=BenchmarkModelResponse.from_domain(row.model),
            transfer_source=row.transfer_source,
            split=row.split,
            scores=row.scores,
        )


class MetricsTableResponse(BaseModel):
    metrics: list[MetricDefinitionResponse]
    experiments: list[ExperimentRowResponse]

    @classmethod
    def from_domain(cls, table: MetricsTable) -> "MetricsTableResponse":
        return cls(
            metrics=[MetricDefinitionResponse.from_domain(m) for m in table.metrics],
            experiments=[
                ExperimentRowResponse.from_domain(e) for e in table.experiments
            ],
        )


class ExperimentScoreResponse(BaseModel):
    metric: MetricDefinitionResponse
    value: float

    @classmethod
    def from_domain(cls, score: ExperimentScore) -> "ExperimentScoreResponse":
        return cls(
            metric=MetricDefinitionResponse.from_domain(score.metric),
            value=score.value,
        )


class ExperimentDetailResponse(BaseModel):
    id: int
    transfer_source: str
    split: str
    model: BenchmarkModelResponse
    scores: list[ExperimentScoreResponse]

    @classmethod
    def from_domain(cls, experiment: Experiment) -> "ExperimentDetailResponse":
        return cls(
            id=experiment.id,
            transfer_source=experiment.transfer_source,
            split=experiment.split,
            model=BenchmarkModelResponse.from_domain(experiment.model),
            scores=[
                ExperimentScoreResponse.from_domain(s) for s in experiment.scores
            ],
        )
