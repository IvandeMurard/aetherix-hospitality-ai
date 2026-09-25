"""Forecast uncertainty calibration — measured, versioned, never assumed.

Why (ADR-0007 §18.2): the forecast eval reported ``interval_coverage_pct``
0.19 for Prophet's nominal 80 % interval — the realised value fell inside it
about one time in five. A risk statement built on that interval would
understate risk. Nothing downstream may show a probability that rests on an
interval whose coverage was not checked.

What this module does (pure, no Prophet, no DB):

* **Coverage** of a nominal interval, overall and per ``category`` × lead time
  (``coverage``).
* **Split-conformal recalibration on relative residuals**: residuals
  ``r = (y − ŷ) / ŷ`` from a *calibration* set give an empirical distribution
  of the error; a forecast ``ŷ`` then has quantiles ``ŷ · (1 + q_r(p))``. The
  rank uses the finite-sample correction (``ceil((n+1)p)`` above the median,
  ``floor((n+1)p)`` below), so the interval is conservative on both sides.
  Coverage is then *checked on a later, disjoint test set* before a
  calibration may be frozen.
* A ``Calibration`` record: forecaster identity, data provenance
  (``synthetic`` | ``realised``), nominal level, quantile grid, measured
  coverage before/after with counts, canary runs, version. A calibration is
  only valid for the forecaster that produced its residuals — the Prophet
  calibration is never applied to the anomaly heuristic, and vice versa.

Honesty rules enforced by consumers (``risk_assessment``):

* ``provenance == "synthetic"`` → every statement that uses it says
  "synthetic-calibrated";
* no calibration for the forecaster in use → no probability, qualitative band
  only.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

NOMINAL_LEVEL_DEFAULT = 0.80
# Quantile grid stored in every calibration: p = 0.01 … 0.99.
GRID: tuple[float, ...] = tuple(round(k / 100, 2) for k in range(1, 100))

PROVENANCES = ("synthetic", "realised")

# Runtime calibration artifacts (one JSON per forecaster version).
CALIBRATION_DIR = Path(__file__).resolve().parents[2] / "data" / "calibration"


# ---------------------------------------------------------------------------
# Residuals and conformal quantiles
# ---------------------------------------------------------------------------

def relative_residual(actual: float, yhat: float) -> Optional[float]:
    """(y − ŷ)/ŷ, or None when ŷ ≤ 0 (no relative error is defined)."""
    if yhat is None or actual is None or float(yhat) <= 0:
        return None
    return (float(actual) - float(yhat)) / float(yhat)


def conformal_quantile(sorted_residuals: Sequence[float], p: float) -> tuple[float, bool]:
    """Finite-sample conformal quantile of the residuals at ``p``.

    Returns ``(value, clamped)``; ``clamped`` is True when the corrected rank
    falls outside the sample (too few residuals to resolve that tail): the
    extreme residual is used and the caller is told.
    """
    n = len(sorted_residuals)
    if n == 0:
        raise ValueError("no residuals")
    if p >= 0.5:
        rank = math.ceil((n + 1) * p)          # 1-based
        if rank > n:
            return sorted_residuals[-1], True
    else:
        rank = math.floor((n + 1) * p)
        if rank < 1:
            return sorted_residuals[0], True
    return sorted_residuals[rank - 1], False


@dataclass
class Calibration:
    version: str
    forecaster: str
    provenance: str                          # synthetic | realised
    nominal_level: float
    n_residuals: int
    residual_quantiles: dict[str, float]     # "0.10" -> r quantile
    clamped_grid_points: int
    created_at: str
    # Kind of training data the forecaster was fit on when the residuals were
    # measured (synthetic | mcp_sandbox | hybrid | tenant id for realised).
    training_data_source: Optional[str] = None
    method: str = "split_conformal_relative_residual"
    status: str = "proposed"                 # proposed | active | retired
    # Evidence recorded when the calibration was validated.
    coverage_before: Optional[dict] = None
    coverage_after: Optional[dict] = None
    canary_runs: int = 0
    canary_identical: Optional[bool] = None
    independent_actuals: Optional[bool] = None  # False while actuals are manager-declared
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.provenance not in PROVENANCES:
            raise ValueError(f"provenance must be one of {PROVENANCES}")
        if not (0 < self.nominal_level < 1):
            raise ValueError("nominal_level must be in (0, 1)")

    # -- serialisation ---------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Mapping) -> "Calibration":
        return cls(**dict(d))

    def dump(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Calibration":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    # -- predictive distribution ----------------------------------------
    def _r(self, p: float) -> float:
        """Residual quantile at ``p`` by linear interpolation on the grid,
        clamped to the grid ends (0.01 / 0.99)."""
        p = min(max(p, GRID[0]), GRID[-1])
        lo_i = max(i for i, g in enumerate(GRID) if g <= p + 1e-12)
        if GRID[lo_i] >= p - 1e-12 or lo_i == len(GRID) - 1:
            return self.residual_quantiles[f"{GRID[lo_i]:.2f}"]
        g0, g1 = GRID[lo_i], GRID[lo_i + 1]
        r0 = self.residual_quantiles[f"{g0:.2f}"]
        r1 = self.residual_quantiles[f"{g1:.2f}"]
        return r0 + (r1 - r0) * (p - g0) / (g1 - g0)

    def quantile(self, yhat: float, p: float) -> float:
        """Demand quantile at ``p`` for a forecast ``yhat`` (never negative)."""
        return max(0.0, float(yhat) * (1.0 + self._r(p)))

    def interval(self, yhat: float, level: Optional[float] = None) -> tuple[float, float]:
        level = self.nominal_level if level is None else level
        a = (1.0 - level) / 2.0
        return self.quantile(yhat, a), self.quantile(yhat, 1.0 - a)

    def prob_at_or_below(self, yhat: float, x: float) -> tuple[float, str]:
        """P(D ≤ x) from the grid, with a resolution flag:
        ``"exact"`` inside the grid, ``"below_grid"`` (< 1 %) or
        ``"above_grid"`` (> 99 %) when x lies beyond the stored tails."""
        qs = [(g, self.quantile(yhat, g)) for g in GRID]
        if x < qs[0][1]:
            return GRID[0], "below_grid"
        if x >= qs[-1][1]:
            return GRID[-1], "above_grid"
        for (g0, q0), (g1, q1) in zip(qs, qs[1:]):
            if q0 <= x < q1:
                return g0 + (g1 - g0) * ((x - q0) / (q1 - q0) if q1 > q0 else 0.0), "exact"
        return GRID[-1], "above_grid"  # pragma: no cover — covered by the bounds above

    def expected_shortfall(self, yhat: float, capacity: float) -> float:
        """E[(D − capacity)+], approximated on the 99-point grid (tails beyond
        1 %/99 % are not resolved: a lower bound on the true value)."""
        return sum(max(0.0, self.quantile(yhat, g) - capacity) for g in GRID) / len(GRID)

    def expected_excess(self, yhat: float, capacity: float) -> float:
        """E[(capacity − D)+] — idle capacity, same grid approximation."""
        return sum(max(0.0, capacity - self.quantile(yhat, g)) for g in GRID) / len(GRID)


def fit(
    residuals: Iterable[float],
    *,
    version: str,
    forecaster: str,
    provenance: str,
    created_at: str,
    nominal_level: float = NOMINAL_LEVEL_DEFAULT,
) -> Calibration:
    rs = sorted(float(r) for r in residuals if r is not None and math.isfinite(r))
    if not rs:
        raise ValueError("no finite residuals to calibrate on")
    quantiles: dict[str, float] = {}
    clamped = 0
    for g in GRID:
        v, c = conformal_quantile(rs, g)
        quantiles[f"{g:.2f}"] = round(v, 6)
        clamped += int(c)
    return Calibration(
        version=version,
        forecaster=forecaster,
        provenance=provenance,
        nominal_level=nominal_level,
        n_residuals=len(rs),
        residual_quantiles=quantiles,
        clamped_grid_points=clamped,
        created_at=created_at,
    )


# ---------------------------------------------------------------------------
# Coverage — arm A (backtest) and arm C (realised covers)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IntervalRecord:
    actual: float
    lower: float
    upper: float
    category: str = "all"
    lead_days: Optional[int] = None


def _cov(hits: int, n: int) -> Optional[float]:
    return round(hits / n, 4) if n else None


def coverage(records: Iterable[IntervalRecord], nominal_level: float) -> dict:
    """Share of realised values inside their interval: overall, per category,
    per lead time and per category × lead. Every cell carries its n."""
    total = [0, 0]
    by_cat: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    by_lead: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    by_cell: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in records:
        hit = int(r.lower <= r.actual <= r.upper)
        lead = "na" if r.lead_days is None else str(r.lead_days)
        for acc in (total, by_cat[r.category], by_lead[lead], by_cell[f"{r.category}|{lead}"]):
            acc[0] += hit
            acc[1] += 1

    def _fmt(d: dict[str, list[int]]) -> dict:
        return {k: {"n": v[1], "coverage": _cov(v[0], v[1])} for k, v in sorted(d.items())}

    return {
        "nominal_level": nominal_level,
        "n": total[1],
        "coverage": _cov(total[0], total[1]),
        "gap_pp": (
            round((total[0] / total[1] - nominal_level) * 100, 1) if total[1] else None
        ),
        "per_category": _fmt(by_cat),
        "per_lead_days": _fmt(by_lead),
        "per_category_lead": _fmt(by_cell),
    }


def realised_coverage(rows: Iterable[Mapping], nominal_level: float = NOMINAL_LEVEL_DEFAULT) -> dict:
    """Arm C: coverage of the interval **stored at issue time** against the
    covers that actually happened. ``rows`` carry ``actual_covers``,
    ``interval_lower``/``interval_upper`` (from the recommendation's stored
    risk assessment) and ``actual_covers_source``. Rows without an actual or
    without a stored interval are skipped. The result says whether the actuals
    are independent of the manager (POS/PMS) or manager-declared."""
    recs: list[IntervalRecord] = []
    sources: dict[str, int] = defaultdict(int)
    for row in rows:
        if row.get("actual_covers") is None:
            continue
        lo, hi = row.get("interval_lower"), row.get("interval_upper")
        if lo is None or hi is None:
            continue
        recs.append(IntervalRecord(
            actual=float(row["actual_covers"]), lower=float(lo), upper=float(hi),
            category=str(row.get("task_class") or "all"),
        ))
        sources[str(row.get("actual_covers_source") or "unknown")] += 1
    out = coverage(recs, nominal_level)
    out["actuals_source"] = dict(sources)
    out["independent_actuals"] = bool(recs) and all(
        s in ("pos_data", "pms_data") for s in sources
    )
    return out


# ---------------------------------------------------------------------------
# Runtime loading
# ---------------------------------------------------------------------------

def load_active(forecaster: str, directory: Path = CALIBRATION_DIR) -> Optional[Calibration]:
    """The active calibration for ``forecaster``, or None. Never falls back to
    another forecaster's calibration."""
    if not directory.exists():
        return None
    found: list[Calibration] = []
    for path in sorted(directory.glob("*.json")):
        try:
            cal = Calibration.load(path)
        except Exception:  # noqa: BLE001 — a malformed file is ignored, never guessed
            continue
        if cal.forecaster == forecaster and cal.status == "active":
            found.append(cal)
    if not found:
        return None
    return max(found, key=lambda c: c.created_at)
