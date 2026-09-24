"""Manager decision capture — pure rules (ADR-0007 §16, Décision #38).

How a manager's reply to a staffing recommendation becomes a recorded
**decision** (``accepted | rejected | modified``) or nothing.

Principle (PO decision, 24/09/2026):

* The **decision** is arm C's ground truth (outcome eval, ADR-0007 §13). It is
  decided deterministically wherever possible (button payload, exact keyword,
  bare-acknowledgement rule), cheap, unambiguous and auditable: every recorded
  decision carries its ``DecisionSource``.
* The **comment** (reason, detail) is optional and rich. It never changes a
  recorded decision.
* HITL (Décision #6): a model-inferred decision below
  ``DECISION_CONFIDENCE_THRESHOLD``, an ambiguous keyword, or a bare
  acknowledgement that cannot be attributed to exactly one pending
  recommendation is **not written**. The manager is asked to confirm; nothing
  is recorded until they do. Unconfirmed after the window → recorded as
  unconfirmed, never as a decision.
* The outcome (actual covers) is never an input here. Decision and outcome stay
  independent variables, or arm C learns circularly (§16.6). Nothing in this
  module reads ``actual_covers``.

Everything in this module is pure (no DB, no network) and unit-tested
form by form in ``tests/services/test_manager_decision.py``.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Iterable, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

Decision = Literal["accepted", "rejected", "modified", "none"]
RECORDABLE_DECISIONS: frozenset[str] = frozenset({"accepted", "rejected", "modified"})


class DecisionSource(str, Enum):
    """Which step decided a recorded decision. Stored on
    ``staffing_recommendations.decision_source`` and on every reply event, so
    arm C can keep an explicit accept apart from an inferred one."""

    button = "button"                        # WhatsApp quick-reply payload
    keyword = "keyword"                      # exact keyword fast path (FR/EN)
    bare_ack_rule = "bare_ack_rule"          # "ok"/"👍" + one pending reco in window
    correction_pattern = "correction_pattern"  # covers regex ("covers: 80"), no model
    model_auto = "model_auto"                # model, confidence >= threshold
    model_confirmed = "model_confirmed"      # model below threshold, manager said yes
    keyword_confirmed = "keyword_confirmed"  # ambiguous keyword, manager said yes
    bare_ack_confirmed = "bare_ack_confirmed"  # unattributable ack, manager said yes


# Origin of a confirmation prompt → source recorded when the manager says yes.
CONFIRMED_SOURCE: dict[str, DecisionSource] = {
    "model": DecisionSource.model_confirmed,
    "keyword_ambiguous": DecisionSource.keyword_confirmed,
    "bare_ack": DecisionSource.bare_ack_confirmed,
}

# Below this model confidence an inferred decision is confirmed, never written
# (Décision #6). 0.85 = the per-intent precision floor of FAILURE_THRESHOLDS.md.
# The model's self-reported confidence is NOT calibrated yet: the first real
# eval run (eval-parser-real.yml) is what will tell whether 0.85 separates
# right from wrong answers. Until then the threshold is a policy, not a measure.
DECISION_CONFIDENCE_THRESHOLD = 0.85

# Bare acknowledgement counts as `accepted` only inside this window after the
# recommendation was dispatched (and only if it is the only pending one).
RESPONSE_WINDOW = timedelta(hours=12)

# A confirmation or reason prompt left unanswered this long expires.
PROMPT_WINDOW = timedelta(minutes=60)

# Reason routing: where a free-text reason should go. Labels only — no consumer
# exists yet for the last four (ADR-0007 §16.5). A reason is routed only above
# this confidence; otherwise it is kept unrouted, never guessed.
REASON_ROUTES: tuple[str, ...] = (
    "memory",           # situational context worth recalling on similar nights
    "decision_rule",    # a local rule the manager applies ("never < 3 servers on Fri")
    "policy",           # a hotel / company constraint (budget freeze, labour rule)
    "case_set",         # a case worth adding to the eval / case set
    "upstream_filter",  # the input data was wrong (PMS occupancy, cancelled event)
)
REASON_ROUTE_THRESHOLD = 0.7


# ---------------------------------------------------------------------------
# Tokenisation
# ---------------------------------------------------------------------------

_PUNCT_RE = re.compile(r"[!?.,;:…()\"«»]+")
# Emoji presentation selectors and skin-tone modifiers carry no meaning here.
_EMOJI_NOISE_RE = re.compile("[️‍\U0001F3FB-\U0001F3FF]")


def _is_symbol(ch: str) -> bool:
    return unicodedata.category(ch) in ("So", "Sk", "Sm")


def tokens(body: str) -> list[str]:
    """Lower-case word and emoji tokens. Punctuation dropped; consecutive
    emojis split ("👍👍" → ["👍", "👍"]); apostrophes kept ("j'accepte")."""
    text = _EMOJI_NOISE_RE.sub("", body.strip().lower()).replace("’", "'")
    text = _PUNCT_RE.sub(" ", text)
    out: list[str] = []
    for raw in text.split():
        word = ""
        for ch in raw:
            if _is_symbol(ch):
                if word:
                    out.append(word)
                    word = ""
                out.append(ch)
            else:
                word += ch
        if word:
            out.append(word)
    return out


def normalise(body: str) -> str:
    return " ".join(tokens(body))


# ---------------------------------------------------------------------------
# (c) Exact-keyword fast path — every mapping is a documented choice
# ---------------------------------------------------------------------------
# Matching is on the WHOLE reply, token by token: a reply is a keyword reply
# only if every token belongs to the sets below. Anything longer goes to the
# model. That keeps the fast path deterministic and narrow: "oui" is a keyword,
# "oui mais 3 serveurs" is not.

# Explicit acceptance. ✅ is here (a check mark answers "validate?"); 👍 is NOT:
# it is a bare acknowledgement under rule (b), it may answer the Receipt.
ACCEPT_TOKENS: frozenset[str] = frozenset({
    "accept", "accepted", "accepte", "accepté", "accepter", "j'accepte",
    "oui", "yes", "yep", "ouais",
    "validé", "valide", "valider", "validée", "validate", "validated",
    "approve", "approved", "approuvé", "agreed", "go",
    "✅", "✔",
})

# Explicit refusal. "non"/"no" alone are unambiguous answers to a proposal.
REJECT_TOKENS: frozenset[str] = frozenset({
    "reject", "rejected", "rejeter", "rejeté", "rejette",
    "refuse", "refused", "refusé", "refuser", "decline", "declined",
    "non", "no", "nope", "nan",
    "❌", "👎", "✖",
})

# Explicit correction without the figure yet: records `modified`, then the
# optional "what change?" line collects the detail. "CORRIGER" is what the text
# fallback tells managers to reply; ✏️ is the modify glyph of the Daily Receipt.
MODIFY_TOKENS: frozenset[str] = frozenset({
    "corriger", "correction", "correct", "modifier", "modify", "modified", "modifié",
    "ajuster", "adjust", "✏", "📝",
})

# Bare acknowledgement: no decision content, may answer the Receipt or the
# recommendation. Rule (b) decides what it records.
ACK_TOKENS: frozenset[str] = frozenset({
    "ok", "okay", "oki", "okk", "k",
    "merci", "thanks", "thank", "you", "thx", "ty", "beaucoup", "much",
    "parfait", "perfect", "great", "super", "top", "cool", "nickel",
    "noted", "noté", "compris", "understood", "got", "it", "bien", "reçu",
    "👍", "👌", "🙏", "💪", "🙂", "😊",
})

# Whole-reply forms that must be confirmed, not guessed. Each one has two
# plausible readings (documented in ADR-0007 §16.3):
#   "non merci"          declines the recommendation   | "no thanks, nothing needed" (all good)
#   "on garde tel quel"  keep the recommendation as is | keep our current plan as is
#   "pas besoin"         we don't need the extra staff | no need to change anything
AMBIGUOUS_PHRASES: frozenset[str] = frozenset({
    "non merci", "no thanks", "no thank you", "nan merci", "non merci beaucoup",
    "non merci on garde tel quel", "on garde tel quel", "on garde comme ça",
    "tel quel", "keep as is", "keep it as is", "as is",
    "pas besoin", "no need", "pas nécessaire",
    "bof",
})

# Multi-word explicit forms that the token rule alone would miss.
_ACCEPT_PHRASES: frozenset[str] = frozenset({
    "je valide", "c'est validé", "ok validé", "ok pour moi", "go for it",
    "d'accord", "ok d'accord",
})
_REJECT_PHRASES: frozenset[str] = frozenset({
    "je refuse", "pas d'accord", "not ok",
})

# Confirmation answers (used only while a confirmation prompt is pending).
CONFIRM_YES_TOKENS: frozenset[str] = frozenset({
    "oui", "yes", "yep", "ouais", "y", "o", "exact", "exactement", "correct",
    "confirm", "confirmed", "confirme", "confirmé", "c'est", "ça", "ok", "👍", "✅",
})
CONFIRM_NO_TOKENS: frozenset[str] = frozenset({
    "non", "no", "nope", "nan", "n", "annuler", "annule", "cancel", "❌", "👎",
})


KeywordKind = Literal["accept", "reject", "modify", "ambiguous", "bare_ack"]


@dataclass(frozen=True)
class KeywordMatch:
    kind: KeywordKind
    # Decision proposed for confirmation when kind == "ambiguous" (the reading
    # the golden labels / most managers intend); the manager has the last word.
    proposed: Optional[Decision] = None


def _has_any(toks: Iterable[str], vocab: frozenset[str]) -> bool:
    return any(t in vocab for t in toks)


def match_keyword(body: str) -> Optional[KeywordMatch]:
    """Deterministic keyword fast path. ``None`` = not a keyword reply.

    Order: ambiguous phrases → explicit phrases → token rule. In the token
    rule, a reply mixing a refusal token with an acceptance/ack token
    ("non ok", "no thanks") is ambiguous → confirmation, never a guess.
    A reply containing "?" is a question ("ok?", "oui ?"), never a keyword.
    """
    if "?" in body:
        return None
    norm = normalise(body)
    if not norm:
        return None
    if norm in AMBIGUOUS_PHRASES:
        return KeywordMatch("ambiguous", proposed="rejected")
    if norm in _ACCEPT_PHRASES:
        return KeywordMatch("accept")
    if norm in _REJECT_PHRASES:
        return KeywordMatch("reject")

    toks = norm.split()
    known = ACCEPT_TOKENS | REJECT_TOKENS | MODIFY_TOKENS | ACK_TOKENS
    if not all(t in known for t in toks):
        return None
    has_accept = _has_any(toks, ACCEPT_TOKENS)
    has_reject = _has_any(toks, REJECT_TOKENS)
    has_modify = _has_any(toks, MODIFY_TOKENS)
    has_ack = _has_any(toks, ACK_TOKENS)
    if has_reject and (has_accept or has_ack or has_modify):
        return KeywordMatch("ambiguous", proposed="rejected")
    if has_modify and has_accept:
        # "oui corriger": accept, or accept with a change? Ask.
        return KeywordMatch("ambiguous", proposed="modified")
    if has_reject:
        return KeywordMatch("reject")
    if has_modify:
        return KeywordMatch("modify")
    if has_accept:
        return KeywordMatch("accept")
    if has_ack:
        return KeywordMatch("bare_ack")
    return None


def is_bare_ack(body: str) -> bool:
    m = match_keyword(body)
    return m is not None and m.kind == "bare_ack"


def match_confirmation_answer(body: str) -> Optional[bool]:
    """While a confirmation is pending: True = yes, False = no, None = neither
    (the reply is then processed normally and the prompt is superseded)."""
    toks = tokens(body)
    if not toks or "?" in body:
        return None
    if all(t in CONFIRM_YES_TOKENS for t in toks):
        return True
    if all(t in CONFIRM_NO_TOKENS for t in toks):
        return False
    return None


# ---------------------------------------------------------------------------
# (d) Quick-reply button payloads — fixed IDs, no model involved
# ---------------------------------------------------------------------------

BUTTON_ACCEPT = "aetherix.decision.accept"
BUTTON_REJECT = "aetherix.decision.reject"
BUTTON_CORRECT = "aetherix.decision.correct"
BUTTON_CONFIRM_YES = "aetherix.confirm.yes"
BUTTON_CONFIRM_NO = "aetherix.confirm.no"

BUTTON_DECISIONS: dict[str, Decision] = {
    BUTTON_ACCEPT: "accepted",
    BUTTON_REJECT: "rejected",
    BUTTON_CORRECT: "modified",
}
BUTTON_CONFIRMATIONS: dict[str, bool] = {
    BUTTON_CONFIRM_YES: True,
    BUTTON_CONFIRM_NO: False,
}


# ---------------------------------------------------------------------------
# (a) Classifier output schema — validated, never coerced (Décision #35 D2)
# ---------------------------------------------------------------------------

class ClassifierOutput(BaseModel):
    """What the model must return for a free-text reply. Anything that does not
    validate is a typed ``llm_unmappable`` result: no decision is recorded."""

    model_config = ConfigDict(extra="ignore")

    decision: Literal["accepted", "rejected", "modified", "none"]
    confidence: float = Field(ge=0.0, le=1.0)
    intent: Literal["structured_correction", "free_form", "acknowledge"] = "free_form"
    corrected_value: Optional[float] = None
    reason: Optional[str] = Field(default=None, max_length=500)
    reason_route: Optional[Literal[
        "memory", "decision_rule", "policy", "case_set", "upstream_filter"
    ]] = None
    reason_route_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    notes: str = Field(default="", max_length=1000)


class ReasonRouteOutput(BaseModel):
    """Model output when routing a follow-up reason reply."""

    model_config = ConfigDict(extra="ignore")

    route: Optional[Literal[
        "memory", "decision_rule", "policy", "case_set", "upstream_filter"
    ]] = None
    confidence: float = Field(ge=0.0, le=1.0)


def parse_model_json(raw: str, schema: type[BaseModel]) -> BaseModel:
    """Strip an optional markdown fence and validate. Raises ``ValueError`` /
    ``ValidationError`` — callers turn either into a typed error."""
    clean = raw.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", clean)
    return schema.model_validate_json(clean)


def routed_reason(route: Optional[str], confidence: Optional[float]) -> Optional[str]:
    """A reason is routed only above ``REASON_ROUTE_THRESHOLD``; else unrouted."""
    if route in REASON_ROUTES and confidence is not None and confidence >= REASON_ROUTE_THRESHOLD:
        return route
    return None


# ---------------------------------------------------------------------------
# Resolution — what happens to a parsed reply
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PendingContext:
    """What rule (b) needs about the manager's pending recommendations."""

    pending_count: int
    latest_dispatched_at: Optional[datetime]
    now: datetime

    def single_in_window(self) -> bool:
        return (
            self.pending_count == 1
            and self.latest_dispatched_at is not None
            and timedelta(0) <= self.now - self.latest_dispatched_at <= RESPONSE_WINDOW
        )


