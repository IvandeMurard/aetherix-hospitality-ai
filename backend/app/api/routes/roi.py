"""Public ROI simulator — P0-3 (Phase 0 Definition of Done).

Exposes a **public** endpoint that lets a prospective hotelier input their own
property parameters and get a simulated savings projection grounded in the
P0-2 backtest KPIs (MAPE 7.8% h+1, directional accuracy 90.9%).

Design constraints:
- No auth (public funnel) — heavy rate-limiting at the edge (infra layer).
- Stateless — no DB writes, no side effects. Pure calculation.
- Disclaimers are first-class response fields — no silent assumptions.
- Distinct from `ROICalculatorService` (Story 3.3b) which scores internal
  anomalies per-hotel and requires DB access.
"""
from __future__ import annotations

from enum import Enum
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

router = APIRouter(prefix="/roi", tags=["roi"])


# ---------------------------------------------------------------------------
# Backtest-anchored constants (source: docs/metrics/backtest_2026-04-17.json)
# ---------------------------------------------------------------------------
# Synthetic data benchmark — not real-hotel validated. Keep conservative.
_MAPE_J1 = 0.078          # 7.8% in-sample MAPE on synthetic Paris 4*
_BASELINE_MAPE = 0.22     # Industry baseline manual planning (heuristic)
_FORECAST_LIFT = _BASELINE_MAPE - _MAPE_J1  # ~14pp improvement headroom

# Hospitality industry references (ADEME/Accor, public)
_FOOD_WASTE_BASELINE_PCT = 0.25   # ~25% gaspillage moyen
_FOOD_WASTE_REDUCTION_MIN = 0.15  # Conservative — -15% of current waste
_FOOD_WASTE_REDUCTION_MAX = 0.30  # Aspirational — -30% of current waste

# Labor cost variance target (CLAUDE.md KPI framework Niveau 2)
_LABOR_COST_REDUCTION_MIN = 0.03
_LABOR_COST_REDUCTION_MAX = 0.08


class PropertyType(str, Enum):
    city = "city"
    resort = "resort"
    airport = "airport"
    boutique = "boutique"


