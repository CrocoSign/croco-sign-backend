"""Redis read-through cache for segment video clips.

Decorates a slow `SegmentVideoSource` (the HuggingFace stream scan) so each clip
is fetched at most once per TTL window. Implements the same port, so the service
is unaware caching exists; in eager/test mode the bare source is used instead.

A future shard/byte-offset index could replace the inner source behind this same
decorator for O(1) ranged reads, with no service or API changes.
"""

from __future__ import annotations

from redis.asyncio import Redis

from croco_sign.domain.ports import SegmentVideoSource

_KEY_PREFIX = "croco:segvid:"


def _key(segment_id: str) -> str:
    return f"{_KEY_PREFIX}{segment_id}"


class RedisSegmentVideoCache:
    """SegmentVideoSource decorator: read-through Redis cache over a slow source."""

    def __init__(
        self, redis: Redis, source: SegmentVideoSource, ttl_seconds: int
    ) -> None:
        self._redis = redis
        self._source = source
        self._ttl = ttl_seconds

    async def get_video(self, segment_id: str) -> bytes:
        cached = await self._redis.get(_key(segment_id))
        if cached is not None:
            return cached
        data = await self._source.get_video(segment_id)
        await self._redis.set(_key(segment_id), data, ex=self._ttl)
        return data
