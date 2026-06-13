"""Core domain models. Pure Python, no framework imports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Language(str, Enum):
    """Spoken-language output targets."""

    POLISH = "pl"
    ENGLISH = "en"
    GERMAN = "de"

    @classmethod
    def from_code(cls, code: str) -> "Language":
        """Resolve a language code (case-insensitive), raising ValueError if unknown."""
        try:
            return cls(code.lower())
        except ValueError as exc:
            supported = ", ".join(lang.value for lang in cls)
            raise ValueError(
                f"Unsupported target language '{code}'. Supported: {supported}."
            ) from exc


class JobStatus(str, Enum):
    """Lifecycle of an asynchronous translation job."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class ModelInfo:
    """Descriptor for a registered translation model."""

    name: str


@dataclass(frozen=True)
class TranslationResult:
    """Output of a successful translation.

    `model_name` is stamped by the service from the registered name; translators
    do not know the name they are registered under.
    """

    text: str
    target_language: Language
    confidence: float | None = None
    model_name: str = ""


@dataclass
class Job:
    """An asynchronous translation job tracked through its lifecycle."""

    id: str
    model_name: str
    target_language: Language
    status: JobStatus = JobStatus.PENDING
    result: TranslationResult | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    @property
    def is_terminal(self) -> bool:
        return self.status in (JobStatus.SUCCEEDED, JobStatus.FAILED)

    def mark_running(self) -> None:
        self.status = JobStatus.RUNNING
        self.updated_at = _utcnow()

    def mark_succeeded(self, result: TranslationResult) -> None:
        self.status = JobStatus.SUCCEEDED
        self.result = result
        self.updated_at = _utcnow()

    def mark_failed(self, error: str) -> None:
        self.status = JobStatus.FAILED
        self.error = error
        self.updated_at = _utcnow()
