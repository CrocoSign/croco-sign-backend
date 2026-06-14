"""End-to-end tests for the metrics matrix and experiment detail endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import KNOWN_ARCH_BYTES


def test_get_metrics_returns_matrix(metrics_client: TestClient) -> None:
    response = metrics_client.get("/metrics")
    assert response.status_code == 200
    body = response.json()

    # Metric columns, ordered by id.
    assert [m["name"] for m in body["metrics"]] == ["BLEU-4", "ROUGE-L"]
    assert body["metrics"][0]["description"]  # descriptions are exposed

    # One row per experiment, grouped/ordered by model then experiment id.
    experiments = body["experiments"]
    assert len(experiments) == 2
    first = experiments[0]
    assert first["model"]["display_name"] == "SpaMo"
    assert first["transfer_source"] == "PHOENIX"
    assert first["split"] == "MS"
    assert first["scores"] == {"BLEU-4": 5.54, "ROUGE-L": 19.66}


def test_get_experiment_detail(metrics_client: TestClient) -> None:
    response = metrics_client.get("/experiments/1")
    assert response.status_code == 200
    body = response.json()

    assert body["id"] == 1
    assert body["transfer_source"] == "PHOENIX"
    assert body["split"] == "MS"
    assert body["model"]["display_name"] == "SpaMo"

    scores = body["scores"]
    assert [s["metric"]["name"] for s in scores] == ["BLEU-4", "ROUGE-L"]
    assert scores[0]["value"] == 5.54
    # Each score carries the metric description.
    assert scores[0]["metric"]["description"]


def test_get_experiment_not_found(metrics_client: TestClient) -> None:
    response = metrics_client.get("/experiments/999")
    assert response.status_code == 404
    assert response.json()["code"] == "experiment_not_found"


def test_get_architecture_image(metrics_client: TestClient) -> None:
    response = metrics_client.get("/experiments/1/architecture")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/")
    assert response.content == KNOWN_ARCH_BYTES


def test_get_architecture_image_missing_file_is_404(metrics_client: TestClient) -> None:
    # Experiment 2's model points at a figure that was never written to disk.
    response = metrics_client.get("/experiments/2/architecture")
    assert response.status_code == 404
    assert response.json()["code"] == "experiment_not_found"
