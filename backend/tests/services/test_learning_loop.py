"""Learning loop (ADR-0007 §18.5, Décision #40): pure rules, hygiene, review,
application, rollback."""
from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.services import forecast_calibration as fc
from app.services import learning_loop as ll

NOW = datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc)


def _risk(p_acc, p_ref, *, cap_acc=140.0, cap_ref=100.0, delta=2, version="cal-v1",
          task="staffing.add", band=None):
    calibrated = p_acc is not None
    return {
        "task_class": task, "forecaster": "anomaly-heuristic-v1",
        "recommended_delta_staff": delta, "baseline_covers": cap_ref, "covers_per_staff": 20.0,
        "uncertainty": {"status": "calibrated" if calibrated else "uncalibrated",
                        "calibration_version": version if calibrated else None,
                        "interval": [90.0, 150.0] if calibrated else None},
        "options": {
            "accept": {"delta_staff": delta, "capacity_covers": cap_acc, "shortfall_probability": p_acc,
                       "qualitative_shortfall": band},
            "refuse": {"delta_staff": 0, "capacity_covers": cap_ref, "shortfall_probability": p_ref,
                       "qualitative_shortfall": band},
        },
    }


def _row(status, actual, risk, decided_by="human_whatsapp", reason=None, reason_source="human",
         source="manager_feedback", predicted=120.0, i=0):
    return {"id": f"r{i}", "status": status, "decided_by": decided_by, "reason_code": reason,
            "reason_source": reason_source, "risk_assessment": risk, "actual_covers": actual,
            "actual_covers_source": source, "predicted_covers": predicted,
            "window_start": (NOW + timedelta(days=i)).isoformat()}


# ---------------------------------------------------------------------------
# Arm C — risk-statement calibration
# ---------------------------------------------------------------------------

def test_well_calibrated_statements_are_not_flagged():
    rng = random.Random(1)
    rows = [_row("accepted", 150 if rng.random() < 0.25 else 130, _risk(0.25, 0.8), i=i) for i in range(200)]
    rep = ll.risk_statement_calibration(rows)
    g = rep["groups"]["staffing.add|human|cal-v1"]
    assert g["n_probabilistic"] == 200 and abs(g["observed"] - 0.25) < 0.08
    assert g["miscalibrated"] is False and ll.miscalibration_alerts(rep) == []
    assert g["independent_actuals"] is False  # manager-declared


def test_miscalibrated_statements_raise_a_typed_alert():
    rows = [_row("accepted", 150, _risk(0.25, 0.8), i=i) for i in range(40)]  # always happens
    rep = ll.risk_statement_calibration(rows)
    alerts = ll.miscalibration_alerts(rep)
    assert len(alerts) == 1 and alerts[0]["reason"] == "risk_statement_miscalibrated"
    assert alerts[0]["observed"] == 1.0 and alerts[0]["mean_stated"] == 0.25


def test_no_alert_below_min_n():
    rows = [_row("accepted", 150, _risk(0.25, 0.8), i=i) for i in range(ll.RISK_CALIBRATION_MIN_N - 1)]
    assert ll.miscalibration_alerts(ll.risk_statement_calibration(rows)) == []


def test_taken_option_decider_split_and_version_split():
    rows = [
        _row("rejected", 120, _risk(0.1, 0.6)),                       # refuse option: cap 100 → happened
        _row("modified", 120, _risk(0.1, 0.6)),                       # excluded
        _row("dispatched", 120, _risk(0.1, 0.6)),                     # undecided → excluded
        _row("accepted", 120, _risk(0.1, 0.6), decided_by="host_agent_autonomous"),
        _row("accepted", 120, _risk(0.1, 0.6, version="cal-v2")),
        _row("accepted", None, _risk(0.1, 0.6)),                      # no actual → excluded
    ]
    g = ll.risk_statement_calibration(rows)["groups"]
    assert g["staffing.add|human|cal-v1"]["n_probabilistic"] == 1
    assert g["staffing.add|human|cal-v1"]["mean_stated"] == 0.6 and g["staffing.add|human|cal-v1"]["observed"] == 1.0
    assert g["staffing.add|agent|cal-v1"]["n_probabilistic"] == 1       # never mixed with humans
    assert g["staffing.add|human|cal-v2"]["n_probabilistic"] == 1       # before/after split


