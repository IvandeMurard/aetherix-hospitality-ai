"""Staffing on the hotel's own rules (HOS-343).

A hotel's ratios and usual team come from hotel_parameters; anything it has not
set falls back to the system default and is labelled "default". Runners have no
default. Without any parameter, the output is the pre-HOS-343 headcount.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.services import hotel_parameters as hp
from app.services.staffing_service import StaffingConfig, StaffingRules, StaffingService

T0 = datetime(2026, 10, 17, 8, 0, tzinfo=timezone.utc)


class _Params:
    """Minimal stand-in for hotel_parameters.HotelParameters."""

    def __init__(self, values: dict, version: str | None = "2026-10-17T08:00:00+00:00"):
        self._values, self._version = values, version

    def get(self, name):
        return self._values.get(name)

    def version(self):
        return self._version


@pytest.fixture(autouse=True)
def _no_sanity_trip_writes():
    with patch("app.services.output_sanity.record_sanity_trip", new_callable=AsyncMock):
        yield


@pytest_asyncio.fixture()
async def maker():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("covers", [10, 50, 82, 85, 101, 160, 161])
async def test_without_hotel_rules_the_headcount_is_unchanged(covers):
    r = await StaffingService().calculate_recommendation(covers)
    assert (r["servers"], r["hosts"], r["kitchen"]) == (
        math.ceil(covers / 18), math.ceil(covers / 70), math.ceil(covers / 50))
    assert r["runners"] == 0
    assert set(r["deltas"]) == {"servers", "hosts", "kitchen", "sommeliers"}
    assert r["deltas"]["servers"] == math.ceil(covers / 18) - 7
    assert r["rules_version"] is None


@pytest.mark.asyncio
async def test_defaults_are_labelled_default_never_hotel():
    r = await StaffingService().calculate_recommendation(101)
    for role in ("servers", "hosts", "kitchen"):
        assert r["rules"][role]["covers_per_source"] == "default"
        assert r["rules"][role]["usual_source"] == "default"
    assert r["rules"]["runners"]["covers_per"] is None
    assert r["rules"]["runners"]["covers_per_source"] == "none"
    assert r["rules"]["sommeliers"]["source"] == "default"
    assert "default ratios" in r["rationale"]


@pytest.mark.asyncio
async def test_hotel_rules_apply_role_by_role_with_their_source():
    rules = StaffingRules.from_parameters(_Params({
        "covers_per_server": 16, "covers_per_runner": 40,
        "usual_servers": 6, "usual_runners": 2,
    }))
    r = await StaffingService().calculate_recommendation(101, rules=rules)
    assert (r["servers"], r["runners"]) == (7, 3)          # ceil(101/16), ceil(101/40)
    assert (r["hosts"], r["kitchen"]) == (2, 3)             # defaults 70 / 50
    assert r["deltas"]["servers"] == 1 and r["deltas"]["runners"] == 1
    assert r["rules"]["servers"] == {"covers_per": 16, "covers_per_source": "hotel",
                                     "covers_per_context": None, "covers_per_label": "hotel",
                                     "usual": 6, "usual_source": "hotel",
                                     "usual_context": None, "usual_label": "hotel"}
    assert r["rules"]["hosts"]["covers_per_source"] == "default"
    assert r["rules_version"] == "2026-10-17T08:00:00+00:00"
    assert "where set, defaults elsewhere" in r["rationale"]


@pytest.mark.asyncio
async def test_runners_not_staffed_without_a_hotel_ratio_even_with_a_usual_team():
    rules = StaffingRules.from_parameters(_Params({"usual_runners": 2}))
    r = await StaffingService().calculate_recommendation(101, rules=rules)
    assert r["runners"] == 0
    assert "runners" not in r["deltas"]


@pytest.mark.asyncio
async def test_all_ratios_set_reads_as_the_hotels_own():
    rules = StaffingRules.from_parameters(_Params({
        "covers_per_server": 20, "covers_per_host": 80, "covers_per_runner": 45, "covers_per_kitchen_staff": 35,
    }))
    r = await StaffingService().calculate_recommendation(101, rules=rules)
    assert (r["servers"], r["hosts"], r["runners"], r["kitchen"]) == (6, 2, 3, 3)
    assert "the hotel's own ratios" in r["rationale"]


@pytest.mark.asyncio
async def test_rules_are_read_from_hotel_parameters(maker):
    async with maker() as db:
        await hp.set_parameter(db, "h1", "covers_per_server", 16, set_by="gm@h1", set_via="dashboard_api", at=T0)
        await hp.set_parameter(db, "h1", "usual_servers", 6, set_by="gm@h1", set_via="dashboard_api", at=T0)
        await hp.set_parameter(db, "h2", "covers_per_server", 30, set_by="gm@h2", set_via="dashboard_api", at=T0)
        await db.commit()
    with patch("app.db.session.AsyncSessionLocal", maker):
        r = await StaffingService().calculate_recommendation(101, tenant_id="h1")
    assert r["servers"] == 7 and r["deltas"]["servers"] == 1
    assert r["rules"]["servers"]["covers_per_source"] == "hotel"
    assert r["rules_version"] == T0.isoformat()


@pytest.mark.asyncio
async def test_unreadable_rules_fall_back_to_labelled_defaults():
    def boom():
        raise RuntimeError("db down")

    with patch("app.db.session.AsyncSessionLocal", boom):
        r = await StaffingService().calculate_recommendation(101, tenant_id="h1")
    assert (r["servers"], r["hosts"], r["kitchen"]) == (6, 2, 3)
    assert r["rules"]["servers"]["covers_per_source"] == "default"


@pytest.mark.asyncio
async def test_explicit_rules_win_over_a_tenant_lookup():
    svc = StaffingService()
    with patch.object(svc, "rules_for", AsyncMock()) as lookup:
        await svc.calculate_recommendation(101, tenant_id="h1", rules=StaffingRules.defaults())
    lookup.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_budget_alert_without_a_budget_anyone_set():
    """HOS-348: the old 1200/day placeholder fired on any night above 15 shifts."""
    from app.services import output_sanity

    with patch.object(output_sanity, "record_sanity_trip", new_callable=AsyncMock) as trip:
        r = await StaffingService().calculate_recommendation(300)
    assert "labor_budget_exceeded" not in r["sanity"]["flags"]
    assert not any("budget" in w.lower() for w in r["warnings"])
    for call in trip.await_args_list:
        assert "labor_budget_exceeded" not in [f for f, _ in call.args[1].flags]


@pytest.mark.asyncio
async def test_an_explicit_budget_is_still_checked():
    r = await StaffingService().calculate_recommendation(
        101, StaffingConfig(labor_budget_gbp_per_day=500.0))
    assert "labor_budget_exceeded" in r["sanity"]["flags"]


_GOLDEN = Path(__file__).resolve().parents[3] / "eval" / "golden_dataset.jsonl"
_SCENARIOS = [
    json.loads(line) for line in _GOLDEN.read_text(encoding="utf-8").splitlines()
    if line.strip() and json.loads(line)["id"].startswith("reco-hotel-rules-")
]


def test_golden_scenarios_exist():
    assert len(_SCENARIOS) >= 2


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", _SCENARIOS, ids=[s["id"] for s in _SCENARIOS])
async def test_golden_hotel_rules_scenarios(scenario):
    """The recommendation layer has no eval runner; these golden rows are graded here."""
    inp, exp = scenario["input"], scenario["expected"]
    rules = StaffingRules.from_parameters(_Params(inp["hotel_parameters"]))
    r = await StaffingService().calculate_recommendation(inp["covers_predicted"], rules=rules)
    assert {role: r[role] for role in exp["headcount"]} == exp["headcount"]
    assert {role: r["rules"][role]["covers_per_source"] for role in exp["sources"]} == exp["sources"]
    for flag in exp.get("flags_absent", []):
        assert flag not in r["sanity"]["flags"]


@pytest.mark.parametrize("name,value", [
    ("covers_per_server", 0), ("covers_per_runner", 201), ("covers_per_kitchen_staff", -3),
    ("usual_servers", 2.5), ("usual_runners", 51), ("usual_hosts", -1),
])
def test_staffing_parameters_are_bounded(name, value):
    with pytest.raises(hp.ParameterError):
        hp.validate(name, value)


def test_staffing_parameters_are_in_the_catalog_for_staffing_decisions():
    for name in ("covers_per_server", "covers_per_host", "covers_per_runner", "covers_per_kitchen_staff",
                 "usual_servers", "usual_hosts", "usual_runners", "usual_kitchen_staff"):
        assert name in hp.CATALOG
        assert set(hp.CATALOG[name].used_by) == {"staffing.add", "staffing.reduce"}
    assert hp.validate("usual_runners", 0) == 0.0
