"""Decision recap — deterministic, template-based, built on the decision ledger
(ADR-0007 §17.2).

One definition, three surfaces:
  * the WhatsApp ``recap`` command (``recap jour | semaine | mois``, FR/EN),
  * the MCP read tool ``get_decision_recap`` for host agents,
  * ``GET /reports/weekly`` (the former "Friday audit", now this template for
    the week) and ``GET /kpi/{hotel_id}/recommendation_acceptance``.

No LLM, no prose, no figure that was not measured:
  * counts come from ``staffing_recommendations`` (status + ``decided_by`` +
    ``decision_source``) and pending ``manager_prompts``;
  * the mean forecast error is computed only on recommendations with actual
    covers, and always printed with the number of days it covers;
  * no savings, no ROI: nothing measured feeds them today.

Acceptance and override rates are **human** metrics: only ``human_whatsapp``
and ``human_via_host`` decisions count. A host agent's own decision is shown
apart and never feeds them. Legacy decided rows without ``decided_by`` are
``unattributed`` and excluded from the rates (shown, not hidden).

Pure functions first (``summarize``, ``render_text``), DB loader last.
"""
from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable, Literal, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config
from app.services.decision_provenance import AGENT_DECIDERS, HUMAN_DECIDERS

Period = Literal["day", "week", "month"]
PERIODS: tuple[str, ...] = ("day", "week", "month")

DECIDED_STATUSES: frozenset[str] = frozenset({"accepted", "rejected", "modified"})

# decision_source → recap bucket. Everything a manager or a host can read.
SOURCE_BUCKET: dict[str, str] = {
    "button": "button",
    "keyword": "keyword",
    "bare_ack_rule": "keyword",
    "correction_pattern": "keyword",
    "model_auto": "model",
    "model_confirmed": "confirmed",
    "keyword_confirmed": "confirmed",
    "bare_ack_confirmed": "confirmed",
    "manager_revision": "revised",
    "host_relay": "host",
    "host_agent": "agent",
}
BUCKET_ORDER: tuple[str, ...] = (
    "button", "keyword", "model", "confirmed", "revised", "host", "agent", "unattributed",
)

ACCEPTANCE_DEFINITION = (
    "acceptance_rate = accepted / (accepted + rejected + modified), human decisions "
    "only (decided_by in human_whatsapp, human_via_host), recommendations keyed by "
    "dispatch time (creation time if never dispatched). No reply is not a decision "
    "and is reported separately."
)


# ---------------------------------------------------------------------------
# Pure core
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RecRow:
    """What the recap needs about one recommendation. Built from the ORM row."""

    id: object
    received_at: datetime            # dispatched_at, else created_at (UTC)
    window_start: Optional[datetime]
    status: str
    decided_by: Optional[str]
    decision_source: Optional[str]
    actioned_at: Optional[datetime]
    predicted_covers: Optional[float]
    actual_covers: Optional[float]
    awaiting_confirmation: bool = False
    # ADR-0007 §18.4: typed per-option consequences stored at issue time.
    risk_assessment: Optional[dict] = None


def acceptance_rate(accepted: int, decided: int) -> Optional[float]:
    """The single definition of the acceptance rate (KPI level 3)."""
    return round(accepted / decided, 4) if decided else None


@dataclass
class DeciderStats:
    decided: int = 0
    accepted: int = 0
    rejected: int = 0
    modified: int = 0
    acceptance_rate: Optional[float] = None
    override_rate: Optional[float] = None
    # Time from dispatch to decision. A latency, NOT a measure of human effort.
    median_response_minutes: Optional[float] = None


@dataclass
class RecapSummary:
    period: str
    start: date
    end: date                         # inclusive, local date
    received: int = 0
    accepted: int = 0
    rejected: int = 0
    corrected: int = 0
    no_reply: int = 0
    awaiting_confirmation: int = 0
    forecast_error_pct: Optional[float] = None
    forecast_error_days: int = 0
    forecast_error_observations: int = 0
    by_source: dict[str, int] = field(default_factory=dict)
    by_decided_by: dict[str, int] = field(default_factory=dict)
    human: DeciderStats = field(default_factory=DeciderStats)
    agent: DeciderStats = field(default_factory=DeciderStats)
    acceptance_definition: str = ACCEPTANCE_DEFINITION
    # ADR-0007 §18.4: undecided recommendations with their per-option risk —
    # always available here, whatever the interruption budget did in the
    # daily message. Newest window last.
    pending_risk: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["start"] = self.start.isoformat()
        d["end"] = self.end.isoformat()
        return d


def _stats(rows: list[RecRow]) -> DeciderStats:
    s = DeciderStats()
    latencies: list[float] = []
    for r in rows:
        s.decided += 1
        if r.status == "accepted":
            s.accepted += 1
        elif r.status == "rejected":
            s.rejected += 1
        elif r.status == "modified":
            s.modified += 1
        if r.actioned_at is not None:
            latencies.append((r.actioned_at - r.received_at).total_seconds() / 60.0)
    s.acceptance_rate = acceptance_rate(s.accepted, s.decided)
    s.override_rate = acceptance_rate(s.rejected + s.modified, s.decided)
    positive = [x for x in latencies if x >= 0]
    s.median_response_minutes = round(statistics.median(positive), 1) if positive else None
    return s