def test_qualitative_bands_are_tracked_too():
    rows = [_row("rejected", 120, _risk(None, None, band="likely"), i=i) for i in range(4)]
    g = ll.risk_statement_calibration(rows)["groups"]["staffing.add|human|uncalibrated"]
    assert g["bands"]["likely"] == {"n": 4, "observed": 1.0} and g["n_probabilistic"] == 0


def test_pos_actuals_are_independent():
    rows = [_row("accepted", 120, _risk(0.1, 0.6), source="pos_data")]
    assert ll.risk_statement_calibration(rows)["groups"]["staffing.add|human|cal-v1"]["independent_actuals"]


# ---------------------------------------------------------------------------
# Recalibration from realised outcomes
# ---------------------------------------------------------------------------

def _realised(n, spread=0.15, seed=3, source="manager_feedback"):
    rng = random.Random(seed)
    return [_row("accepted", round(120 * (1 + rng.uniform(-spread, spread))), _risk(None, None), i=i,
                 source=source) for i in range(n)]


def test_recalibration_needs_enough_data():
    p = ll.propose_realised_calibration(_realised(59), tenant_id="h1", forecaster="anomaly-heuristic-v1",
                                        created_at="2026-09-25")
    assert p.ok is False and "60" in p.reason and p.calibration is None


def test_recalibration_passes_canary_and_freeze_rule_and_is_labelled():
    p = ll.propose_realised_calibration(_realised(300), tenant_id="h1", forecaster="anomaly-heuristic-v1",
                                        created_at="2026-09-25")
    assert p.ok, p.reason
    cal = p.calibration
    assert cal.provenance == "realised" and cal.training_data_source == "tenant:h1"
    assert cal.canary_runs == 3 and cal.canary_identical
    assert cal.independent_actuals is False and cal.notes
    assert p.report["n_calibration"] == 200 and p.report["n_test"] == 100  # later third = test


def test_recalibration_refused_when_it_undercovers():
    rows = _realised(60, spread=0.05) + _realised(30, spread=0.5, seed=9)
    for i, r in enumerate(rows):
        r["window_start"] = (NOW + timedelta(days=i)).isoformat()
    p = ll.propose_realised_calibration(rows, tenant_id="h1", forecaster="anomaly-heuristic-v1",
                                        created_at="2026-09-25")
    assert p.ok is False and "under-covers" in p.reason


def test_recalibration_refused_when_not_better_than_active():
    rows = _realised(300)
    first = ll.propose_realised_calibration(rows, tenant_id="h1", forecaster="anomaly-heuristic-v1",
                                            created_at="2026-09-25")
    again = ll.propose_realised_calibration(rows, tenant_id="h1", forecaster="anomaly-heuristic-v1",
                                            created_at="2026-09-26", current=first.calibration)
    assert again.ok is False and "not closer" in again.reason


def test_recalibration_ignores_other_forecasters():
    rows = _realised(90)
    for r in rows:
        r["risk_assessment"] = {**r["risk_assessment"], "forecaster": "prophet-predictionengine-v1"}
    p = ll.propose_realised_calibration(rows, tenant_id="h1", forecaster="anomaly-heuristic-v1",
                                        created_at="2026-09-25")
    assert p.report["n"] == 0


# ---------------------------------------------------------------------------
# Cost proposals — human decisions only, reasons only when human
# ---------------------------------------------------------------------------

def _decisions(n_acc, n_rej, **kw):
    rows = [_row("accepted", None, _risk(0.2, 0.7), i=i, **kw) for i in range(n_acc)]
    rows += [_row("rejected", None, _risk(0.2, 0.7), i=100 + i, **kw) for i in range(n_rej)]
    return rows


def test_revealed_critical_ratio_is_between_the_bounds():
    rcr = ll.revealed_critical_ratio(_decisions(8, 4))
    # accept → CR > F(cap 0) = 0.3 ; reject → CR < F(cap Δ) = 0.8 ; both satisfiable
    assert rcr["n"] == 12 and rcr["violations"] == 0 and 0.3 <= rcr["estimate"] <= 0.8


