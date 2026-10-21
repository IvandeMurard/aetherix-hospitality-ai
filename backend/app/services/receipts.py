"""Phase 2 — Agent Receipts daily composer + inbound feedback parser + weekly digest.

P2-1: `ReceiptsService.daily_receipt` reads `agent_action_log` for a (hotel_id, date)
      and returns a typed `ReceiptPayload`.
P2-2: Enriches each `ReceiptLine` with `memory_hits` — `operational_memory` rows
      written during that same tool call, linked via `request_id` backlink.
P2-3: `compose_narrative` builds an OQ4-tone WhatsApp message from a ReceiptPayload
      using LLMProvider (Claude Sonnet). Terse + sharp bullets + luxury feel.
P2-4: `parse_inbound` classifies a manager's WhatsApp reply into one of three intents:
      structured_correction (regex) | free_form (Haiku) | acknowledge (regex), plus
      the manager's stance toward the recommendation (ADR-0007 §19). The model is
      shown what the recommendation proposed; `resolve_feedback` derives the
      decision from stance × proposal and decides what is written; low-confidence
      stances are confirmed with the manager, never written silently (Décision #6).
P2-5: `weekly_digest` aggregates the 3 Niveau-2 KPIs (tool success rate, memory writes,
      agent errors) from `agent_action_log` + `memory_instrumentation_daily` MV for
      the past 7 days. `compose_weekly_narrative` formats the result OQ4-style.

Memory-hits enrichment uses a single second SELECT (batch by request_id set),
not N+1 queries.

Phase 2 spec: docs/planning/phase-2-agent-receipts.md
PM-locked decisions: CLAUDE.md Decision #15.
"""
from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from datetime import date, datetime, time, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AgentActionLog,
    OperationalMemory,
    RestaurantProfile,
    StaffingRecommendation,
)
from app.i18n.abstention_messages import DEFAULT_LOCALE, localized_message
from app.providers.base import LLMProvider
from app.providers.factory import get_llm_provider
from app.services.abstention import AgentAbstention
from app.services.manager_decision import (
    DECISION_CONFIDENCE_THRESHOLD,
    ClassifierOutput,
    DecisionSource,
    PendingContext,
    Proposal,
    ReasonRouteOutput,
    Resolution,
    is_bare_ack,
    parse_model_json,
    read_staff_figure,
    resolve_bare_ack,
    resolve_model,
)

# Below this inbound-parser confidence the parser abstains (ADR-0007 §D6 / Décision #15).
_PARSER_ABSTAIN_THRESHOLD = 0.6

logger = logging.getLogger(__name__)


class MemoryHitSummary(BaseModel):
    """Condensed view of an `operational_memory` row linked to a Receipt line."""

    memory_id: str
    reflection_snippet: str  # first 200 chars
    manager_feedback: Optional[str] = None
    memory_type: str
    created_at: datetime


class ReceiptLine(BaseModel):
    """One row of an agent's daily action log, in Receipt-friendly form."""

    timestamp: datetime
    tool_name: str
    status: str  # ok | auth_error | tool_error | rate_limited | rate_limit_fallback
    request_id: str
    latency_ms: Optional[int] = None
    error_code: Optional[str] = None
    dedup_hit: Optional[bool] = None
    top_similarity: Optional[float] = None
    # P2-2: memory rows written during this call (empty for non-write calls)
    memory_hits: list[MemoryHitSummary] = Field(default_factory=list)


class ReceiptPayload(BaseModel):
    """Full Receipt for a hotel on a single UTC date.

    P2-1 returns log-only data. P2-2 enriches with memory_hits via request_id.
    P2-3 wraps this in narrative + dispatch. P2-6 renders the web view.
    """

    hotel_id: str
    receipt_date: date
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    total_actions: int
    counts_by_status: dict[str, int]
    counts_by_tool: dict[str, int]
    lines: list[ReceiptLine]


# ---------------------------------------------------------------------------
# P2-4: FeedbackIntent — inbound message classification
# ---------------------------------------------------------------------------

# Structured correction: "dinner covers 180", "covers: 80", "180 pax tonight"
_COVERS_RE = re.compile(
    r"(?:(?:dinner|lunch|breakfast|brunch|bar|room\s*service)\s+)?"
    r"covers?\s*:?\s*(\d+)"
    r"|(\d+)\s+(?:covers?|pax|guests?)",
    re.IGNORECASE,
)

