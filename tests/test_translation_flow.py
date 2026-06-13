"""End-to-end test of the async translation flow."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _submit(client: TestClient, model: str = "mock", target_language: str = "en"):
    return client.post(
        f"/models/{model}/translate",
        files={"video": ("clip.mp4", b"fake-video-bytes", "video/mp4")},
        data={"target_language": target_language},
    )


def test_list_models_includes_mock(client: TestClient) -> None:
    resp = client.get("/models")
    assert resp.status_code == 200
    names = {m["name"] for m in resp.json()}
    assert "mock" in names


def test_submit_and_poll_until_succeeded(client: TestClient) -> None:
    submit = _submit(client, target_language="en")
    assert submit.status_code == 202
    body = submit.json()
    job_id = body["job_id"]
    assert body["status"] == "pending"
    assert job_id in body["status_url"]

    # Background task runs synchronously under TestClient, so the job is done.
    poll = client.get(f"/jobs/{job_id}")
    assert poll.status_code == 200
    job = poll.json()
    assert job["status"] == "succeeded"
    assert job["model_name"] == "mock"
    assert job["target_language"] == "en"
    assert job["result"]["text"]
    assert job["result"]["target_language"] == "en"


def test_default_target_language_is_polish(client: TestClient) -> None:
    resp = client.post(
        "/models/mock/translate",
        files={"video": ("clip.mp4", b"abc", "video/mp4")},
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]
    job = client.get(f"/jobs/{job_id}").json()
    assert job["target_language"] == "pl"
