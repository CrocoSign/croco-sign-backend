"""Error-path tests for the API."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_unknown_model_returns_404(client: TestClient) -> None:
    resp = client.post(
        "/models/does-not-exist/translate",
        files={"video": ("clip.mp4", b"abc", "video/mp4")},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "model_not_found"


def test_unknown_job_returns_404(client: TestClient) -> None:
    resp = client.get("/jobs/nonexistent")
    assert resp.status_code == 404
    assert resp.json()["code"] == "job_not_found"


def test_unsupported_media_returns_415(client: TestClient) -> None:
    resp = client.post(
        "/models/mock/translate",
        files={"video": ("notes.txt", b"abc", "text/plain")},
    )
    assert resp.status_code == 415
    assert resp.json()["code"] == "unsupported_media"


def test_invalid_language_returns_422(client: TestClient) -> None:
    resp = client.post(
        "/models/mock/translate",
        files={"video": ("clip.mp4", b"abc", "video/mp4")},
        data={"target_language": "xx"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "invalid_language"
