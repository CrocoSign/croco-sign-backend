"""Routes for polling and subscribing to translation job status and results."""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from croco_sign.api.dependencies import get_translation_service
from croco_sign.api.schemas import JobStatusResponse
from croco_sign.services.translation_service import TranslationService

router = APIRouter(tags=["jobs"])

# Send a comment line if no update arrives within this window: keeps the
# connection alive through proxies and lets us notice client disconnects.
_HEARTBEAT_SECONDS = 15.0


@router.get("/jobs/{job_id}", response_model=JobStatusResponse, name="get_job")
async def get_job(
    job_id: str,
    service: TranslationService = Depends(get_translation_service),
) -> JobStatusResponse:
    job = await service.get_job(job_id)
    return JobStatusResponse.from_domain(job)


@router.get("/jobs/{job_id}/events", name="job_events")
async def job_events(
    job_id: str,
    request: Request,
    service: TranslationService = Depends(get_translation_service),
) -> StreamingResponse:
    # Validate up front so a missing job returns 404 before the stream opens.
    await service.get_job(job_id)

    async def event_stream() -> AsyncIterator[str]:
        updates = service.stream_job(job_id).__aiter__()
        # Pull the next update in its own task. asyncio.wait() with a timeout
        # leaves a pending task untouched, so the subscription survives across
        # heartbeats. (asyncio.wait_for would cancel it, tearing down the
        # underlying generator and unsubscribing it from the job store.)
        next_update = asyncio.ensure_future(updates.__anext__())
        try:
            while True:
                done, _ = await asyncio.wait(
                    {next_update}, timeout=_HEARTBEAT_SECONDS
                )
                if not done:
                    if await request.is_disconnected():
                        break
                    yield ": keep-alive\n\n"
                    continue

                try:
                    job = next_update.result()
                except StopAsyncIteration:
                    break

                # Schedule the next pull before yielding so no update is missed.
                next_update = asyncio.ensure_future(updates.__anext__())

                payload = JobStatusResponse.from_domain(job).model_dump_json()
                yield f"data: {payload}\n\n"
                if job.is_terminal:
                    break
        finally:
            next_update.cancel()
            await updates.aclose()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
