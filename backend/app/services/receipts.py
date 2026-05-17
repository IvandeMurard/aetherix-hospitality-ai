"""Phase 2 — Agent Receipts daily composer + inbound feedback parser.

P2-1: `ReceiptsService.daily_receipt` reads `agent_action_log` for a (hotel_id, date)
      and returns a typed `ReceiptPayload`.
P2-2: Enriches each `ReceiptLine` with `memory_hits` — `operational_memory` rows
      written during that same tool call, linked via `request_id` backlink.
P2-3: `compose_narrative` builds an OQ4-tone WhatsApp message from a ReceiptPayload
      using LLMProvider (Claude Sonnet). Terse + sharp bullets + luxury feel.
P2-4: `parse_inbound` classifies a manager's WhatsApp reply into one of three intents:
      structured_correction (regex) | free_form (Haiku) | acknowledge (regex).
      Confidence logged via structured log. Auto-modified + thumbs-up prompt if < 0.6.

Memory-hits enrichment uses a single second SELECT (batch by request_id set),
not N+1 queries.

Phase 2 spec: docs/planning/phase-2-agent-receipts.md
PM-locked decisions: CLAUDE.md Decision #15.
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from datetime import date, datetime, time, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentActionLog, OperationalMemory
from app.providers.base import LLMProvider
from app.providers.factory import get_llm_provider

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

# Acknowledgement patterns — single-intent, no memory write needed
_ACK_RE = re.compile(
    r"^\s*(?:ok|okay|thanks?(?:\s+you)?|got\s+it|noted|sure|great|perfect|cool|"
    r"merci|compris|bien\s+reçu|👍|✅|💪|🙏)\s*[!.]*\s*$",
    re.IGNORECASE,
)

_HAIKU_CLASSIFIER_SYSTEM = """\
You are a hotel operations assistant classifying a manager's WhatsApp reply to a daily operational Receipt.

Classify the message into exactly one of these intents:
- structured_correction: manager corrects a specific number (covers, guests, staff count)
- free_form: manager adds context or correction that is not a simple number (events, changes, notes)
- acknowledge: pure acknowledgement with no operational content (ok, thanks, noted, emoji only)

Respond with a single JSON object only — no explanation, no markdown:
{"intent": "<intent>", "confidence": <0.0-1.0>, "outcome": "modified", "actual_value": <number or null>, "notes": "<cleaned manager note or empty string>"}\
"""

_HAIKU_CLASSIFIER_USER = "Manager reply: {text}"

# Low-confidence threshold: auto-downgrade + request thumbs-up confirmation (OQ2)
_CONFIDENCE_THRESHOLD = 0.6


class FeedbackIntent:
    """Classification result from `ReceiptsService.parse_inbound`.

    Attributes:
        intent: One of ``structured_correction``, ``free_form``, ``acknowledge``.
        outcome: Feedback outcome for `submit_feedback_to_memory` — always
                 ``"modified"`` for P2-4 (manager is correcting, not accepting/rejecting).
        actual_value: Extracted numeric value (covers, pax) or None.
        notes: Cleaned free-text note for the memory reflection.
        confidence: 1.0 for regex matches; Haiku classifier score for LLM path.
        requires_confirmation: True when confidence < _CONFIDENCE_THRESHOLD.
    """

    __slots__ = ("intent", "outcome", "actual_value", "notes", "confidence",
                 "requires_confirmation")

    def __init__(
        self,
        intent: Literal["structured_correction", "free_form", "acknowledge"],
        outcome: str,
        actual_value: Optional[float],
        notes: str,
        confidence: float,
    ) -> None:
        self.intent = intent
        self.outcome = outcome
        self.actual_value = actual_value
        self.notes = notes
        self.confidence = confidence
        self.requires_confirmation = confidence < _CONFIDENCE_THRESHOLD


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

    async def parse_inbound(self, text: str) -> FeedbackIntent:
        """Classify a manager's WhatsApp reply into a FeedbackIntent (P2-4).

        Routing:
          1. Acknowledge regex → ``acknowledge`` at confidence 1.0, no DB write.
          2. Covers regex → ``structured_correction`` at confidence 1.0.
          3. Haiku classifier → ``free_form`` or fallback.

        Confidence is logged as a structured INFO line. If confidence < 0.6 the
        caller must set ``outcome="modified"`` and request manager confirmation.
        No migration required — confidence is captured in the memory reflection
        string (ADR 0002) and the structured log.
        """
        stripped = text.strip()

        # --- Pass 1: acknowledge ---
        if _ACK_RE.match(stripped):
            intent = FeedbackIntent(
                intent="acknowledge",
                outcome="ignored",
                actual_value=None,
                notes="",
                confidence=1.0,
            )
            logger.info(
                "receipts.parse_inbound: intent=acknowledge confidence=1.0 text=%r",
                stripped[:80],
            )
            return intent

        # --- Pass 2: structured correction (regex) ---
        m = _COVERS_RE.search(stripped)
        if m:
            raw_val = m.group(1) or m.group(2)
            actual = float(raw_val) if raw_val else None
            intent = FeedbackIntent(
                intent="structured_correction",
                outcome="modified",
                actual_value=actual,
                notes=stripped,
                confidence=1.0,
            )
            logger.info(
                "receipts.parse_inbound: intent=structured_correction actual_value=%s confidence=1.0 text=%r",
                actual,
                stripped[:80],
            )
            return intent

        # --- Pass 3: Haiku classifier ---
        try:
            raw = await self._llm.complete(
                messages=[{"role": "user", "content": _HAIKU_CLASSIFIER_USER.format(text=stripped[:500])}],
                max_tokens=120,
                temperature=0.0,
                system=_HAIKU_CLASSIFIER_SYSTEM,
            )
            # Strip markdown code fences if LLM wraps the JSON
            clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            parsed = json.loads(clean)
            llm_intent: str = parsed.get("intent", "free_form")
            confidence: float = float(parsed.get("confidence", 0.5))
            actual_val: Optional[float] = parsed.get("actual_value")
            notes: str = parsed.get("notes", stripped)

            if llm_intent not in ("structured_correction", "free_form", "acknowledge"):
                llm_intent = "free_form"

            intent = FeedbackIntent(
                intent=llm_intent,  # type: ignore[arg-type]
                outcome="modified",
                actual_value=float(actual_val) if actual_val is not None else None,
                notes=notes,
                confidence=confidence,
            )
        except Exception:
            logger.exception(
                "receipts.parse_inbound: Haiku classifier failed, defaulting to free_form text=%r",
                stripped[:80],
            )
            intent = FeedbackIntent(
                intent="free_form",
                outcome="modified",
                actual_value=None,
                notes=stripped,
                confidence=0.5,
            )

        logger.info(
            "receipts.parse_inbound: intent=%s confidence=%.2f requires_confirmation=%s text=%r",
            intent.intent,
            intent.confidence,
            intent.requires_confirmation,
            stripped[:80],
        )
        return intent
