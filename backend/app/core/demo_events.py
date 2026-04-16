"""Demo observability — shared broadcast state for the SSE pipeline diagram.

Architecture note
-----------------
This module is intentionally placed in ``app/core/`` (not ``app/api/routes/``)
so that service-layer files (prediction_engine, reasoning_service, etc.) can
import ``demo_emit`` without creating routes→services circular imports.

``app/api/routes/demo.py`` reads ``_subscribers`` to fan-out events to SSE
clients. Service files call ``asyncio.create_task(demo_emit("stage"))`` — fire-
and-forget, never blocking the main pipeline.

DEMO_MODE=false
---------------
``demo_emit()`` is a no-op. No queue is created, no event is emitted.
``/demo/stream`` still exists but returns HTTP 503 (see routes/demo.py).
"""
from __future__ import annotations

import asyncio

from app.core.config import DEMO_MODE

# Module-level list of subscriber queues — one per connected SSE client.
# Mutated only from the event loop (append on connect, remove on disconnect).
_subscribers: list[asyncio.Queue[str]] = []


async def demo_emit(stage: str) -> None:
    """Broadcast a pipeline stage event to all connected SSE clients.

    Emits two SSE data lines per call:
      1. ``{stage}``       — node turns blue (in-progress)
      2. ``{stage}_done``  — node turns green (done)

    A 400 ms gap between the two events gives the SVG animation time to render.

    Call sites must use fire-and-forget pattern::

        asyncio.create_task(demo_emit("mcp_probe"))

    Never ``await demo_emit(...)`` directly — that would block the pipeline if
    an SSE subscriber queue is full or a client is slow.
    """
    if not DEMO_MODE:
        return
    if not _subscribers:
        return

    # In-progress event
    for q in _subscribers:
        await q.put(stage)

    # Brief pause so the browser renders the blue→green transition
    await asyncio.sleep(0.4)

    # Done event
    for q in _subscribers:
        await q.put(f"{stage}_done")
