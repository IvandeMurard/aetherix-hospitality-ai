"""
F&B Operations Agent — FastAPI

Two execution paths, selected automatically:
  · Claude MCP  (ANTHROPIC_API_KEY set)   — full LLM reasoning via MCP tools
  · Heuristic   (no keys needed)          — rule-based, always works

Endpoints:
  GET  /              → redirect to /docs
  GET  /health        → service + key status
  POST /predict       → demand forecast for a date / location
  POST /predict/quick → same but heuristic-only (faster, no LLM)
"""

import asyncio
import os
import re
from datetime import datetime, timedelta
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator

load_dotenv()

app = FastAPI(
    title="F&B Operations Agent",
    description=(
        "AI-powered demand forecasting for hotel Food & Beverage operations. "
        "Combines PMS data, local events, weather, and historical patterns "
        "to produce actionable staffing and procurement recommendations."
    ),
    version="2.0.0",
)

DATE_FMT = "%Y-%m-%d"


# ── Models ────────────────────────────────────────────────────────────────────

class PredictRequest(BaseModel):
    date: str = Field(
        default_factory=lambda: (datetime.now() + timedelta(days=1)).strftime(DATE_FMT),
        example="2025-12-24",
        description="Target date (YYYY-MM-DD). Defaults to tomorrow.",
    )
    location: str = Field(
        default="Paris, France",
        example="Paris, France",
        description="Hotel location — used for local events lookup.",
        max_length=120,
    )
    city: str = Field(
        default="Paris",
        example="Paris",
        description="City name — used for weather lookup.",
        max_length=60,
    )

    @field_validator("date")
    @classmethod
    def _validate_date(cls, v: str) -> str:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise ValueError("date must be YYYY-MM-DD")
        try:
            datetime.strptime(v, DATE_FMT)
        except ValueError:
            raise ValueError(f"Invalid calendar date: {v!r}")
        return v

    @field_validator("location", "city")
    @classmethod
    def _validate_text(cls, v: str) -> str:
        # Only allow printable characters; no control chars or injection payloads
        if not re.fullmatch(r"[\w ,.\-]+", v):
            raise ValueError(f"Invalid characters in field: {v!r}")
        return v


class PredictResponse(BaseModel):
    date: str
    location: str
    expected_covers: int
    recommended_staff: int
    confidence: int
    key_factors: List[str]
    operational_recommendations: List[str]
    method: str


class HealthResponse(BaseModel):
    status: str
    active_path: str
    keys: dict
    mcp_servers: dict


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health", response_model=HealthResponse, tags=["System"])
def health():
    """Service health — shows active path and credential status."""
    from mcp_servers.registry import get_available_systems

    has_claude = bool(os.getenv("ANTHROPIC_API_KEY"))
    has_mistral = bool(os.getenv("MISTRAL_API_KEY"))

    if has_claude:
        path = "claude_mcp"
    elif has_mistral:
        path = "mistral_direct"
    else:
        path = "heuristic"

    return HealthResponse(
        status="ok",
        active_path=path,
        keys={
            "ANTHROPIC_API_KEY": "set" if has_claude else "not set",
            "MISTRAL_API_KEY": "set" if has_mistral else "not set",
            "QDRANT_URL": "set" if os.getenv("QDRANT_URL") else "not set",
            "APALEO_CLIENT_ID": "set" if os.getenv("APALEO_CLIENT_ID") else "not set",
            "PREDICTHQ_API_KEY": "set" if os.getenv("PREDICTHQ_API_KEY") else "not set",
            "OPENWEATHER_API_KEY": "set" if os.getenv("OPENWEATHER_API_KEY") else "not set",
        },
        mcp_servers=get_available_systems(),
    )


# ── Predict (unified) ─────────────────────────────────────────────────────────