ResolutionAction = Literal["record", "confirm", "none"]


@dataclass(frozen=True)
class Resolution:
    """``record`` → write ``decision`` with ``source``. ``confirm`` → write
    nothing, ask the manager to confirm ``decision`` (``origin`` says why).
    ``none`` → nothing to write (``why`` is the typed reason)."""

    action: ResolutionAction
    decision: Optional[Decision] = None
    source: Optional[DecisionSource] = None
    origin: Optional[str] = None      # confirm only: model | keyword_ambiguous | bare_ack
    confidence: float = 1.0
    why: Optional[str] = None


def resolve_keyword(match: KeywordMatch, ctx: PendingContext) -> Resolution:
    if match.kind == "accept":
        return Resolution("record", "accepted", DecisionSource.keyword)
    if match.kind == "reject":
        return Resolution("record", "rejected", DecisionSource.keyword)
    if match.kind == "modify":
        return Resolution("record", "modified", DecisionSource.keyword)
    if match.kind == "ambiguous":
        return Resolution("confirm", match.proposed, origin="keyword_ambiguous")
    return resolve_bare_ack(ctx)


def resolve_bare_ack(ctx: PendingContext) -> Resolution:
    """Rule (b): a bare acknowledgement records ``accepted`` only when exactly
    one recommendation is pending and the reply is inside the response window.
    No pending recommendation → it acknowledged something else (the Receipt):
    nothing to decide. Otherwise → ask."""
    if ctx.pending_count == 0:
        return Resolution("none", why="no_pending_recommendation")
    if ctx.single_in_window():
        return Resolution("record", "accepted", DecisionSource.bare_ack_rule)
    why = "several_pending" if ctx.pending_count > 1 else "outside_response_window"
    return Resolution("confirm", "accepted", origin="bare_ack", why=why)


