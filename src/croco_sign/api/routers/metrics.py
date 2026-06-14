"""Routes for the benchmark metrics matrix and per-experiment detail."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from croco_sign.api.dependencies import get_metrics_service
from croco_sign.api.schemas import (
    ExperimentDetailResponse,
    MetricsTableResponse,
)
from croco_sign.services.metrics_service import MetricsService

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_model=MetricsTableResponse)
async def get_metrics(
    service: MetricsService = Depends(get_metrics_service),
) -> MetricsTableResponse:
    table = await service.list_metrics_table()
    return MetricsTableResponse.from_domain(table)


@router.get("/experiments/{id}", response_model=ExperimentDetailResponse)
async def get_experiment(
    id: int,
    service: MetricsService = Depends(get_metrics_service),
) -> ExperimentDetailResponse:
    experiment = await service.get_experiment(id)
    return ExperimentDetailResponse.from_domain(experiment)


@router.get("/experiments/{id}/architecture")
async def get_experiment_architecture(
    id: int,
    service: MetricsService = Depends(get_metrics_service),
) -> Response:
    data, media_type = await service.get_architecture_image(id)
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Content-Disposition": "inline",
            "Cache-Control": "public, max-age=3600",
        },
    )
