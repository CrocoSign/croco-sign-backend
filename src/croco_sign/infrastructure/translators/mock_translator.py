"""A stub translator used for development and tests.

It performs no real inference; it returns deterministic, video-derived text so the
end-to-end async flow can be exercised. Real models implement the same
`PJMTranslator` port and drop into the registry unchanged.
"""

from __future__ import annotations

import hashlib

from croco_sign.domain.models import Language, TranslationResult


class MockPJMTranslator:
    """Implements the PJMTranslator port with canned output."""

    def translate(self, video: bytes, target_language: Language) -> TranslationResult:
        # Derive a short, stable signature from the input so callers can see the
        # request actually influenced the (fake) output.
        digest = hashlib.sha256(video).hexdigest()[:8]
        phrases = {
            Language.POLISH: "Witaj, to jest przykładowe tłumaczenie.",
            Language.ENGLISH: "Hello, this is a sample translation.",
            Language.GERMAN: "Hallo, dies ist eine Beispielübersetzung.",
        }
        text = f"{phrases.get(target_language, phrases[Language.ENGLISH])} [{digest}]"
        return TranslationResult(
            text=text,
            target_language=target_language,
            confidence=0.99,
        )