def summarize(rows: Iterable[RecRow], period: str, start: date, end: date,
              tz: Optional[ZoneInfo] = None) -> RecapSummary:
    """Recap of ``rows`` (already filtered to the period). Deterministic."""
    tz = tz or _tz()
    rows = list(rows)
    s = RecapSummary(period=period, start=start, end=end, received=len(rows))
    decided: list[RecRow] = []
    for r in rows:
        if r.status in DECIDED_STATUSES:
            decided.append(r)
            if r.status == "accepted":
                s.accepted += 1
            elif r.status == "rejected":
                s.rejected += 1
            else:
                s.corrected += 1
            bucket = SOURCE_BUCKET.get(r.decision_source or "", "unattributed")
            s.by_source[bucket] = s.by_source.get(bucket, 0) + 1
            who = r.decided_by or "unattributed"
            s.by_decided_by[who] = s.by_decided_by.get(who, 0) + 1
        elif r.awaiting_confirmation:
            s.awaiting_confirmation += 1
        else:
            s.no_reply += 1
        if r.status not in DECIDED_STATUSES and r.risk_assessment:
            s.pending_risk.append({
                "recommendation_id": str(r.id),
                "window_start": (r.window_start or r.received_at).isoformat(),
                "risk": r.risk_assessment,
            })

    s.human = _stats([r for r in decided if r.decided_by in HUMAN_DECIDERS])
    s.agent = _stats([r for r in decided if r.decided_by in AGENT_DECIDERS])

    measured = [
        r for r in rows
        if r.actual_covers is not None and r.predicted_covers is not None and float(r.actual_covers) > 0
    ]
    if measured:
        errors = [abs(float(r.predicted_covers) - float(r.actual_covers)) / float(r.actual_covers)
                  for r in measured]
        s.forecast_error_pct = round(sum(errors) / len(errors) * 100, 1)
        s.forecast_error_observations = len(measured)
        s.forecast_error_days = len({
            (r.window_start or r.received_at).astimezone(tz).date() for r in measured
        })
    return s


# ---------------------------------------------------------------------------
# Periods
# ---------------------------------------------------------------------------

def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(config.RECEIPT_TIMEZONE or "UTC")
    except Exception:  # noqa: BLE001 — bad config falls back to UTC, never crashes a recap
        return ZoneInfo("UTC")


def period_bounds(period: str, now: datetime, tz: Optional[ZoneInfo] = None) -> tuple[date, date]:
    """Local calendar bounds, inclusive: day = today; week = Monday → today;
    month = 1st → today."""
    tz = tz or _tz()
    today = now.astimezone(tz).date()
    if period == "day":
        return today, today
    if period == "month":
        return today.replace(day=1), today
    return today - timedelta(days=today.weekday()), today


def utc_window(start: date, end: date, tz: Optional[ZoneInfo] = None) -> tuple[datetime, datetime]:
    tz = tz or _tz()
    lo = datetime.combine(start, time.min, tzinfo=tz).astimezone(timezone.utc)
    hi = datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz).astimezone(timezone.utc)
    return lo, hi


# ---------------------------------------------------------------------------
# Text template (FR default, EN) — one compact block
# ---------------------------------------------------------------------------

_T = {
    "fr": {
        "title": {"day": "Récap jour", "week": "Récap semaine", "month": "Récap mois"},
        "empty": "Aucune recommandation sur la période.",
        "received": "Recommandations reçues : {n}",
        "decisions": "Validées {a} · Refusées {r} · Corrigées {c}",
        "pending": "Sans réponse {n} · À confirmer {p}",
        "error": "Écart moyen prévision/réel : {e} % ({d} jour{s} mesuré{s})",
        "error_none": "Écart prévision/réel : aucun couvert réel saisi sur la période.",
        "sources": "Décidé via : {items}",
        "sources_none": "Décidé via : aucune décision.",
        "agent_note": "Décisions d'agent autonome : {n} (exclues des taux de confiance).",
        "fix": "Décision mal enregistrée ? Répondez « corriger mardi ».",
        "risk_head": "Risque par option, sans réponse :",
        "bucket": {"button": "bouton", "keyword": "mot-clé", "model": "modèle",
                   "confirmed": "confirmé", "revised": "corrigé après coup",
                   "host": "outil hôte", "agent": "agent", "unattributed": "non attribué"},
    },
    "en": {
        "title": {"day": "Recap day", "week": "Recap week", "month": "Recap month"},
        "empty": "No recommendation in this period.",
        "received": "Recommendations received: {n}",
        "decisions": "Accepted {a} · Rejected {r} · Corrected {c}",
        "pending": "No reply {n} · Awaiting confirmation {p}",
        "error": "Mean forecast error: {e}% ({d} measured day{s})",
        "error_none": "Forecast error: no actual covers entered in this period.",
        "sources": "Decided via: {items}",
        "sources_none": "Decided via: no decision.",
        "agent_note": "Autonomous agent decisions: {n} (excluded from trust rates).",
        "fix": "Decision recorded wrong? Reply \"fix tuesday\".",
        "risk_head": "Risk per option, no reply yet:",
        "bucket": {"button": "button", "keyword": "keyword", "model": "model",
                   "confirmed": "confirmed", "revised": "fixed later",
                   "host": "host tool", "agent": "agent", "unattributed": "unattributed"},
    },
}


