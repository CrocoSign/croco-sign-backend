"""Redis-backed VideoStore: hands uploaded bytes from the API to the worker.

Storing the whole upload in Redis is a deliberate simplicity trade-off — it
reuses the broker we already run, works across hosts, and the bytes are
short-lived (the worker deletes them once read). At the 100 MiB upload cap a value
fits comfortably under Redis's 512 MiB string limit. When uploads grow, swap this
for an S3/MinIO adapter behind the `VideoStore` port.
"""

from __future__ import annotations

from redis.asyncio import Redis

from croco_sign.domain.exceptions import VideoNotFoundError

_KEY_PREFIX = "croco:video:"


def _key(key: str) -> str:
    return f"{_KEY_PREFIX}{key}"


class RedisVideoStore:
    """Implements the VideoStore port using Redis string values with a TTL."""

    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    async def put(self, key: str, data: bytes) -> None:
        await self._redis.set(_key(key), data, ex=self._ttl)

    async def get(self, key: str) -> bytes:
        data = await self._redis.get(_key(key))
        if data is None:
            raise VideoNotFoundError(f"Video for '{key}' not found (expired or never stored).")
        return data

    async def remove(self, key: str) -> None:
        await self._redis.delete(_key(key))
