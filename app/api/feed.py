"""
feed.py — Real-time intelligence feed via Server-Sent Events (SSE)
────────────────────────────────────────────────────────────────────
GET /api/feed/stream   — SSE stream; frontend connects once and receives
                         events pushed by admin uploads in real time.
GET /api/feed/recent   — REST fallback: returns last 10 events as JSON.
"""
import asyncio
import json
import logging
import time

from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse

from app.feed_store import get_recent_events, subscribe, unsubscribe

logger = logging.getLogger(__name__)
router = APIRouter()


# ── SSE stream ────────────────────────────────────────────────────────────────

@router.get("/stream")
async def feed_stream():
    """
    Server-Sent Events endpoint.
    - Immediately flushes the last 10 stored events so the client renders
      something before any new upload happens.
    - Then blocks, waiting for new events pushed from admin uploads.
    - Sends a heartbeat comment every 25 s to keep the connection alive
      through proxies and load balancers.
    """
    async def event_generator():
        # 1. Flush existing events (newest first, already sorted by feed_store)
        for ev in get_recent_events(10):
            yield f"data: {json.dumps(ev)}\n\n"

        # 2. Subscribe and stream future events
        q = subscribe()
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=25.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat keeps the TCP connection alive
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            unsubscribe(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",       # disable nginx buffering
            "Connection": "keep-alive",
        },
    )


# ── REST fallback ─────────────────────────────────────────────────────────────

@router.get("/recent")
async def feed_recent(n: int = 10):
    """Returns the last n feed events as JSON (for initial page load / polling)."""
    return JSONResponse(content=get_recent_events(n))