def resolve_model(decision: Optional[str], confidence: float) -> Resolution:
    """A model-inferred decision is written only at or above the threshold.

    The threshold applies to ``modified`` too (stricter than the minimum asked
    for accepted/rejected): nothing the model infers is written unconfirmed
    below it. ``none`` records nothing."""
    if decision not in RECORDABLE_DECISIONS:
        return Resolution("none", why="model_decision_none", confidence=confidence)
    if confidence >= DECISION_CONFIDENCE_THRESHOLD:
        return Resolution("record", decision, DecisionSource.model_auto, confidence=confidence)  # type: ignore[arg-type]
    return Resolution("confirm", decision, origin="model", confidence=confidence,  # type: ignore[arg-type]
                      why="below_confidence_threshold")


def wants_reason_prompt(decision: Optional[str], reason_already_given: bool) -> bool:
    """Ask "Une raison ? (facultatif)" after a reject or a correction only —
    never after an accept (interruption budget), never twice."""
    return decision in ("rejected", "modified") and not reason_already_given


# ---------------------------------------------------------------------------
# Manager-facing copy (FR default, EN) — short, one line each
# ---------------------------------------------------------------------------

_DECISION_WORD = {
    "fr": {"accepted": "une validation", "rejected": "un refus", "modified": "une correction"},
    "en": {"accepted": "an acceptance", "rejected": "a refusal", "modified": "a correction"},
}

