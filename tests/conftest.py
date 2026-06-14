"""Shared test fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from croco_sign.domain.models import Language, SpokenTranslationInput
from croco_sign.main import create_app


class MockSpokenLanguageTranslator:
    """Deterministic SpokenLanguageTranslator double for tests.

    Returns the input text unchanged for English and a clearly marked
    transformation otherwise, so the spoken-translation stage is observable.
    """

    def translate(self, input: SpokenTranslationInput) -> str:
        if input.target_language == Language.ENGLISH:
            return input.text
        return f"[{input.target_language.value}] {input.text}"


@pytest.fixture
def client() -> TestClient:
    # TestClient runs lifespan (composition root) on enter/exit. eager_processing
    # uses the in-memory store + in-process execution (no Redis/arq), so jobs
    # complete within the request like the old BackgroundTasks path. Inject a mock
    # spoken translator so no real model is loaded.
    app = create_app(
        spoken_translator=MockSpokenLanguageTranslator(),
        eager_processing=True,
    )
    with TestClient(app) as test_client:
        yield test_client
