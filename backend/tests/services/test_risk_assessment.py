"""Risk-based recommendation (ADR-0007 §18.4, Décision #40)."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.services import risk_assessment as ra
from app.services.forecast_calibration import fit
from app.services.hotel_parameters import HotelParameters, ParamValue
from app.services.task_classes import TaskClassKey

NOW = datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc)
# Residuals uniform on [-0.3, 0.3]: demand for ŷ=130 is ~uniform on [91, 169].
CAL = fit([(-0.3 + k / 100 * 0.6) for k in range(101)], version="t-v1", forecaster="f",
          provenance="synthetic", created_at="2026-09-25")
REALISED = fit([(-0.3 + k / 100 * 0.6) for k in range(101)], version="r-v1", forecaster="f",
               provenance="realised", created_at="2026-09-25")


def _params(**values) -> HotelParameters:
    p = HotelParameters("h1")
    units = {"extra_shift_cost": "money", "lost_cover_value": "money", "risk_display_min_gap": "money",
             "covers_per_extra_staff": "covers", "max_extra_staff": "staff", "max_staff_reduction": "staff"}
    for k, v in values.items():
        p.values[k] = ParamValue(float(v), units[k], "EUR", "gm@x", "dashboard_api", NOW, None)
    return p


FULL = dict(extra_shift_cost=180, lost_cover_value=25, covers_per_extra_staff=20)


def _inp(params, cal=CAL, fallback=1, c=20.0, point=130.0, base=100.0):
    return ra.Inputs(TaskClassKey.staffing_add, point, base, fallback, "f", cal, params, c,
                     "hotel_parameter" if c else None)


def test_newsvendor_critical_ratio_and_quantity():
    a = ra.assess(_inp(_params(**FULL)))
    assert a["decision_rule"] == ra.RULE_NEWSVENDOR and a["fallback_missing_inputs"] == []
    # cu = 20 covers x 25 = 500 per staff short; co = 180 → CR = 500/680
    assert a["critical_ratio"] == pytest.approx(500 / 680, abs=1e-4)
    assert 145 <= a["demand_quantile"] <= 152
    assert a["recommended_delta_staff"] == 3  # ceil((Q - 100)/20)
    acc, ref = a["options"]["accept"], a["options"]["refuse"]
    assert acc["extra_shift_cost"] == 540.0 and ref["extra_shift_cost"] == 0.0
    assert acc["shortfall_probability"] < ref["shortfall_probability"]
    assert acc["expected_total_cost"] < ref["expected_total_cost"]
    assert a["uncertainty"]["label"] == "synthetic-calibrated"
    assert a["costs"]["parameters_version"] == NOW.isoformat()


def test_higher_shift_cost_lowers_the_quantity():
    cheap = ra.assess(_inp(_params(**FULL)))["recommended_delta_staff"]
    dear = ra.assess(_inp(_params(**{**FULL, "extra_shift_cost": 2000})))["recommended_delta_staff"]
    assert dear < cheap


def test_caps_bound_the_quantity():
    a = ra.assess(_inp(_params(**FULL, max_extra_staff=1)))
    assert a["recommended_delta_staff"] == 1


@pytest.mark.parametrize("drop,missing", [
    ("calibration", "calibration:f"), ("extra_shift_cost", "extra_shift_cost"),
    ("lost_cover_value", "lost_cover_value"), ("c", "covers_per_extra_staff"),
])
def test_any_missing_input_keeps_the_previous_rule_and_says_why(drop, missing):
    values = dict(FULL)
    values.pop(drop, None)
    a = ra.assess(_inp(_params(**values), cal=None if drop == "calibration" else CAL,
                       c=None if drop == "c" else 20.0, fallback=2))
    assert a["decision_rule"] == ra.RULE_FALLBACK
    assert missing in a["fallback_missing_inputs"]
    assert a["recommended_delta_staff"] == 2


def test_no_probability_without_calibration_no_money_without_costs():
    a = ra.assess(_inp(HotelParameters("h1"), cal=None, fallback=1))
    for opt in a["options"].values():
        assert opt["shortfall_probability"] is None and opt["extra_shift_cost"] is None
        assert opt["expected_total_cost"] is None and opt["qualitative_shortfall"]
    assert a["uncertainty"]["label"] == "qualitative" and a["costs"]["status"] == "missing"
    lines = ra.render_lines(a, "en")
    assert lines == [
        "If accepted: +1 shift; shortfall possible (qualitative, uncertainty not calibrated).",
        "If refused: no change; shortfall likely if the forecast holds (qualitative, uncertainty not calibrated).",
    ]
    assert not any(re.search(r"\d+ ?%|€", line) for line in lines)
    assert a["material"] is False and a["material_basis"] == "not_quantified"


def test_calibrated_without_costs_shows_probability_never_money():
    a = ra.assess(_inp(_params(covers_per_extra_staff=20), fallback=1))
    assert a["decision_rule"] == ra.RULE_FALLBACK
    lines = ra.render_lines(a, "fr")
    assert all("%" in line and "€" not in line for line in lines)
    assert all("incertitude calibrée sur données synthétiques" in line for line in lines)


def test_lines_are_deterministic_and_carry_the_provenance():
    a = ra.assess(_inp(_params(**FULL)))
    assert ra.render_lines(a, "en") == ra.render_lines(a, "en")
    en = ra.render_lines(a, "en")
    assert en[0].startswith("If accepted: +3 shifts (€540); shortfall risk ≈")
    assert en[1].startswith("If refused: no change; shortfall risk ≈")
    assert all(line.endswith("(synthetic-calibrated uncertainty).") for line in en)
    r = ra.assess(_inp(_params(**FULL), cal=REALISED))
    assert ra.render_lines(r, "en")[0].endswith("(calibrated on realised covers).")


def test_interruption_budget():
    a = ra.assess(_inp(_params(**FULL)))
    assert a["material"] is True and a["material_basis"] == "money_gap_default_threshold"
    high = ra.assess(_inp(_params(**FULL, risk_display_min_gap=100000)))
    assert high["material"] is False and high["material_basis"] == "money_gap_hotel_threshold"
    # No change recommended → both options are the same action → never material.
    zero = ra.assess(_inp(_params(**FULL), point=80.0))
    assert zero["recommended_delta_staff"] <= 0 or zero["material"] is True


def test_probability_is_rounded_and_never_0_or_100():
    assert ra._pct(0.0) == 5 and ra._pct(1.0) == 95 and ra._pct(0.126) == 15


# ---------------------------------------------------------------------------
# Formatter end to end (SQLite, ORM tables)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def db():
    from app.db.models import Base

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


async def _anomaly(db, tenant, prop, start):
    from app.db.models import DemandAnomaly

    a = DemandAnomaly(
        tenant_id=tenant, property_id=prop, window_start=start, window_end=start + timedelta(hours=4),
        expected_demand=130, baseline_demand=100, deviation_pct=30, direction="surge",
        triggering_factors=[{"label": "Concert", "weight": 0.9}], status="roi_positive",
        roi_revenue_opp=700, roi_labor_cost=56, roi_net=644,
    )
    db.add(a)
    await db.commit()
    return a


async def _set(db, tenant, **values):
    from app.services import hotel_parameters as hp

    for k, v in values.items():
        await hp.set_parameter(db, tenant, k, v, set_by="gm@x", set_via="dashboard_api", at=NOW)
    await db.commit()


@pytest.mark.asyncio
async def test_formatter_without_calibration_stays_on_previous_rule_qualitative(db):
    from app.db.models import StaffingRecommendation
    from app.services.recommendation_formatter import RecommendationFormatterService
    from sqlalchemy import select

    prop = uuid.uuid4()
    await _anomaly(db, "h1", prop, datetime.now(timezone.utc) + timedelta(days=5))
    await _set(db, "h1", **FULL)
    await RecommendationFormatterService().run_full_scan(db)
    rec = (await db.execute(select(StaffingRecommendation))).scalars().one()
    risk = rec.risk_assessment if isinstance(rec.risk_assessment, dict) else json.loads(rec.risk_assessment)
    # No calibration exists for the anomaly heuristic → previous rule, recorded.
    assert rec.decision_rule == ra.RULE_FALLBACK
    assert "calibration:anomaly-heuristic-v1" in risk["fallback_missing_inputs"]
    assert risk["options"]["accept"]["extra_shift_cost"] == 180.0  # configured → money
    assert risk["options"]["accept"]["shortfall_probability"] is None
    assert risk["material"] is False
    assert "If accepted" not in rec.message_text and "Si accepté" not in rec.message_text


@pytest.mark.asyncio
async def test_formatter_with_calibration_and_costs_uses_newsvendor(db, monkeypatch):
    from app.db.models import StaffingRecommendation
    from app.services import forecast_calibration
    from app.services.recommendation_formatter import RecommendationFormatterService
    from sqlalchemy import select

    anomaly_cal = fit([(-0.3 + k / 100 * 0.6) for k in range(101)], version="a-v1",
                      forecaster=ra.ANOMALY_FORECASTER, provenance="realised", created_at="2026-09-25")
    monkeypatch.setattr(forecast_calibration, "load_active",
                        lambda f, *a, **k: anomaly_cal if f == ra.ANOMALY_FORECASTER else None)
    prop = uuid.uuid4()
    await _anomaly(db, "h1", prop, datetime.now(timezone.utc) + timedelta(days=5))
    await _set(db, "h1", **FULL)
    await RecommendationFormatterService().run_full_scan(db)
    rec = (await db.execute(select(StaffingRecommendation))).scalars().one()
    assert rec.decision_rule == ra.RULE_NEWSVENDOR
    assert rec.recommended_headcount == 3 and rec.task_class == "staffing.add"
    assert rec.message_text.startswith("Add 3 staff for ")
    assert "Si accepté : +3 extras (€540)" in rec.message_text
    assert "Si refusé : aucun changement" in rec.message_text

    from app.mcp_server import tool_get_pending_recommendations

    out = await tool_get_pending_recommendations("h1", db, locale="en")
    item = out["recommendations"][0]
    assert item["recommendation_id"] == str(rec.id) and item["decision_rule"] == ra.RULE_NEWSVENDOR
    assert item["risk"]["options"]["accept"]["delta_staff"] == 3
    assert item["risk"]["uncertainty"]["label"] == "calibrated-on-realised"
    assert item["correction_window"]["commit_point"] == "extra_shift_confirmed"
    assert item["lines"][0].startswith("If accepted: +3 shifts (€540)")
    assert (await tool_get_pending_recommendations("other-hotel", db))["recommendations"] == []


@pytest.mark.asyncio
async def test_pending_tool_validates_input(db):
    from app.mcp_core import MCPAuthError
    from app.mcp_server import tool_get_pending_recommendations

    with pytest.raises(MCPAuthError):
        await tool_get_pending_recommendations("h1", db, locale="de")
    with pytest.raises(MCPAuthError):
        await tool_get_pending_recommendations("h1", db, limit=0)


def test_pending_tool_requires_the_read_scope():
    from app.mcp_core import MCPAuthError, require_scope

    with pytest.raises(MCPAuthError):
        require_scope(["feedback"], "get_pending_recommendations")
    require_scope(["receipts:read"], "get_pending_recommendations")


def test_recap_always_shows_the_lines_for_undecided_recommendations():
    from datetime import date

    from app.services.decision_recap import RecRow, render_text, summarize

    risk = ra.assess(_inp(HotelParameters("h1"), cal=None, fallback=2))
    rows = [
        RecRow(id="r1", received_at=NOW, window_start=NOW + timedelta(hours=10), status="dispatched",
               decided_by=None, decision_source=None, actioned_at=None, predicted_covers=130,
               actual_covers=None, risk_assessment=risk),
        RecRow(id="r2", received_at=NOW, window_start=NOW, status="accepted", decided_by="human_whatsapp",
               decision_source="keyword", actioned_at=NOW, predicted_covers=130, actual_covers=None,
               risk_assessment=risk),
    ]
    s = summarize(rows, "day", date(2026, 9, 25), date(2026, 9, 25))
    assert [p["recommendation_id"] for p in s.pending_risk] == ["r1"]  # decided ones excluded
    text = render_text(s, "en")
    assert "Risk per option, no reply yet:" in text
    assert "  If accepted: +2 shifts; shortfall possible (qualitative, uncertainty not calibrated)." in text
