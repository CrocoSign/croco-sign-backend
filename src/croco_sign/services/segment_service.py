"""Application service for browsing segments and their video clips."""

from __future__ import annotations

from croco_sign.domain.models import (
    Segment,
    SegmentFacets,
    SegmentFilters,
    SegmentPage,
)
from croco_sign.domain.ports import SegmentRepository, SegmentVideoSource


class SegmentService:
    """Orchestrates the segment catalog (SQLite) and clip source (dataset)."""

    def __init__(
        self, repository: SegmentRepository, video_source: SegmentVideoSource
    ) -> None:
        self._repository = repository
        self._video_source = video_source

    async def list_segments(
        self, limit: int, offset: int, filters: SegmentFilters
    ) -> SegmentPage:
        return await self._repository.list(limit, offset, filters)

    async def list_filter_facets(self) -> SegmentFacets:
        return await self._repository.facets()

    async def get_segment(self, id: int) -> Segment:
        return await self._repository.get_by_id(id)

    async def get_segment_video(self, id: int) -> bytes:
        # Resolve the PK first: gives a clean 404 for a bad id before touching the
        # slow video source, and maps the integer id to the textual segment_id.
        segment = await self._repository.get_by_id(id)
        return await self._video_source.get_video(segment.segment_id)
