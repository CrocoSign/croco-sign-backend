"""A passthrough spoken-language translator.

Implements the `SpokenLanguageTranslator` port by returning the input text
unchanged. Useful as a placeholder when no real translation is desired.
"""

from __future__ import annotations

from croco_sign.domain.models import SpokenTranslationInput


class NoopSpokenLanguageTranslator:
    """Implements the SpokenLanguageTranslator port as a no-op passthrough."""

    def translate(self, input: SpokenTranslationInput) -> str:
        return input.text
