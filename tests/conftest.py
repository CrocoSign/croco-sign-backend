"""Shared test fixtures."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from croco_sign.core.config import get_settings
from croco_sign.domain.exceptions import SegmentVideoNotFoundError
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


# --- Segments fixtures ------------------------------------------------------

# The one segment_id for which a clip "exists"; the seeded DB also has a second
# segment with no clip so the video 404 path is exercisable.
KNOWN_SEGMENT_ID = "004_000_M"
KNOWN_SEGMENT_VIDEO = b"\x00\x00fake-mp4-bytes"


class FakeSegmentVideoSource:
    """SegmentVideoSource double — returns fixed bytes, no HuggingFace access."""

    def __init__(self) -> None:
        self.calls = 0

    async def get_video(self, segment_id: str) -> bytes:
        self.calls += 1
        if segment_id == KNOWN_SEGMENT_ID:
            return KNOWN_SEGMENT_VIDEO
        raise SegmentVideoNotFoundError(f"No video for '{segment_id}'.")


def _seed_segments_db(db_path: Path) -> None:
    """Create the three catalog tables and a tiny, hermetic dataset."""
    con = sqlite3.connect(db_path)
    con.executescript(
        """
        CREATE TABLE signer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            speaker_id TEXT NOT NULL UNIQUE,
            sex TEXT NOT NULL,
            age TEXT NOT NULL,
            special_case TEXT NOT NULL
        );
        CREATE TABLE video_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL UNIQUE,
            video_url TEXT NOT NULL,
            subtitles_url TEXT NOT NULL,
            video_type TEXT NOT NULL,
            task_id INTEGER NOT NULL,
            speaker_side TEXT NOT NULL,
            signer_id INTEGER NOT NULL REFERENCES signer(id)
        );
        CREATE TABLE segment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            segment_id TEXT NOT NULL UNIQUE,
            sentence TEXT NOT NULL,
            video_metadata_id INTEGER NOT NULL REFERENCES video_metadata(id)
        );
        """
    )
    with con:
        con.execute(
            "INSERT INTO signer (id, speaker_id, sex, age, special_case) "
            "VALUES (1, 'F_46-60_001', 'F', '46-60', '-')"
        )
        con.execute(
            "INSERT INTO video_metadata "
            "(id, video_id, video_url, subtitles_url, video_type, task_id, speaker_side, signer_id) "
            "VALUES (1, 4, 'http://v/4.mp4', 'http://v/4.vtt', 'monolog;film', 8, '-', 1)"
        )
        con.execute(
            "INSERT INTO segment (id, segment_id, sentence, video_metadata_id) "
            "VALUES (1, '004_000_M', 'Wiesz, kot i ptak.', 1)"
        )
        con.execute(
            "INSERT INTO segment (id, segment_id, sentence, video_metadata_id) "
            "VALUES (2, '004_001_M', 'Druga sentencja.', 1)"
        )
    con.close()


@pytest.fixture
def fake_video_source() -> FakeSegmentVideoSource:
    return FakeSegmentVideoSource()


@pytest.fixture
def segments_client(
    tmp_path: Path, fake_video_source: FakeSegmentVideoSource
) -> TestClient:
    db_path = tmp_path / "segments.db"
    _seed_segments_db(db_path)
    # Reuse cached settings (deepl_key etc. from env) but point at the temp DB.
    settings = get_settings().model_copy(update={"sqlite_db_path": str(db_path)})
    app = create_app(
        settings=settings,
        spoken_translator=MockSpokenLanguageTranslator(),
        segment_video_source=fake_video_source,
        eager_processing=True,
    )
    with TestClient(app) as test_client:
        yield test_client
