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


CROCO_ENDPOINT = "http://100.117.203.112:8000/translate"

# Every model exposed by the unified croco service (GET /models). The registry
# key is the model's canonical name, which is also what the service expects.
CROCO_MODELS = (
    "spamo-pjm-phoenix-ms",
    "spamo-pjm-phoenix-si",
    "spamo-pjm-scratch-ms",
    "spamo-pjm-scratch-si",
    "mod-spamo-pjm-phoenix-ms",
    "mod-spamo-pjm-phoenix-si",
    "mod-spamo-pjm-scratch-ms",
    "mod-spamo-pjm-scratch-si",
    "unisign-pjm-cslnews-ms",
    "unisign-pjm-cslnews-si",
    "unisign-pjm-how2sign-ms",
    "unisign-pjm-how2sign-si",
    "unisign-pjm-openasl-ms",
    "unisign-pjm-openasl-si",
    "unisign-pjm-scratch-ms",
    "unisign-pjm-scratch-si",
)

def build_default_registry() -> TranslatorRegistry:
    """Create the registry with all translators wired up."""
    registry = TranslatorRegistry()
    registry.register("mock", MockPJMTranslator())
    for model_name in CROCO_MODELS:
        registry.register(
            model_name,
            UnifiedCrocoTranslator(model_name=model_name, endpoint=CROCO_ENDPOINT),
        )

    return registry
