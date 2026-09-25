"""Task classes and their point of no return (correction window).

A hotel cannot undo a service. What it has is a **correction window**: the time
between the recommendation and the moment the action commits (an extra shift is
confirmed to a person or an agency, staff are told not to come, prep starts, an
order passes its supplier cut-off). Before the commit point the decision can
still be changed at little or no cost; after it, only costly corrective actions
remain, or none.

This module is the single catalog of task classes the product can recommend,
with, for each: the commit point relative to service start, the corrective
actions still possible before it (and after it, at a cost), and whether the
downside of a wrong decision is bounded. It is consumed by:

* the recommendation formatter — stores ``task_class`` and ``commit_at`` on
  every staffing recommendation and surfaces the window when it matters
  (``should_surface``);
* ADR-0013 (status: proposed) — ``autonomy_eligibility_facts`` is an input to
  a scope's autonomy eligibility, never a gate by itself (ADR-0013 §2.4.5).

Commit offsets here are **defaults, not measurements**: they are assumptions
until the hotel sets its own (``hotel_decision_parameters``,
``commit_offset_hours``), because the real notice period depends on the
hotel's staffing contracts, agency terms and collective agreement. Every
default says so (``offset_basis = "default_assumption"``).

ADR-0007 §18 (Décision #40).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from zoneinfo import ZoneInfo

from app.services.decision_policy import TaskClass as PolicyTaskClass

CATALOG_VERSION = "task-classes-v1"

# The correction window is shown in the manager's message when the commit point
# is at most this many hours after the message, or already passed. Farther
# away, it only lives in the stored record, the recap and MCP (interruption
# budget).
SURFACE_WITHIN_HOURS_DEFAULT = 48.0

# Hard bounds on a hotel's own commit offset (validation, part of
# hotel_decision_parameters): 0 h (commits at service start) to 30 days.
COMMIT_OFFSET_MIN_HOURS = 0.0
COMMIT_OFFSET_MAX_HOURS = 24.0 * 30


class TaskClassKey(str, Enum):
    staffing_add = "staffing.add"
    staffing_reduce = "staffing.reduce"
    food_prep_batch = "food_prep.batch"


@dataclass(frozen=True)
class TaskClassSpec:
    key: TaskClassKey
    # Scope the decision policy (ADR-0013) is keyed on; None = no policy scope
    # exists because the product does not recommend this class.
    policy_task_class: Optional[PolicyTaskClass]
    recommended_by_product: bool
    commit_point: str                       # typed id of the committing event
    commit_offset_hours: float              # default, hours before service start
    offset_basis: str                       # default_assumption | hotel_configured
    corrective_before_commit: tuple[str, ...]
    corrective_after_commit: tuple[str, ...]
    # Downside of each wrong decision, typed.
    downside_if_accepted_wrongly: str
    downside_if_refused_wrongly: str
    downside_bounded: bool                  # the worst case has a known ceiling
    reversible_after_commit: bool           # anything but a costly partial fix after commit


CATALOG: dict[TaskClassKey, TaskClassSpec] = {
    TaskClassKey.staffing_add: TaskClassSpec(
        key=TaskClassKey.staffing_add,
        policy_task_class=PolicyTaskClass.staffing,
        recommended_by_product=True,
        commit_point="extra_shift_confirmed",
        commit_offset_hours=24.0,
        offset_basis="default_assumption",
        corrective_before_commit=("do_not_call_in", "call_in_fewer", "put_on_standby"),
        corrective_after_commit=("cancel_shift_with_cost", "reassign_to_other_outlet"),
        downside_if_accepted_wrongly="extra_shift_cost",
        downside_if_refused_wrongly="understaffed_service",
        # Accepted wrongly: at most the extra shifts' cost. Refused wrongly: at
        # most the covers the outlet could not serve (bounded by capacity).
        downside_bounded=True,
        reversible_after_commit=False,
    ),
    TaskClassKey.staffing_reduce: TaskClassSpec(
        key=TaskClassKey.staffing_reduce,
        policy_task_class=PolicyTaskClass.staffing,
        recommended_by_product=True,
        commit_point="staff_notified_not_to_come",
        # Longer than an addition: telling staff a shift is cancelled usually
        # needs notice (contract / collective agreement). Assumption until the
        # hotel sets its own.
        commit_offset_hours=72.0,
        offset_basis="default_assumption",
        corrective_before_commit=("keep_shift", "reduce_fewer", "move_to_other_outlet"),
        corrective_after_commit=("call_back_if_available",),
        downside_if_accepted_wrongly="understaffed_service",
        downside_if_refused_wrongly="idle_shift_cost",
        downside_bounded=True,
        reversible_after_commit=False,
    ),
    TaskClassKey.food_prep_batch: TaskClassSpec(
        key=TaskClassKey.food_prep_batch,
        # Not recommended by the product today (food-waste tracking is an open
        # decision for Ivan): defined so its window is known before it is built.
        policy_task_class=None,
        recommended_by_product=False,
        commit_point="prep_started",
        commit_offset_hours=4.0,
        offset_basis="default_assumption",
        corrective_before_commit=("adjust_batch_size", "split_batch", "switch_to_cook_to_order"),
        corrective_after_commit=("repurpose", "staff_meal", "remove_item_from_menu"),
        downside_if_accepted_wrongly="food_waste_cost",
        downside_if_refused_wrongly="stockout",
        downside_bounded=True,
        reversible_after_commit=False,
    ),
}


def for_direction(direction: str) -> TaskClassKey:
    """Anomaly direction → task class. A surge recommends adding staff, a lull
    reducing it (``recommendation_formatter``)."""
    return TaskClassKey.staffing_add if direction == "surge" else TaskClassKey.staffing_reduce


def spec(key: TaskClassKey | str) -> TaskClassSpec:
    return CATALOG[TaskClassKey(key)]


def validate_commit_offset(hours: float) -> float:
    hours = float(hours)
    if not (COMMIT_OFFSET_MIN_HOURS <= hours <= COMMIT_OFFSET_MAX_HOURS):
        raise ValueError(
            f"commit_offset_hours must be within [{COMMIT_OFFSET_MIN_HOURS:g}, "
            f"{COMMIT_OFFSET_MAX_HOURS:g}]"
        )
    return hours


class WindowStatus(str, Enum):
    open = "open"          # commit point far enough away
    closing = "closing"    # commit point within the surfacing horizon
    passed = "passed"      # commit point already passed when the rec was issued


@dataclass(frozen=True)
class CorrectionWindow:
    task_class: TaskClassKey
    commit_point: str
    commit_at: datetime
    hours_left: float
    status: WindowStatus
    offset_hours: float
    offset_basis: str
    catalog_version: str = CATALOG_VERSION

    def as_dict(self) -> dict:
        return {
            "task_class": self.task_class.value,
            "commit_point": self.commit_point,
            "commit_at": self.commit_at.isoformat(),
            "hours_left": round(self.hours_left, 1),
            "status": self.status.value,
            "offset_hours": self.offset_hours,
            "offset_basis": self.offset_basis,
            "catalog_version": self.catalog_version,
        }


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def correction_window(
    key: TaskClassKey | str,
    service_start: datetime,
    issued_at: datetime,
    *,
    offset_hours: Optional[float] = None,
    surface_within_hours: float = SURFACE_WITHIN_HOURS_DEFAULT,
) -> CorrectionWindow:
    """Commit point for a recommendation about a service starting at
    ``service_start``, seen from ``issued_at``. ``offset_hours`` is the hotel's
    own setting when it has one (else the catalog default, labelled as such)."""
    s = spec(key)
    basis = s.offset_basis
    if offset_hours is None:
        offset = s.commit_offset_hours
    else:
        offset = validate_commit_offset(offset_hours)
        basis = "hotel_configured"
    commit_at = _utc(service_start) - timedelta(hours=offset)
    hours_left = (commit_at - _utc(issued_at)).total_seconds() / 3600.0
    if hours_left <= 0:
        status = WindowStatus.passed
    elif hours_left <= surface_within_hours:
        status = WindowStatus.closing
    else:
        status = WindowStatus.open
    return CorrectionWindow(
        task_class=s.key,
        commit_point=s.commit_point,
        commit_at=commit_at,
        hours_left=hours_left,
        status=status,
        offset_hours=offset,
        offset_basis=basis,
    )


def should_surface(window: CorrectionWindow) -> bool:
    """The window "matters" to the manager when it is closing or has passed."""
    return window.status in (WindowStatus.closing, WindowStatus.passed)


_COMMIT_LABELS = {
    "fr": {
        "extra_shift_confirmed": "confirmation des extras",
        "staff_notified_not_to_come": "prévenir l'équipe",
        "prep_started": "début de la mise en place",
    },
    "en": {
        "extra_shift_confirmed": "extra shifts confirmed",
        "staff_notified_not_to_come": "staff notified",
        "prep_started": "prep starts",
    },
}
_WEEKDAYS = {
    "fr": ("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."),
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
}


def _loc(locale: Optional[str]) -> str:
    return "en" if (locale or "").lower().startswith("en") else "fr"


def render_window(window: CorrectionWindow, tz: ZoneInfo, locale: Optional[str] = "fr") -> str:
    """One deterministic line. FR default (``manager_locale`` None → fr)."""
    loc = _loc(locale)
    local = window.commit_at.astimezone(tz)
    when = f"{_WEEKDAYS[loc][local.weekday()]} {local:%H:%M}"
    label = _COMMIT_LABELS[loc].get(window.commit_point, window.commit_point)
    assumed = window.offset_basis == "default_assumption"
    if loc == "en":
        note = " — default, not set by the hotel" if assumed else ""
        if window.status == WindowStatus.passed:
            return f"Past the usual commit point ({label}, {when}){note}."
        return f"Can still be changed until {when} ({label}){note}."
    note = " — valeur par défaut, non réglée par l'hôtel" if assumed else ""
    if window.status == WindowStatus.passed:
        return f"Point de non-retour habituel dépassé ({label}, {when}){note}."
    return f"Modifiable jusqu'à {when} ({label}){note}."


def autonomy_eligibility_facts(key: TaskClassKey | str) -> dict:
    """Input to ADR-0013 §2.4.5 (status: proposed). A scope is a better autonomy
    candidate when it has a correction window (a commit point before service
    and corrective actions before it) or a bounded downside. Facts only: this
    never makes a scope eligible, and staffing stays L0 in ADR-0013 §2.1."""
    s = spec(key)
    return {
        "task_class": s.key.value,
        "has_correction_window": s.commit_offset_hours > 0 and bool(s.corrective_before_commit),
        "downside_bounded": s.downside_bounded,
        "reversible_after_commit": s.reversible_after_commit,
        "recommended_by_product": s.recommended_by_product,
        "offset_basis": s.offset_basis,
        "catalog_version": CATALOG_VERSION,
    }
