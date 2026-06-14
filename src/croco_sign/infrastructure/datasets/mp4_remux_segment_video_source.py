"""SegmentVideoSource decorator that remuxes MPEG-TS clips to MP4.

The pjm-segments dataset stores each clip as an MPEG-TS stream (H.264 video)
even though the WebDataset column is named `mp4`. Browsers cannot play MPEG-TS
in a `<video>` element, so we losslessly remux to a faststart MP4 here — a
container change only (`-c copy`, no re-encode), so it is fast and quality-
preserving. Wrapping happens *below* the Redis cache in the composition root, so
each clip is remuxed at most once and the cached/served bytes are real MP4.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path

from croco_sign.domain.exceptions import SegmentVideoProcessingError
from croco_sign.domain.ports import SegmentVideoSource

logger = logging.getLogger(__name__)


class Mp4RemuxingSegmentVideoSource:
    """SegmentVideoSource decorator: remux MPEG-TS clips to faststart MP4."""

    def __init__(self, source: SegmentVideoSource) -> None:
        self._source = source

    async def get_video(self, segment_id: str) -> bytes:
        raw = await self._source.get_video(segment_id)
        return await asyncio.to_thread(self._remux, raw, segment_id)

    @staticmethod
    def _remux(data: bytes, segment_id: str) -> bytes:
        # Read TS from stdin; write MP4 to a seekable temp file so +faststart can
        # relocate the moov atom to the front for progressive playback.
        with tempfile.NamedTemporaryFile(suffix=".mp4") as out:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-i",
                    "pipe:0",
                    "-c",
                    "copy",
                    "-movflags",
                    "+faststart",
                    out.name,
                ],
                input=data,
                capture_output=True,
            )
            if result.returncode != 0:
                detail = result.stderr.decode("utf-8", "replace").strip()
                logger.error("ffmpeg remux failed for segment %s: %s", segment_id, detail)
                raise SegmentVideoProcessingError(
                    f"Could not prepare the video clip for segment '{segment_id}'."
                )
            return Path(out.name).read_bytes()
