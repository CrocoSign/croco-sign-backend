"""In-memory implementation of the JobStore port.

Async-safe via a lock, with per-job pub/sub so SSE subscribers receive pushes on
every update. Suitable for a single process; swap for Redis (shared store +
pub/sub) later without touching the service or domain layers.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import AsyncIterator

from croco_sign.domain.exceptions import JobNotFoundError
from croco_sign.domain.models import Job


class InMemoryJobStore:
    """Implements the JobStore port using a dict guarded by an asyncio lock."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._subscribers: dict[str, set[asyncio.Queue[Job]]] = {}
        self._lock = asyncio.Lock()

    async def create(self, job: Job) -> None:
        async with self._lock:
            self._jobs[job.id] = deepcopy(job)

    async def get(self, job_id: str) -> Job:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(f"Job '{job_id}' not found.")
            return deepcopy(job)

    async def update(self, job: Job) -> None:
        async with self._lock:
            if job.id not in self._jobs:
                raise JobNotFoundError(f"Job '{job.id}' not found.")
            self._jobs[job.id] = deepcopy(job)
            queues = list(self._subscribers.get(job.id, ()))
        # Notify outside the lock; queues are unbounded so put_nowait won't block.
        for queue in queues:
            queue.put_nowait(deepcopy(job))

    async def subscribe(self, job_id: str) -> AsyncIterator[Job]:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(f"Job '{job_id}' not found.")
            queue: asyncio.Queue[Job] = asyncio.Queue()
            self._subscribers.setdefault(job_id, set()).add(queue)
            current = deepcopy(job)

        try:
            yield current
            if current.is_terminal:
                return
            while True:
                job = await queue.get()
                yield job
                if job.is_terminal:
                    return
        finally:
            async with self._lock:
                subscribers = self._subscribers.get(job_id)
                if subscribers is not None:
                    subscribers.discard(queue)
                    if not subscribers:
                        self._subscribers.pop(job_id, None)
