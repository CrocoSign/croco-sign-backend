"""Unit tests for RedisJobStore using fakeredis (no live Redis required)."""

from __future__ import annotations

import asyncio

import pytest
from fakeredis import FakeAsyncRedis

from croco_sign.domain.exceptions import JobNotFoundError
from croco_sign.domain.models import Job, Language, TranslationResult
from croco_sign.infrastructure.storage.redis_job_store import RedisJobStore, _key


@pytest.fixture
def redis() -> FakeAsyncRedis:
    return FakeAsyncRedis()


@pytest.fixture
def store(redis: FakeAsyncRedis) -> RedisJobStore:
    return RedisJobStore(redis, ttl_seconds=3600)


def _job(job_id: str = "job-1", target: Language = Language.POLISH) -> Job:
    return Job(id=job_id, model_name="mock", target_language=target)


async def test_create_and_get_round_trip(store: RedisJobStore) -> None:
    job = _job()
    job.mark_succeeded(
        TranslationResult(text="cześć", target_language=Language.POLISH, model_name="mock")
    )
    await store.create(job)

    loaded = await store.get(job.id)
    assert loaded.id == job.id
    assert loaded.model_name == "mock"
    assert loaded.target_language is Language.POLISH  # enum fidelity
    assert loaded.status is job.status
    assert loaded.result is not None
    assert loaded.result.text == "cześć"
    assert loaded.result.target_language is Language.POLISH
    assert loaded.created_at == job.created_at  # datetime fidelity (tz-aware)
    assert loaded.updated_at == job.updated_at


async def test_get_missing_raises(store: RedisJobStore) -> None:
    with pytest.raises(JobNotFoundError):
        await store.get("nope")


async def test_update_missing_raises(store: RedisJobStore) -> None:
    with pytest.raises(JobNotFoundError):
        await store.update(_job("ghost"))


async def test_update_persists_new_state(store: RedisJobStore) -> None:
    job = _job()
    await store.create(job)
    job.mark_running()
    await store.update(job)

    loaded = await store.get(job.id)
    assert loaded.status.value == "running"


async def test_create_sets_ttl(store: RedisJobStore, redis: FakeAsyncRedis) -> None:
    job = _job()
    await store.create(job)
    ttl = await redis.ttl(_key(job.id))
    assert 0 < ttl <= 3600


async def test_subscribe_yields_current_then_updates_until_terminal(
    store: RedisJobStore,
) -> None:
    job = _job()
    await store.create(job)

    received = []
    sub = store.subscribe(job.id)

    async def drive() -> None:
        # Let subscribe register, then push two updates.
        await asyncio.sleep(0.05)
        job.mark_running()
        await store.update(job)
        await asyncio.sleep(0.05)
        job.mark_succeeded(
            TranslationResult(text="done", target_language=Language.POLISH, model_name="mock")
        )
        await store.update(job)

    driver = asyncio.create_task(drive())
    async for emitted in sub:
        received.append(emitted.status.value)
        if emitted.is_terminal:
            break
    await driver

    assert received == ["pending", "running", "succeeded"]


async def test_subscribe_returns_immediately_for_terminal_job(
    store: RedisJobStore,
) -> None:
    job = _job()
    job.mark_failed("boom")
    await store.create(job)

    received = [emitted.status.value async for emitted in store.subscribe(job.id)]
    assert received == ["failed"]


async def test_subscribe_missing_raises(store: RedisJobStore) -> None:
    with pytest.raises(JobNotFoundError):
        async for _ in store.subscribe("nope"):
            pass
