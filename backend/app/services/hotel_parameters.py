"""Per-hotel decision parameters — configured by the hotel, never invented.

ADR-0007 §18.3 (Décision #40). The asymmetric costs a risk-based
recommendation needs (an extra shift, a lost cover, food cost), the labour
constraints it must respect, and the hotel's own commit offsets (§18.1) come
from here and nowhere else:

* **Missing → no money.** A risk statement without the relevant cost shows no
  amount, only a qualitative band. The legacy ``restaurant_profiles``
  ``staff_hourly_rate`` / ``avg_spend_per_cover`` and the system defaults in
  ``config`` are **not** read: they carry no record of who set them, and the
  defaults are placeholders (ROI simulator), not the hotel's costs.
* **Staffing rules (HOS-343).** Ratios and the usual team per role. Missing →
  the staffing service uses its system default for that role and labels it
  ``default``. The legacy ``restaurant_profiles.covers_per_*`` columns are not
  read either, for the same reason as the legacy costs. Each rule can also be
  set per context class (``covers_per_server.event_night``, HOS-345,
  ``staffing_context``), with the hotel's high-season months.
* **Bounded.** Every parameter has a unit and hard bounds (``CATALOG``); an
  out-of-bounds value is refused, never clamped.
* **Provenance.** Append-only rows (``hotel_decision_parameters``): who set
  each value (``set_by``), through which surface (``set_via``), when
  (``set_at``). The value in force is the latest row; ``value`` None clears.
* **Currency.** Money is stored with the currency it was entered in
  (``config.CURRENCY`` at the time). If the configured currency changes, old
  money values are ignored (listed in ``ignored``), never converted.
* **Tenant-scoped.** Every read and write takes the tenant id; routes check
  ownership with ``app/api/tenant_scope``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import currency_code
from app.services import staffing_context, task_classes

# hotel_system (HOS-346, Décision #43): a value read from the hotel's own system
# (scheduling tool, SOP); set_by names the system.
SET_VIA = ("dashboard_api", "ops", "proposal_approval", "hotel_system")


@dataclass(frozen=True)
class ParamSpec:
    name: str
    unit: str                 # money | covers | staff | hours | month
    minimum: float
    maximum: float
    min_inclusive: bool
    used_by: tuple[str, ...]  # task classes whose decision rule reads it
    description: str


def _money(name, maximum, used_by, description) -> ParamSpec:
    return ParamSpec(name, "money", 0.0, maximum, False, used_by, description)


_STAFFING = (task_classes.TaskClassKey.staffing_add.value, task_classes.TaskClassKey.staffing_reduce.value)
_FOOD = (task_classes.TaskClassKey.food_prep_batch.value,)

CATALOG: dict[str, ParamSpec] = {
    p.name: p
    for p in (
        _money("extra_shift_cost", 2000.0, _STAFFING,
               "Fully loaded cost of one extra staff shift for one service window "
               "(or the saving of removing one)."),
        _money("lost_cover_value", 1000.0, _STAFFING,
               "Value lost per cover the outlet cannot serve (the hotel chooses "
               "margin or revenue and says which in the note)."),
        _money("food_cost_per_cover", 500.0, _FOOD,
               "Food cost of one cover prepared and not sold (food prep; not "
               "recommended by the product today)."),
        _money("stockout_cost_per_cover", 1000.0, _FOOD,
               "Value lost per cover short on a prepared item (food prep; not "
               "recommended by the product today)."),
        ParamSpec("covers_per_extra_staff", "covers", 1.0, 200.0, True, _STAFFING,
                  "Covers one additional staff member can serve in the window."),
        # HOS-343: the hotel's own staffing rules. Unset -> StaffingService
        # uses its system default for that role and labels it "default".
        *(
            ParamSpec(f"covers_per_{role}", "covers", 1.0, 200.0, True, _STAFFING,
                      f"Covers one {label} handles in a service (the hotel's own ratio).")
            for role, label in (("server", "server"), ("host", "host"),
                                ("runner", "runner"), ("kitchen_staff", "kitchen staff member"))
        ),
        *(
            ParamSpec(f"usual_{role}", "staff", 0.0, 50.0, True, _STAFFING,
                      f"{label} on a usual service, the team the recommendation is compared to.")
            for role, label in (("servers", "Servers"), ("hosts", "Hosts"),
                                ("runners", "Runners"), ("kitchen_staff", "Kitchen staff"))
        ),
        ParamSpec("max_extra_staff", "staff", 0.0, 50.0, True, _STAFFING,
                  "Most extra staff the hotel can call in for one window."),
        ParamSpec("max_staff_reduction", "staff", 0.0, 50.0, True, _STAFFING,
                  "Most staff the hotel can remove from one window."),
        ParamSpec("risk_display_min_gap", "money", 0.0, 100000.0, True, _STAFFING + _FOOD,
                  "Interruption budget: show the 'if accepted / if refused' lines "
                  "in the daily message only when the expected cost gap between "
                  "the options is at least this amount."),
        *(
            ParamSpec(f"commit_offset_hours.{k.value}", "hours",
                      task_classes.COMMIT_OFFSET_MIN_HOURS, task_classes.COMMIT_OFFSET_MAX_HOURS,
                      True, (k.value,),
                      f"Hours before service start at which {k.value} commits "
                      f"({task_classes.spec(k).commit_point}).")
            for k in task_classes.TaskClassKey
        ),
        # HOS-350: when the one reminder goes out, in hours before the point
        # of no return; 0 = no reminder for this decision type.
        *(
            ParamSpec(f"reminder_offset_hours.{k.value}", "hours", 0.0, 48.0, True, (k.value,),
                      f"Hours before the point of no return of {k.value} at which an unanswered "
                      "recommendation gets its one reminder (0 = no reminder).")
            for k in task_classes.TaskClassKey
        ),
    )
}


# HOS-345: the same staffing rules per context class, ``<rule>.<class>``
# (classes: staffing_context.CONTEXT_CLASSES, closed list), and the hotel's
# own high season. A class without a value falls back to the flat rule.
_ROLE_RULES = tuple(
    n for n in CATALOG if n.startswith(("covers_per_", "usual_")) and n != "covers_per_extra_staff"
)
CATALOG.update({
    p.name: p
    for p in (
        *(
            ParamSpec(f"{rule}.{cls}", CATALOG[rule].unit, CATALOG[rule].minimum, CATALOG[rule].maximum,
                      CATALOG[rule].min_inclusive, _STAFFING,
                      f"{CATALOG[rule].description} Applies on {staffing_context.CLASS_LABELS['en'][cls]} "
                      "services; unset = the flat rule.")
            for rule in _ROLE_RULES for cls in staffing_context.CONTEXT_CLASSES
        ),
        ParamSpec("high_season_start_month", "month", 1.0, 12.0, True, _STAFFING,
                  "First month of the hotel's high season (1-12); with the end month, "
                  "enables the high_season staffing rules."),
        ParamSpec("high_season_end_month", "month", 1.0, 12.0, True, _STAFFING,
                  "Last month of the hotel's high season (1-12, may be before the start "
                  "month to wrap over the new year)."),
    )
})


class ParameterError(ValueError):
    """Typed refusal (→ 422)."""


def validate(name: str, value: Optional[float]) -> Optional[float]:
    """Return the value to store, or raise ``ParameterError``. None = clear."""
    spec = CATALOG.get(name)
    if spec is None:
        raise ParameterError(f"unknown parameter {name!r}")
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError) as exc:
        raise ParameterError(f"{name}: not a number") from exc
    if not math.isfinite(v):
        raise ParameterError(f"{name}: not a finite number")
    low_ok = v >= spec.minimum if spec.min_inclusive else v > spec.minimum
    if not low_ok or v > spec.maximum:
        bracket = "[" if spec.min_inclusive else "]"
        raise ParameterError(f"{name} must be within {bracket}{spec.minimum:g}, {spec.maximum:g}]")
    if spec.unit == "staff" and v != int(v):
        raise ParameterError(f"{name}: a whole number of staff")
    if spec.unit == "month" and v != int(v):
        raise ParameterError(f"{name}: a month number, 1 to 12")
    return round(v, 2)


@dataclass(frozen=True)
class ParamValue:
    value: float
    unit: str
    currency: Optional[str]
    set_by: str
    set_via: str
    set_at: datetime
    note: Optional[str]

    def as_dict(self) -> dict:
        return {
            "value": self.value, "unit": self.unit, "currency": self.currency,
            "set_by": self.set_by, "set_via": self.set_via,
            "set_at": self.set_at.isoformat() if self.set_at else None, "note": self.note,
        }


@dataclass
class HotelParameters:
    tenant_id: str
    values: dict[str, ParamValue] = field(default_factory=dict)
    # Money values entered in another currency than the configured one.
    ignored: dict[str, str] = field(default_factory=dict)

    def get(self, name: str) -> Optional[float]:
        pv = self.values.get(name)
        return pv.value if pv is not None else None

    def version(self) -> Optional[str]:
        """Latest set_at among values in force — stored on every
        recommendation so a decision can be traced to the costs it used."""
        stamps = [pv.set_at for pv in self.values.values() if pv.set_at is not None]
        return max(stamps).isoformat() if stamps else None

    def commit_offsets(self) -> dict[str, float]:
        prefix = "commit_offset_hours."
        return {k[len(prefix):]: v.value for k, v in self.values.items() if k.startswith(prefix)}

    def as_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "currency": currency_code(),
            "values": {k: v.as_dict() for k, v in sorted(self.values.items())},
            "ignored": dict(self.ignored),
            "missing": sorted(set(CATALOG) - set(self.values)),
            "version": self.version(),
        }


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


async def load(db: AsyncSession, tenant_id: str) -> HotelParameters:
    """Values in force for ``tenant_id`` (latest row per parameter)."""
    from app.db.models import HotelDecisionParameter as Row

    rows = (
        await db.execute(
            select(Row).where(Row.tenant_id == tenant_id).order_by(Row.set_at, Row.id)
        )
    ).scalars().all()
    latest: dict[str, Any] = {}
    for r in rows:
        latest[r.parameter] = r
    out = HotelParameters(tenant_id=tenant_id)
    configured = currency_code()
    for name, r in latest.items():
        if r.value is None or name not in CATALOG:
            continue
        if r.unit == "money" and (r.currency or "").upper() != configured:
            out.ignored[name] = f"entered in {r.currency}, configured currency is {configured}"
            continue
        out.values[name] = ParamValue(
            value=float(r.value), unit=r.unit, currency=r.currency,
            set_by=r.set_by, set_via=r.set_via, set_at=_utc(r.set_at), note=r.note,
        )
    return out


async def history(db: AsyncSession, tenant_id: str, parameter: Optional[str] = None) -> list[dict]:
    from app.db.models import HotelDecisionParameter as Row

    stmt = select(Row).where(Row.tenant_id == tenant_id)
    if parameter:
        stmt = stmt.where(Row.parameter == parameter)
    rows = (await db.execute(stmt.order_by(Row.set_at.desc(), Row.id))).scalars().all()
    return [
        {
            "parameter": r.parameter,
            "value": float(r.value) if r.value is not None else None,
            "unit": r.unit, "currency": r.currency, "set_by": r.set_by,
            "set_via": r.set_via, "note": r.note,
            "set_at": _utc(r.set_at).isoformat() if r.set_at else None,
        }
        for r in rows
    ]


async def set_parameter(
    db: AsyncSession,
    tenant_id: str,
    name: str,
    value: Optional[float],
    *,
    set_by: str,
    set_via: str,
    note: Optional[str] = None,
    at: Optional[datetime] = None,
) -> dict:
    """Append one row (validated). Commits nothing: the caller owns the
    transaction. ``value`` None clears the parameter."""
    from app.db.models import HotelDecisionParameter as Row

    if not tenant_id:
        raise ParameterError("tenant_id required")
    if set_via not in SET_VIA:
        raise ParameterError(f"set_via must be one of {SET_VIA}")
    if not (set_by or "").strip():
        raise ParameterError("set_by required: every value records who set it")
    stored = validate(name, value)
    spec = CATALOG[name]
    row = Row(
        tenant_id=tenant_id,
        parameter=name,
        value=stored,
        unit=spec.unit,
        currency=currency_code() if spec.unit == "money" else None,
        set_by=set_by.strip()[:200],
        set_via=set_via,
        note=(note or None) and note.strip()[:500],
        set_at=at or datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()
    return {
        "parameter": name, "value": stored, "unit": spec.unit, "currency": row.currency,
        "set_by": row.set_by, "set_via": set_via, "set_at": row.set_at.isoformat(),
    }


def catalog_as_dict() -> list[dict]:
    return [
        {
            "parameter": s.name, "unit": s.unit,
            "currency": currency_code() if s.unit == "money" else None,
            "minimum": s.minimum, "minimum_inclusive": s.min_inclusive, "maximum": s.maximum,
            "used_by": list(s.used_by), "description": s.description,
        }
        for s in CATALOG.values()
    ]
