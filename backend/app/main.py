"""Aetherix FastAPI application entry point.

Architecture constraints:
- ALL HTTP exceptions are formatted as RFC 7807 Problem Details (Story 1.1).
- ALL business logic lives in app/services/, not in routes.
- OpenAPI schema is served at /api/openapi.json for the typed client generator.
[Source: architecture.md#Process-Patterns, architecture.md#Architectural-Boundaries]
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.core.error_handlers import problem_details_handler
from app.api.routes import pms, webhooks, auth, dashboard, predictions, reports
from app.api.routes import anomalies, notifications
from app.db.models import Base
from app.db.session import engine
from app.workers.anomaly_scan import register_anomaly_scan_job
from app.workers.dispatch_worker import register_dispatch_job

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Aetherix API",
    description="Aetherix F&B Operations Agent backend",
    version="0.1.0",
    # AC #3 & #5: OpenAPI schema at /api/openapi.json; Swagger UI at /docs
    openapi_url="/api/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ... (middleware and exception handlers)
app.add_exception_handler(HTTPException, problem_details_handler)

# APScheduler instance — shared across all registered cron jobs
_scheduler = AsyncIOScheduler()


@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        # Create tables
        await conn.run_sync(Base.metadata.create_all)

    # Register background cron jobs
    register_anomaly_scan_job(_scheduler)
    register_dispatch_job(_scheduler)  # Story 4.2: dispatch alerts every 2 minutes
    _scheduler.start()
    logger.info("APScheduler started with %d jobs", len(_scheduler.get_jobs()))


@app.on_event("shutdown")
async def on_shutdown():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")


# Include routers
app.include_router(pms.router, prefix="/api/v1")
app.include_router(predictions.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(anomalies.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Health check — used by Docker Compose healthcheck and CI
# ---------------------------------------------------------------------------
@app.get("/health", tags=["ops"])
async def health_check():
    """Returns 200 OK when the service is up."""
    return {"status": "ok"}
