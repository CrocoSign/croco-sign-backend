"""API-side reader for uploaded videos.

Translation runs in a separate worker, so the upload is no longer staged to local
disk. The API streams the upload into memory under a size guard and hands the
bytes to a shared `VideoStore` (see `video_store.py`); the worker reads them there.
"""

from __future__ import annotations

from typing import Protocol

from croco_sign.domain.exceptions import PayloadTooLargeError

_CHUNK_SIZE = 1024 * 1024  # 1 MiB


class UploadLike(Protocol):
    """Minimal interface of Starlette's UploadFile that we depend on."""

    async def read(self, size: int = -1) -> bytes:
        ...


class VideoStorage:
    """Reads an upload into memory, enforcing a streamed size limit."""

    def __init__(self, max_bytes: int) -> None:
        self._max_bytes = max_bytes

    async def read_with_limit(self, upload: UploadLike) -> bytes:
        """Stream the upload into memory, enforcing the size limit.

        Raises PayloadTooLargeError if the limit is exceeded.
        """
        buffer = bytearray()
        while True:
            chunk = await upload.read(_CHUNK_SIZE)
            if not chunk:
                break
            buffer.extend(chunk)
            if len(buffer) > self._max_bytes:
                raise PayloadTooLargeError(
                    f"Upload exceeds the maximum allowed size of {self._max_bytes} bytes."
                )
        return bytes(buffer)