_HAIKU_CLASSIFIER_SYSTEM = """\
You are a hotel operations assistant. A restaurant manager replied on WhatsApp to a staffing recommendation (or to the daily operational Receipt). You are told what the recommendation proposed. Say what STANCE the manager takes toward that proposal. Do not decide whether the recommendation is accepted or rejected: that is derived from your stance and the proposal.

stance (required, exactly one):
- adopt_proposal: the manager will do what the recommendation proposes
- decline_proposal: the manager refuses the recommendation (polite refusals, sarcasm)
- keep_current: the manager keeps the plan already in place ("we keep it as is", "we stay as scheduled")
- counter_value: the manager wants a different action or figure (another number of staff or covers, an added or removed role)
- unclear: the manager takes a position but you cannot tell which one (hesitation, "we'll see")
- none: the reply takes no position on this recommendation (a question, context only, a greeting)
If the reply is about another day or another service than the recommendation's, use unclear.
If the reply could express two different stances toward THIS proposal (e.g. "no need" to a proposal to reduce staff: no need to cut, or no need for them), give your best stance with a low confidence.

confidence: your probability (0.0-1.0) that the stance is right. Use a low value when the reply could be read two ways. Low-confidence answers are confirmed with the manager, never recorded silently.

intent: structured_correction (corrects a specific number) | free_form (context or a non-numeric change) | acknowledge (pure acknowledgement).
corrected_value: the corrected number of covers if the manager gives one, else null.
reason: the manager's reason in their own words if they give one, else null. Never invent one.
reason_route: only if a reason is given, where it belongs: memory (situational context for similar nights) | decision_rule (a rule the manager applies) | policy (a hotel or company constraint) | case_set (a case where the forecast was wrong for an identifiable cause) | upstream_filter (the input data was wrong) | null.
reason_route_confidence: 0.0-1.0, or null.

Respond with a single JSON object only, no explanation, no markdown:
{"stance": "<stance>", "confidence": <0.0-1.0>, "intent": "<intent>", "corrected_value": <number or null>, "reason": <string or null>, "reason_route": <string or null>, "reason_route_confidence": <number or null>, "notes": "<cleaned manager note or empty string>"}\
"""

# The proposal line comes first; the reply is always the last line, after
# this prefix (the eval's scripted models key on it).
_HAIKU_CLASSIFIER_USER = "Recommendation: {proposal}\nManager reply: {text}"

_REASON_ROUTER_SYSTEM = """\
A restaurant manager gave a reason after declining or correcting a staffing recommendation. Say where the reason belongs:
- memory: situational context worth recalling on similar nights (an event, weather, a group)
- decision_rule: a rule the manager applies ("never fewer than 3 servers on Fridays")
- policy: a hotel or company constraint (budget freeze, labour rule)
- case_set: a case where the forecast was wrong for an identifiable cause
- upstream_filter: the input data was wrong (occupancy, cancelled event)
- null: none of these, or you cannot tell

Respond with a single JSON object only: {"route": <string or null>, "confidence": <0.0-1.0>}\
"""

# HOS-283 + Décision #35: this classification task needs a cheap, deterministic
# model, not the reasoning one. Ask for the "fast" tier; each provider maps it
# (Claude → Haiku, Gemini fallback → Flash). Reasoning / explainability /
# narrative paths keep the default "reasoning" tier.
_CLASSIFIER_TIER = "fast"


class FeedbackIntent:
    """Classification result from `ReceiptsService.parse_inbound`.

    Attributes:
        intent: One of ``structured_correction``, ``free_form``, ``acknowledge``.
        stance: The manager's stance toward the recommendation (ADR-0007 §19):
                ``manager_decision.STANCES``. Fixed for the regex passes (bare ack
                → ``None``, resolved by rule (b); covers → ``counter_value``); the
                schema-validated answer for the model; ``None`` on a model error.
                The decision is NOT here: it depends on what the recommendation
                proposed and is derived by `resolve_feedback`.
        actual_value: Extracted / corrected numeric value (covers) or None.
        notes: Cleaned free-text note for the memory reflection.
        reason: The manager's reason if the reply gave one (model only).
        reason_route / reason_route_confidence: where the reason belongs (typed,
                  ``manager_decision.REASON_ROUTES``), as proposed by the model.
        confidence: 1.0 for regex matches; the model's score otherwise.
        requires_confirmation: True when a model stance that carries a decision
                  is below ``DECISION_CONFIDENCE_THRESHOLD`` (it will be confirmed,
                  not written). Replies with two readings are also confirmed;
                  that depends on the proposal and is decided by `resolve_feedback`.
        source: Which pass decided — ``ack_regex``, ``covers_regex``, ``llm``,
                ``llm_unmappable`` (answer failed the schema) or ``llm_error``
                (call failed). The last two never carry a stance. For a question
                (HOS-357) also ``staff_figure`` (a counter figure stated in it)
                and ``figure_unit`` (a number to qualify, nothing to decide).
        retained_delta_staff: the staffing figure the reply states as a delta
                  (``manager_decision.read_staff_figure``, HOS-354). Written only
                  with a ``modified`` decision, never guessed by the model.
        figure_unit_unknown: a number the manager must qualify ("plutôt 2").
    """

    __slots__ = ("intent", "stance", "actual_value", "notes", "reason",
                 "reason_route", "reason_route_confidence", "confidence",
                 "requires_confirmation", "source", "retained_delta_staff",
                 "figure_unit_unknown")

    def __init__(
        self,
        intent: Literal["structured_correction", "free_form", "acknowledge"],
        stance: Optional[str],
        actual_value: Optional[float],
        notes: str,
        confidence: float,
        source: str = "llm",
        reason: Optional[str] = None,
        reason_route: Optional[str] = None,
        reason_route_confidence: Optional[float] = None,
        retained_delta_staff: Optional[int] = None,
        figure_unit_unknown: Optional[int] = None,
    ) -> None:
        self.intent = intent
        self.stance = stance
        self.actual_value = actual_value
        self.notes = notes
        self.reason = reason
        self.reason_route = reason_route
        self.reason_route_confidence = reason_route_confidence
        self.confidence = confidence
        self.source = source
        self.retained_delta_staff = retained_delta_staff
        self.figure_unit_unknown = figure_unit_unknown
        self.requires_confirmation = (
            source == "llm"
            and stance in ("adopt_proposal", "decline_proposal", "keep_current", "counter_value")
            and confidence < DECISION_CONFIDENCE_THRESHOLD
        )


