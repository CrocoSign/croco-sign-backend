"""A stub translator used for development and tests.

It performs no real inference; it returns deterministic, video-derived English text
so the end-to-end async flow can be exercised. Real models implement the same
`PJMTranslator` port and drop into the registry unchanged.
"""

from __future__ import annotations

import hashlib


class MockPJMTranslator:
    """Implements the PJMTranslator port with canned English output."""

    def translate(self, video: bytes) -> str:
        # Derive a short, stable signature from the input so callers can see the
        # request actually influenced the (fake) output.
        digest = hashlib.sha256(video).hexdigest()[:8]
        return f"Hello, this is a sample translation. [{digest}]"
