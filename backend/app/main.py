"""Aetherix FastAPI application entry point.

Architecture constraints:
- ALL HTTP exceptions are formatted as RFC 7807 Problem Details (Story 1.1).
- ALL business logic lives in app/services/, not in routes.
- OpenAPI schema is served at /api/openapi.json for the typed client generator.
[Source: architecture.md#Process-Patterns, architecture.md#Architectural-Boundaries]
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.core.error_handlers import problem_details_handler
from app.api.routes import pms, webhooks, auth, dashboard, predictions, reports, weather, baselines
from app.db.models import Base
from app.db.session import engine
from app.workers.weather_sync import start_weather_scheduler, stop_weather_scheduler

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

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        # Create tables
        await conn.run_sync(Base.metadata.create_all)
    start_weather_scheduler()


@app.on_event("shutdown")
async def on_shutdown():
    stop_weather_scheduler()

# Include routers
app.include_router(pms.router, prefix="/api/v1")
app.include_router(predictions.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(weather.router, prefix="/api/v1")
app.include_router(baselines.router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Health check — used by Docker Compose healthcheck and CI
# ---------------------------------------------------------------------------
@app.get("/health", tags=["ops"])
async def health_check():
    """Returns 200 OK when the service is up."""
    return {"status": "ok"}
