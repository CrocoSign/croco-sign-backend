"""Domain ports (interfaces). Adapters in `infrastructure` implement these."""

from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from croco_sign.domain.models import Job
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