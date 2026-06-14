"""Domain ports (interfaces). Adapters in `infrastructure` implement these."""

from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from croco_sign.domain.models import Experiment, MetricsTable
from croco_sign.domain.models import Job
from croco_sign.domain.models import Segment, SegmentFacets, SegmentFilters, SegmentPage
from croco_sign.domain.models import SpokenTranslationInput

@runtime_checkable
class PJMTranslator(Protocol):
    """A model that recognizes Polish Sign Language video into English text.

    Implementations are typically blocking/CPU-bound, so the service layer runs
    `translate` in a worker thread. Translating the recognized English text into
    the caller's target language is a separate concern handled by a
    `SpokenLanguageTranslator`. The registered model name is owned by the
    registry, not the translator.
    """

    def translate(self, video: bytes) -> str:
        ...


class JobStore(Protocol):
    """Persistence port for translation jobs."""

    async def create(self, job: Job) -> None:
        ...

    async def get(self, job_id: str) -> Job:
        """Return the job, or raise JobNotFoundError if it does not exist."""
        ...

    async def update(self, job: Job) -> None:
        ...

    def subscribe(self, job_id: str) -> AsyncIterator[Job]:
        """Yield the job's current state, then each subsequent update until terminal.

        Raises JobNotFoundError if the job does not exist.
        """
        ...


class SpokenLanguageTranslator(Protocol):
    def translate(self, input: SpokenTranslationInput) -> str:
        ...


class VideoStore(Protocol):
    """Shared blob storage for uploaded videos, keyed by job id.

    The API receives the upload but processing runs in a separate worker, so the
    bytes must live somewhere both can reach. Adapters in `infrastructure`
    implement this (Redis today; S3/MinIO is a drop-in later).
    """

    async def put(self, key: str, data: bytes) -> None:
        ...

    async def get(self, key: str) -> bytes:
        """Return the stored bytes, or raise VideoNotFoundError if absent."""
        ...

    async def remove(self, key: str) -> None:
        ...


class JobRunner(Protocol):
    """Triggers processing of a previously-created job.

    Production enqueues onto a task queue so a separate worker runs it; tests run
    it in-process. Adapters live in the service/infrastructure layers.
    """

    async def run(self, job_id: str) -> None:
        ...


class SegmentRepository(Protocol):
    """Read port for the local relational segment catalog (SQLite today)."""

    async def list(
        self, limit: int, offset: int, filters: SegmentFilters
    ) -> SegmentPage:
        """Return a page of segment summaries plus the total matching `filters`."""
        ...

    async def get_by_id(self, id: int) -> Segment:
        """Return the full segment aggregate, or raise SegmentNotFoundError."""
        ...

    async def facets(self) -> SegmentFacets:
        """Return the distinct values available for each dropdown filter."""
        ...


class MetricsRepository(Protocol):
    """Read port for the local benchmark-metrics catalog (SQLite today)."""

    async def list_metrics_table(self) -> MetricsTable:
        """Return the full matrix: metric columns plus one row per experiment."""
        ...

    async def get_experiment(self, id: int) -> Experiment:
        """Return the full experiment aggregate, or raise ExperimentNotFoundError."""
        ...


class SegmentVideoSource(Protocol):
    """Fetches raw mp4 bytes for a segment, located by its textual segment_id.

    Backed by the HuggingFace WebDataset; a caching decorator may wrap it. The
    `segment_id` is the dataset `__key__` (e.g. "004_000_M").
    """

    async def get_video(self, segment_id: str) -> bytes:
        """Return raw mp4 bytes, or raise SegmentVideoNotFoundError."""
        ...