def test_revealed_ratio_hygiene():
    agent = _decisions(5, 5, decided_by="host_agent_autonomous")
    inferred = _decisions(5, 5, reason="budget", reason_source="agent_inferred")
    forecast = _decisions(5, 5, reason="forecast_too_high")
    assert ll.revealed_critical_ratio(agent + inferred + forecast)["n"] == 0


def test_outcomes_never_change_the_revealed_ratio():
    rows = _decisions(8, 4)
    base = ll.revealed_critical_ratio(rows)
    for r in rows:
        r["actual_covers"] = 999.0
    assert ll.revealed_critical_ratio(rows) == base


def test_lost_cover_value_proposal():
    rows = _decisions(12, 0)  # always accepted → CR high
    params = {"extra_shift_cost": 180.0, "lost_cover_value": 5.0, "covers_per_extra_staff": 20.0}
    props = ll.propose_cost_updates(rows, params)
    lcv = [p for p in props if p["parameter"] == "lost_cover_value"][0]
    cr = lcv["evidence"]["estimate"]
    assert lcv["proposed_value"] == round(180 * cr / ((1 - cr) * 20), 2)
    assert lcv["current_value"] == 5.0 and lcv["rule"] == "revealed_critical_ratio_v1"
    # below the minimum number of decisions → nothing
    assert ll.propose_cost_updates(_decisions(3, 0), params) == []


def test_max_extra_staff_proposal_from_constraint_rejections():
    small = [_row("accepted", None, _risk(0.2, 0.7, delta=1), i=i) for i in range(3)]
    big = [_row("rejected", None, _risk(0.2, 0.7, delta=3), reason="staffing_constraint", i=10 + i)
           for i in range(3)]
    inferred = [_row("rejected", None, _risk(0.2, 0.7, delta=3), reason="staffing_constraint",
                     reason_source="agent_inferred", i=20 + i) for i in range(5)]
    props = ll.propose_cost_updates(small + big, {"max_extra_staff": None})
    cap = [p for p in props if p["parameter"] == "max_extra_staff"][0]
    assert cap["proposed_value"] == 1.0 and cap["evidence"]["rejections_staffing_constraint"] == 3
    assert not [p for p in ll.propose_cost_updates(small + inferred, {}) if p["parameter"] == "max_extra_staff"]


def test_route_override():
    item = ll.route_override({"id": "e1", "reason_route": "case_set", "reason_text": "x",
                              "reason_route_confidence": 0.8, "recommendation_id": None})
    assert item["kind"] == "eval_case" and item["reviewer"] == "ivan" and item["route_source"] == "model_suggestion"
    assert ll.route_override({"id": "e2", "reason_route": None}) is None
    assert {v[0] for v in ll.ROUTE_DESTINATIONS.values()} == {
        "memory_note", "decision_rule_note", "policy_note", "eval_case", "upstream_filter_note"}


# ---------------------------------------------------------------------------
# Store — review, application, rollback (SQLite)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def db():
    from app.db.models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:",
                                 connect_args={"check_same_thread": False}, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


OWNER = {"id": "u1", "email": "gm@hotel", "is_superuser": False}
IVAN = {"id": "u0", "email": "ivan@aetherix", "is_superuser": True}


@pytest.mark.asyncio
async def test_cost_proposal_applied_only_on_approval_with_provenance(db):
    from app.services import hotel_parameters as hp
    from app.services import learning_store as ls

    item = await ls.add_item(db, "h1", "cost_parameter", "lost_cover_value",
                             {"parameter": "lost_cover_value", "proposed_value": 21.5, "rule": "r"})
    assert (await hp.load(db, "h1")).get("lost_cover_value") is None  # proposing applies nothing
    newer = await ls.add_item(db, "h1", "cost_parameter", "lost_cover_value",
                              {"parameter": "lost_cover_value", "proposed_value": 22.0, "rule": "r"})
    assert item.status == "superseded"
    out = await ls.decide(db, "h1", str(newer.id), approve=True, actor=OWNER, note="ok")
    assert out["status"] == "applied" and out["decided_by"] == "gm@hotel"
    pv = (await hp.load(db, "h1")).values["lost_cover_value"]
    assert pv.value == 22.0 and pv.set_via == "proposal_approval" and f"proposal:{newer.id}" in pv.set_by
    with pytest.raises(ls.LearningError):
        await ls.decide(db, "h1", str(newer.id), approve=True, actor=OWNER)  # 409 already decided
    with pytest.raises(ls.LearningError):
        await ls.decide(db, "h2", str(newer.id), approve=True, actor=OWNER)  # other tenant → 404