_COPY = {
    "confirm_question": {
        "fr": "Je note {word}, c'est bien ça ?",
        "en": "I'm noting {word}, is that right?",
    },
    "confirm_text_hint": {
        "fr": "Répondez OUI ou NON.",
        "en": "Reply YES or NO.",
    },
    "recorded": {
        "fr": {"accepted": "Validation enregistrée.", "rejected": "Refus enregistré.",
               "modified": "Correction enregistrée."},
        "en": {"accepted": "Acceptance recorded.", "rejected": "Refusal recorded.",
               "modified": "Correction recorded."},
    },
    "declined": {"fr": "Rien n'est enregistré.", "en": "Nothing recorded."},
    "reason_after_reject": {
        "fr": "Une raison ? (facultatif)",
        "en": "A reason? (optional)",
    },
    "reason_after_correct": {
        "fr": "Quel changement, et pourquoi ? (facultatif)",
        "en": "What change, and why? (optional)",
    },
    "reason_thanks": {"fr": "Merci, c'est noté.", "en": "Thanks, noted."},
    "not_understood": {"fr": "Je n'ai pas compris.", "en": "I didn't understand."},
    "no_pending": {
        "fr": "Aucune recommandation en attente de décision.",
        "en": "No recommendation is waiting for a decision.",
    },
    "ack": {"fr": "Bien reçu.", "en": "Understood."},
    "buttons_decision": {
        "fr": ("Accepter", "Refuser", "Corriger"),
        "en": ("Accept", "Reject", "Correct"),
    },
    "buttons_confirm": {"fr": ("Oui", "Non"), "en": ("Yes", "No")},
    "decision_text_hint": {
        "fr": "Répondez ACCEPTER, REFUSER ou CORRIGER.",
        "en": "Reply ACCEPT, REJECT or CORRECT.",
    },
}


