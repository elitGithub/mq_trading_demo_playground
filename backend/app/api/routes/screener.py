"""Screener API routes — scan MT5 symbols against filters."""

import json

from fastapi import APIRouter, Query
from starlette.responses import StreamingResponse

from app.services.screener_service import screener_service

router = APIRouter(prefix="/screener", tags=["screener"])


@router.get("/scan")
async def scan(
    price_min: float | None = Query(default=None),
    price_max: float | None = Query(default=None),
    volume_min: float | None = Query(default=None),
    range_min: float | None = Query(default=None),
    range_max: float | None = Query(default=None),
    lookback_days: float | None = Query(default=None),
    visible_only: bool | None = Query(default=None),
):
    """Scan tradeable symbols. Query params override YAML defaults."""
    data = await screener_service.scan(
        visible_only=visible_only,
        price_min=price_min,
        price_max=price_max,
        volume_min=volume_min,
        range_min=range_min,
        range_max=range_max,
        lookback_days=lookback_days,
    )
    return {
        "results": data["results"],
        "count": len(data["results"]),
        "scanned": data["scanned"],
        "errors": data["errors"],
    }


@router.get("/scan/stream")
async def scan_stream(
    price_min: float | None = Query(default=None),
    price_max: float | None = Query(default=None),
    volume_min: float | None = Query(default=None),
    range_min: float | None = Query(default=None),
    range_max: float | None = Query(default=None),
    lookback_days: float | None = Query(default=None),
    visible_only: bool | None = Query(default=None),
):
    """SSE stream of scan progress. Sends 'progress' events per batch, then 'done'."""

    async def event_generator():
        async for event in screener_service.scan_stream(
            visible_only=visible_only,
            price_min=price_min,
            price_max=price_max,
            volume_min=volume_min,
            range_min=range_min,
            range_max=range_max,
            lookback_days=lookback_days,
        ):
            yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
        # Signal end of stream
        yield "event: close\ndata: {}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Transfer-Encoding": "chunked",
        },
    )


@router.get("/defaults")
async def defaults():
    """Return current YAML defaults so the frontend can pre-populate filters."""
    return screener_service.get_defaults()