@pytest.mark.asyncio
async def test_ivan_only_kinds_and_eval_case_needs_the_reviewers_case(db):
    from app.services import learning_store as ls

    case_item = await ls.add_item(db, "h1", "eval_case", "case_set", {"reason_text": "x"}, source_ref="e1")
    assert (await ls.add_item(db, "h1", "eval_case", "case_set", {"reason_text": "x"}, source_ref="e1")).id == case_item.id
    with pytest.raises(ls.LearningError) as exc:
        await ls.decide(db, "h1", str(case_item.id), approve=True, actor=OWNER)
    assert exc.value.status == 403
    with pytest.raises(ls.LearningError) as exc:
        await ls.decide(db, "h1", str(case_item.id), approve=True, actor=IVAN, case={"id": "Bad Id"})
    assert exc.value.status == 422
    case = {"id": "parser-learned-case-001", "category": "parser_intent", "layer": "parser",
            "input": {"message": "on garde 4 serveurs", "language": "fr"},
            "expected": {"decision": "rejected"}, "failure_trigger": "decision != rejected"}
    out = await ls.decide(db, "h1", str(case_item.id), approve=True, actor=IVAN, case=case)
    assert out["status"] == "approved" and out["payload"]["case"]["id"] == case["id"]


@pytest.mark.asyncio
async def test_calibration_activation_and_rollback(db):
    from app.services import learning_store as ls

    def _cal(v):
        c = fc.fit([-0.1, 0.0, 0.1], version=v, forecaster="anomaly-heuristic-v1",
                   provenance="realised", created_at="2026-09-25")
        return {"version": v, "calibration": c.to_dict()}

    assert await ls.active_calibration(db, "h1", "anomaly-heuristic-v1") is None
    a = await ls.add_item(db, "h1", "calibration", "anomaly-heuristic-v1", _cal("v1"))
    await ls.decide(db, "h1", str(a.id), approve=True, actor=IVAN, now=NOW)
    b = await ls.add_item(db, "h1", "calibration", "anomaly-heuristic-v1", _cal("v2"))
    with pytest.raises(ls.LearningError):
        await ls.decide(db, "h1", str(b.id), approve=True, actor=OWNER)
    await ls.decide(db, "h1", str(b.id), approve=True, actor=IVAN, now=NOW + timedelta(days=7))
    assert (await ls.active_calibration(db, "h1", "anomaly-heuristic-v1")).version == "v2"
    assert a.status == "retired"
    with pytest.raises(ls.LearningError):
        await ls.rollback_calibration(db, "h1", "anomaly-heuristic-v1", OWNER)
    out = await ls.rollback_calibration(db, "h1", "anomaly-heuristic-v1", IVAN, now=NOW + timedelta(days=8))
    assert out == {"retired": str(b.id), "reapplied": str(a.id)}
    assert (await ls.active_calibration(db, "h1", "anomaly-heuristic-v1")).version == "v1"
    assert await ls.active_calibration(db, "h2", "anomaly-heuristic-v1") is None  # tenant-scoped


