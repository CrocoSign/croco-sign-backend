"""Domain exceptions. The API layer maps these to HTTP responses."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain-level errors."""

    code: str = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ModelNotFoundError(DomainError):
    """Requested translation model is not registered."""

    code = "model_not_found"


class JobNotFoundError(DomainError):
    """Requested job id does not exist."""

    code = "job_not_found"


class UnsupportedMediaError(DomainError):
    """Uploaded file is not an accepted video type."""

    code = "unsupported_media"


class InvalidLanguageError(DomainError):
    """Requested target language is not supported."""

    code = "invalid_language"


class PayloadTooLargeError(DomainError):
    """Uploaded file exceeds the configured size limit."""

    code = "payload_too_large"


class TranslationFailedError(DomainError):
    """The translator failed to produce a result."""

    code = "translation_failed"


class VideoNotFoundError(DomainError):
    """Stored video bytes are missing (never stored, or expired)."""

    code = "video_not_found"


class SegmentNotFoundError(DomainError):
    """Requested segment id does not exist in the catalog."""

    code = "segment_not_found"


class SegmentVideoNotFoundError(DomainError):
    """No video clip for the requested segment exists in the dataset."""

    code = "segment_video_not_found"


class SegmentVideoProcessingError(DomainError):
    """A segment clip was found but could not be transcoded for delivery."""

    code = "segment_video_processing_error"


class ExperimentNotFoundError(DomainError):
    """Requested experiment id does not exist in the metrics catalog."""

    code = "experiment_not_found"
