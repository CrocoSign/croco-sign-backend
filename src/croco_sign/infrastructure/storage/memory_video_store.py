"""In-memory VideoStore for single-process runs and tests.

Mirrors RedisVideoStore semantics without a broker, so the eager (test) path and
local single-process runs can hand video bytes to processing in-process.
"""

from __future__ import annotations

from croco_sign.domain.exceptions import VideoNotFoundError


class InMemoryVideoStore:
    """Implements the VideoStore port using a dict."""

    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes) -> None:
        self._blobs[key] = data

    async def get(self, key: str) -> bytes:
        try:
            return self._blobs[key]
        except KeyError as exc:
            raise VideoNotFoundError(f"Video for '{key}' not found.") from exc

    async def remove(self, key: str) -> None:
        self._blobs.pop(key, None)
