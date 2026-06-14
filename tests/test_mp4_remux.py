"""Tests for the MPEG-TS -> MP4 remuxing video source decorator."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from croco_sign.domain.exceptions import SegmentVideoProcessingError
from croco_sign.infrastructure.datasets.mp4_remux_segment_video_source import (
    Mp4RemuxingSegmentVideoSource,
)

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)


def _make_ts_clip() -> bytes:
    """Generate a tiny, valid H.264 MPEG-TS clip with ffmpeg."""
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=1:size=160x120:rate=10",
            "-c:v",
            "libx264",
            "-f",
            "mpegts",
            "pipe:1",
        ],
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    return result.stdout


class _StaticSource:
    def __init__(self, data: bytes) -> None:
        self._data = data

    async def get_video(self, segment_id: str) -> bytes:
        return self._data


@pytest.mark.asyncio
async def test_remux_ts_to_mp4_produces_faststart_mp4() -> None:
    ts = _make_ts_clip()
    assert ts[0] == 0x47  # MPEG-TS sync byte

    source = Mp4RemuxingSegmentVideoSource(_StaticSource(ts))
    out = await source.get_video("seg")

    # Real MP4: starts with an `ftyp` box, and faststart moves `moov` to the front.
    assert out[4:8] == b"ftyp"
    head = out[:4096]
    assert b"moov" in head


@pytest.mark.asyncio
async def test_remux_rejects_garbage_input() -> None:
    source = Mp4RemuxingSegmentVideoSource(_StaticSource(b"not a video"))
    with pytest.raises(SegmentVideoProcessingError):
        await source.get_video("seg")
