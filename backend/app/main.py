"""Aetherix FastAPI application entry point.

Architecture constraints:
- ALL HTTP exceptions are formatted as RFC 7807 Problem Details (Story 1.1).
- ALL business logic lives in app/services/, not in routes.
- OpenAPI schema is served at /api/openapi.json for the typed client generator.
[Source: architecture.md#Process-Patterns, architecture.md#Architectural-Boundaries]
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    anomalies,
    auth,
    baselines,
    dashboard,
    demo,
    events,
    mcp_v1,
    notifications,
    pms,
    predictions,
    reports,
    roi,
    weather,
    webhooks,
    wellknown,
)
from app.api.routes import (
    kpi as kpi_route,
)
from app.api.routes import (
    receipts as receipts_route,
)
from app.api.routes import twilio_inbound as twilio_inbound_webhook
from app.core.error_handlers import problem_details_handler
from app.db.schema_check import verify_schema
from app.db.session import engine
from app.middleware.agent_tracking import AgentTrackingMiddleware
from app.providers.factory import get_embedding_provider, get_llm_provider
from app.services.aetherix_engine import AetherixEngine
from app.workers.agent_action_log_partition_rotation import (
    register_partition_rotation_job,
)
from app.workers.anomaly_scan import register_anomaly_scan_job
from app.workers.dispatch_worker import register_dispatch_job
from app.workers.error_rate_monitor import register_error_rate_monitor_job
from app.workers.event_sync import start_event_scheduler
from app.workers.retention_purge import register_retention_purge_job
from app.workers.heartbeat import register_heartbeat_monitor_job
from app.workers.kpi_aggregator import register_kpi_aggregator_job
from app.workers.latency_slo_worker import register_latency_slo_job
from app.workers.memory_metrics import register_memory_metrics_job
from app.workers.receipts_dispatcher import (
    register_receipt_dispatch_job,
    register_weekly_digest_job,
)
from app.workers.recap_dispatcher import register_weekly_recap_job
from app.workers.weather_sync import start_weather_scheduler

logger = logging.getLogger(__name__)

# APScheduler instance — shared across all registered cron jobs
_scheduler = AsyncIOScheduler()


def _validate_startup_env(env: "dict | None" = None) -> None:
    """Fail-fast checks for critical env vars (HOS-149 AC1 + AC7).

    Called once at lifespan startup — exits the process before any request
    is served if the environment is dangerously misconfigured.

    env: optional dict for hermetic unit tests; defaults to os.environ.
    """
    _env = env if env is not None else os.environ
    auth_secret = _env.get("AUTH_SECRET", "")
    if not auth_secret or auth_secret == "SECRET_CHANGE_ME" or len(auth_secret) < 32:
        raise SystemExit(
            "FATAL: AUTH_SECRET is missing, uses the placeholder 'SECRET_CHANGE_ME', "
            "or is shorter than 32 characters. "
            "Generate a secret with: "
            "python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    app_env = _env.get("APP_ENV", _env.get("ENV", ""))
    if app_env == "production" and _env.get(
        "TWILIO_SKIP_SIGNATURE_VALIDATION", "false"
    ).lower() == "true":
        raise SystemExit(
            "FATAL: TWILIO_SKIP_SIGNATURE_VALIDATION=true is forbidden in "
            "APP_ENV=production. Remove this variable before starting the server."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --------------- startup ---------------
    _validate_startup_env()

    # HOS-311 — Logfire traces (FastAPI + Anthropic tokens/cost). Runs before
    # provider singletons so the anthropic client class is patched first.
    # Strict no-op without LOGFIRE_TOKEN (CI/tests/dev need nothing).
    from app.core.observability import configure_observability

    configure_observability(app)

    # HOS-150 AC7 — verify migrations have been applied; refuse boot if any
    # critical table is missing. Replaces the old `Base.metadata.create_all`
    # path, which silently created divergent tables in fresh environments.
    await verify_schema(engine)

    # Decision #10: provider singletons — one instance for the entire process.
    # Services receive these via dependency injection rather than calling the
    # factory on every request.
    app.state.llm = get_llm_provider()
    app.state.embedding = get_embedding_provider()
    logger.info(
        "Providers initialised: llm=%s embedding=%s",
        app.state.llm.model_id,
        type(app.state.embedding).__name__,
    )

    # HOS-282 — fallback (Gemini) canary: fire-and-forget WARNING if the parachute
    # is down, so silent rot (expired key / quota / drift) is caught at deploy time
    # rather than during a real Claude outage. Only runs when a fallback key is
    # configured; never blocks or fails startup.
    _fallback_health = getattr(app.state.llm, "check_fallback_health", None)
    if callable(_fallback_health) and os.getenv("GEMINI_API_KEY"):
        asyncio.create_task(_fallback_health())

    # Decision #10 (HOS-157): AetherixEngine singleton — one instance per process.
    # Prophet CPU-bound methods run via asyncio.to_thread; engine shared across all routes.
    app.state.engine = AetherixEngine()
    logger.info("AetherixEngine initialised")

    # Register all background cron jobs on the single shared scheduler before starting it.
    register_anomaly_scan_job(_scheduler)
    register_dispatch_job(_scheduler)
    register_memory_metrics_job(_scheduler)
    # P3-3 — daily Trust-KPI aggregation at 02:30 UTC (after memory_metrics at 02:00).
    register_kpi_aggregator_job(_scheduler)
    # HOS-150 AC4 — keep agent_action_log monthly partitions ahead of `now()`.
    register_partition_rotation_job(_scheduler)
    # HOS-115 / Story 7.5 AC5 — première purge de rétention du système
    # (conversational_queries, 90 j). Voir docs/GDPR-DATA-INVENTORY.md §6.2.
    register_retention_purge_job(_scheduler)
    # HOS-156 — injected into the shared scheduler (no separate scheduler instances).
    start_weather_scheduler(_scheduler)
    start_event_scheduler(_scheduler)
    # P2-3 — daily Receipt dispatch at RECEIPT_DISPATCH_HOUR (default 18:00 UTC).
    register_receipt_dispatch_job(_scheduler)
    # P2-5 — weekly KPI digest every Sunday at RECEIPT_DISPATCH_HOUR.
    register_weekly_digest_job(_scheduler)
    # ADR-0007 §17.3 — opt-in weekly decision recap (Monday), 24 h rule respected.
    register_weekly_recap_job(_scheduler)
    # HOS-248 (Epic 12 G-1) — dead-man's switch over scheduled dispatchers.
    register_heartbeat_monitor_job(_scheduler)
    # HOS-249 (Epic 12 G-2) — rolling-window error-rate / LLM-timeout alerting.
    register_error_rate_monitor_job(_scheduler)
    # HOS-209 (EVAL-5) — nightly latency SLO MV refresh + p95 breach alert.
    register_latency_slo_job(_scheduler)
    _scheduler.start()
    logger.info("APScheduler started with %d jobs", len(_scheduler.get_jobs()))
    app.state.scheduler = _scheduler

    yield

    # --------------- shutdown ---------------
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")

    # Close providers that hold open HTTP connections (e.g. AsyncAnthropic).
    for provider in (app.state.llm, app.state.embedding):
        _close = getattr(provider, "aclose", None)
        if callable(_close):
            try:
                await _close()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Provider close error (non-fatal): %s", exc)

    # Close Redis rate-limit connection if opened
    try:
        from app.services.rate_limit import close as _close_rate_limit
        await _close_rate_limit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Rate-limit close error (non-fatal): %s", exc)


app = FastAPI(
    title="Aetherix API",
    description="Aetherix F&B Operations Agent backend",
    version="0.1.0",
    openapi_url="/api/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# P1-5: purely observational — logs agent calls and attaches X-Request-Id.
app.add_middleware(AgentTrackingMiddleware)
app.add_exception_handler(HTTPException, problem_details_handler)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(pms.router, prefix="/api/v1")
app.include_router(predictions.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(anomalies.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(weather.router, prefix="/api/v1")
app.include_router(baselines.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")
# P0-3 public ROI simulator — stateless, public, rate-limited at the edge
app.include_router(roi.router, prefix="/api/v1")
# P2-6 Receipt drill-down — MCP bearer + receipts:read scope (HOS-172)
app.include_router(receipts_route.router, prefix="/api/v1")
# P3-3 Trust-KPI — recommendation_acceptance_rate timeseries (HOS-177)
app.include_router(kpi_route.router, prefix="/api/v1")
# Aetherix MCP Server v1 — atomic tools (ADR-0004). v0 (/mcp/v0/) retired
# 2026-08-01 per its announced Sunset header (Décision #19, HOS-315).
app.include_router(mcp_v1.router)
# Demo observability board — always registered, returns 503 when DEMO_MODE=false
app.include_router(demo.router, prefix="/api/v1")
# Story 4.3 (HOS-26): public Twilio callback — no /api/v1 or auth prefix
app.include_router(twilio_inbound_webhook.router)
# P1-5 Agent SEO: discovery manifest — public, no auth, no prefix
app.include_router(wellknown.router)


# ---------------------------------------------------------------------------
# Health check — used by Docker Compose healthcheck and CI
# ---------------------------------------------------------------------------
@app.get("/health", tags=["ops"])
async def health_check():
    """Returns 200 OK when the service is up."""
    return {"status": "ok"}
