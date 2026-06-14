"""Concrete `JobRunner` implementations (the port lives in `domain.ports`).

Production enqueues onto the arq queue so a separate worker runs it; tests run it
in-process so the existing TestClient-based suite still sees jobs complete within
the request.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arq import ArqRedis

    from croco_sign.services.translation_service import TranslationService


class ArqJobRunner:
    """Enqueues the job onto arq; a worker process picks it up."""

    def __init__(self, pool: "ArqRedis") -> None:
        self._pool = pool

    async def run(self, job_id: str) -> None:
        await self._pool.enqueue_job("translate_job", job_id)


class EagerJobRunner:
    """Runs the job in-process (single-process / test path)."""

    def __init__(self, service: "TranslationService") -> None:
        self._service = service

    async def run(self, job_id: str) -> None:
        await self._service.process(job_id)
