"""Routes for browsing segments and streaming their video clips."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from croco_sign.api.dependencies import get_segment_service
from croco_sign.api.schemas import (
    SegmentDetailResponse,
    SegmentFacetsResponse,
    SegmentPageResponse,
)
from croco_sign.domain.models import SegmentFilters
from croco_sign.services.segment_service import SegmentService

router = APIRouter(tags=["segments"])


@router.get("/segments", response_model=SegmentPageResponse)
async def list_segments(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    age: list[str] | None = Query(None),
    sex: list[str] | None = Query(None),
    speaker_id: list[str] | None = Query(None),
    sentence: str | None = Query(None, description="Case-insensitive substring search."),
    service: SegmentService = Depends(get_segment_service),
) -> SegmentPageResponse:
    # age/sex/speaker_id are repeatable query params (?sex=F&sex=M) — multi-select.
    filters = SegmentFilters(
        ages=tuple(age or ()),
        sexes=tuple(sex or ()),
        speaker_ids=tuple(speaker_id or ()),
        sentence=sentence,
    )
    page = await service.list_segments(limit, offset, filters)
    return SegmentPageResponse.from_domain(page)


# Declared before "/segments/{id}" so the literal "filters" isn't matched (and
# rejected) by the int path converter.
@router.get("/segments/filters", response_model=SegmentFacetsResponse)
async def get_segment_filters(
    service: SegmentService = Depends(get_segment_service),
) -> SegmentFacetsResponse:
    facets = await service.list_filter_facets()
    return SegmentFacetsResponse.from_domain(facets)


@router.get("/segments/{id}", response_model=SegmentDetailResponse)
async def get_segment(
    id: int,
    service: SegmentService = Depends(get_segment_service),
) -> SegmentDetailResponse:
    segment = await service.get_segment(id)
    return SegmentDetailResponse.from_domain(segment)


@router.get("/segments/{id}/video")
async def get_segment_video(
    id: int,
    service: SegmentService = Depends(get_segment_service),
) -> Response:
    data = await service.get_segment_video(id)
    # Clips are short single-sentence mp4s, so the whole buffer is returned at
    # once; a <video> element plays it directly. Range support is unnecessary.
    return Response(
        content=data,
        media_type="video/mp4",
        headers={
            "Content-Disposition": "inline",
            "Cache-Control": "public, max-age=3600",
            "Accept-Ranges": "none",
        },
    )