def _loc(locale: Optional[str]) -> str:
    return "en" if (locale or "").lower().startswith("en") else "fr"


def text_for(key: str, locale: Optional[str] = "fr", **fmt: str):
    value = _COPY[key][_loc(locale)]
    return value.format(**fmt) if isinstance(value, str) and fmt else value


def confirmation_question(decision: str, locale: Optional[str] = "fr") -> str:
    return text_for("confirm_question", locale, word=_DECISION_WORD[_loc(locale)][decision])


def recorded_message(decision: str, locale: Optional[str] = "fr") -> str:
    return _COPY["recorded"][_loc(locale)][decision]


# ---------------------------------------------------------------------------
# Metrics — capture rate, source shares, confirmation / timeout rates
# ---------------------------------------------------------------------------

# Results of one reply event (one inbound reply → one event; a prompt expiring
# also emits one event, which is not a reply).
REPLY_RESULTS: tuple[str, ...] = (
    "recorded",               # a decision was written from this reply
    "confirmation_requested",  # nothing written, confirmation prompt sent
    "confirmed",              # reply confirmed a pending prompt → decision written
    "declined",               # reply declined a pending prompt → nothing written
    "not_recorded",           # nothing written (typed `why`)
    "reason_captured",        # reply answered a reason prompt (never a decision)
)
NON_REPLY_RESULTS: tuple[str, ...] = ("confirmation_expired",)

