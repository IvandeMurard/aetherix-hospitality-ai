"""Logfire observability — concretises ADR-0003 (HOS-311).

Design invariants:
- **Zero-config safety**: without ``LOGFIRE_TOKEN`` nothing is sent anywhere
  (``send_to_logfire="if-token-present"``) and without ``configure_observability()``
  every helper below is a strict no-op — CI, unit tests and local dev need no
  setup and produce no warnings.
- **Never on the failure path**: instrumentation errors are swallowed and
  logged at WARNING; a broken exporter must not break a forecast or a reply.

What it provides:
- ``configure_observability(app)`` — FastAPI request traces + Anthropic client
  instrumentation (tokens in/out per LLM call → cost per recommendation, AC4).
- ``span(name, **attrs)`` — manual spans for the forecast pipeline and
  WhatsApp sends (AC2).
- ``guardrail_trip(...)`` — one structured event per typed guardrail trip
  (AC3), mirroring the ``agent_action_log`` rows (invariant NFR2, ADR-0009).
"""
from __future__ import annotations

import logging
import os
from contextlib import nullcontext

logger = logging.getLogger(__name__)

try:
    import logfire
except ImportError:  # pragma: no cover — dependency is in pyproject
    logfire = None  # type: ignore[assignment]

# Set only by configure_observability(); keeps every helper inert in unit
# tests that import instrumented services without booting the app.
_enabled = False


def configure_observability(app=None) -> bool:
    """Configure Logfire. Returns True when a token is present (data flows)."""
    global _enabled
    if logfire is None:
        logger.info("observability: logfire not installed — disabled")
        return False

    try:
        logfire.configure(
            service_name="aetherix-backend",
            send_to_logfire="if-token-present",
            environment=os.getenv("AETHERIX_ENV", "staging" if os.getenv("FLY_APP_NAME") else "dev"),
            console=False,
        )
        # AC4 — patches the anthropic client: every completion carries
        # model, input/output tokens and latency.
        logfire.instrument_anthropic()
        if app is not None:
            logfire.instrument_fastapi(app, capture_headers=False)
        _enabled = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("observability: logfire setup failed (non-fatal): %s", exc)
        return False

    has_token = bool(os.getenv("LOGFIRE_TOKEN"))
    logger.info(
        "observability: logfire configured (export=%s)",
        "on" if has_token else "off — no LOGFIRE_TOKEN",
    )
    return has_token


def span(name: str, **attributes):
    """Manual span context manager; ``nullcontext`` when disabled."""
    if not _enabled or logfire is None:
        return nullcontext()
    try:
        return logfire.span(name, **attributes)
    except Exception:  # noqa: BLE001
        return nullcontext()


def guardrail_trip(guardrail: str, hotel_id: str, reason: str, detail: str = "") -> None:
    """AC3 — structured event for a typed guardrail trip (NFR2)."""
    if not _enabled or logfire is None:
        return
    try:
        logfire.warn(
            "guardrail trip: {guardrail} [{reason}]",
            guardrail=guardrail,
            reason=reason,
            hotel_id=hotel_id or "_system",
            detail=detail,
        )
    except Exception:  # noqa: BLE001
        logger.debug("observability: guardrail event failed", exc_info=True)
