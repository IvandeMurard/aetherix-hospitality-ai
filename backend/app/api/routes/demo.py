"""Demo observability — SSE endpoint for the Loom pipeline board.

GET /demo/stream
----------------
Server-Sent Events stream.  Each connected browser tab (demo_board.html)
subscribes by opening this endpoint.  The pipeline emits stage names via
``demo_emit()`` (app/core/demo_events.py); this route fans them out.

DEMO_MODE=false
---------------
The route is always registered in main.py (no conditional import), but
returns HTTP 503 with a JSON body when DEMO_MODE is off.  This avoids
import-time env reads and keeps the router predictable in tests.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.core.config import DEMO_MODE
from app.core.demo_events import _subscribers

logger = logging.getLogger(__name__)

router = APIRouter(tags=["demo"])


@router.get("/demo/stream", summary="SSE stream for demo_board.html")
async def demo_stream(request: Request):
    """Subscribe to pipeline stage events via Server-Sent Events.

    Returns HTTP 503 when ``DEMO_MODE=false``.

    Each event is a plain ``data:`` line::

        data: mcp_probe\\n\\n
        data: mcp_probe_done\\n\\n
        data: pms_sync\\n\\n
        ...

    The demo_board.html EventSource listener calls ``highlight(stage, state)``
    on each received event.
    """
    if not DEMO_MODE:
        return JSONResponse(
            {"status": "demo_mode_disabled", "detail": "Set DEMO_MODE=true to enable the demo board."},
            status_code=503,
        )

    queue: asyncio.Queue[str] = asyncio.Queue()
    _subscribers.append(queue)
    logger.debug("Demo SSE client connected (%d total)", len(_subscribers))

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    stage = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {stage}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive comment to prevent proxy/browser timeouts
                    yield ": keepalive\n\n"
        finally:
            try:
                _subscribers.remove(queue)
            except ValueError:
                pass
            logger.debug("Demo SSE client disconnected (%d remaining)", len(_subscribers))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
