"""HuggingFace WebDataset-backed SegmentVideoSource.

Locating one segment's clip means streaming the dataset and filtering by
`__key__`, which is an O(n) scan across tar shards — slow. The composition root
wraps this in a Redis read-through cache so the cost is paid once per clip. The
blocking iteration is offloaded to a worker thread via `asyncio.to_thread`.
"""

from __future__ import annotations

import asyncio

from datasets import Value, load_dataset

from croco_sign.domain.exceptions import SegmentVideoNotFoundError


class HuggingFaceSegmentVideoSource:
    """Implements SegmentVideoSource by scanning the streamed WebDataset."""

    def __init__(self, repo_id: str, split: str = "train") -> None:
        self._repo_id = repo_id
        self._split = split

    async def get_video(self, segment_id: str) -> bytes:
        return await asyncio.to_thread(self._scan_for_video, segment_id)

    def _scan_for_video(self, segment_id: str) -> bytes:
        ds = load_dataset(self._repo_id, split=self._split, streaming=True)
        # Cast the video column to raw bytes so frames are never decoded — we only
        # need to hand the mp4 through to the client.
        ds = ds.cast_column("mp4", Value("binary"))
        for record in ds:
            if record["__key__"] == segment_id:
                return record["mp4"]["bytes"]
        raise SegmentVideoNotFoundError(
            f"No video clip for segment '{segment_id}' in dataset."
        )
