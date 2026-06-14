"""Routes for browsing segments and streaming their video clips."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from croco_sign.api.dependencies import get_segment_service
from croco_sign.api.schemas import SegmentDetailResponse, SegmentPageResponse
from croco_sign.services.segment_service import SegmentService

router = APIRouter(tags=["segments"])


@router.get("/segments", response_model=SegmentPageResponse)
async def list_segments(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: SegmentService = Depends(get_segment_service),
) -> SegmentPageResponse:
    page = await service.list_segments(limit, offset)
    return SegmentPageResponse.from_domain(page)


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
