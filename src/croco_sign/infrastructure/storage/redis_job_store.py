"""Redis implementation of the JobStore port.

Shared across processes/instances: job state lives in Redis keys and each update
is published on a per-job channel so SSE subscribers on any worker receive pushes.
This is the production swap for `InMemoryJobStore` — the service and domain layers
are unaware of it.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, AsyncIterator

from redis.asyncio import Redis

from croco_sign.domain.exceptions import JobNotFoundError
from croco_sign.domain.models import (
    Job,
    JobStatus,
    Language,
    TranslationResult,
)

_KEY_PREFIX = "croco:job:"


def _key(job_id: str) -> str:
    return f"{_KEY_PREFIX}{job_id}"


def _channel(job_id: str) -> str:
    return f"{_KEY_PREFIX}{job_id}:events"


def _job_to_dict(job: Job) -> dict[str, Any]:
    """Serialize a Job to JSON-safe primitives (enums -> values, datetimes -> ISO)."""
    result = None
    if job.result is not None:
        result = {
            "text": job.result.text,
            "target_language": job.result.target_language.value,
            "model_name": job.result.model_name,
        }
    return {
        "id": job.id,
        "model_name": job.model_name,
        "target_language": job.target_language.value,
        "status": job.status.value,
        "result": result,
        "error": job.error,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }


def _job_from_dict(data: dict[str, Any]) -> Job:
    result = data.get("result")
    return Job(
        id=data["id"],
        model_name=data["model_name"],
        target_language=Language(data["target_language"]),
        status=JobStatus(data["status"]),
        result=(
            TranslationResult(
                text=result["text"],
                target_language=Language(result["target_language"]),
                model_name=result["model_name"],
            )
            if result is not None
            else None
        ),
        error=data.get("error"),
        created_at=datetime.fromisoformat(data["created_at"]),
        updated_at=datetime.fromisoformat(data["updated_at"]),
    )


def _dumps(job: Job) -> str:
    return json.dumps(_job_to_dict(job))


def _loads(raw: str | bytes) -> Job:
    return _job_from_dict(json.loads(raw))


class RedisJobStore:
    """Implements the JobStore port backed by Redis keys + pub/sub channels."""

    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    async def create(self, job: Job) -> None:
        # No publish needed: nothing can subscribe before the id is handed back,
        # and subscribers always read the current state first.
        await self._redis.set(_key(job.id), _dumps(job), ex=self._ttl)

    async def get(self, job_id: str) -> Job:
        raw = await self._redis.get(_key(job_id))
        if raw is None:
            raise JobNotFoundError(f"Job '{job_id}' not found.")
        return _loads(raw)

    async def update(self, job: Job) -> None:
        payload = _dumps(job)
        # SET ... XX writes only if the key exists, giving us the "missing job"
        # check (and TTL refresh) in a single round-trip.
        stored = await self._redis.set(_key(job.id), payload, ex=self._ttl, xx=True)
        if not stored:
            raise JobNotFoundError(f"Job '{job.id}' not found.")
        await self._redis.publish(_channel(job.id), payload)

    async def subscribe(self, job_id: str) -> AsyncIterator[Job]:
        pubsub = self._redis.pubsub()
        # Subscribe BEFORE reading current state so an update published between
        # the read and the subscribe can't be lost.
        await pubsub.subscribe(_channel(job_id))
        try:
            raw = await self._redis.get(_key(job_id))
            if raw is None:
                raise JobNotFoundError(f"Job '{job_id}' not found.")
            current = _loads(raw)
            yield current
            if current.is_terminal:
                return

            while True:
                # Finite timeout so the await is cleanly cancellable (the SSE
                # router cancels + aclose()s this generator); a message arriving
                # returns immediately, the timeout just re-checks the loop.
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message is None or message.get("type") != "message":
                    continue
                job = _loads(message["data"])
                # Drop anything not newer than what we've already emitted; this
                # de-dups the snapshot vs. an update that raced the subscribe.
                if job.updated_at < current.updated_at:
                    continue
                current = job
                yield job
                if job.is_terminal:
                    return
        finally:
            await pubsub.unsubscribe(_channel(job_id))
            await pubsub.aclose()
