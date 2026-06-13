"""Tests for the SSE subscription endpoint and CORS."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient


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


def test_sse_unknown_job_returns_404(client: TestClient) -> None:
    resp = client.get("/jobs/nope/events")
    assert resp.status_code == 404
    assert resp.json()["code"] == "job_not_found"


def test_cors_headers_present(client: TestClient) -> None:
    resp = client.get("/models", headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "*"