_DECISION_SEEKING = ("recorded", "confirmation_requested", "not_recorded")


@dataclass
class CaptureMetrics:
    replies: int = 0
    decision_seeking_replies: int = 0
    decisions_written: int = 0
    capture_rate: Optional[float] = None
    by_source: dict[str, int] = field(default_factory=dict)
    source_share: dict[str, float] = field(default_factory=dict)
    confirmations_requested: int = 0
    confirmations_confirmed: int = 0
    confirmations_declined: int = 0
    confirmations_expired: int = 0
    confirmation_rate: Optional[float] = None
    confirmation_timeout_rate: Optional[float] = None
    not_recorded_by_why: dict[str, int] = field(default_factory=dict)
    reasons_captured: int = 0
    reasons_routed: int = 0

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def _ratio(n: int, d: int) -> Optional[float]:
    return round(n / d, 4) if d else None


def compute_capture_metrics(events: Iterable[dict]) -> CaptureMetrics:
    """Pure metrics over reply events (dicts with ``result``, ``decision_source``,
    ``why``, ``reason_route``).

    * capture rate = decisions written ÷ decision-seeking replies. A decision
      written by a confirming "oui" is credited to the reply that raised the
      prompt, so each prompt counts once. Reason replies and confirmation
      answers are not decision-seeking and are excluded from the denominator.
    * confirmation rate = confirmed ÷ requested; timeout rate = expired ÷ requested.
    """
    m = CaptureMetrics()
    for ev in events:
        result = ev.get("result")
        if result in REPLY_RESULTS:
            m.replies += 1
        if result in _DECISION_SEEKING:
            m.decision_seeking_replies += 1
        if result in ("recorded", "confirmed"):
            m.decisions_written += 1
            src = ev.get("decision_source") or "unknown"
            m.by_source[src] = m.by_source.get(src, 0) + 1
        if result == "confirmation_requested":
            m.confirmations_requested += 1
        elif result == "confirmed":
            m.confirmations_confirmed += 1
        elif result == "declined":
            m.confirmations_declined += 1
        elif result == "confirmation_expired":
            m.confirmations_expired += 1
        elif result == "not_recorded":
            why = ev.get("why") or "unknown"
            m.not_recorded_by_why[why] = m.not_recorded_by_why.get(why, 0) + 1
        elif result == "reason_captured":
            m.reasons_captured += 1
            if ev.get("reason_route"):
                m.reasons_routed += 1

    m.capture_rate = _ratio(m.decisions_written, m.decision_seeking_replies)
    m.source_share = {k: round(v / m.decisions_written, 4) for k, v in sorted(m.by_source.items())}
    m.confirmation_rate = _ratio(m.confirmations_confirmed, m.confirmations_requested)
    m.confirmation_timeout_rate = _ratio(m.confirmations_expired, m.confirmations_requested)
    return m
