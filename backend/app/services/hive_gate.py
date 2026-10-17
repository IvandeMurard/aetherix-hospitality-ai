"""Hive gate: opt-in, always anonymized (HOS-346, Décision #43).

The only path through which anything derived from a hotel may enter a
cross-hotel aggregate. No Hive flow exists yet (``memory_service`` Layer 2 is
not implemented, ``fb_patterns`` holds global seeds and per-hotel rows only);
this gate exists first so that the first flow has to go through it.

Rules, enforced here and pinned by tests:

1. **Opt-in.** Only hotels whose consent in force is ``opted_in`` contribute.
   No consent row = not opted in. A hotel that opts out is excluded from every
   later aggregate.
2. **Aggregate only.** The output is a count of hotels and a rounded mean. No
   hotel identifier, no single-hotel value, no min / max / median (with few
   hotels, each of those is one hotel's value).
3. **Floor of hotels.** Below ``MIN_HOTELS`` distinct opted-in contributors,
   nothing is produced (``HiveRefused``), never a smaller group.
4. **Concentration guard.** No hotel may weigh more than ``MAX_SHARE`` of a
   weighted aggregate (a mean dominated by one hotel describes that hotel).

``MIN_HOTELS = 5`` and ``MAX_SHARE = 0.25`` take the rule of thumb of the 1996
US antitrust "safety zone" for exchanges of business data between competitors
(at least five participants, none above 25 % of the weight). That guidance was
withdrawn in 2023 and gives no legal cover; it is used here as a floor, a
product choice recorded with HOS-346, separate from the k = 20 guests per
cohort of HOS-323 (personal data).

**What this does not prove.** Anonymity is not claimed (Décisions #2, #33):
the gate makes the rules checkable, it does not replace a re-identification
analysis. Known residual risk: two aggregates published before and after one
hotel joins or leaves can be differenced to estimate its value; publishing on
a fixed schedule and rounding reduce it, they do not remove it.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

MIN_HOTELS = 5
MAX_SHARE = 0.25
# mcp: an opt-out by the hotel's agent (immediate); whatsapp: an opt-in the
# owner confirmed with a one-time code (HOS-349). An agent never opts in alone.
CONSENT_SET_VIA = ("dashboard_api", "ops", "mcp", "whatsapp")


class HiveRefused(Exception):
    """Typed refusal: nothing leaves the hotels' tenants."""

    def __init__(self, reason: str, detail: str):
        super().__init__(f"{reason}: {detail}")
        self.reason, self.detail = reason, detail


@dataclass(frozen=True)
class HiveAggregate:
    metric: str
    n_hotels: int
    mean: float

    def as_dict(self) -> dict:
        return {"metric": self.metric, "n_hotels": self.n_hotels, "mean": self.mean}


def aggregate(
    metric: str,
    contributions: Mapping[str, float],
    opted_in: set[str],
    *,
    weights: Optional[Mapping[str, float]] = None,
    precision: int = 1,
) -> HiveAggregate:
    """One anonymized aggregate, or ``HiveRefused``.

    ``contributions`` maps a tenant id to that hotel's value (one value per
    hotel: a hotel with many rows is summarised inside its tenant first).
    ``weights`` (optional) maps a tenant id to its weight in the mean.
    """
    eligible = {t: float(v) for t, v in contributions.items() if t in opted_in}
    if len(eligible) < MIN_HOTELS:
        raise HiveRefused("below_floor", f"{len(eligible)} opted-in hotels, at least {MIN_HOTELS} required")
    w = {t: float((weights or {}).get(t, 1.0)) for t in eligible}
    if any(x <= 0 for x in w.values()):
        raise HiveRefused("invalid_weight", "every contributing hotel needs a positive weight")
    total = sum(w.values())
    if max(w.values()) / total > MAX_SHARE:
        raise HiveRefused("concentration", f"one hotel weighs more than {MAX_SHARE:.0%} of the aggregate")
    mean = sum(eligible[t] * w[t] for t in eligible) / total
    return HiveAggregate(metric=metric, n_hotels=len(eligible), mean=round(mean, precision))


async def opted_in_tenants(db: AsyncSession) -> set[str]:
    """Tenants whose latest consent row says opted in."""
    from app.db.models import HiveConsent

    rows = (await db.execute(select(HiveConsent).order_by(HiveConsent.set_at, HiveConsent.id))).scalars().all()
    latest: dict[str, bool] = {}
    for r in rows:
        latest[r.tenant_id] = bool(r.opted_in)
    return {t for t, ok in latest.items() if ok}


async def consent_for(db: AsyncSession, tenant_id: str) -> dict:
    """The consent in force for one hotel, with its history (newest first)."""
    from app.db.models import HiveConsent

    rows = (await db.execute(
        select(HiveConsent).where(HiveConsent.tenant_id == tenant_id)
        .order_by(HiveConsent.set_at.desc(), HiveConsent.id)
    )).scalars().all()
    history = [
        {"opted_in": r.opted_in, "set_by": r.set_by, "set_via": r.set_via, "note": r.note,
         "set_at": r.set_at.isoformat() if r.set_at else None}
        for r in rows
    ]
    return {"tenant_id": tenant_id, "opted_in": bool(rows and rows[0].opted_in), "history": history}


async def set_consent(
    db: AsyncSession, tenant_id: str, opted_in: bool, *, set_by: str, set_via: str,
    note: Optional[str] = None, at: Optional[datetime] = None,
) -> dict:
    """Append one consent row. Commits nothing: the caller owns the transaction."""
    from app.db.models import HiveConsent

    if not tenant_id:
        raise ValueError("tenant_id required")
    if set_via not in CONSENT_SET_VIA:
        raise ValueError(f"set_via must be one of {CONSENT_SET_VIA}")
    if not (set_by or "").strip():
        raise ValueError("set_by required: every consent records who gave or withdrew it")
    row = HiveConsent(
        tenant_id=tenant_id, opted_in=bool(opted_in), set_by=set_by.strip()[:200], set_via=set_via,
        note=(note or None) and note.strip()[:500], set_at=at or datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()
    return {"tenant_id": tenant_id, "opted_in": row.opted_in, "set_by": row.set_by,
            "set_via": set_via, "set_at": row.set_at.isoformat()}
