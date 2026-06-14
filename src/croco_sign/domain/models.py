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

@dataclass
class SpokenTranslationInput:
    target_language: Language
    text: str


@dataclass(frozen=True)
class Signer:
    """A person who produced sign-language recordings."""

    id: int
    speaker_id: str
    sex: str
    age: str
    special_case: str


@dataclass(frozen=True)
class VideoMetadata:
    """Metadata for a source corpus recording, with its signer composed in."""

    id: int
    video_id: int
    video_url: str
    subtitles_url: str
    video_type: str
    task_id: int
    speaker_side: str
    signer: Signer


@dataclass(frozen=True)
class Segment:
    """A single sentence-level clip cut from a recording.

    The full aggregate used by the detail view: it nests the recording metadata,
    which in turn nests the signer. `segment_id` is the WebDataset `__key__`.
    """

    id: int
    segment_id: str
    sentence: str
    video_metadata: VideoMetadata


@dataclass(frozen=True)
class SegmentSummary:
    """Lightweight list projection — only the columns the list query selects."""

    id: int
    segment_id: str
    sentence: str
    age: str
    sex: str
    speaker_id: str


@dataclass(frozen=True)
class SegmentFilters:
    """Optional narrowing criteria for the segment list.

    `ages`, `sexes` and `speaker_ids` are multi-select: a non-empty tuple matches
    any of its values (SQL `IN`). `sentence` is a case-insensitive substring
    search. Empty tuples / `None` mean "no filtering on that field". Tuples (not
    lists) so the dataclass stays frozen/hashable.
    """

    ages: tuple[str, ...] = ()
    sexes: tuple[str, ...] = ()
    speaker_ids: tuple[str, ...] = ()
    sentence: str | None = None


@dataclass(frozen=True)
class SegmentFacets:
    """The distinct values available for each dropdown filter on the list."""

    ages: list[str]
    sexes: list[str]
    speaker_ids: list[str]


@dataclass(frozen=True)
class SegmentPage:
    """A page of segment summaries plus the total matching the active filters."""

    items: list[SegmentSummary]
    total: int


# --- Benchmark metrics ------------------------------------------------------
# A small read-only catalog of model evaluation experiments and their scores,
# built offline from metrics.md (see scripts/metrics_to_sqlite.py). Named
# `BenchmarkModel` to avoid clashing with the translation registry's `ModelInfo`.


@dataclass(frozen=True)
class BenchmarkModel:
    """A translation architecture that was evaluated (e.g. SpaMo, Uni-Sign)."""

    id: int
    display_name: str
    architecture_fig: str  # path to the architecture diagram, relative to resources base


@dataclass(frozen=True)
class MetricDefinition:
    """An evaluation metric (e.g. BLEU-4) with a human-readable description."""

    id: int
    name: str
    description: str


@dataclass(frozen=True)
class ExperimentScore:
    """One metric's value for a single experiment, with the metric definition."""

    metric: MetricDefinition
    value: float


@dataclass(frozen=True)
class Experiment:
    """The detail aggregate for one evaluation run: a model under a setup, scored.

    `transfer_source` is the pretraining/transfer dataset (or "brak …" for none)
    and `split` is the evaluation split (e.g. MS / SI).
    """

    id: int
    transfer_source: str
    split: str
    model: BenchmarkModel
    scores: list[ExperimentScore]


@dataclass(frozen=True)
class ExperimentRow:
    """A row in the metrics matrix: one experiment with its scores keyed by name.

    `scores` maps metric name -> value, so the list view can look up cells by the
    ordered column names carried in `MetricsTable.metrics`.
    """

    id: int
    model: BenchmarkModel
    transfer_source: str
    split: str
    scores: dict[str, float]


@dataclass(frozen=True)
class MetricsTable:
    """The full benchmark matrix: the metric columns plus one row per experiment."""

    metrics: list[MetricDefinition]
    experiments: list[ExperimentRow]
