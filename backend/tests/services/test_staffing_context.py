"""Staffing rules per context class — HOS-345.

Closed list of classes, each resolved from a signal already in the pipeline
(never guessed), a written priority order, the fallback chain class → flat →
default, the output saying which rule served and why, and back-compatibility
with HOS-343 for a hotel that set no class rule.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import hotel_parameters as hp
from app.services import staffing_context as sc
from app.services.staffing_service import StaffingRules, StaffingService

TUESDAY = date(2026, 10, 20)        # no holiday, October
BASTILLE_DAY = date(2026, 7, 14)    # Fête nationale


class _Params:
    def __init__(self, values: dict, version: str | None = "2026-10-18T08:00:00+00:00"):
        self._values, self._version = values, version

    def get(self, name):
        return self._values.get(name)

    def version(self):
        return self._version


CONCERT = {"title": "Concert Bercy", "rank": 72, "phq_attendance": 15000, "distance_km": 2.1}


# --- resolution: signals, never guesses ---------------------------------------------

def test_the_list_of_classes_is_closed_and_ordered():
    assert sc.CONTEXT_CLASSES == ("banquet", "event_night", "public_holiday", "school_holidays",
                                  "high_season", "breakfast", "lunch", "dinner")
    assert set(sc.CLASS_LABELS["en"]) == set(sc.CLASS_LABELS["fr"]) == set(sc.CONTEXT_CLASSES)


def test_a_quiet_dinner_is_only_a_dinner():
    r = sc.resolve(TUESDAY, "dinner", {"events": []})
    assert r.classes == ("dinner",) and r.signals == {"dinner": "service_type"}


@pytest.mark.parametrize("event, qualifies", [
    (CONCERT, True),
    ({"title": "Big but far", "rank": 90, "distance_km": 12.0}, False),
    ({"title": "Small fair", "rank": 30, "phq_attendance": 400}, False),
    ({"title": "Crowd, no rank", "phq_attendance": 2500}, True),
    ({"title": "Local favourite", "local_rank": 65}, True),
    ({"title": "Bad data", "rank": "high"}, False),
])
def test_event_nights_come_from_the_events_already_in_context(event, qualifies):
    r = sc.resolve(TUESDAY, "dinner", {"events": [event]})
    assert ("event_night" in r.classes) is qualifies
    if qualifies:
        assert r.signals["event_night"] == [event["title"]]


def test_public_holidays_come_from_the_french_calendar():
    r = sc.resolve(BASTILLE_DAY, "dinner", {})
    assert r.classes == ("public_holiday", "dinner")
    assert "nationale" in r.signals["public_holiday"]


def test_banquet_and_school_holidays_only_when_declared():
    assert sc.resolve(TUESDAY, "dinner", {"banquet": "yes", "school_holidays": 1}).classes == ("dinner",)
    r = sc.resolve(TUESDAY, "dinner", {"banquet": True, "school_holidays": True})
    assert r.classes == ("banquet", "school_holidays", "dinner")
    assert r.signals["banquet"] == r.signals["school_holidays"] == "declared"


@pytest.mark.parametrize("start, end, month, inside", [
    (6, 9, 7, True), (6, 9, 10, False),
    (11, 2, 12, True), (11, 2, 1, True), (11, 2, 3, False),   # wraps over the new year
    (None, 9, 7, False),                                      # half a season is no season
])
def test_high_season_is_the_hotels_own(start, end, month, inside):
    params = _Params({"high_season_start_month": start, "high_season_end_month": end})
    r = sc.resolve(date(2026, month, 6), "lunch", {}, params)
    assert ("high_season" in r.classes) is inside


def test_unknown_service_type_adds_no_class():
    assert sc.resolve(TUESDAY, "brunch", {}).classes == ()


def test_classes_come_out_in_priority_order():
    params = _Params({"high_season_start_month": 6, "high_season_end_month": 9})
    r = sc.resolve(BASTILLE_DAY, "dinner", {"events": [CONCERT], "banquet": True, "school_holidays": True}, params)
    assert r.classes == sc.CONTEXT_CLASSES[:5] + ("dinner",)


# --- rules: class → flat → default ---------------------------------------------------

def _rules(values, **ctx):
    params = _Params(values)
    return StaffingRules.from_parameters(params, context=sc.resolve(ctx.get("day", TUESDAY), ctx.get("service", "dinner"),
                                                                    ctx.get("context", {}), params))


def test_the_first_class_with_a_hotel_value_wins_then_flat_then_default():
    values = {"covers_per_server": 16, "covers_per_server.dinner": 14, "covers_per_server.event_night": 10,
              "usual_servers": 6, "usual_servers.event_night": 9}
    ev = _rules(values, context={"events": [CONCERT]})
    assert (ev.roles["servers"].covers_per, ev.roles["servers"].covers_per_context) == (10, "event_night")
    assert (ev.roles["servers"].usual, ev.roles["servers"].usual_context) == (9, "event_night")
    quiet = _rules(values)
    assert (quiet.roles["servers"].covers_per, quiet.roles["servers"].covers_per_context) == (14, "dinner")
    assert (quiet.roles["servers"].usual, quiet.roles["servers"].usual_context) == (6, None)   # flat
    lunch = _rules(values, service="lunch")
    assert (lunch.roles["servers"].covers_per, lunch.roles["servers"].covers_per_context) == (16, None)
    assert (lunch.roles["hosts"].covers_per, lunch.roles["hosts"].covers_per_source) == (70, "default")


def test_a_class_can_staff_a_role_the_flat_rules_do_not():
    r = _rules({"covers_per_runner.banquet": 30}, context={"banquet": True})
    assert r.roles["runners"].covers_per == 30 and "runners" in r.staffed()
    assert "runners" not in _rules({"covers_per_runner.banquet": 30}).staffed()


@pytest.mark.asyncio
async def test_the_output_says_which_rule_served_and_why():
    rules = _rules({"covers_per_server.event_night": 10, "covers_per_server": 16}, context={"events": [CONCERT]})
    r = await StaffingService().calculate_recommendation(101, rules=rules)
    assert r["servers"] == 11                                   # ceil(101 / 10)
    s = r["rules"]["servers"]
    assert (s["covers_per_source"], s["covers_per_context"], s["covers_per_label"]) == (
        "hotel", "event_night", "hotel · event night")
    assert r["rules"]["hosts"]["covers_per_label"] == "default"
    assert r["context"] == {"classes": ["event_night", "dinner"],
                            "signals": {"event_night": ["Concert Bercy"], "dinner": "service_type"}}
    assert "(event night rules)" in r["rationale"]


@pytest.mark.asyncio
async def test_a_hotel_without_class_rules_gets_exactly_the_hos343_staffing():
    flat = {"covers_per_server": 16, "covers_per_runner": 40, "usual_servers": 6, "usual_runners": 2}
    before = await StaffingService().calculate_recommendation(101, rules=StaffingRules.from_parameters(_Params(flat)))
    after = await StaffingService().calculate_recommendation(
        101, rules=_rules(flat, day=BASTILLE_DAY, context={"events": [CONCERT], "banquet": True}))
    keys = ("servers", "hosts", "runners", "kitchen", "deltas")
    assert {k: before[k] for k in keys} == {k: after[k] for k in keys}
    assert all(v["covers_per_context"] is None for k, v in after["rules"].items() if k != "sommeliers")


@pytest.mark.asyncio
async def test_rules_for_resolves_the_class_with_the_hotels_season():
    params = MagicMock()
    params.get = lambda n: {"high_season_start_month": 6, "high_season_end_month": 9,
                            "covers_per_server.high_season": 12}.get(n)
    params.version = lambda: "v1"
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    with (patch("app.db.session.AsyncSessionLocal", return_value=session),
          patch.object(hp, "load", AsyncMock(return_value=params))):
        rules = await StaffingService().rules_for("h1", target_date=date(2026, 8, 4), service_type="lunch", context={})
    assert rules.context.classes == ("high_season", "lunch")
    assert (rules.roles["servers"].covers_per, rules.roles["servers"].covers_per_context) == (12, "high_season")


# --- parameters: bounded, closed ------------------------------------------------------

def test_class_parameters_are_in_the_bounded_catalog():
    for rule in ("covers_per_server", "covers_per_host", "covers_per_runner", "covers_per_kitchen_staff",
                 "usual_servers", "usual_hosts", "usual_runners", "usual_kitchen_staff"):
        for c in sc.CONTEXT_CLASSES:
            spec = hp.CATALOG[f"{rule}.{c}"]
            assert (spec.unit, spec.minimum, spec.maximum) == (
                hp.CATALOG[rule].unit, hp.CATALOG[rule].minimum, hp.CATALOG[rule].maximum)
    assert "covers_per_extra_staff.dinner" not in hp.CATALOG
    with pytest.raises(hp.ParameterError):
        hp.validate("covers_per_server.full_moon", 10)        # no class invented on the fly
    with pytest.raises(hp.ParameterError):
        hp.validate("usual_servers.event_night", 2.5)         # a whole number of staff


@pytest.mark.parametrize("value, ok", [(1, True), (12, True), (0, False), (13, False), (6.5, False)])
def test_season_months_are_month_numbers(value, ok):
    if ok:
        assert hp.validate("high_season_start_month", value) == value
    else:
        with pytest.raises(hp.ParameterError):
            hp.validate("high_season_start_month", value)


# --- golden scenarios (recommendation layer, graded here) -------------------------------

def _golden():
    path = Path(__file__).resolve().parents[3] / "eval" / "golden_dataset.jsonl"
    rows = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return [r for r in rows if r["id"].startswith("reco-context-rules-")]


_GOLDEN = _golden()


def test_context_golden_scenarios_exist():
    assert len(_GOLDEN) >= 2


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", _GOLDEN, ids=[s["id"] for s in _GOLDEN])
async def test_context_golden_scenarios(scenario):
    """The recommendation layer has no eval runner; these golden rows are graded here."""
    inp, exp = scenario["input"], scenario["expected"]
    params = _Params(inp["hotel_parameters"])
    resolution = sc.resolve(date.fromisoformat(inp["date"]), inp["service_type"], inp["context"], params)
    rules = StaffingRules.from_parameters(params, context=resolution)
    r = await StaffingService().calculate_recommendation(inp["covers_predicted"], rules=rules)
    assert list(resolution.classes) == exp["classes"]
    assert {role: r[role] for role in exp["headcount"]} == exp["headcount"]
    assert {role: r["rules"][role]["covers_per_label"] for role in exp["labels"]} == exp["labels"]
