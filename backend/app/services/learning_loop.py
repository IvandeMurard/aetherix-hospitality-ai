"""The learning loop — pure functions (ADR-0007 §18.5, Décision #40).

The outcome loop must change the system, not only measure it — under
safeguards. This module computes; it never writes a decision, never activates
anything, never applies a cost. What it produces are **reports** (arm C, with
arm B alerts) and **proposals** that a named person approves
(``learning_store``). End-to-end description: ``docs/context/learning-loop.md``.

Inputs are plain dicts built from ``staffing_recommendations`` rows
(``learning_store.recommendation_rows``): ``id``, ``tenant_id``, ``status``,
``decided_by``, ``reason_code``, ``reason_source``, ``decision_rule``,
``risk_assessment`` (as stored at issue time), ``predicted_covers``,
``actual_covers``, ``actual_covers_source``, ``window_start``.

Learning hygiene, enforced here (tested):

1. Human-decided and agent-decided records stay separate: every report is
   split by ``decided_by`` group; cost proposals read **human** decisions only.
2. Agent-inferred reasons are never ground truth: a reason with
   ``reason_source = agent_inferred`` is ignored by every reason-conditional
   rule (the decision itself is still a human's if ``decided_by`` says so).
3. Outcomes never relabel decisions: no function here reads an outcome to
   change a decision; outcome and decision stay two variables.
4. Actuals declared by the manager are **not independent** of the decision
   loop (§16.6): every report and proposal carries ``independent_actuals``,
   false until POS/PMS actuals exist.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional

from app.services import forecast_calibration as fc

HUMAN_DECIDERS = ("human_whatsapp", "human_via_host")
AGENT_DECIDERS = ("host_agent_autonomous",)
INDEPENDENT_SOURCES = ("pos_data", "pms_data")

# Arm C risk-statement calibration: minimum n before a miscalibration alert.
RISK_CALIBRATION_MIN_N = 30
RISK_CALIBRATION_MIN_TOLERANCE = 0.10
# Realised recalibration: minimum residuals, test share, freeze tolerance.
RECALIBRATION_MIN_N = 60
RECALIBRATION_TEST_SHARE = 1 / 3
RECALIBRATION_MAX_UNDERCOVER_PP = 5.0
RECALIBRATION_CANARY_RUNS = 3
# Cost proposals: minimum human decisions, relative change worth proposing.
COST_PROPOSAL_MIN_N = 10
COST_PROPOSAL_MIN_CHANGE = 0.25
CONSTRAINT_PROPOSAL_MIN_N = 3
# Reasons that say "the forecast / the data is wrong": such a decision
# disagrees with the forecast, not with the cost trade-off → excluded from the
# revealed critical ratio.
FORECAST_REASONS = (
    "forecast_too_high", "forecast_too_low", "event_not_in_forecast",
    "event_cancelled", "data_issue", "already_handled", "other",
)


def decider_group(decided_by: Optional[str]) -> str:
    if decided_by in HUMAN_DECIDERS:
        return "human"
    if decided_by in AGENT_DECIDERS:
        return "agent"
    return "unattributed"


def human_reason(row: Mapping) -> Optional[str]:
    """The reason code only when a human gave it (hygiene rule 2)."""
    if row.get("reason_source") != "human":
        return None
    return row.get("reason_code")


def _independent(sources: Iterable[str]) -> bool:
    sources = list(sources)
    return bool(sources) and all(s in INDEPENDENT_SOURCES for s in sources)


# ---------------------------------------------------------------------------
# 1. Arm C — were the risk statements calibrated?
# ---------------------------------------------------------------------------

def _taken_option(row: Mapping) -> Optional[str]:
    """The option the hotel actually took. ``modified`` (another quantity) and
    undecided rows have no stated risk for what happened → excluded."""
    return {"accepted": "accept", "rejected": "refuse"}.get(row.get("status"))


def risk_statement_calibration(rows: Iterable[Mapping]) -> dict:
    """When the system said "≈25 %", did the shortfall happen about 1 in 4?

    One observation per decided recommendation with a realised actual: the
    option taken, its stated shortfall probability (or qualitative band) and
    whether actual covers exceeded that option's capacity. Grouped by task
    class × decider group × calibration version (before/after split), with
    Brier score, reliability bins and the qualitative bands' realised
    frequencies. ``miscalibrated`` = |observed − mean stated| beyond
    max(10 pp, 2 binomial SE), only from ``RISK_CALIBRATION_MIN_N``.
    """
    groups: dict[str, dict] = {}
    for row in rows:
        ra = row.get("risk_assessment")
        option = _taken_option(row)
        if not isinstance(ra, Mapping) or option is None or row.get("actual_covers") is None:
            continue
        opt = (ra.get("options") or {}).get(option) or {}
        capacity = opt.get("capacity_covers")
        if capacity is None:
            continue
        happened = float(row["actual_covers"]) > float(capacity)
        key = "|".join((
            str(ra.get("task_class") or row.get("task_class") or "unknown"),
            decider_group(row.get("decided_by")),
            str((ra.get("uncertainty") or {}).get("calibration_version") or "uncalibrated"),
        ))
        g = groups.setdefault(key, {"p": [], "hit": [], "bands": defaultdict(lambda: [0, 0]),
                                    "sources": []})
        g["sources"].append(str(row.get("actual_covers_source") or "unknown"))
        p = opt.get("shortfall_probability")
        if p is not None:
            g["p"].append(float(p))
            g["hit"].append(int(happened))
        band = opt.get("qualitative_shortfall")
        if band:
            g["bands"][band][0] += int(happened)
            g["bands"][band][1] += 1

    out: dict[str, dict] = {}
    for key, g in sorted(groups.items()):
        task_class, decider, version = key.split("|")
        n = len(g["p"])
        entry: dict = {
            "task_class": task_class, "decider": decider, "calibration_version": version,
            "n_probabilistic": n,
            "independent_actuals": _independent(g["sources"]),
            "actuals_source": dict(_count(g["sources"])),
            "bands": {b: {"n": v[1], "observed": round(v[0] / v[1], 4)}
                      for b, v in sorted(g["bands"].items())},
            "mean_stated": None, "observed": None, "brier": None,
            "reliability": [], "miscalibrated": None,
        }
        if n:
            mean_p = sum(g["p"]) / n
            obs = sum(g["hit"]) / n
            entry["mean_stated"] = round(mean_p, 4)
            entry["observed"] = round(obs, 4)
            entry["brier"] = round(sum((p - h) ** 2 for p, h in zip(g["p"], g["hit"])) / n, 4)
            entry["reliability"] = _bins(g["p"], g["hit"])
            if n >= RISK_CALIBRATION_MIN_N:
                tol = max(RISK_CALIBRATION_MIN_TOLERANCE, 2 * math.sqrt(max(mean_p * (1 - mean_p), 1e-6) / n))
                entry["miscalibrated"] = abs(obs - mean_p) > tol
                entry["tolerance"] = round(tol, 4)
        out[key] = entry
    return {"groups": out}


def _count(xs: Iterable[str]) -> dict[str, int]:
    c: dict[str, int] = defaultdict(int)
    for x in xs:
        c[x] += 1
    return c


def _bins(ps: list[float], hits: list[int], edges=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0001)) -> list[dict]:
    out = []
    for lo, hi in zip(edges, edges[1:]):
        idx = [i for i, p in enumerate(ps) if lo <= p < hi]
        if idx:
            out.append({
                "bin": f"{lo:.1f}-{min(hi, 1.0):.1f}", "n": len(idx),
                "mean_stated": round(sum(ps[i] for i in idx) / len(idx), 4),
                "observed": round(sum(hits[i] for i in idx) / len(idx), 4),
            })
    return out


def miscalibration_alerts(report: Mapping) -> list[dict]:
    """Arm B signals from an arm C report: one typed alert per miscalibrated
    group (reason ``risk_statement_miscalibrated``)."""
    alerts = []
    for key, g in (report.get("groups") or {}).items():
        if g.get("miscalibrated"):
            alerts.append({
                "reason": "risk_statement_miscalibrated",
                "group": key,
                "n": g["n_probabilistic"],
                "mean_stated": g["mean_stated"],
                "observed": g["observed"],
                "tolerance": g.get("tolerance"),
                "independent_actuals": g["independent_actuals"],
            })
    return alerts


# ---------------------------------------------------------------------------
# 2. Recalibration of the forecast uncertainty from realised outcomes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CalibrationProposal:
    calibration: Optional[fc.Calibration]
    ok: bool
    reason: str
    report: dict


def _realised_pairs(rows: Iterable[Mapping], forecaster: str) -> list[tuple[str, float, float, str]]:
    pairs = []
    for r in rows:
        ra = r.get("risk_assessment") if isinstance(r.get("risk_assessment"), Mapping) else {}
        if (ra.get("forecaster") or forecaster) != forecaster:
            continue
        if r.get("actual_covers") is None or r.get("predicted_covers") is None:
            continue
        if float(r["predicted_covers"]) <= 0:
            continue
        pairs.append((
            str(r.get("window_start") or ""), float(r["actual_covers"]),
            float(r["predicted_covers"]), str(r.get("actual_covers_source") or "unknown"),
        ))
    return sorted(pairs)  # temporal order (ISO timestamps sort chronologically)


def propose_realised_calibration(
    rows: Iterable[Mapping],
    *,
    tenant_id: str,
    forecaster: str,
    created_at: str,
    current: Optional[fc.Calibration] = None,
    nominal_level: float = fc.NOMINAL_LEVEL_DEFAULT,
) -> CalibrationProposal:
    """A calibration fitted on the earlier realised residuals of this tenant ×
    forecaster, validated on the later ones (disjoint in time), with the
    canary rule (``RECALIBRATION_CANARY_RUNS`` identical recomputations) and
    the freeze rule of §18.2: closer to nominal than the ``current`` one on
    the same test set (when there is one) and not under-covering by more than
    5 pp. Returns a proposal, never an active calibration."""
    pairs = _realised_pairs(rows, forecaster)
    report: dict = {"n": len(pairs), "tenant_id": tenant_id, "forecaster": forecaster,
                    "nominal_level": nominal_level,
                    "independent_actuals": _independent(p[3] for p in pairs)}
    if len(pairs) < RECALIBRATION_MIN_N:
        return CalibrationProposal(None, False, f"n={len(pairs)} < {RECALIBRATION_MIN_N}", report)
    n_test = max(1, int(round(len(pairs) * RECALIBRATION_TEST_SHARE)))
    calib, test = pairs[:-n_test], pairs[-n_test:]

    def _fit() -> fc.Calibration:
        return fc.fit(
            (fc.relative_residual(a, y) for _, a, y, _ in calib),
            version=f"{forecaster}-{tenant_id}-{created_at}",
            forecaster=forecaster, provenance="realised",
            created_at=created_at, nominal_level=nominal_level,
        )

    runs = [_fit() for _ in range(RECALIBRATION_CANARY_RUNS)]
    identical = all(r.to_dict() == runs[0].to_dict() for r in runs[1:])
    cal = runs[0]

    def _coverage(c: fc.Calibration) -> dict:
        return fc.coverage(
            [fc.IntervalRecord(a, *c.interval(y), "all", None) for _, a, y, _ in test], nominal_level
        )

    after = _coverage(cal)
    before = _coverage(current) if current is not None else None
    report.update({
        "n_calibration": len(calib), "n_test": len(test),
        "coverage_after": after["coverage"], "gap_after_pp": after["gap_pp"],
        "coverage_before": before["coverage"] if before else None,
        "gap_before_pp": before["gap_pp"] if before else None,
        "canary_runs": len(runs), "canary_identical": identical,
    })
    cal.training_data_source = f"tenant:{tenant_id}"
    cal.independent_actuals = report["independent_actuals"]
    cal.canary_runs, cal.canary_identical = len(runs), identical
    cal.coverage_after = {"n": after["n"], "coverage": after["coverage"]}
    cal.coverage_before = {"n": before["n"], "coverage": before["coverage"]} if before else None
    if not report["independent_actuals"]:
        cal.notes = ["Actuals are manager-declared: not independent of the decision loop (§16.6)."]

    if not identical:
        return CalibrationProposal(cal, False, "canary: recomputations differ", report)
    if after["gap_pp"] < -RECALIBRATION_MAX_UNDERCOVER_PP:
        return CalibrationProposal(cal, False, f"under-covers by {-after['gap_pp']:g} pp", report)
    if before is not None and abs(after["gap_pp"]) >= abs(before["gap_pp"]):
        return CalibrationProposal(cal, False, "not closer to nominal than the active calibration", report)
    return CalibrationProposal(cal, True, "passes canary and freeze rule", report)


# ---------------------------------------------------------------------------
# 3. Cost parameters — proposals from observed decisions, never applied here
# ---------------------------------------------------------------------------

def _decision_bounds(row: Mapping) -> Optional[tuple[str, float, float]]:
    """Revealed-preference bound on the manager's critical ratio from one human
    decision between Δ>0 extra staff (accept) and none (refuse), under the
    demand distribution the system stated (F). The newsvendor loss is convex,
    so: accepting reveals CR > F(capacity with 0 extra) — otherwise 0 would be
    at least as good; refusing reveals CR < F(capacity with Δ extra) —
    otherwise Δ would be better. Loose but valid bounds. Returns
    (kind, lower, upper) on CR, or None when the row says nothing."""
    ra = row.get("risk_assessment")
    if not isinstance(ra, Mapping) or row.get("status") not in ("accepted", "rejected"):
        return None
    if (ra.get("uncertainty") or {}).get("status") != "calibrated":
        return None
    delta = int((ra.get("options") or {}).get("accept", {}).get("delta_staff") or 0)
    p_acc = (ra.get("options") or {}).get("accept", {}).get("shortfall_probability")
    p_ref = (ra.get("options") or {}).get("refuse", {}).get("shortfall_probability")
    if delta <= 0 or p_acc is None or p_ref is None:
        return None
    f_delta, f_zero = 1.0 - float(p_acc), 1.0 - float(p_ref)
    if row["status"] == "accepted":
        return ("accepted", f_zero, 1.0)
    return ("rejected", 0.0, f_delta)


def revealed_critical_ratio(rows: Iterable[Mapping]) -> dict:
    """Interval-censored estimate of the critical ratio the hotel's managers
    act on, from human decisions on calibrated recommendations whose reason is
    not about the forecast. The estimate is the grid point violating the
    fewest bounds (ties → median of the tied points)."""
    bounds = []
    for r in rows:
        if decider_group(r.get("decided_by")) != "human":
            continue
        if human_reason(r) in FORECAST_REASONS:
            continue
        if r.get("reason_source") == "agent_inferred":
            continue  # hygiene rule 2: we cannot tell whether it was about the forecast
        b = _decision_bounds(r)
        if b is not None:
            bounds.append(b)
    if not bounds:
        return {"n": 0, "estimate": None}
    grid = [k / 100 for k in range(1, 100)]
    violations = [sum(1 for _, lo, hi in bounds if not (lo <= g <= hi)) for g in grid]
    best = min(violations)
    tied = [g for g, v in zip(grid, violations) if v == best]
    est = tied[len(tied) // 2]
    return {
        "n": len(bounds),
        "estimate": est,
        "violations": best,
        "accepted": sum(1 for k, _, _ in bounds if k == "accepted"),
        "rejected": sum(1 for k, _, _ in bounds if k == "rejected"),
    }


def propose_cost_updates(rows: Iterable[Mapping], params: Mapping[str, Optional[float]]) -> list[dict]:
    """Proposals, each with its evidence. Never applied here.

    * ``lost_cover_value`` — implied by the revealed critical ratio, holding the
      observable ``extra_shift_cost`` fixed: ``v = co · CR / ((1 − CR) · c)``;
      proposed only from ``COST_PROPOSAL_MIN_N`` decisions and a ≥ 25 % change.
    * ``max_extra_staff`` — when ≥ 3 human rejections give the human reason
      ``staffing_constraint`` for adding more staff than any accepted addition,
      propose the largest accepted addition.
    """
    rows = list(rows)
    proposals: list[dict] = []
    independent = False  # decisions are the evidence here, not actuals

    co, cu, c = params.get("extra_shift_cost"), params.get("lost_cover_value"), params.get("covers_per_extra_staff")
    rcr = revealed_critical_ratio(rows)
    if co and c and rcr["estimate"] is not None and rcr["n"] >= COST_PROPOSAL_MIN_N and 0 < rcr["estimate"] < 1:
        implied = round(co * rcr["estimate"] / ((1 - rcr["estimate"]) * c), 2)
        if cu is None or abs(implied - cu) / cu >= COST_PROPOSAL_MIN_CHANGE:
            proposals.append({
                "parameter": "lost_cover_value", "current_value": cu, "proposed_value": implied,
                "rule": "revealed_critical_ratio_v1",
                "evidence": {**rcr, "extra_shift_cost": co, "covers_per_extra_staff": c},
                "independent_actuals": independent,
            })

    human = [r for r in rows if decider_group(r.get("decided_by")) == "human"]
    accepted = [
        int(r["risk_assessment"]["recommended_delta_staff"]) for r in human
        if r.get("status") == "accepted" and isinstance(r.get("risk_assessment"), Mapping)
        and int(r["risk_assessment"].get("recommended_delta_staff") or 0) > 0
    ]
    top = max(accepted) if accepted else 0
    constrained = [
        r for r in human
        if r.get("status") == "rejected" and human_reason(r) == "staffing_constraint"
        and isinstance(r.get("risk_assessment"), Mapping)
        and int(r["risk_assessment"].get("recommended_delta_staff") or 0) > top
    ]
    current_cap = params.get("max_extra_staff")
    if len(constrained) >= CONSTRAINT_PROPOSAL_MIN_N and (current_cap is None or top < current_cap):
        proposals.append({
            "parameter": "max_extra_staff", "current_value": current_cap, "proposed_value": float(top),
            "rule": "constraint_rejections_v1",
            "evidence": {"rejections_staffing_constraint": len(constrained),
                         "largest_accepted_addition": top,
                         "recommendation_ids": [str(r.get("id")) for r in constrained][:20]},
            "independent_actuals": independent,
        })
    return proposals


# ---------------------------------------------------------------------------
# 4. Overrides and reasons → destination
# ---------------------------------------------------------------------------

ROUTE_DESTINATIONS = {
    # route           → (learning item kind, who reviews it, what approval does)
    "memory": ("memory_note", "hotel", "kept as operational memory (already written as feedback memory)"),
    "decision_rule": ("decision_rule_note", "hotel", "evidence for a cost / constraint proposal"),
    "policy": ("policy_note", "ivan", "input to the decision policy (ADR-0013, proposed)"),
    "case_set": ("eval_case", "ivan", "becomes an eval case once a reviewer writes the expected output"),
    "upstream_filter": ("upstream_filter_note", "ivan", "review of the input data / anomaly filter"),
}


def route_override(event: Mapping) -> Optional[dict]:
    """A routed reason (``inbound_reply_events.reason_route``) → a learning
    item to review. The route label itself comes from the model at ≥ 0.7
    (§16.5), so it is a *suggestion*: nothing is applied without review."""
    route = event.get("reason_route")
    if route not in ROUTE_DESTINATIONS:
        return None
    kind, reviewer, effect = ROUTE_DESTINATIONS[route]
    return {
        "kind": kind,
        "reviewer": reviewer,
        "effect_on_approval": effect,
        "source_ref": str(event.get("id")),
        "recommendation_id": str(event.get("recommendation_id")) if event.get("recommendation_id") else None,
        "reason_text": event.get("reason_text"),
        "route_confidence": event.get("reason_route_confidence"),
        "route_source": "model_suggestion",
    }