@pytest.mark.asyncio
async def test_run_pass_proposes_and_never_applies(db):
    from app.db.models import InboundReplyEvent, StaffingRecommendation
    from app.services import hotel_parameters as hp
    from app.services import learning_store as ls

    rng = random.Random(5)
    for i in range(90):
        risk = _risk(0.25, 0.8)
        db.add(StaffingRecommendation(
            tenant_id="h1", property_id=uuid.uuid4(), anomaly_id=uuid.uuid4(), message_text="m",
            window_start=NOW - timedelta(days=100 - i), window_end=NOW - timedelta(days=100 - i, hours=-4),
            status="accepted", decided_by="human_whatsapp", reason_source="human",
            risk_assessment=risk, predicted_covers=120,
            actual_covers=round(120 * (1 + rng.uniform(-0.15, 0.15))), actual_covers_source="manager_feedback",
            created_at=NOW - timedelta(days=100 - i),
        ))
    db.add(InboundReplyEvent(tenant_id="h1", channel="text", result="reason_captured",
                             reason_text="grosse erreur de prévision", reason_route="case_set",
                             reason_route_confidence=0.9, created_at=NOW - timedelta(days=3)))
    await db.commit()
    out = await ls.run_pass(db, "h1", now=NOW)
    await db.commit()
    assert out["rows"] == 90
    assert out["calibration_proposal"]["ok"] is True
    items = await ls.list_items(db, "h1")
    kinds = sorted(i["kind"] for i in items)
    assert kinds == ["calibration", "eval_case"]
    assert all(i["status"] == "proposed" for i in items)
    assert await ls.active_calibration(db, "h1", "anomaly-heuristic-v1") is None  # not applied
    assert (await hp.load(db, "h1")).values == {}
    cal_item = [i for i in items if i["kind"] == "calibration"][0]
    assert cal_item["independent_actuals"] is False and cal_item["reviewer_role"] == "ivan"
    # a second pass does not duplicate the routed reason
    await ls.run_pass(db, "h1", now=NOW)
    assert len([i for i in await ls.list_items(db, "h1") if i["kind"] == "eval_case"]) == 1


@pytest.mark.asyncio
async def test_export_appends_reviewed_cases_to_the_dataset(db, tmp_path):
    from app.services import learning_store as ls

    dataset = tmp_path / "golden.jsonl"
    dataset.write_text(json.dumps({"id": "existing-001"}) + "\n", encoding="utf-8")
    it = await ls.add_item(db, "h1", "eval_case", "case_set", {"reason_text": "x"}, source_ref="e9")
    case = {"id": "parser-learned-case-002", "category": "parser_intent", "layer": "parser",
            "input": {"message": "non, 3 suffisent"}, "expected": {"decision": "rejected"},
            "failure_trigger": "decision != rejected"}
    await ls.decide(db, "h1", str(it.id), approve=True, actor=IVAN, case=case)
    written = await ls.export_approved_cases(db, dataset, today="2026-09-25")
    assert written == ["parser-learned-case-002"]
    last = json.loads(dataset.read_text(encoding="utf-8").splitlines()[-1])
    assert last["author"] == "ivan@aetherix" and last["created_at"] == "2026-09-25"
    assert it.status == "applied"
    assert await ls.export_approved_cases(db, dataset, today="2026-09-25") == []  # idempotent


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_learning_routes_are_tenant_scoped(db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.routes import learning as route
    from app.core.security import get_current_user
    from app.db.models import RestaurantProfile
    from app.db.session import get_db
    from app.services import learning_store as ls

    owner_id = "c1b2c3d4-0000-4000-8000-00000000000c"
    db.add(RestaurantProfile(tenant_id="h1", property_name="P", outlet_name="O", total_seats=80,
                             owner_id=uuid.UUID(owner_id)))
    item = await ls.add_item(db, "h1", "cost_parameter", "max_extra_staff",
                             {"parameter": "max_extra_staff", "proposed_value": 2.0, "rule": "r"})
    await db.commit()

    app = FastAPI()
    app.include_router(route.router, prefix="/api/v1")

    async def _db():
        yield db

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: {"id": "someone", "email": "x@y", "is_superuser": False}
    with TestClient(app) as c:
        assert c.get("/api/v1/hotels/h1/learning/items").status_code == 403
        assert c.post(f"/api/v1/hotels/h1/learning/items/{item.id}/approve", json={}).status_code == 403
    app.dependency_overrides[get_current_user] = lambda: {"id": owner_id, "email": "gm@h1", "is_superuser": False}
    with TestClient(app) as c:
        assert c.get("/api/v1/hotels/h1/learning/report").json()["rows"] == 0
        r = c.post(f"/api/v1/hotels/h1/learning/items/{item.id}/approve", json={"note": "yes"})
        assert r.status_code == 200 and r.json()["status"] == "applied"
        assert c.post("/api/v1/hotels/h1/learning/calibration/rollback", json={}).status_code == 403
