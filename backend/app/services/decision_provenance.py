"""Decision provenance and the reason contract for agent callers (ADR-0007 §17).

Aetherix can be integrated headless: the party that accepts or rejects a
recommendation may be a host platform's agent, calling the MCP tool
``submit_feedback_to_memory``. Two things are recorded with every decision:

* **who decided** — ``DecidedBy``. Only human deciders count as a human trust
  signal (acceptance rate, override rate, response time). A decision taken by a
  host agent on its own is stored, flagged, and kept out of those metrics.
* **why** (agent callers only) — a structured reason: a closed ``reason_code``,
  a short sanitised ``reason_detail``, optional ``evidence``, and
  ``reason_source``. When a host agent relays a human's decision and the human
  gave no reason, the agent says so (``none_given``) or flags its own guess as
  ``agent_inferred``: a guessed reason is never stored as the human's.

The burden stays on the agent, not the human: for ``human_via_host`` the human
may give no reason (``none_given`` + ``reason_source=human``). What the agent
sends is always structured.

"Required" is not "informative": required fields get filled with filler.
``informativeness`` measures, per caller, the share of ``other``, of empty
details and of near-duplicate details — a runtime signal (arm B), not a gate.

Pure module (no DB). Rules pinned by ``tests/services/test_decision_provenance.py``.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.mcp_core import sanitize_notes


class DecidedBy(str, Enum):
    human_whatsapp = "human_whatsapp"                # manager on WhatsApp (Décision #38)
    human_via_host = "human_via_host"                # a human, relayed by a host agent via MCP
    host_agent_autonomous = "host_agent_autonomous"  # the host agent decided alone
    # Reserved: a policy-defined default on expiry. Never written today — an
    # unanswered recommendation is "no reply", not a decision (Décision #6).
    timeout = "timeout"


HUMAN_DECIDERS: frozenset[str] = frozenset({
    DecidedBy.human_whatsapp.value, DecidedBy.human_via_host.value,
})
AGENT_DECIDERS: frozenset[str] = frozenset({DecidedBy.host_agent_autonomous.value})

# What an MCP caller may declare. human_whatsapp is set by the WhatsApp path
# only; timeout is reserved.
MCP_DECIDED_BY: tuple[str, ...] = (
    DecidedBy.human_via_host.value, DecidedBy.host_agent_autonomous.value,
)

# Closed reason vocabulary, F&B staffing domain. Positive and negative reasons
# are both required from agent callers: "why accepted" is as useful as "why not".
REASON_CODES: dict[str, str] = {
    # accept
    "agrees_with_drivers": "the forecast drivers (occupancy, events, weather) match what the caller sees",
    "matches_own_plan": "the recommendation matches a plan the team already had",
    # reject / correct
    "forecast_too_high": "expected covers are too high",
    "forecast_too_low": "expected covers are too low",
    "event_not_in_forecast": "a known event or group is missing from the forecast",
    "event_cancelled": "an event the forecast relies on is cancelled",
    "staffing_constraint": "people are not available (rota, sickness, contract hours)",
    "budget": "labour budget does not allow it",
    "policy": "a hotel or company rule forbids it",
    "data_issue": "an input is wrong (PMS occupancy, outlet hours, duplicate)",
    "already_handled": "the need is already covered by another action",
    # relayed human decision without a reason — allowed, never a guess
    "none_given": "the human gave no reason (human_via_host only)",
    "other": "none of the above — reason_detail required",
}

REASON_DETAIL_MAX = 280
EVIDENCE_SOURCES: tuple[str, ...] = (
    "pms", "pos", "weather", "events", "rota", "manager_message", "host_notes", "other",
)


class ProvenanceError(ValueError):
    """Typed rejection of an agent decision (→ MCP 400 ``invalid_input``)."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["pms", "pos", "weather", "events", "rota", "manager_message", "host_notes", "other"]
    detail: str = Field(default="", max_length=200)

    @field_validator("detail")
    @classmethod
    def _clean(cls, v: str) -> str:
        return sanitize_notes(v, max_len=200)


class AgentDecision(BaseModel):
    """What an MCP caller must send with a decision. Validated, never coerced."""

    model_config = ConfigDict(extra="forbid")

    decided_by: Literal["human_via_host", "host_agent_autonomous"]
    reason_code: str
    reason_detail: str = Field(default="", max_length=2000)
    reason_source: Literal["human", "agent_inferred"]
    evidence: list[Evidence] = Field(default_factory=list, max_length=5)

    @field_validator("reason_detail")
    @classmethod
    def _clean_detail(cls, v: str) -> str:
        return sanitize_notes(v, max_len=REASON_DETAIL_MAX)


