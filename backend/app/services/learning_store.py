"""The learning loop — storage, review and application (ADR-0007 §18.5).

``learning_loop`` computes; this module persists what it proposes as
``learning_items`` and applies an item **only** when a named person approves
it. Nothing here runs on its own schedule except through
``workers/learning_loop_worker`` (weekly), which only *proposes*.

Who may decide (``reviewer_role``):

* ``hotel`` — cost / constraint proposals and memory / decision-rule notes:
  the hotel's owner (dashboard user owning the tenant) or a superuser (Ivan);
* ``ivan`` — calibration activation and rollback, eval cases, policy and
  upstream-filter notes: superuser only.

Applying:

* ``cost_parameter`` (costs, constraints, and the staffing ratio
  ``covers_per_extra_staff`` since HOS-344) → ``hotel_parameters.set_parameter``
  with ``set_via = "proposal_approval"`` and ``set_by = "<approver>
  (proposal:<id>)"``; ``rollback_parameter`` sets the replaced value again;
* ``calibration`` → the item becomes ``applied`` = the tenant's active
  calibration for that forecaster; the previously applied one is ``retired``.
  ``rollback_calibration`` retires the active one and re-applies the previous
  — the calibration version is rolled back, not the service;
* ``eval_case`` → ``approved`` with the reviewer's case (expected output
  written by the reviewer, never inferred); ``export_approved_cases`` appends
  it to the golden dataset and marks it ``applied``;
* notes → ``approved`` (acknowledged); no automatic side effect.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import forecast_calibration as fc
from app.services import hotel_parameters as hp
from app.services import learning_loop as ll

KINDS = (
    "cost_parameter", "calibration", "eval_case", "memory_note",
    "decision_rule_note", "policy_note", "upstream_filter_note",
)
IVAN_ONLY = ("calibration", "eval_case", "policy_note", "upstream_filter_note")
_KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class LearningError(ValueError):
    """Typed refusal (→ 4xx)."""

    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _json(v: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return None
    return v


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

async def recommendation_rows(db: AsyncSession, tenant_id: str, since: datetime) -> list[dict]:
    from app.db.models import StaffingRecommendation as SR

    recs = (await db.execute(
        select(SR).where(SR.tenant_id == tenant_id, SR.created_at >= since)
    )).scalars().all()
    return [
        {
            "id": r.id, "tenant_id": r.tenant_id, "status": r.status,
            "decided_by": r.decided_by, "reason_code": r.reason_code,
            "reason_source": r.reason_source, "decision_rule": r.decision_rule,
            "task_class": r.task_class, "risk_assessment": _json(r.risk_assessment),
            "predicted_covers": float(r.predicted_covers) if r.predicted_covers is not None else None,
            "actual_covers": float(r.actual_covers) if r.actual_covers is not None else None,
            "actual_covers_source": r.actual_covers_source,
            "window_start": _utc(r.window_start).isoformat() if r.window_start else None,
            "retained_delta_staff": r.retained_delta_staff,
        }
        for r in recs
    ]


async def routed_reason_events(db: AsyncSession, tenant_id: str, since: datetime) -> list[dict]:
    from app.db.models import InboundReplyEvent as E

    rows = (await db.execute(
        select(E).where(E.tenant_id == tenant_id, E.created_at >= since, E.reason_route.isnot(None))
    )).scalars().all()
    return [
        {"id": e.id, "recommendation_id": e.recommendation_id, "reason_route": e.reason_route,
         "reason_text": e.reason_text,
         "reason_route_confidence": float(e.reason_route_confidence) if e.reason_route_confidence is not None else None}
        for e in rows
    ]


# ---------------------------------------------------------------------------
# Proposals
# ---------------------------------------------------------------------------

async def add_item(
    db: AsyncSession, tenant_id: str, kind: str, subject: str, payload: Mapping,
    *, evidence: Optional[Mapping] = None, independent_actuals: Optional[bool] = None,
    source_ref: Optional[str] = None, now: Optional[datetime] = None,
):
    """Insert a proposal; an earlier *proposed* item of the same tenant × kind
    × subject is superseded (one open proposal per thing). Items keyed on a
    source event (routed reasons) are never duplicated."""
    from app.db.models import LearningItem

    if kind not in KINDS:
        raise LearningError(422, f"unknown kind {kind!r}")
    if source_ref:
        dup = (await db.execute(select(LearningItem).where(
            LearningItem.tenant_id == tenant_id, LearningItem.kind == kind,
            LearningItem.source_ref == source_ref,
        ))).scalars().first()
        if dup is not None:
            return dup
    else:
        open_items = (await db.execute(select(LearningItem).where(
            LearningItem.tenant_id == tenant_id, LearningItem.kind == kind,
            LearningItem.subject == subject, LearningItem.status == "proposed",
        ))).scalars().all()
        for it in open_items:
            it.status = "superseded"
    item = LearningItem(
        tenant_id=tenant_id, kind=kind, subject=subject, status="proposed",
        reviewer_role="ivan" if kind in IVAN_ONLY else "hotel",
        payload=dict(payload), evidence=dict(evidence) if evidence else None,
        independent_actuals=independent_actuals, source_ref=source_ref,
        created_at=now or datetime.now(timezone.utc),
    )
    db.add(item)
    await db.flush()
    return item


def item_as_dict(it) -> dict:
    return {
        "id": str(it.id), "tenant_id": it.tenant_id, "kind": it.kind, "subject": it.subject,
        "status": it.status, "reviewer_role": it.reviewer_role,
        "payload": _json(it.payload), "evidence": _json(it.evidence),
        "independent_actuals": it.independent_actuals, "source_ref": it.source_ref,
        "created_at": _utc(it.created_at).isoformat() if it.created_at else None,
        "decided_by": it.decided_by,
        "decided_at": _utc(it.decided_at).isoformat() if it.decided_at else None,
        "decision_note": it.decision_note, "applied_ref": it.applied_ref,
    }


async def list_items(db: AsyncSession, tenant_id: str, status: Optional[str] = None) -> list[dict]:
    from app.db.models import LearningItem

    stmt = select(LearningItem).where(LearningItem.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(LearningItem.status == status)
    items = (await db.execute(stmt.order_by(LearningItem.created_at.desc()))).scalars().all()
    return [item_as_dict(i) for i in items]


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------

def _actor_name(actor: Mapping) -> str:
    return str(actor.get("email") or actor.get("id") or "").strip()


def _check_reviewer(item, actor: Mapping) -> None:
    if item.reviewer_role == "ivan" and not actor.get("is_superuser"):
        raise LearningError(403, f"{item.kind} is reviewed by Ivan (superuser) only")
    if not _actor_name(actor):
        raise LearningError(403, "an approver must be identified")


def _validate_case(case: Any) -> dict:
    """Shape check of a reviewer-written eval case. The full dataset validator
    runs again at export (``scripts/eval/export_case_candidates.py``)."""
    if not isinstance(case, Mapping):
        raise LearningError(422, "an eval case needs the reviewer's case object")
    for f in ("id", "category", "layer", "input", "expected", "failure_trigger"):
        if f not in case:
            raise LearningError(422, f"case.{f} required")
    if not _KEBAB.match(str(case["id"])):
        raise LearningError(422, "case.id must be kebab-case")
    if not isinstance(case["input"], Mapping) or not isinstance(case["expected"], Mapping):
        raise LearningError(422, "case.input and case.expected must be objects")
    return dict(case)


async def _get(db: AsyncSession, tenant_id: str, item_id: str):
    from app.db.models import LearningItem

    try:
        iid = uuid.UUID(str(item_id))
    except ValueError:
        raise LearningError(404, "not found") from None
    item = (await db.execute(select(LearningItem).where(
        LearningItem.id == iid, LearningItem.tenant_id == tenant_id,
    ))).scalars().first()
    if item is None:
        raise LearningError(404, "not found")
    return item


async def decide(
    db: AsyncSession, tenant_id: str, item_id: str, *, approve: bool, actor: Mapping,
    note: Optional[str] = None, case: Optional[Mapping] = None, now: Optional[datetime] = None,
) -> dict:
    """Approve or reject a proposed item; approving applies it (see module
    docstring). Commits nothing: the caller owns the transaction."""
    from app.db.models import LearningItem

    item = await _get(db, tenant_id, item_id)
    if item.status != "proposed":
        raise LearningError(409, f"item is {item.status}, not proposed")
    _check_reviewer(item, actor)
    now = now or datetime.now(timezone.utc)
    who = _actor_name(actor)
    item.decided_by, item.decided_at = who, now
    item.decision_note = (note or None) and str(note)[:1000]
    if not approve:
        item.status = "rejected"
        return item_as_dict(item)

    payload = _json(item.payload) or {}
    if item.kind == "cost_parameter":
        row = await hp.set_parameter(
            db, tenant_id, payload["parameter"], payload["proposed_value"],
            set_by=f"{who} (proposal:{item.id})", set_via="proposal_approval",
            note=f"learning proposal {payload.get('rule')}", at=now,
        )
        item.status, item.applied_ref = "applied", f"hotel_decision_parameters:{row['parameter']}@{row['set_at']}"
    elif item.kind == "calibration":
        previous = (await db.execute(select(LearningItem).where(
            LearningItem.tenant_id == tenant_id, LearningItem.kind == "calibration",
            LearningItem.subject == item.subject, LearningItem.status == "applied",
        ))).scalars().all()
        for p in previous:
            p.status = "retired"
        item.status, item.applied_ref = "applied", payload.get("version")
    elif item.kind == "eval_case":
        item.payload = {**payload, "case": _validate_case(case)}
        item.status = "approved"
    else:
        item.status = "approved"
    await db.flush()
    return item_as_dict(item)


async def rollback_parameter(
    db: AsyncSession, tenant_id: str, item_id: str, actor: Mapping, *, now: Optional[datetime] = None,
) -> dict:
    """Undo an applied parameter proposal (HOS-344): set the value it replaced
    again — history stays append-only — and retire the item. Refused when the
    parameter was changed since, so a later choice is never overwritten.
    Commits nothing: the caller owns the transaction."""
    item = await _get(db, tenant_id, item_id)
    if item.kind != "cost_parameter" or item.status != "applied":
        raise LearningError(409, "only an applied parameter proposal can be rolled back")
    _check_reviewer(item, actor)
    payload = _json(item.payload) or {}
    name = payload["parameter"]
    if (await hp.load(db, tenant_id)).get(name) != payload["proposed_value"]:
        raise LearningError(409, f"{name} changed since this proposal was applied: set it directly")
    now = now or datetime.now(timezone.utc)
    row = await hp.set_parameter(
        db, tenant_id, name, payload.get("current_value"),
        set_by=f"{_actor_name(actor)} (rollback:{item.id})", set_via="proposal_approval",
        note=f"rollback of learning proposal {payload.get('rule')}", at=now,
    )
    item.status = "retired"
    item.applied_ref = f"{item.applied_ref} | rolled back {row['set_at']}"
    await db.flush()
    return item_as_dict(item)


async def active_calibration(db: AsyncSession, tenant_id: str, forecaster: str) -> Optional[fc.Calibration]:
    """The tenant's active realised calibration for ``forecaster`` (latest
    applied item), or None."""
    from app.db.models import LearningItem

    items = (await db.execute(select(LearningItem).where(
        LearningItem.tenant_id == tenant_id, LearningItem.kind == "calibration",
        LearningItem.subject == forecaster, LearningItem.status == "applied",
    ).order_by(LearningItem.decided_at.desc()))).scalars().all()
    if not items:
        return None
    cal = fc.Calibration.from_dict((_json(items[0].payload) or {})["calibration"])
    cal.status = "active"
    return cal


async def rollback_calibration(
    db: AsyncSession, tenant_id: str, forecaster: str, actor: Mapping, now: Optional[datetime] = None,
) -> dict:
    """Retire the active calibration and re-apply the one it replaced (if any).
    Superuser only. With no previous one, the forecaster falls back to no
    calibration → qualitative risk statements."""
    from app.db.models import LearningItem

    if not actor.get("is_superuser"):
        raise LearningError(403, "calibration rollback is Ivan's (superuser) only")
    now = now or datetime.now(timezone.utc)
    items = (await db.execute(select(LearningItem).where(
        LearningItem.tenant_id == tenant_id, LearningItem.kind == "calibration",
        LearningItem.subject == forecaster, LearningItem.status.in_(("applied", "retired")),
    ).order_by(LearningItem.decided_at.desc()))).scalars().all()
    active = [i for i in items if i.status == "applied"]
    if not active:
        raise LearningError(409, "no active calibration to roll back")
    current = active[0]
    current.status = "retired"
    current.decision_note = f"rolled back by {_actor_name(actor)} at {now.isoformat()}"
    previous = next((i for i in items if i.status == "retired" and i.id != current.id), None)
    if previous is not None:
        previous.status = "applied"
        previous.decided_at = now
    await db.flush()
    return {"retired": str(current.id), "reapplied": str(previous.id) if previous else None}


# ---------------------------------------------------------------------------
# One learning pass (called by the weekly worker)
# ---------------------------------------------------------------------------

def stored_interval(row: Mapping) -> dict:
    """The interval stored with the recommendation at issue time (arm C)."""
    interval = ((row.get("risk_assessment") or {}).get("uncertainty") or {}).get("interval")
    if not interval:
        return {"interval_lower": None, "interval_upper": None}
    return {"interval_lower": interval[0], "interval_upper": interval[1]}


async def run_pass(
    db: AsyncSession, tenant_id: str, *, now: Optional[datetime] = None,
    lookback_days: int = 180, forecaster: Optional[str] = None,
) -> dict:
    """Compute the arm C report, and write proposals. Never applies anything."""
    from app.services.risk_assessment import ANOMALY_FORECASTER

    forecaster = forecaster or ANOMALY_FORECASTER
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=lookback_days)
    rows = await recommendation_rows(db, tenant_id, since)
    report = ll.risk_statement_calibration(rows)
    alerts = ll.miscalibration_alerts(report)
    coverage = fc.realised_coverage([{**r, **stored_interval(r)} for r in rows])

    created: list[str] = []
    current = await active_calibration(db, tenant_id, forecaster)
    proposal = ll.propose_realised_calibration(
        rows, tenant_id=tenant_id, forecaster=forecaster, created_at=now.date().isoformat(), current=current,
    )
    if proposal.ok and proposal.calibration is not None:
        it = await add_item(
            db, tenant_id, "calibration", forecaster,
            {"version": proposal.calibration.version, "calibration": proposal.calibration.to_dict()},
            evidence=proposal.report, independent_actuals=proposal.report["independent_actuals"], now=now,
        )
        created.append(str(it.id))

    params = await hp.load(db, tenant_id)
    param_values = {k: params.get(k) for k in hp.CATALOG}
    for p in [*ll.propose_cost_updates(rows, param_values), *ll.propose_staffing_ratio(rows, param_values)]:
        it = await add_item(
            db, tenant_id, "cost_parameter", p["parameter"], p,
            evidence=p["evidence"], independent_actuals=p["independent_actuals"], now=now,
        )
        created.append(str(it.id))

    for ev in await routed_reason_events(db, tenant_id, since):
        routed = ll.route_override(ev)
        if routed is None:
            continue
        it = await add_item(
            db, tenant_id, routed["kind"], ev["reason_route"], routed,
            source_ref=routed["source_ref"], now=now,
        )
        created.append(str(it.id))

    return {
        "tenant_id": tenant_id, "rows": len(rows), "risk_calibration": report,
        "alerts": alerts, "interval_coverage": coverage,
        "calibration_proposal": {"ok": proposal.ok, "reason": proposal.reason, "report": proposal.report},
        "items_created": created,
    }


# ---------------------------------------------------------------------------
# Eval cases → golden dataset (after review)
# ---------------------------------------------------------------------------

async def export_approved_cases(db: AsyncSession, dataset: Path, *, today: str) -> list[str]:
    """Append every approved eval case to ``dataset`` (JSONL) in the dated
    zone (``created_at`` = today, ``author`` = the reviewer) and mark it
    applied. The caller validates the resulting file and commits only if it
    is valid (``scripts/eval/export_case_candidates.py``)."""
    from app.db.models import LearningItem

    items = (await db.execute(select(LearningItem).where(
        LearningItem.kind == "eval_case", LearningItem.status == "approved",
    ))).scalars().all()
    existing = {
        json.loads(line).get("id") for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()
    }
    written: list[str] = []
    lines: list[str] = []
    for it in items:
        case = dict((_json(it.payload) or {}).get("case") or {})
        if not case or case.get("id") in existing:
            continue
        case.setdefault("schema_version", "1.0.0")
        case["created_at"] = today
        case["author"] = it.decided_by or "reviewer"
        case.setdefault("notes", f"From learning item {it.id} (case-set-routed override, ADR-0007 §18.5).")
        lines.append(json.dumps(case, ensure_ascii=False))
        it.status, it.applied_ref = "applied", f"golden_dataset:{case['id']}"
        written.append(case["id"])
    if lines:
        with dataset.open("a", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")
    await db.flush()
    return written