def resolve_feedback(feedback: FeedbackIntent, ctx: PendingContext) -> Resolution:
    """What production does with a parsed free-text reply (ADR-0007 §16, §19).

    Single definition shared by the Twilio route and the parser eval (EVAL-4):

    * bare acknowledgement (``ack_regex``) → rule (b), ``resolve_bare_ack``;
    * covers pattern (``covers_regex``) → ``modified``, deterministic;
    * model (``llm``) → stance × ``ctx.proposal`` through the stance mapping:
      written at or above ``DECISION_CONFIDENCE_THRESHOLD``, confirmation below
      it or when the direction is unknown, nothing for ``none``, an explicit
      question for ``unclear``;
    * model error / schema failure → nothing written (typed ``why``). The old
      path wrote ``modified`` here; a failure is never a decision.
    """
    if feedback.source == "ack_regex":
        return resolve_bare_ack(ctx)
    if feedback.source in ("covers_regex", "staff_figure"):
        return Resolution("record", "modified", DecisionSource.correction_pattern)
    if feedback.source == "llm":
        return resolve_model(feedback.stance, feedback.confidence, ctx.proposal)
    if feedback.source == "figure_unit":
        return Resolution("none", why="figure_unit_unknown")
    return Resolution("none", why=feedback.source)


def resolve_question(feedback: FeedbackIntent, ctx: PendingContext) -> Resolution:
    """A question never writes a decision (HOS-357, Décisions #6, #38).

    The position stated in it, if any ("pourquoi 3 extras ? 2 suffisent", "ok
    mais pourquoi ?"), is resolved like any reply, then always CONFIRMED with
    the manager, whatever the confidence: ``record`` becomes ``confirm`` (origin
    ``question``). No position → ``none``: the question is only answered.
    Shared by the Twilio route and the parser eval, like `resolve_feedback`."""
    res = resolve_feedback(feedback, ctx)
    if res.action in ("record", "confirm") and res.decision is not None:
        return Resolution("confirm", res.decision, origin="question",
                          confidence=res.confidence, why=res.why or "question")
    return res


def outcome_for_feedback(feedback: FeedbackIntent, ctx: PendingContext) -> Optional[str]:
    """The decision written for a parsed reply, or ``None`` (confirmation asked,
    or nothing to record). Thin view over `resolve_feedback`."""
    res = resolve_feedback(feedback, ctx)
    return res.decision if res.action == "record" else None


# ---------------------------------------------------------------------------
# P2-5: WeeklyDigestPayload — weekly KPI aggregates
# ---------------------------------------------------------------------------

class WeeklyDigestPayload(BaseModel):
    """Weekly KPI digest for one hotel covering the past 7 days.

    KPIs are derived from available data sources:
    - tool_success_rate_pct: fraction of ok calls in agent_action_log (proxy for reliability)
    - memory_writes_week: total operational_memory rows written (memory adoption)
    - memory_pending_pct: % writes still awaiting embedding (data quality indicator)
    - agent_error_count: total non-ok agent_action_log rows (incident count proxy)

    MAPE and labor_cost_variance require PMS actual data — deferred to live pilot (Phase 3).
    """

    hotel_id: str
    week_start: date
    week_end: date
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    total_agent_actions: int
    tool_success_rate_pct: float  # 0–100
    agent_error_count: int
    memory_writes_week: int
    memory_pending_pct: float  # 0–100; 0.0 if no MV data

    # P3-12 (HOS-202): real forecast accuracy from ground-truth actual_covers
    # (manager feedback persisted by HOS-200). MAPE is the Level-1 product KPI.
    mape_week: Optional[float] = None          # None when < 3 cover observations
    predicted_covers_week: Optional[int] = None
    actual_covers_week: Optional[int] = None
    cover_observations: int = 0


_WEEKLY_NARRATIVE_SYSTEM = """\
You are the Aetherix F&B operations agent composing a weekly KPI digest for a hotel manager.

Tone rules (OQ4 — PM-locked 19/04/2026):
- Terse + sharp bullets + luxury feel
- Never 1st-person narrative
- Always evidence-led bullets with quantified data
- End with explicit trend indicator: Trending Up / Stable / Trending Down
- End with a single proactive follow-up offer
- Maximum 6 bullet points
- No emojis, no markdown headers, plain text only
- Forecast-accuracy framing (when MAPE is present): MAPE < 15% → present it as concrete
  evidence of forecasting value; 15–22% → present it neutrally; > 22% → present it
  honestly and note it may not be representative yet (early sample)\
"""

_WEEKLY_NARRATIVE_PROMPT = """\
Compose a weekly KPI digest for {hotel_name} — week of {week_start} to {week_end}.

Agent activity this week:
- Total agent actions: {total_actions}
- Tool success rate: {success_rate:.1f}%
- Errors / non-ok calls: {error_count}
- Memory writes (new feedback & reflections): {memory_writes}
- Memory pending embedding: {memory_pending:.1f}%
- {mape_line}

Write the weekly digest now.\
"""


def _format_mape_line(payload: "WeeklyDigestPayload") -> str:
    """Render the forecast-accuracy line for the weekly digest (HOS-202, AC3).

    Shared by the LLM prompt and the non-LLM fallback so MAPE always surfaces.
    """
    if payload.mape_week is None:
        return (
            "Forecast accuracy: insufficient data (< 3 cover observations) "
            "— share actuals via WhatsApp after each service."
        )
    return (
        f"Forecast accuracy this week: MAPE {payload.mape_week:.1f}% "
        f"({payload.cover_observations} observations)"
    )