class ROISimulateRequest(BaseModel):
    """Inputs a prospective hotelier enters. All values are per-property."""

    rooms_count: int = Field(..., ge=5, le=2000, description="Total rooms in property")
    avg_cover_revenue_eur: float = Field(
        ..., ge=5, le=500,
        description="Average revenue per F&B cover (€)",
    )
    labor_cost_per_hour_eur: float = Field(
        ..., ge=8, le=80,
        description="Fully-loaded F&B labor cost (€/hour)",
    )
    food_cost_pct: float = Field(
        0.30, ge=0.10, le=0.60,
        description="Food cost as fraction of F&B revenue (0.30 = 30%)",
    )
    current_waste_pct: float = Field(
        _FOOD_WASTE_BASELINE_PCT, ge=0.0, le=0.80,
        description="Estimated share of prepped food wasted (0.25 = 25%)",
    )
    annual_fb_revenue_eur: float = Field(
        ..., ge=50_000, le=50_000_000,
        description="Annual F&B revenue (€) — dining, banquet, minibar combined",
    )
    property_type: PropertyType = Field(
        PropertyType.city,
        description="Property type — adjusts staffing volatility factor",
    )

    @field_validator("food_cost_pct", "current_waste_pct")
    @classmethod
    def _clamp_unit_interval(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class ROISavingsBreakdown(BaseModel):
    annual_eur: float
    low_eur: float
    high_eur: float
    assumption: str


class ROISimulateResponse(BaseModel):
    total_annual_savings_eur: float
    total_annual_savings_low_eur: float
    total_annual_savings_high_eur: float
    food_waste_reduction: ROISavingsBreakdown
    labor_cost_reduction: ROISavingsBreakdown
    forecast_accuracy_uplift: ROISavingsBreakdown
    assumptions: List[str]
    disclaimers: List[str]
    source_metrics: dict


def _property_type_factor(ptype: PropertyType) -> float:
    """Resort/airport properties have higher staffing volatility → more upside."""
    return {
        PropertyType.city: 1.00,
        PropertyType.boutique: 0.90,
        PropertyType.resort: 1.15,
        PropertyType.airport: 1.10,
    }[ptype]


def _range(mid: float, low_pct: float, high_pct: float) -> tuple[float, float]:
    return round(mid * low_pct, 2), round(mid * high_pct, 2)


@router.post(
    "/simulate",
    response_model=ROISimulateResponse,
    summary="Simulate Aetherix ROI for a prospective property (public, stateless)",
)
async def simulate_roi(body: ROISimulateRequest) -> ROISimulateResponse:
    """Return an order-of-magnitude savings projection grounded in P0-2 backtest KPIs.

    Notes:
    - All figures are **simulated** — based on synthetic-data backtest and public
      hospitality benchmarks (ADEME, Accor sustainability reports). No live pilot.
    - Low/high bounds reflect +/- reasonable ranges around central assumptions.
    - Use this to size the opportunity, not to commit to a contract number.
    """
    ptype_factor = _property_type_factor(body.property_type)

    # --- 1. Food waste reduction ---------------------------------------------------
    # Waste reduction = current_waste_pct * food_cost_pct * annual_fb * lift
    waste_cost_baseline = (
        body.annual_fb_revenue_eur * body.food_cost_pct * body.current_waste_pct
    )
    waste_low = waste_cost_baseline * _FOOD_WASTE_REDUCTION_MIN
    waste_high = waste_cost_baseline * _FOOD_WASTE_REDUCTION_MAX
    waste_mid = (waste_low + waste_high) / 2

    # --- 2. Labor cost reduction ---------------------------------------------------
    # Assumes labor is ~35% of F&B revenue (industry avg); Aetherix reduces
    # over-staffing on low-demand days.
    labor_baseline = body.annual_fb_revenue_eur * 0.35
    labor_low = labor_baseline * _LABOR_COST_REDUCTION_MIN * ptype_factor
    labor_high = labor_baseline * _LABOR_COST_REDUCTION_MAX * ptype_factor
    labor_mid = (labor_low + labor_high) / 2

    # --- 3. Forecast accuracy uplift (over/under-prep avoided) ---------------------
    # Each percentage point of MAPE reduction saves roughly food_cost_pct * fb_revenue
    # at the margin (avoids both stockouts and over-prep). Conservative 0.5x multiplier.
    accuracy_margin = body.annual_fb_revenue_eur * body.food_cost_pct * _FORECAST_LIFT * 0.5
    acc_low = accuracy_margin * 0.5
    acc_high = accuracy_margin * 1.0
    acc_mid = (acc_low + acc_high) / 2

    total_mid = waste_mid + labor_mid + acc_mid
    total_low = waste_low + labor_low + acc_low
    total_high = waste_high + labor_high + acc_high

    return ROISimulateResponse(
        total_annual_savings_eur=round(total_mid, 2),
        total_annual_savings_low_eur=round(total_low, 2),
        total_annual_savings_high_eur=round(total_high, 2),
        food_waste_reduction=ROISavingsBreakdown(
            annual_eur=round(waste_mid, 2),
            low_eur=round(waste_low, 2),
            high_eur=round(waste_high, 2),
            assumption=(
                f"Reduces current food waste by {int(_FOOD_WASTE_REDUCTION_MIN*100)}–"
                f"{int(_FOOD_WASTE_REDUCTION_MAX*100)}% via demand-calibrated prep."
            ),
        ),
        labor_cost_reduction=ROISavingsBreakdown(
            annual_eur=round(labor_mid, 2),
            low_eur=round(labor_low, 2),
            high_eur=round(labor_high, 2),
            assumption=(
                f"Reduces F&B labor cost by {int(_LABOR_COST_REDUCTION_MIN*100)}–"
                f"{int(_LABOR_COST_REDUCTION_MAX*100)}% via right-sized staffing "
                f"(property_type factor {ptype_factor:.2f})."
            ),
        ),
        forecast_accuracy_uplift=ROISavingsBreakdown(
            annual_eur=round(acc_mid, 2),
            low_eur=round(acc_low, 2),
            high_eur=round(acc_high, 2),
            assumption=(
                f"Forecast MAPE improvement from ~{int(_BASELINE_MAPE*100)}% baseline "
                f"to {_MAPE_J1*100:.1f}% (P0-2 backtest, synthetic) avoids "
                f"over/under-prep at the margin."
            ),
        ),
        assumptions=[
            f"Labor modelled as 35% of annual F&B revenue (industry average).",
            f"Food waste baseline: {int(_FOOD_WASTE_BASELINE_PCT*100)}% "
            f"(ADEME/Accor reference).",
            f"Forecast lift: ~{_FORECAST_LIFT*100:.0f}pp MAPE improvement vs manual baseline.",
            f"Property type factor for {body.property_type.value}: {ptype_factor:.2f}x.",
        ],
        disclaimers=[
            "Simulated figures — based on synthetic-data backtest (P0-2, 17 April 2026), "
            "not validated on real hotel pilots.",
            "Real-world MAPE may increase by 5–10pp vs synthetic benchmark.",
            "Savings are directional; commit to numbers only after a live pilot.",
            "No guarantee of results. ROI depends on data quality, adoption rate, "
            "and property-specific operational patterns.",
        ],
        source_metrics={
            "mape_j1_backtest": _MAPE_J1,
            "baseline_mape_assumed": _BASELINE_MAPE,
            "food_waste_baseline_pct": _FOOD_WASTE_BASELINE_PCT,
            "labor_cost_reduction_range": [
                _LABOR_COST_REDUCTION_MIN,
                _LABOR_COST_REDUCTION_MAX,
            ],
            "backtest_report": "docs/metrics/backtest_2026-04-17.json",
        },
    )