@app.post("/predict", response_model=PredictResponse, tags=["Forecast"])
async def predict(req: PredictRequest):
    """
    Demand forecast for a given date and location.

    - When **ANTHROPIC_API_KEY** is set: uses Claude + MCP tools for rich
      reasoning over PMS data, local events, weather, and historical patterns.
    - Otherwise: runs the heuristic pipeline (mock data, zero keys needed).
    """
    has_claude = bool(os.getenv("ANTHROPIC_API_KEY"))

    if has_claude:
        result = await _run_mcp(req.date, req.location, req.city)
    else:
        result = _run_heuristic(req.date, req.location, req.city)

    return PredictResponse(
        date=req.date,
        location=req.location,
        expected_covers=int(result["expected_covers"]),
        recommended_staff=int(result["recommended_staff"]),
        confidence=int(result["confidence"]),
        key_factors=result.get("key_factors", []),
        operational_recommendations=result.get("operational_recommendations", []),
        method=result.get("method", "unknown"),
    )


@app.post("/predict/quick", response_model=PredictResponse, tags=["Forecast"])
def predict_quick(req: PredictRequest):
    """
    Heuristic-only forecast — always fast, no LLM, no API keys required.
    Use when you need a sub-second response or when Claude is unavailable.
    """
    try:
        datetime.strptime(req.date, DATE_FMT)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid date format: {req.date!r}. Use YYYY-MM-DD.")

    result = _run_heuristic(req.date, req.location, req.city)
    return PredictResponse(
        date=req.date,
        location=req.location,
        expected_covers=int(result["expected_covers"]),
        recommended_staff=int(result["recommended_staff"]),
        confidence=int(result["confidence"]),
        key_factors=result.get("key_factors", []),
        operational_recommendations=result.get("operational_recommendations", []),
        method=result.get("method", "heuristic"),
    )


# ── Execution paths ───────────────────────────────────────────────────────────

def _run_heuristic(date: str, location: str, city: str) -> dict:
    """Call the heuristic pipeline from run_scenario directly."""
    from run_scenario import (
        step_reservations,
        step_fb_context,
        step_comment_signals,
        step_events,
        step_weather,
        step_patterns,
        _heuristic_predict,
    )
    from datetime import datetime as dt

    reservations = step_reservations(date)
    fb_context = step_fb_context(date)
    comment_signals = step_comment_signals(date)
    events = step_events(date, location)
    weather = step_weather(city)

    event_desc = (
        f"{'weekend' if dt.strptime(date, DATE_FMT).weekday() >= 4 else 'weekday'} "
        + (events[0]["title"] if events else "business day")
    )
    patterns = step_patterns(event_desc)

    return _heuristic_predict(
        date=date,
        reservations=reservations,
        fb_context=fb_context,
        events=events,
        weather=weather,
        patterns=patterns,
        comment_signals=comment_signals,
    )


async def _run_mcp(date: str, location: str, city: str) -> dict:
    """Run the Claude MCP agent and parse its output into a dict."""
    from mcp_agent import run_hotel_mcp_agent

    raw: str = await run_hotel_mcp_agent(date, location, city)

    import re

    def _extract_int(pattern: str, text: str, default: int) -> int:
        m = re.search(pattern, text, re.IGNORECASE)
        return int(m.group(1).replace(",", "")) if m else default

    covers = _extract_int(r"expected covers[:\s]*(\d[\d,]*)", raw, 0)
    staff = _extract_int(r"recommended staff[:\s]*(\d+)", raw, 0)
    confidence_str = re.search(r"confidence[:\s]*(\d+)\s*%?", raw, re.IGNORECASE)
    confidence = int(confidence_str.group(1)) if confidence_str else 75

    factors = re.findall(r"[·•\-\*]\s+(.+)", raw)

    reco_match = re.search(
        r"operational recommendations[:\s]*\n(.*?)(?:\n\n|\Z)",
        raw, re.IGNORECASE | re.DOTALL
    )
    recommendations = []
    if reco_match:
        recommendations = [
            l.strip().lstrip("→·•-* ")
            for l in reco_match.group(1).split("\n")
            if l.strip()
        ]

    return {
        "expected_covers": covers if covers > 0 else 80,
        "recommended_staff": staff if staff > 0 else 5,
        "confidence": confidence,
        "key_factors": factors[:5] if factors else ["See full Claude analysis"],
        "operational_recommendations": recommendations[:5] if recommendations else [],
        "raw_analysis": raw,
        "method": "claude_mcp",
    }
