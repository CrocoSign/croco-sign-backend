"""Registry mapping model names to translator implementations (Strategy pattern)."""

from __future__ import annotations

from croco_sign.domain.exceptions import ModelNotFoundError
from croco_sign.domain.models import ModelInfo
from croco_sign.domain.ports import PJMTranslator
from croco_sign.infrastructure.translators.mock_translator import MockPJMTranslator
from croco_sign.infrastructure.translators.unified import UnifiedCrocoTranslator


class TranslatorRegistry:
    """Holds the available translators, keyed by their `name`."""

    def __init__(self) -> None:
        self._translators: dict[str, PJMTranslator] = {}

    def register(self, name: str, translator: PJMTranslator) -> None:
        self._translators[name] = translator

    def get(self, model_name: str) -> PJMTranslator:
        try:
            return self._translators[model_name]
        except KeyError as exc:
            available = ", ".join(sorted(self._translators)) or "(none)"
            raise ModelNotFoundError(
                f"Unknown model '{model_name}'. Available models: {available}."
            ) from exc

    def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(name=name) for name in self._translators]


def build_default_registry() -> TranslatorRegistry:
    """Create the registry with all translators wired up."""
    registry = TranslatorRegistry()
    registry.register("mock", MockPJMTranslator())
    registry.register("uni-sign-si", UnifiedCrocoTranslator(model_name="unisign-pjm-openasl-si", endpoint="http://100.117.203.112:8000/translate"))
    registry.register("uni-sign-ms", UnifiedCrocoTranslator(model_name="unisign-pjm-openasl-ms", endpoint="http://100.117.203.112:8000/translate"))
    registry.register("spamo-si", UnifiedCrocoTranslator(model_name="spamo-pjm-phoenix-si", endpoint="http://100.117.203.112:8000/translate"))
    registry.register("ddd", UnifiedCrocoTranslator(model_name="dsdsd", endpoint="http://100.117.203.112:8000/translate"))
    return registry
