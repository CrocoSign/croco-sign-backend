"""Temporary storage for uploaded videos.

The upload must be persisted during the request because translation runs in a
background task after the HTTP response has been sent (the request's spooled file
is no longer available by then).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Protocol

from croco_sign.domain.exceptions import PayloadTooLargeError

_CHUNK_SIZE = 1024 * 1024  # 1 MiB


class UploadLike(Protocol):
    """Minimal interface of Starlette's UploadFile that we depend on."""

    async def read(self, size: int = -1) -> bytes:
        ...


class VideoStorage:
    """Saves uploads to temp files with a streamed size guard."""

    def __init__(self, max_bytes: int) -> None:
        self._max_bytes = max_bytes

    async def save(self, upload: UploadLike, suffix: str = ".video") -> Path:
        """Stream the upload to a temp file, enforcing the size limit.

        Raises PayloadTooLargeError if the limit is exceeded.
        """
        fd, name = tempfile.mkstemp(prefix="croco-", suffix=suffix)
        path = Path(name)
        written = 0
        try:
            with os.fdopen(fd, "wb") as out:
                while True:
                    chunk = await upload.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > self._max_bytes:
                        raise PayloadTooLargeError(
                            f"Upload exceeds the maximum allowed size of {self._max_bytes} bytes."
                        )
                    out.write(chunk)
        except BaseException:
            self.remove(path)
            raise
        return path

    @staticmethod
    def read_bytes(path: Path) -> bytes:
        return path.read_bytes()

    @staticmethod
    def remove(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
