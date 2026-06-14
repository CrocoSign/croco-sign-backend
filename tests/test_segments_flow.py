"""End-to-end tests for the segment browsing API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import KNOWN_SEGMENT_VIDEO


def test_list_segments_returns_summaries_and_total(segments_client: TestClient) -> None:
    resp = segments_client.get("/segments")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    first = body["items"][0]
    assert set(first) == {"id", "segment_id", "sentence", "age", "sex"}
    assert first["segment_id"] == "004_000_M"
    assert first["age"] == "46-60"
    assert first["sex"] == "F"


def test_list_segments_paginates_with_limit_and_offset(
    segments_client: TestClient,
) -> None:
    page = segments_client.get("/segments", params={"limit": 1, "offset": 1}).json()
    assert page["total"] == 2  # total is unfiltered
    assert len(page["items"]) == 1
    assert page["items"][0]["id"] == 2


def test_get_segment_returns_full_nested_aggregate(segments_client: TestClient) -> None:
    body = segments_client.get("/segments/1").json()
    assert body["id"] == 1
    assert body["segment_id"] == "004_000_M"
    assert body["sentence"] == "Wiesz, kot i ptak."
    vm = body["video_metadata"]
    assert vm["video_id"] == 4
    assert vm["video_type"] == "monolog;film"
    assert vm["signer"]["speaker_id"] == "F_46-60_001"
    assert vm["signer"]["age"] == "46-60"


def test_get_unknown_segment_is_404(segments_client: TestClient) -> None:
    resp = segments_client.get("/segments/999999")
    assert resp.status_code == 404
    assert resp.json()["code"] == "segment_not_found"


def test_get_segment_video_returns_mp4_bytes(segments_client: TestClient) -> None:
    resp = segments_client.get("/segments/1/video")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "video/mp4"
    assert resp.content == KNOWN_SEGMENT_VIDEO


def test_get_segment_video_missing_clip_is_404(segments_client: TestClient) -> None:
    # Segment 2 exists in the catalog but has no clip in the (fake) source.
    resp = segments_client.get("/segments/2/video")
    assert resp.status_code == 404
    assert resp.json()["code"] == "segment_video_not_found"


def test_get_segment_video_unknown_segment_is_404(segments_client: TestClient) -> None:
    # Bad PK should 404 on the catalog lookup before touching the video source.
    resp = segments_client.get("/segments/999999/video")
    assert resp.status_code == 404
    assert resp.json()["code"] == "segment_not_found"


@pytest.mark.asyncio
async def test_redis_cache_reads_through_once() -> None:
    """The Redis cache should hit the inner source only on a miss."""
    fakeredis = pytest.importorskip("fakeredis")
    from croco_sign.infrastructure.cache.redis_segment_video_cache import (
        RedisSegmentVideoCache,
    )

    class CountingSource:
        def __init__(self) -> None:
            self.calls = 0

        async def get_video(self, segment_id: str) -> bytes:
            self.calls += 1
            return b"clip"

    redis = fakeredis.aioredis.FakeRedis()
    source = CountingSource()
    cache = RedisSegmentVideoCache(redis, source, ttl_seconds=60)

    assert await cache.get_video("k") == b"clip"
    assert await cache.get_video("k") == b"clip"
    assert source.calls == 1  # second call served from cache
    await redis.aclose()
