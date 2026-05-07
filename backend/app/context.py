"""Request-scoped context variables shared across the application.

Set by ``AgentTrackingMiddleware`` at the start of each request.
Read by LLM providers to include ``request_id`` in structured log lines.
"""
from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
