"""Tests for the SSE subscription endpoint and CORS."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from croco_sign.api.routers import jobs as jobs_router
from croco_sign.domain.models import Language, TranslationResult
from croco_sign.main import create_app


def _submit(client: TestClient) -> str:
    resp = client.post(
        "/models/mock/translate",
        files={"video": ("clip.mp4", b"fake-video-bytes", "video/mp4")},
        data={"target_language": "en"},
    )
    assert resp.status_code == 202
    return resp.json()["job_id"]


def test_sse_streams_until_succeeded(client: TestClient) -> None:
    job_id = _submit(client)
    events: list[dict] = []
    with client.stream("GET", f"/jobs/{job_id}/events") as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        for line in resp.iter_lines():
            if line.startswith("data:"):
                event = json.loads(line[len("data:"):].strip())
                events.append(event)
                if event["status"] in ("succeeded", "failed"):
                    break

    assert events, "expected at least one SSE data event"
    assert events[-1]["status"] == "succeeded"
    assert events[-1]["result"]["text"]


async def test_sse_survives_heartbeat_for_slow_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Regression: a job still running when a heartbeat fires must keep its stream
    # and still deliver the terminal event. Previously the heartbeat cancelled
    # the subscription (asyncio.wait_for), tearing down the stream mid-job — only
    # the slow PL path stayed running long enough to hit it. TestClient can't
    # reproduce this (it runs background tasks to completion before returning),
    # so we drive the job lifecycle directly while streaming over ASGI.
    monkeypatch.setattr(jobs_router, "_HEARTBEAT_SECONDS", 0.1)

    app = create_app(eager_processing=True)
    async with app.router.lifespan_context(app):
        service = app.state.translation_service
        job = await service.submit("mock", Language.POLISH)

        async def finish_after_heartbeat() -> None:
            await asyncio.sleep(0.3)  # outlast the 0.1s heartbeat window
            current = await service.get_job(job.id)
            current.mark_succeeded(
                TranslationResult(
                    text="[pl] done",
                    target_language=Language.POLISH,
                    model_name="mock",
                )
            )
            await service._job_store.update(current)

        finisher = asyncio.create_task(finish_after_heartbeat())
        events: list[dict] = []
        saw_keep_alive = False
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            async with client.stream("GET", f"/jobs/{job.id}/events") as stream:
                assert stream.status_code == 200
                async for line in stream.aiter_lines():
                    if line.startswith(":"):
                        saw_keep_alive = True
                    elif line.startswith("data:"):
                        event = json.loads(line[len("data:"):].strip())
                        events.append(event)
                        if event["status"] in ("succeeded", "failed"):
                            break
        await finisher

    assert saw_keep_alive, "expected a keep-alive while the slow job was running"
    assert events[-1]["status"] == "succeeded"


def test_sse_unknown_job_returns_404(client: TestClient) -> None:
    resp = client.get("/jobs/nope/events")
    assert resp.status_code == 404
    assert resp.json()["code"] == "job_not_found"


def test_cors_headers_present(client: TestClient) -> None:
    resp = client.get("/models", headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "*"