# At most this many recommendations get their risk lines in the recap text
# (all of them are in as_dict / MCP).
RECAP_RISK_MAX = 3


def _loc(locale: Optional[str]) -> str:
    return "en" if (locale or "").lower().startswith("en") else "fr"


def render_text(s: RecapSummary, locale: Optional[str] = "fr") -> str:
    t = _T[_loc(locale)]
    head = f"{t['title'][s.period]} · {s.start:%d/%m}–{s.end:%d/%m}"
    if s.received == 0:
        return f"{head}\n{t['empty']}"
    lines = [
        head,
        t["received"].format(n=s.received),
        t["decisions"].format(a=s.accepted, r=s.rejected, c=s.corrected),
        t["pending"].format(n=s.no_reply, p=s.awaiting_confirmation),
    ]
    if s.forecast_error_pct is None:
        lines.append(t["error_none"])
    else:
        lines.append(t["error"].format(
            e=f"{s.forecast_error_pct:g}", d=s.forecast_error_days,
            s="" if s.forecast_error_days == 1 else "s"))
    items = [f"{t['bucket'][b]} {s.by_source[b]}" for b in BUCKET_ORDER if s.by_source.get(b)]
    lines.append(t["sources"].format(items=" · ".join(items)) if items else t["sources_none"])
    if s.agent.decided:
        lines.append(t["agent_note"].format(n=s.agent.decided))
    if s.accepted + s.rejected + s.corrected:
        lines.append(t["fix"])
    if s.pending_risk:
        from app.services.risk_assessment import render_lines

        tz = _tz()
        lines.append(t["risk_head"])
        for item in s.pending_risk[:RECAP_RISK_MAX]:
            when = datetime.fromisoformat(item["window_start"]).astimezone(tz)
            lines.append(f"{when:%d/%m %H:%M}")
            lines.extend(f"  {line}" for line in render_lines(item["risk"], locale))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# DB loader
# ---------------------------------------------------------------------------

def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def load_rows(db: AsyncSession, tenant_id: str, lo: datetime, hi: datetime) -> list[RecRow]:
    """Recommendations of ``tenant_id`` received in [lo, hi). A recommendation
    is "received" once dispatched, or once decided by a host if it never went
    through WhatsApp. Undispatched, undecided rows are not counted."""
    from app.db.models import ManagerPrompt, StaffingRecommendation

    SR = StaffingRecommendation
    recs = (await db.execute(
        select(SR).where(
            SR.tenant_id == tenant_id,
            or_(SR.dispatched_at >= lo - timedelta(days=1),
                SR.created_at >= lo - timedelta(days=1)),
        )
    )).scalars().all()

    rows: list[RecRow] = []
    for r in recs:
        if r.dispatched_at is None and r.decided_by is None:
            continue
        received = _utc(r.dispatched_at) or _utc(r.created_at)
        if received is None or not (lo <= received < hi):
            continue
        rows.append(RecRow(
            id=r.id, received_at=received, window_start=_utc(r.window_start),
            status=r.status, decided_by=r.decided_by, decision_source=r.decision_source,
            actioned_at=_utc(r.actioned_at),
            predicted_covers=float(r.predicted_covers) if r.predicted_covers is not None else None,
            actual_covers=float(r.actual_covers) if r.actual_covers is not None else None,
            risk_assessment=r.risk_assessment if isinstance(r.risk_assessment, dict) else None,
        ))
    if not rows:
        return rows

    now = datetime.now(tz=timezone.utc)
    ids = [r.id for r in rows if r.status not in DECIDED_STATUSES]
    waiting: set = set()
    if ids:
        prompts = (await db.execute(
            select(ManagerPrompt).where(
                ManagerPrompt.recommendation_id.in_(ids),
                ManagerPrompt.kind == "decision_confirmation",
                ManagerPrompt.status == "pending",
            )
        )).scalars().all()
        waiting = {p.recommendation_id for p in prompts if (_utc(p.expires_at) or now) > now}
    return [replace(r, awaiting_confirmation=True) if r.id in waiting else r for r in rows]


async def build_recap(
    db: AsyncSession, tenant_id: str, period: str = "week",
    now: Optional[datetime] = None, start: Optional[date] = None, end: Optional[date] = None,
) -> RecapSummary:
    """Recap for a named period ending today, or for explicit local dates."""
    if period not in PERIODS:
        raise ValueError(f"period must be one of {PERIODS}")
    tz = _tz()
    if start is None or end is None:
        start, end = period_bounds(period, now or datetime.now(tz=timezone.utc), tz)
    lo, hi = utc_window(start, end, tz)
    rows = await load_rows(db, tenant_id, lo, hi)
    return summarize(rows, period, start, end, tz)