_OQ4_SYSTEM = """\
You are the Aetherix F&B operations agent composing a daily Receipt for a hotel manager.

Tone rules (OQ4 — PM-locked 19/04/2026):
- Terse + sharp bullets + luxury feel
- Never 1st-person narrative ("I predicted…", "I found…")
- Always evidence-led bullets — cite the data source inline
- At least one quantified comparative (vs baseline / vs similar nights) when data permits
- End with explicit confidence on a single line: "Confidence: High / Medium / Low"
- End with a single proactive follow-up offer as the last line
- Maximum 7 bullet points total
- No emojis
- No verbose preamble — start directly with the bullets
- Output plain text only, no markdown headers\
"""

_RECEIPT_NARRATIVE_PROMPT = """\
Compose a daily Receipt message for {hotel_name} — {receipt_date}.

Agent activity summary:
- Total actions: {total_actions}
- Breakdown by status: {counts_by_status}
- Breakdown by tool: {counts_by_tool}
- Memory hits (patterns that shaped recommendations): {memory_hit_count} hit(s) across {memory_hit_tools} tool call(s)

Key actions (most recent first, max 5):
{action_summary}

Deep link for full breakdown: {drill_down_url}

Write the Receipt message now.\
"""


class ReceiptsService:
    """Daily Receipt composer. Stateless beyond the injected DB session."""

    def __init__(self, db: AsyncSession, llm: LLMProvider | None = None):
        self.db = db
        self._llm: LLMProvider = llm or get_llm_provider()

    async def daily_receipt(
        self, hotel_id: str, target_date: date
    ) -> ReceiptPayload:
        """Build a `ReceiptPayload` for `hotel_id` on `target_date`.

        Date boundaries are inclusive UTC (00:00:00 → 23:59:59.999999).
        Memory enrichment uses one additional batch SELECT (P2-2).
        """
        day_start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
        day_end = datetime.combine(target_date, time.max, tzinfo=timezone.utc)

        result = await self.db.execute(
            select(AgentActionLog)
            .where(AgentActionLog.hotel_id == hotel_id)
            .where(AgentActionLog.created_at >= day_start)
            .where(AgentActionLog.created_at <= day_end)
            .order_by(AgentActionLog.created_at.asc())
        )
        rows = result.scalars().all()

        lines = [
            ReceiptLine(
                timestamp=r.created_at,
                tool_name=r.tool_name,
                status=r.status,
                request_id=r.request_id or "",
                latency_ms=r.latency_ms,
                error_code=r.error_code,
                dedup_hit=r.dedup_hit,
                top_similarity=r.top_similarity,
            )
            for r in rows
        ]

        # P2-2: batch-fetch memory rows linked to these tool calls
        await self._attach_memory_hits(hotel_id, lines)

        return ReceiptPayload(
            hotel_id=hotel_id,
            receipt_date=target_date,
            total_actions=len(lines),
            counts_by_status=dict(Counter(line.status for line in lines)),
            counts_by_tool=dict(Counter(line.tool_name for line in lines)),
            lines=lines,
        )

    async def _attach_memory_hits(
        self, hotel_id: str, lines: list[ReceiptLine]
    ) -> None:
        """Enrich each ReceiptLine with memory rows sharing its request_id.

        Single batch query — no N+1. Lines with empty request_id or no matching
        memory rows keep their default empty list.
        """
        request_ids = {line.request_id for line in lines if line.request_id}
        if not request_ids:
            return

        mem_result = await self.db.execute(
            select(OperationalMemory)
            .where(OperationalMemory.hotel_id == hotel_id)
            .where(OperationalMemory.request_id.in_(request_ids))
            .order_by(OperationalMemory.created_at.asc())
        )
        memory_rows = mem_result.scalars().all()

        hits_by_rid: dict[str, list[MemoryHitSummary]] = defaultdict(list)
        for m in memory_rows:
            hits_by_rid[m.request_id].append(
                MemoryHitSummary(
                    memory_id=str(m.id),
                    reflection_snippet=(m.reflection or "")[:200],
                    manager_feedback=m.manager_feedback,
                    memory_type=m.memory_type,
                    created_at=m.created_at,
                )
            )

        for line in lines:
            if line.request_id in hits_by_rid:
                line.memory_hits = hits_by_rid[line.request_id]

    async def compose_narrative(
        self,
        payload: ReceiptPayload,
        hotel_name: str,
        drill_down_url: str,
    ) -> str:
        """Compose an OQ4-tone WhatsApp Receipt narrative via LLMProvider.

        Returns a plain-text string ready for Twilio / SendGrid dispatch.
        Max 7 bullets, terse + luxury, evidence-led (PM-locked Decision #15 OQ4).
        """
        lines_with_hits = [ln for ln in payload.lines if ln.memory_hits]
        memory_hit_count = sum(len(ln.memory_hits) for ln in lines_with_hits)

        recent_lines = sorted(payload.lines, key=lambda ln: ln.timestamp, reverse=True)[:5]
        action_summary_parts = []
        for ln in recent_lines:
            hit_note = f" [{len(ln.memory_hits)} memory hit(s)]" if ln.memory_hits else ""
            action_summary_parts.append(
                f"  - {ln.tool_name} | {ln.status}{hit_note}"
            )
        action_summary = "\n".join(action_summary_parts) or "  (no actions recorded)"

        user_msg = _RECEIPT_NARRATIVE_PROMPT.format(
            hotel_name=hotel_name,
            receipt_date=payload.receipt_date.isoformat(),
            total_actions=payload.total_actions,
            counts_by_status=payload.counts_by_status,
            counts_by_tool=payload.counts_by_tool,
            memory_hit_count=memory_hit_count,
            memory_hit_tools=len(lines_with_hits),
            action_summary=action_summary,
            drill_down_url=drill_down_url,
        )

        try:
            narrative = await self._llm.complete(
                messages=[{"role": "user", "content": user_msg}],
                max_tokens=400,
                temperature=0.2,
                system=_OQ4_SYSTEM,
            )
        except Exception:
            logger.exception(
                "receipts: LLM narrative composition failed hotel_id=%s date=%s",
                payload.hotel_id,
                payload.receipt_date,
            )
            narrative = (
                f"Daily Receipt — {payload.receipt_date}\n"
                f"{hotel_name}\n\n"
                f"• {payload.total_actions} agent action(s) recorded\n"
                f"• Status breakdown: {payload.counts_by_status}\n\n"
                f"Full breakdown: {drill_down_url}"
            )

        return narrative.strip()

    async def parse_inbound(
        self, text: str, proposal: Optional[Proposal] = None, question: bool = False,
    ) -> FeedbackIntent:
        """Classify a manager's WhatsApp reply into a FeedbackIntent (P2-4, ADR-0007 §16, §19).

        ``proposal``: what the pending recommendation proposed (direction,
        magnitude, task class, window), shown to the model. ``None`` → the model
        is told the direction is not recorded; the stance mapping then asks
        instead of guessing whenever the decision depends on it.

        Routing:
          1. Bare acknowledgement (``manager_decision.is_bare_ack``) → ``acknowledge``,
             no stance (rule (b) decides later), no model call.
          2. Covers regex → ``structured_correction``, stance ``counter_value``.
          3. Model (fast tier) → stance, validated against ``ClassifierOutput``.
             A call failure is ``llm_error``, a schema failure ``llm_unmappable``:
             neither carries a stance, nothing is coerced.
        A staffing figure stated as a delta ("2 extras") is read deterministically
        and carried as ``retained_delta_staff`` (HOS-354); the model never gives it.

        ``question`` (HOS-357, ``manager_decision.is_question``): the reply asks
        something. Passes 1-2 are skipped (a covers figure in a question quotes
        the forecast, it does not correct it). A counter figure in it →
        ``staff_figure``; a number to qualify → ``figure_unit``; otherwise the
        model reads the position, if any. `resolve_question` confirms whatever
        it lands on.

        Explicit keywords ("oui", "refusé", "✅") never reach this method: the
        route matches them first (``action_logger.parse_action``).
        """
        stripped = text.strip()
        figure = read_staff_figure(stripped, proposal)
        figure_delta = figure.delta if figure else None

        if question and figure is not None:
            if figure.delta is not None:
                return FeedbackIntent(
                    intent="structured_correction", stance="counter_value", actual_value=None,
                    notes=stripped, confidence=1.0, source="staff_figure",
                    retained_delta_staff=figure.delta,
                )
            return FeedbackIntent(
                intent="free_form", stance=None, actual_value=None, notes=stripped,
                confidence=1.0, source="figure_unit", figure_unit_unknown=figure.unit_unknown,
            )

        # --- Pass 1: bare acknowledgement ---
        if not question and is_bare_ack(stripped):
            intent = FeedbackIntent(
                intent="acknowledge",
                stance=None,
                actual_value=None,
                notes="",
                confidence=1.0,
                source="ack_regex",
            )
            logger.info(
                "receipts.parse_inbound: intent=acknowledge confidence=1.0 text=%r",
                stripped[:80],
            )
            return intent

        # --- Pass 2: structured correction (regex) ---
        m = None if question else _COVERS_RE.search(stripped)
        if m:
            raw_val = m.group(1) or m.group(2)
            actual = float(raw_val) if raw_val else None
            intent = FeedbackIntent(
                intent="structured_correction",
                stance="counter_value",
                actual_value=actual,
                notes=stripped,
                confidence=1.0,
                source="covers_regex",
                retained_delta_staff=figure_delta,
            )
            logger.info(
                "receipts.parse_inbound: intent=structured_correction actual_value=%s confidence=1.0 text=%r",
                actual,
                stripped[:80],
            )
            return intent

        # --- Pass 3: model, schema-validated ---
        try:
            raw = await self._llm.complete(
                messages=[{"role": "user", "content": _HAIKU_CLASSIFIER_USER.format(
                    proposal=(proposal or Proposal()).describe(), text=stripped[:500])}],
                max_tokens=200,
                temperature=0.0,
                system=_HAIKU_CLASSIFIER_SYSTEM,
                tier=_CLASSIFIER_TIER,
            )
        except Exception:
            logger.exception(
                "receipts.parse_inbound: classifier call failed text=%r", stripped[:80]
            )
            intent = FeedbackIntent(
                intent="free_form", stance=None, actual_value=None,
                notes=stripped, confidence=0.0, source="llm_error",
            )
        else:
            try:
                out = parse_model_json(raw, ClassifierOutput)
            except ValueError:  # pydantic ValidationError is a ValueError
                logger.warning(
                    "receipts.parse_inbound: classifier answer failed the schema text=%r raw=%r",
                    stripped[:80],
                    raw[:200],
                )
                intent = FeedbackIntent(
                    intent="free_form", stance=None, actual_value=None,
                    notes=stripped, confidence=0.0, source="llm_unmappable",
                )
            else:
                intent = FeedbackIntent(
                    intent=out.intent,
                    stance=out.stance,
                    # A covers figure in a question quotes the forecast.
                    actual_value=None if question else out.corrected_value,
                    notes=out.notes or stripped,
                    confidence=out.confidence,
                    source="llm",
                    reason=out.reason,
                    reason_route=out.reason_route,
                    reason_route_confidence=out.reason_route_confidence,
                    retained_delta_staff=figure_delta,
                )

        logger.info(
            "receipts.parse_inbound: intent=%s stance=%s source=%s confidence=%.2f "
            "requires_confirmation=%s text=%r",
            intent.intent,
            intent.stance,
            intent.source,
            intent.confidence,
            intent.requires_confirmation,
            stripped[:80],
        )
        return intent

    async def route_reason(self, text: str) -> tuple[Optional[str], Optional[float]]:
        """Route a follow-up reason (after a reject / correction) to one of
        ``REASON_ROUTES``. Returns ``(route, confidence)``; ``(None, None)`` on a
        model error or schema failure — the reason is then kept unrouted."""
        try:
            raw = await self._llm.complete(
                messages=[{"role": "user", "content": f"Reason: {text.strip()[:500]}"}],
                max_tokens=60,
                temperature=0.0,
                system=_REASON_ROUTER_SYSTEM,
                tier=_CLASSIFIER_TIER,
            )
            out = parse_model_json(raw, ReasonRouteOutput)
        except Exception:
            logger.warning("receipts.route_reason: routing failed, reason kept unrouted")
            return None, None
        return out.route, out.confidence

    # -----------------------------------------------------------------------
    # P3-11b (HOS-217 / EVAL-2): AgentAbstention contract — parser low-confidence
    # + the 3 manager-facing WhatsApp variants (ADR-0007 §D6). The reason code is
    # ALWAYS resolved through the i18n mapping — never shown raw (PM caveat).
    # -----------------------------------------------------------------------
    @staticmethod
    def abstention_for_feedback(feedback: FeedbackIntent) -> Optional[AgentAbstention]:
        """Map a low-confidence inbound parse to an AgentAbstention (additive).

        Returns ``None`` when the parse is confident enough to act on. Does not
        change ``parse_inbound`` — callers opt in.
        """
        if feedback.confidence < _PARSER_ABSTAIN_THRESHOLD:
            return AgentAbstention(
                reason="parser_low_confidence",
                layer="parser",
                context={"confidence": feedback.confidence, "intent": feedback.intent},
                human_message=localized_message("parser_low_confidence"),
            )
        return None

    @staticmethod
    def _full_abstention_variant(
        forecast_reason: str,
        reco_reason: str,
        locale: str = DEFAULT_LOCALE,
        drill_down_url: str = "",
    ) -> str:
        """Variant 1 (ADR §D6.d): forecast + reco both unknown."""
        link = drill_down_url or "l'historique de l'établissement"
        return (
            "Bonjour. Ce matin, les données insuffisantes empêchent de générer "
            f"un Receipt fiable. {localized_message(reco_reason, locale)} "
            f"Vous pouvez consulter {link}."
        )

    @staticmethod
    def _partial_abstention_variant(
        forecast_summary: str,
        reco_reason: str,
        locale: str = DEFAULT_LOCALE,
    ) -> str:
        """Variant 2 (ADR §D6.d): forecast OK, recommendation abstained."""
        return (
            f"Bonjour, voici les prévisions du jour : {forecast_summary}. "
            "Aetherix n'est pas confiant pour recommander un staffing aujourd'hui. "
            f"{localized_message(reco_reason, locale)} "
            "Suggestion : maintenir le staffing standard."
        )

    @staticmethod
    def _drift_alert_variant(
        normal_body: str,
        drift_reason: str,
        locale: str = DEFAULT_LOCALE,
    ) -> str:
        """Variant 3 (ADR §D6.d): forecast + reco normal, but drift detected."""
        return (
            f"{normal_body}\n\n"
            f"Avis qualité : {localized_message(drift_reason, locale)}"
        )

    # -----------------------------------------------------------------------
    # P3-10 (HOS-200): persist manager-reported actual covers — close the
    # prediction → recommendation → feedback → actual outcome loop.
    # -----------------------------------------------------------------------
    async def persist_actual_covers(
        self,
        recommendation: StaffingRecommendation,
        actual_value: float,
        *,
        request_id: str = "",
        observed_on: date | None = None,
    ) -> Optional[OperationalMemory]:
        """Persist a manager's ground-truth covers correction.

        Story 10.10 (HOS-200). Called from the Twilio inbound handler when
        `parse_inbound` returns a ``structured_correction`` with a numeric
        ``actual_value``.

        AC1 — writes ``actual_covers`` onto the matched StaffingRecommendation,
        stamping ``actual_covers_source = "manager_feedback"`` and
        ``actual_covers_at = now()``.
        AC2 — appends a ``ground_truth`` row to ``operational_memory`` with a
        ``"actual covers X vs predicted Y on DATE"`` reflection, tagged
        ``["ground_truth", "covers_correction"]``, linked via ``request_id``
        and (HOS-317) via ``recommendation_id`` — the Decision Ledger edge.

        The caller owns the transaction (commit happens upstream so the
        recommendation update and the memory write land atomically). Returns the
        created OperationalMemory row, or ``None`` when the value was rejected by
        the feedback bounds guard (HOS-250).

        HOS-250 (Epic 12 G-3): ``actual_value`` is bounded against the property
        capacity + historical range before any write. An implausible value is
        rejected (not ingested) or flagged, per ``FEEDBACK_BOUNDS_POLICY``, and
        always raises a typed ops alert — never a silent poison of the model.
        """
        now = datetime.now(tz=timezone.utc)

        # HOS-250 — bound the value before it touches the training path.
        verdict = await self._check_feedback_bounds(
            recommendation.tenant_id, float(actual_value)
        )
        flagged = False
        if not verdict.plausible:
            from app.services.feedback_guard import record_feedback_trip

            await record_feedback_trip(
                recommendation.tenant_id,
                verdict.reason or "implausible_feedback",
                verdict.detail or "",
                verdict.severity,
                db=self.db,
            )
            if verdict.severity == "reject":
                logger.warning(
                    "receipts.persist_actual_covers: REJECTED actual=%s hotel_id=%s — %s",
                    actual_value, recommendation.tenant_id, verdict.detail,
                )
                return None
            flagged = True  # severity == "flag" → ingest but tag

        # AC1 — ground truth onto the recommendation
        recommendation.actual_covers = actual_value
        recommendation.actual_covers_source = (
            "manager_feedback_flagged" if flagged else "manager_feedback"
        )
        recommendation.actual_covers_at = now

        # AC2 — ground_truth memory row (no embedding: factual, not retrieved by
        # similarity — written pending like other non-embedded rows, ADR D9).
        predicted = recommendation.predicted_covers
        on_date = observed_on or now.date()
        reflection = (
            f"actual covers {actual_value} vs predicted {predicted} on {on_date}"
        )
        tags = ["ground_truth", "covers_correction"]
        if flagged:
            tags.append("implausible_flag")
        memory = OperationalMemory(
            hotel_id=recommendation.tenant_id,
            reflection=reflection,
            memory_type="ground_truth",
            tags=tags,
            embedding_pending=True,
            request_id=request_id,
            # HOS-317 (Decision Ledger) — the outcome leg was previously linked
            # to its recommendation only by a shared request_id, which is absent
            # on any path that doesn't originate from an inbound WhatsApp turn.
            recommendation_id=recommendation.id,
        )
        self.db.add(memory)
        await self.db.flush()

        logger.info(
            "receipts.persist_actual_covers: rec=%s actual=%s predicted=%s hotel_id=%s memory_id=%s",
            recommendation.id,
            actual_value,
            predicted,
            recommendation.tenant_id,
            memory.id,
        )
        return memory

    async def _check_feedback_bounds(self, tenant_id: str, actual_value: float):
        """HOS-250 — evaluate actual_covers against capacity + historical range.

        Looks up the property capacity (``total_seats × turns``) and the
        historical max ``actual_covers`` for the tenant. A missing profile →
        capacity is not enforced (only the lower bound applies). Any lookup
        failure degrades open (treated as plausible) so the guard never blocks
        legitimate feedback on an infra hiccup.
        """
        from app.services.feedback_guard import BoundsVerdict, evaluate

        total_seats: float | None = None
        turns_sum: float | None = None
        historical_max: float | None = None
        try:
            profile = (
                await self.db.execute(
                    select(RestaurantProfile).where(
                        RestaurantProfile.tenant_id == tenant_id
                    )
                )
            ).scalars().first()
            if profile is not None and profile.total_seats:
                total_seats = float(profile.total_seats)
                turns_sum = (
                    float(profile.turns_breakfast or 0)
                    + float(profile.turns_lunch or 0)
                    + float(profile.turns_dinner or 0)
                )
            # HOS-268: exclude flagged-but-ingested rows from the historical max.
            # Under FEEDBACK_BOUNDS_POLICY="flag" an implausible value is persisted
            # tagged "manager_feedback_flagged"; counting it here would let the soft
            # historical-sanity bound self-erode (each aberrant value raises the max,
            # admitting the next). NULL-safe: legacy rows (source unset) still count.
            from sqlalchemy import or_
            hist = (
                await self.db.execute(
                    select(func.max(StaffingRecommendation.actual_covers)).where(
                        StaffingRecommendation.tenant_id == tenant_id,
                        StaffingRecommendation.actual_covers.is_not(None),
                        or_(
                            StaffingRecommendation.actual_covers_source.is_(None),
                            StaffingRecommendation.actual_covers_source != "manager_feedback_flagged",
                        ),
                    )
                )
            ).scalar_one_or_none()
            if hist is not None:
                historical_max = float(hist)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "receipts._check_feedback_bounds: lookup failed hotel_id=%s: %s",
                tenant_id, exc,
            )
            return BoundsVerdict(True, "ok")

        return evaluate(
            actual_value,
            total_seats=total_seats,
            turns_sum=turns_sum,
            historical_max=historical_max,
        )

    async def weekly_digest(
        self, hotel_id: str, week_end: date
    ) -> WeeklyDigestPayload:
        """Build a WeeklyDigestPayload for `hotel_id` covering the 7 days ending on `week_end` (P2-5).

        Queries:
          1. `agent_action_log` — total actions + status breakdown for the week.
          2. `memory_instrumentation_daily` MV — total writes + pending_pct for the week.

        MAPE and labor_cost_variance require live PMS actuals — deferred to Phase 3.
        """
        from datetime import timedelta

        week_start = week_end - timedelta(days=6)
        day_start = datetime.combine(week_start, time.min, tzinfo=timezone.utc)
        day_end = datetime.combine(week_end, time.max, tzinfo=timezone.utc)

        # 1. agent_action_log aggregates for the week
        log_result = await self.db.execute(
            select(AgentActionLog)
            .where(AgentActionLog.hotel_id == hotel_id)
            .where(AgentActionLog.created_at >= day_start)
            .where(AgentActionLog.created_at <= day_end)
        )
        log_rows = log_result.scalars().all()

        total_actions = len(log_rows)
        ok_count = sum(1 for r in log_rows if r.status == "ok")
        error_count = total_actions - ok_count
        success_rate = (ok_count / total_actions * 100.0) if total_actions > 0 else 0.0

        # 2. memory_instrumentation_daily MV — raw SQL (no ORM model for MV)
        mv_result = await self.db.execute(
            text(
                "SELECT COALESCE(SUM(writes), 0) AS total_writes, "
                "COALESCE(AVG(pending_pct), 0) AS avg_pending_pct "
                "FROM memory_instrumentation_daily "
                "WHERE hotel_id = :hotel_id AND date BETWEEN :week_start AND :week_end"
            ),
            {"hotel_id": hotel_id, "week_start": week_start, "week_end": week_end},
        )
        mv_row = mv_result.fetchone()
        memory_writes = int(mv_row[0]) if mv_row else 0
        memory_pending_pct = float(mv_row[1]) if mv_row else 0.0

        # 3. Forecast accuracy (HOS-202 / P3-12): real MAPE from ground-truth
        # actual_covers persisted via manager feedback (HOS-200). Only rows with
        # both predicted and actual present, and actual != 0 (MAPE divides by it).
        rec_result = await self.db.execute(
            select(
                StaffingRecommendation.predicted_covers,
                StaffingRecommendation.actual_covers,
            )
            .where(StaffingRecommendation.tenant_id == hotel_id)
            .where(StaffingRecommendation.actual_covers.isnot(None))
            .where(StaffingRecommendation.predicted_covers.isnot(None))
            .where(StaffingRecommendation.window_start >= day_start)
            .where(StaffingRecommendation.window_start <= day_end)
        )
        observations = [
            (float(p), float(a))
            for p, a in rec_result.all()
            if p is not None and a is not None and float(a) != 0.0
        ]
        cover_observations = len(observations)
        if cover_observations == 0:
            mape_week = None
            predicted_covers_week = None
            actual_covers_week = None
        else:
            predicted_covers_week = round(sum(p for p, _ in observations))
            actual_covers_week = round(sum(a for _, a in observations))
            # < 3 observations is too thin to publish an accuracy number (AC5).
            mape_week = (
                round(
                    sum(abs(a - p) / a for p, a in observations)
                    / cover_observations
                    * 100,
                    1,
                )
                if cover_observations >= 3
                else None
            )

        return WeeklyDigestPayload(
            hotel_id=hotel_id,
            week_start=week_start,
            week_end=week_end,
            total_agent_actions=total_actions,
            tool_success_rate_pct=round(success_rate, 1),
            agent_error_count=error_count,
            memory_writes_week=memory_writes,
            memory_pending_pct=round(memory_pending_pct, 1),
            mape_week=mape_week,
            predicted_covers_week=predicted_covers_week,
            actual_covers_week=actual_covers_week,
            cover_observations=cover_observations,
        )

    async def compose_weekly_narrative(
        self,
        payload: WeeklyDigestPayload,
        hotel_name: str,
    ) -> str:
        """Compose an OQ4-tone weekly digest message via LLMProvider (P2-5).

        Returns a plain-text string ready for Twilio / SendGrid dispatch.
        Falls back to a structured plain-text summary on LLM error.
        """
        user_msg = _WEEKLY_NARRATIVE_PROMPT.format(
            hotel_name=hotel_name,
            week_start=payload.week_start.isoformat(),
            week_end=payload.week_end.isoformat(),
            total_actions=payload.total_agent_actions,
            success_rate=payload.tool_success_rate_pct,
            error_count=payload.agent_error_count,
            memory_writes=payload.memory_writes_week,
            memory_pending=payload.memory_pending_pct,
            mape_line=_format_mape_line(payload),
        )

        try:
            narrative = await self._llm.complete(
                messages=[{"role": "user", "content": user_msg}],
                max_tokens=350,
                temperature=0.2,
                system=_WEEKLY_NARRATIVE_SYSTEM,
            )
        except Exception:
            logger.exception(
                "receipts: weekly narrative composition failed hotel_id=%s week_end=%s",
                payload.hotel_id,
                payload.week_end,
            )
            narrative = (
                f"Weekly Digest — {payload.week_start} to {payload.week_end}\n"
                f"{hotel_name}\n\n"
                f"• {payload.total_agent_actions} agent actions — "
                f"{payload.tool_success_rate_pct:.0f}% success rate\n"
                f"• {payload.agent_error_count} error(s) this week\n"
                f"• {payload.memory_writes_week} memory write(s), "
                f"{payload.memory_pending_pct:.0f}% pending embedding\n"
                f"• {_format_mape_line(payload)}"
            )

        return narrative.strip()
