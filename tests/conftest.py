"""Shared test fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from croco_sign.main import create_app


@pytest.fixture
def client() -> TestClient:
    # TestClient runs lifespan (composition root) on enter/exit.
    with TestClient(create_app()) as test_client:
        yield test_client
