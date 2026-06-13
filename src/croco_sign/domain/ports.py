"""Domain ports (interfaces). Adapters in `infrastructure` implement these."""

from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from croco_sign.domain.models import Job, Language, TranslationResult
from croco_sign.domain.models import SpokenTranslationInput

@runtime_checkable
class PJMTranslator(Protocol):
    """A model that translates Polish Sign Language video into spoken text.

    Implementations are typically blocking/CPU-bound, so the service layer runs
    `translate` in a worker thread. The registered model name is owned by the
    registry, not the translator.
    """

    def translate(self, video: bytes, target_language: Language) -> TranslationResult:
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