"""Risk-based recommendation — the decision rule, and what each option risks.

ADR-0007 §18.4 (Décision #40). For a quantity decided under uncertain demand
(staff to schedule for a service window), the recommendation is derived from
the asymmetric loss — the **newsvendor rule** — and states, per option, what
happens if it is accepted and what happens if it is refused. Deterministic,
no prose, no LLM.

Newsvendor (``newsvendor-v1``), in staff units:

* one extra staff member serves ``c`` covers (``covers_per_extra_staff``);
* overage cost ``co`` = one shift too many = ``extra_shift_cost``;
* underage cost ``cu`` = one staff member short = ``c × lost_cover_value``;
* critical ratio ``CR = cu / (cu + co)``; staff for the demand quantile
  ``Q = F⁻¹(CR)`` from the **calibrated** distribution (§18.2):
  ``Δstaff = ceil((Q − baseline) / c)``, within the hotel's caps.
* Assumption, stated: the usual staffing is sized for ``baseline`` covers, so
  capacity with Δ extra staff is ``baseline + Δ·c``.

The rule needs a calibration **for the forecaster in use** and the hotel's
costs. Any missing input → the previous rule (``deviation-scale-v1``, ROI
headcount scale) stays the recommendation, and the missing inputs are
recorded. Consequences follow the same honesty rules:

* a **probability** only from a calibration of this forecaster, labelled with
  its provenance (``synthetic-calibrated`` / ``calibrated-on-realised``);
* **money** only from configured costs (``hotel_parameters``);
* otherwise a qualitative band, said to be qualitative.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Optional

from app.core import config
from app.core.money import currency_code, format_money
from app.services.forecast_calibration import Calibration
from app.services.hotel_parameters import HotelParameters
from app.services.task_classes import TaskClassKey

SCHEMA = "risk-assessment-v1"
RULE_NEWSVENDOR = "newsvendor-v1"
RULE_FALLBACK = "deviation-scale-v1"

# Forecaster identity of the anomaly-detection heuristic (baseline × weather /
# event modifiers) that produces dispatched staffing recommendations. No
# calibration exists for it until realised covers produce one (§18.5).
ANOMALY_FORECASTER = "anomaly-heuristic-v1"

# When the hotel set no cap, Δstaff stays within the previous rule's range.
DEFAULT_MAX_DELTA = 4


# Qualitative band thresholds on (capacity − point forecast) / point forecast.
_BAND = 0.10


@dataclass(frozen=True)
class Inputs:
    task_class: TaskClassKey
    point_forecast: float           # covers expected in the window
    baseline_covers: float          # covers the usual staffing is sized for
    fallback_delta_staff: int       # previous rule's recommendation
    forecaster: str
    calibration: Optional[Calibration]
    params: HotelParameters
    covers_per_staff: Optional[float] = None       # from params, else profile ratio
    covers_per_staff_source: Optional[str] = None  # hotel_parameter | profile_ratio


def _round(x: Optional[float], nd: int = 2) -> Optional[float]:
    return None if x is None else round(float(x), nd)


def _qualitative(capacity: float, yhat: float) -> str:
    if yhat <= 0:
        return "unlikely"
    gap = (capacity - yhat) / yhat
    if gap < -_BAND:
        return "likely"
    if gap > _BAND:
        return "unlikely"
    return "possible"


def _option(inp: Inputs, delta: int, co: Optional[float], cu_cover: Optional[float]) -> dict:
    c = inp.covers_per_staff
    capacity = None if c is None else inp.baseline_covers + delta * c
    out: dict[str, Any] = {
        "delta_staff": delta,
        "capacity_covers": _round(capacity, 1),
        "extra_shift_cost": _round(delta * co) if co is not None else None,
        "shortfall_probability": None,
        "shortfall_probability_resolution": None,
        "expected_shortfall_covers": None,
        "expected_idle_covers": None,
        "expected_shortfall_value": None,
        "expected_total_cost": None,
        "qualitative_shortfall": None,
    }
    if capacity is None:
        return out
    cal = inp.calibration
    if cal is None:
        out["qualitative_shortfall"] = _qualitative(capacity, inp.point_forecast)
        return out
    p_le, resolution = cal.prob_at_or_below(inp.point_forecast, capacity)
    out["shortfall_probability"] = round(1.0 - p_le, 4)
    out["shortfall_probability_resolution"] = resolution
    short = cal.expected_shortfall(inp.point_forecast, capacity)
    out["expected_shortfall_covers"] = _round(short, 1)
    out["expected_idle_covers"] = _round(cal.expected_excess(inp.point_forecast, capacity), 1)
    if cu_cover is not None:
        out["expected_shortfall_value"] = _round(short * cu_cover)
        if co is not None:
            out["expected_total_cost"] = _round(delta * co + short * cu_cover)
    return out


def assess(inp: Inputs) -> dict:
    """The typed risk assessment for one recommendation (stored as JSON on the
    recommendation, served by MCP, rendered by ``render_lines``)."""
    p = inp.params
    co = p.get("extra_shift_cost")
    cu_cover = p.get("lost_cover_value")
    c = inp.covers_per_staff
    cal = inp.calibration

    missing: list[str] = []
    if cal is None:
        missing.append(f"calibration:{inp.forecaster}")
    if co is None:
        missing.append("extra_shift_cost")
    if cu_cover is None:
        missing.append("lost_cover_value")
    if c is None:
        missing.append("covers_per_extra_staff")

    max_add = p.get("max_extra_staff")
    max_cut = p.get("max_staff_reduction")
    hi = int(max_add) if max_add is not None else DEFAULT_MAX_DELTA
    lo = -int(max_cut) if max_cut is not None else -DEFAULT_MAX_DELTA

    cr = quantile = None
    if not missing:
        cu = c * cu_cover
        cr = cu / (cu + co)
        quantile = cal.quantile(inp.point_forecast, cr)
        delta = math.ceil((quantile - inp.baseline_covers) / c - 1e-9)
        delta = max(lo, min(hi, delta))
        rule = RULE_NEWSVENDOR
    else:
        delta = inp.fallback_delta_staff
        rule = RULE_FALLBACK

    accept = _option(inp, delta, co, cu_cover)
    refuse = _option(inp, 0, co, cu_cover)

    # Interruption budget (§18.4): is the gap between the options material?
    gap = None
    if accept["expected_total_cost"] is not None and refuse["expected_total_cost"] is not None:
        gap = abs(accept["expected_total_cost"] - refuse["expected_total_cost"])
        threshold = p.get("risk_display_min_gap")
        basis = "money_gap_hotel_threshold"
        if threshold is None:
            threshold, basis = config.RISK_DISPLAY_MIN_GAP_DEFAULT, "money_gap_default_threshold"
        material = gap >= threshold
    elif accept["shortfall_probability"] is not None and refuse["shortfall_probability"] is not None:
        material = (
            abs(accept["shortfall_probability"] - refuse["shortfall_probability"])
            >= config.RISK_DISPLAY_MIN_PROB_GAP
        )
        basis = "probability_gap"
    else:
        material, basis = False, "not_quantified"
    if delta == 0:
        material = False  # both options are the same action

    interval = None
    if cal is not None:
        lo_i, hi_i = cal.interval(inp.point_forecast)
        interval = [_round(lo_i, 1), _round(hi_i, 1)]

    return {
        "schema": SCHEMA,
        "task_class": inp.task_class.value,
        "decision_rule": rule,
        "fallback_missing_inputs": missing if rule == RULE_FALLBACK else [],
        "forecaster": inp.forecaster,
        "point_forecast": _round(inp.point_forecast, 1),
        "baseline_covers": _round(inp.baseline_covers, 1),
        "baseline_assumption": "usual staffing is sized for baseline_covers",
        "covers_per_staff": _round(c, 1),
        "covers_per_staff_source": inp.covers_per_staff_source,
        "uncertainty": {
            "status": "calibrated" if cal is not None else "uncalibrated",
            "calibration_version": cal.version if cal else None,
            "provenance": cal.provenance if cal else None,
            "label": (
                ("synthetic-calibrated" if cal.provenance == "synthetic" else "calibrated-on-realised")
                if cal else "qualitative"
            ),
            "nominal_level": cal.nominal_level if cal else None,
            "interval": interval,
        },
        "costs": {
            "status": "configured" if (co is not None and cu_cover is not None) else "missing",
            "currency": currency_code(),
            "extra_shift_cost": co,
            "lost_cover_value": cu_cover,
            "parameters_version": p.version(),
        },
        "critical_ratio": _round(cr, 4),
        "demand_quantile": _round(quantile, 1),
        "recommended_delta_staff": delta,
        "options": {"accept": accept, "refuse": refuse},
        "expected_cost_gap": _round(gap),
        "material": bool(material),
        "material_basis": basis,
    }


# ---------------------------------------------------------------------------
# Rendering — one deterministic line per option (FR default / EN)
# ---------------------------------------------------------------------------

_T = {
    "fr": {
        "accept": "Si accepté", "refuse": "Si refusé", "sep": " : ", "join": " ; ",
        "shifts_add": "+{n} extra{s}", "shifts_cut": "−{n} poste{s}", "shifts_none": "aucun changement",
        "cost": " ({m})", "saving": " (économie {m})",
        "p": "risque de manquer de bras ≈{p} %, ~{c} couverts",
        "p_value": " (≈{m})",
        "q": {"likely": "manque de bras probable si la prévision se confirme",
              "possible": "manque de bras possible",
              "unlikely": "manque de bras peu probable"},
        "label": {"synthetic-calibrated": "incertitude calibrée sur données synthétiques",
                  "calibrated-on-realised": "incertitude calibrée sur couverts réels",
                  "qualitative": "qualitatif, incertitude non calibrée"},
    },
    "en": {
        "accept": "If accepted", "refuse": "If refused", "sep": ": ", "join": "; ",
        "shifts_add": "+{n} shift{s}", "shifts_cut": "−{n} shift{s}", "shifts_none": "no change",
        "cost": " ({m})", "saving": " (saves {m})",
        "p": "shortfall risk ≈{p}%, ~{c} covers",
        "p_value": " (≈{m})",
        "q": {"likely": "shortfall likely if the forecast holds",
              "possible": "shortfall possible",
              "unlikely": "shortfall unlikely"},
        "label": {"synthetic-calibrated": "synthetic-calibrated uncertainty",
                  "calibrated-on-realised": "calibrated on realised covers",
                  "qualitative": "qualitative, uncertainty not calibrated"},
    },
}


def _loc(locale: Optional[str]) -> str:
    return "en" if (locale or "").lower().startswith("en") else "fr"


def _pct(p: float) -> int:
    """Probability → nearest 5 %, never 0 or 100 (the grid does not resolve them)."""
    return int(min(95, max(5, 5 * round(p * 100 / 5))))


def _line(opt: dict, label_key: str, t: dict, uncertainty_label: str) -> str:
    n = opt["delta_staff"]
    if n > 0:
        shifts = t["shifts_add"].format(n=n, s="s" if n > 1 else "")
    elif n < 0:
        shifts = t["shifts_cut"].format(n=-n, s="s" if n < -1 else "")
    else:
        shifts = t["shifts_none"]
    if opt["extra_shift_cost"] is not None and n != 0:
        m = format_money(abs(opt["extra_shift_cost"]))
        shifts += (t["cost"] if n > 0 else t["saving"]).format(m=m)
    head = f"{t[label_key]}{t['sep']}{shifts}"
    if opt["shortfall_probability"] is not None:
        risk = t["p"].format(p=_pct(opt["shortfall_probability"]),
                             c=f"{opt['expected_shortfall_covers']:g}")
        if opt["expected_shortfall_value"] is not None:
            risk += t["p_value"].format(m=format_money(opt["expected_shortfall_value"]))
    elif opt["qualitative_shortfall"] is not None:
        risk = t["q"][opt["qualitative_shortfall"]]
    else:
        return f"{head}."
    return f"{head}{t['join']}{risk} ({t['label'][uncertainty_label]})."


def render_lines(assessment: dict, locale: Optional[str] = "fr") -> list[str]:
    """Two lines: "If accepted: …" and "If refused: …"."""
    t = _T[_loc(locale)]
    label = assessment["uncertainty"]["label"]
    return [
        _line(assessment["options"]["accept"], "accept", t, label),
        _line(assessment["options"]["refuse"], "refuse", t, label),
    ]