def parse_agent_decision(raw: dict) -> AgentDecision:
    """Validate the provenance + reason fields of an MCP decision.

    Raises ``ProvenanceError`` with a typed code:
      * ``missing_provenance`` / ``invalid_provenance`` — schema failure
      * ``unknown_reason_code``
      * ``reason_detail_required`` — ``other`` without a detail
      * ``none_given_not_allowed`` — ``none_given`` is only for a human decision
        relayed as such (``human_via_host`` + ``reason_source=human``)
      * ``autonomous_reason_must_be_agent_inferred`` — an agent deciding alone
        cannot attribute its reason to a human
    """
    required = ("decided_by", "reason_code", "reason_source")
    missing = [k for k in required if raw.get(k) in (None, "")]
    if missing:
        raise ProvenanceError(
            "missing_provenance",
            f"agent decisions must carry {', '.join(required)}; missing: {', '.join(missing)}",
        )
    try:
        d = AgentDecision.model_validate(raw)
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = ".".join(str(x) for x in first.get("loc", ()))
        raise ProvenanceError("invalid_provenance", f"{loc}: {first.get('msg')}") from exc
    if d.reason_code not in REASON_CODES:
        raise ProvenanceError(
            "unknown_reason_code", f"reason_code must be one of {', '.join(REASON_CODES)}"
        )
    if d.reason_code == "other" and not d.reason_detail:
        raise ProvenanceError("reason_detail_required", "reason_code 'other' needs a reason_detail")
    if d.reason_code == "none_given" and not (
        d.decided_by == "human_via_host" and d.reason_source == "human"
    ):
        raise ProvenanceError(
            "none_given_not_allowed",
            "'none_given' is only for a human decision relayed as such "
            "(decided_by=human_via_host, reason_source=human)",
        )
    if d.decided_by == "host_agent_autonomous" and d.reason_source != "agent_inferred":
        raise ProvenanceError(
            "autonomous_reason_must_be_agent_inferred",
            "an autonomous agent decision cannot carry a human reason",
        )
    return d


# ---------------------------------------------------------------------------
# Informativeness guard — runtime signal (arm B), per caller
# ---------------------------------------------------------------------------

_WS = re.compile(r"\s+")
_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)


def _norm_detail(text: Optional[str]) -> str:
    return _WS.sub(" ", _NON_WORD.sub(" ", (text or "").lower())).strip()


@dataclass
class CallerInformativeness:
    caller: str
    decisions: int = 0
    other_share: Optional[float] = None
    empty_detail_share: Optional[float] = None
    near_duplicate_detail_share: Optional[float] = None
    agent_inferred_share: Optional[float] = None
    reason_codes: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def informativeness(records: Iterable[dict]) -> list[CallerInformativeness]:
    """Per caller: share of ``other``, of empty details, of near-duplicate
    details (same normalised text as another decision of the same caller), of
    ``agent_inferred`` reasons. Records: dicts with ``caller``, ``reason_code``,
    ``reason_detail``, ``reason_source``. Only records carrying a reason_code
    (agent callers) are considered.

    High shares mean the required fields are filled, not informative. It is a
    signal to look at, not a threshold that rejects calls.
    """
    by_caller: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        if r.get("reason_code"):
            by_caller[r.get("caller") or "unknown"].append(r)
    out: list[CallerInformativeness] = []
    for caller, rows in sorted(by_caller.items()):
        n = len(rows)
        details = [_norm_detail(r.get("reason_detail")) for r in rows]
        counts = Counter(d for d in details if d)
        dup = sum(1 for d in details if d and counts[d] > 1)
        out.append(CallerInformativeness(
            caller=caller,
            decisions=n,
            other_share=round(sum(1 for r in rows if r["reason_code"] == "other") / n, 4),
            empty_detail_share=round(sum(1 for d in details if not d) / n, 4),
            near_duplicate_detail_share=round(dup / n, 4),
            agent_inferred_share=round(
                sum(1 for r in rows if r.get("reason_source") == "agent_inferred") / n, 4),
            reason_codes=dict(sorted(Counter(r["reason_code"] for r in rows).items())),
        ))
    return out
