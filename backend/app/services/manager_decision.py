"""Manager decision capture — pure rules (ADR-0007 §16, §19; Décisions #38, #41).

How a manager's reply to a staffing recommendation becomes a recorded
**decision** (``accepted | rejected | modified``) or nothing.

Principle (PO decision, 24/09/2026):

* The **decision** is arm C's ground truth (outcome eval, ADR-0007 §13). It is
  decided deterministically wherever possible (button payload, lexicon,
  bare-acknowledgement rule), cheap, unambiguous and auditable: every recorded
  decision carries its ``DecisionSource``.
* A reply expresses a **stance** toward the recommendation (adopt it, decline
  it, keep the current plan, counter it). The decision is derived from the
  stance and from what the recommendation proposed (add / reduce / no change),
  by one function, ``decision_for_stance`` (§19, PO: "fix the logic, not the
  example"). The lexicon and the model both return stances.
* The **comment** (reason, detail) is optional and rich. It never changes a
  recorded decision.
* HITL (Décision #6): a model stance below ``DECISION_CONFIDENCE_THRESHOLD``, a
  reply with two readings, a stance whose meaning needs a direction the code
  cannot tell, or a bare acknowledgement that cannot be attributed to exactly
  one pending recommendation is **not written**. The manager is asked; nothing
  is recorded until they answer. Unconfirmed after the window → recorded as
  unconfirmed, never as a decision.
* The outcome (actual covers) is never an input here. Decision and outcome stay
  independent variables, or arm C learns circularly (§16.6). Nothing in this
  module reads ``actual_covers``.

Everything in this module is pure (no DB, no network) and unit-tested
form by form in ``tests/services/test_manager_decision.py``.
"""
from __future__ import annotations

import json
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
    manager_revision = "manager_revision"    # "corriger mardi" from the recap, confirmed (ADR-0007 §17.2)
    host_relay = "host_relay"                # MCP: a human's decision relayed by a host agent (§17.4)
    host_agent = "host_agent"                # MCP: host agent alone — refused by the default policy


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
# Stance → decision (ADR-0007 §19) — the one mapping
# ---------------------------------------------------------------------------
# A reply expresses a STANCE toward the recommendation; the decision follows
# from the stance AND what the recommendation proposed, deterministically.
# "Keep the current plan" rejects a proposal to add staff but accepts a
# proposal to keep the usual staffing: the reply is the same, the decision is
# not. Neither the keyword lexicon nor the model maps a reply to a decision
# directly; both go through `decision_for_stance`.

Stance = Literal[
    "adopt_proposal",    # do what the recommendation says ("oui", "ça marche")
    "decline_proposal",  # refuse the recommendation ("non", "refusé", "❌")
    "keep_current",      # keep the plan in place ("on garde tel quel", "keep as is")
    "counter_value",     # a different action or figure ("plutôt 3", "corriger")
    "unclear",           # takes a position, but the code cannot tell which
    "none",              # no position on the recommendation (question, other topic)
]
STANCES: tuple[str, ...] = (
    "adopt_proposal", "decline_proposal", "keep_current", "counter_value", "unclear", "none",
)

# What the recommendation proposed, derived from the stored recommendation,
# never from the reply. `unknown` = the stored fields cannot tell.
ProposalKind = Literal["add", "reduce", "no_change", "unknown"]
PROPOSAL_KINDS: tuple[str, ...] = ("add", "reduce", "no_change", "unknown")


def decision_for_stance(stance: Optional[str], kind: str) -> Optional[Decision]:
    """The single stance → decision mapping. ``None`` = no decision can be
    derived (no stance, unclear stance, or a stance whose meaning depends on a
    direction that is not known): the caller asks, it never guesses.

    ==================  =========  =========  ==========  =========
    stance              add        reduce     no_change   unknown
    ==================  =========  =========  ==========  =========
    adopt_proposal      accepted   accepted   accepted    accepted
    decline_proposal    rejected   rejected   rejected    rejected
    keep_current        rejected   rejected   accepted    —
    counter_value       modified   modified   modified    modified
    unclear / none      —          —          —           —
    ==================  =========  =========  ==========  =========
    """
    if stance == "adopt_proposal":
        return "accepted"
    if stance == "decline_proposal":
        return "rejected"
    if stance == "counter_value":
        return "modified"
    if stance == "keep_current":
        return {"add": "rejected", "reduce": "rejected", "no_change": "accepted"}.get(kind)  # type: ignore[return-value]
    return None


@dataclass(frozen=True)
class Proposal:
    """What a staffing recommendation proposed: direction and magnitude."""

    kind: str = "unknown"                 # ProposalKind
    magnitude: Optional[int] = None       # staff added or removed (absolute)
    task_class: Optional[str] = None
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None

    def describe(self) -> str:
        """One line for the classifier prompt. Never invents a direction."""
        when = ""
        if self.window_start is not None:
            when = f" for {self.window_start:%A %d/%m %H:%M}"
            if self.window_end is not None:
                when += f"–{self.window_end:%H:%M}"
        n = self.magnitude
        if self.kind == "add":
            what = f"ADD {n} staff" if n else "ADD staff"
        elif self.kind == "reduce":
            what = f"REDUCE staffing by {n}" if n else "REDUCE staffing"
        elif self.kind == "no_change":
            what = "NO CHANGE (keep the usual staffing)"
        else:
            what = "a staffing change whose direction is not recorded"
        cls = f" (task class {self.task_class})" if self.task_class else ""
        return f"{what}{when}{cls}"


_ADD = "staffing.add"
_REDUCE = "staffing.reduce"
_NEWSVENDOR = "newsvendor"   # risk_assessment.RULE_NEWSVENDOR, not imported (keeps this module pure)


def proposal_from_recommendation(
    recommended_headcount: Optional[int],
    task_class: Optional[str] = None,
    risk_assessment: Optional[dict | str] = None,
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
) -> Proposal:
    """Direction and magnitude of a stored staffing recommendation.

    1. ``risk_assessment.recommended_delta_staff`` (signed, ADR-0007 §18.4) when
       stored: > 0 add, < 0 reduce. 0 is ``no_change`` only under the newsvendor
       rule, whose message says "keep the usual staffing"; a 0 from the ROI
       scale means no magnitude was computed (a lull reads "reduce by 0",
       open decision "ROI gate and reductions") → ``unknown``.
    2. Otherwise the signed ``recommended_headcount`` (legacy rows): > 0 add,
       < 0 reduce; 0 or missing → ``unknown`` (no legacy message said "keep").
    3. ``task_class`` must agree with the sign; a contradiction → ``unknown``.
    Anything the stored fields cannot tell is ``unknown``, never a guess.
    """
    delta: Optional[int] = None
    explicit_keep = False
    ra = risk_assessment
    if isinstance(ra, str):  # JSON column read back as text on some drivers
        try:
            ra = json.loads(ra)
        except ValueError:
            ra = None
    ra = ra if isinstance(ra, dict) else None
    if ra is not None and isinstance(ra.get("recommended_delta_staff"), (int, float)):
        delta = int(ra["recommended_delta_staff"])
        explicit_keep = delta == 0 and ra.get("decision_rule") == _NEWSVENDOR
    elif recommended_headcount is not None:
        delta = int(recommended_headcount)

    kind = "unknown"
    if delta is not None and delta > 0 and task_class != _REDUCE:
        kind = "add"
    elif delta is not None and delta < 0 and task_class != _ADD:
        kind = "reduce"
    elif explicit_keep:
        kind = "no_change"
    magnitude = abs(delta) if (delta is not None and kind in ("add", "reduce")) else None
    return Proposal(kind, magnitude, task_class, window_start, window_end)


# ---------------------------------------------------------------------------
# (c) Deterministic fast path — stance lexicons, whole reply only
# ---------------------------------------------------------------------------
# A reply is a keyword reply only if EVERY token belongs to one of the lexicons
# below (multi-word forms matched first, longest first). Anything longer goes
# to the model: "oui" is a keyword, "oui mais 3 serveurs" is not. The lexicons
# say which STANCE a form expresses, never which decision: the decision comes
# from `decision_for_stance` once the proposal is known.

# Adopt the proposal. ✅ is here (a check mark answers "validate?"); 👍 is NOT:
# it is a bare acknowledgement under rule (b), it may answer the Receipt.
ADOPT_TOKENS: frozenset[str] = frozenset({
    "accept", "accepted", "accepte", "accepté", "accepter", "j'accepte",
    "oui", "yes", "yep", "ouais",
    "validé", "valide", "valider", "validée", "validate", "validated",
    "approve", "approved", "approuvé", "agreed", "go",
    "✅", "✔",
})
ADOPT_PHRASES: frozenset[str] = frozenset({
    "je valide", "c'est validé", "ok pour moi", "go for it", "d'accord",
})

# Decline the proposal. "non"/"no" alone are unambiguous answers to a proposal.
DECLINE_TOKENS: frozenset[str] = frozenset({
    "reject", "rejected", "rejeter", "rejeté", "rejette",
    "refuse", "refused", "refusé", "refuser", "decline", "declined",
    "non", "no", "nope", "nan",
    "❌", "👎", "✖",
})
DECLINE_PHRASES: frozenset[str] = frozenset({"je refuse", "pas d'accord", "not ok"})

# Counter the proposal without the figure yet: `modified`, then the optional
# "what change?" line collects the detail. "CORRIGER" is what the text
# fallback tells managers to reply; ✏️ is the modify glyph of the Daily Receipt.
COUNTER_TOKENS: frozenset[str] = frozenset({
    "corriger", "correction", "correct", "modifier", "modify", "modified", "modifié",
    "ajuster", "adjust", "✏", "📝",
})

# Keep the current plan (PO clarification 24/09/2026, ADR-0007 §17.8): "keep"
# means the manager's own plan, not the recommendation.
KEEP_CURRENT_PHRASES: frozenset[str] = frozenset({
    "tel quel", "on garde tel quel", "on garde comme ça",
    "keep as is", "keep it as is", "as is",
})

# "No thanks": the idiom that declines an offer and keeps what one has. Two
# readings, decline or keep current — the same decision when the proposal
# changes something, different ones when it proposes no change.
POLITE_DECLINE_PHRASES: frozenset[str] = frozenset({
    "non merci", "nan merci", "no thanks", "no thank you",
})

# Need negation: denies a need for staff. It rejects a proposal to ADD staff
# (keep current); to a proposal to REDUCE it reads two ways ("no need to cut"
# keeps current | "no need for them" adopts the cut). Ivan's clarification of
# "non merci / tel quel" generalised through the proposal's direction.
NEED_NEGATION_PHRASES: frozenset[str] = frozenset({
    "pas besoin", "no need", "pas nécessaire", "not necessary", "not needed",
})

# Hesitation: reluctant yes or soft no.
HESITATION_TOKENS: frozenset[str] = frozenset({"bof"})

# Acknowledgement: assent without decision content. Alone → rule (b). Next to
# a stance it reads as adopting ("oui 👍"), so "non ok" is two readings.
ACK_TOKENS: frozenset[str] = frozenset({
    "ok", "okay", "oki", "okk", "k",
    "parfait", "perfect", "great", "super", "top", "cool", "nickel",
    "noted", "noté", "compris", "understood", "got", "it", "bien", "reçu",
    "👍", "👌", "💪", "🙂", "😊",
})

# Politeness: carries no stance at all ("✏️ merci", "non merci beaucoup").
POLITENESS_TOKENS: frozenset[str] = frozenset({
    "merci", "thanks", "thank", "you", "thx", "ty", "beaucoup", "much", "🙏",
})

# Lexicon unit classes, in match order for multi-word forms.
_PHRASE_CLASSES: tuple[tuple[str, frozenset[str]], ...] = (
    ("polite_decline", POLITE_DECLINE_PHRASES),
    ("keep", KEEP_CURRENT_PHRASES),
    ("need_negation", NEED_NEGATION_PHRASES),
    ("adopt", ADOPT_PHRASES),
    ("decline", DECLINE_PHRASES),
)
_TOKEN_CLASSES: tuple[tuple[str, frozenset[str]], ...] = (
    ("adopt", ADOPT_TOKENS),
    ("decline", DECLINE_TOKENS),
    ("counter", COUNTER_TOKENS),
    ("hesitation", HESITATION_TOKENS),
    ("ack", ACK_TOKENS),
    ("politeness", POLITENESS_TOKENS),
)
_PHRASES: dict[tuple[str, ...], str] = {
    tuple(p.split()): cls for cls, vocab in _PHRASE_CLASSES for p in vocab
}
_MAX_PHRASE = max(len(k) for k in _PHRASES)

# Confirmation answers (used only while a confirmation prompt is pending).
CONFIRM_YES_TOKENS: frozenset[str] = frozenset({
    "oui", "yes", "yep", "ouais", "y", "o", "exact", "exactement", "correct",
    "confirm", "confirmed", "confirme", "confirmé", "c'est", "ça", "ok", "👍", "✅",
})
CONFIRM_NO_TOKENS: frozenset[str] = frozenset({
    "non", "no", "nope", "nan", "n", "annuler", "annule", "cancel", "❌", "👎",
})


def stance_readings(unit: str, kind: str) -> tuple[str, ...]:
    """Stances a lexicon unit can express, given the proposal's direction.
    Empty = no stance (politeness). Order is irrelevant: readings are compared
    through the decisions they imply."""
    if unit == "adopt" or unit == "ack":
        return ("adopt_proposal",)
    if unit == "decline":
        return ("decline_proposal",)
    if unit == "counter":
        return ("counter_value",)
    if unit == "keep":
        return ("keep_current",)
    if unit == "polite_decline":
        return ("decline_proposal", "keep_current")
    if unit == "need_negation":
        return ("keep_current", "adopt_proposal") if kind == "reduce" else ("keep_current",)
    if unit == "hesitation":
        return ("decline_proposal", "adopt_proposal")
    return ()


KeywordKind = Literal["stance", "bare_ack"]


@dataclass(frozen=True)
class KeywordMatch:
    """A whole-reply lexicon match: the unit classes found, in reply order.
    ``bare_ack`` = only acknowledgement / politeness units (rule (b))."""

    kind: KeywordKind
    units: tuple[str, ...] = ()

    def summary(self) -> str:
        """Coarse, proposal-independent label (logs, ``ActionType``):
        accept | reject | modify | decline | ambiguous | bare_ack.
        ``decline`` = a form whose decision depends on the proposal."""
        if self.kind == "bare_ack":
            return "bare_ack"
        stances = {u for u in self.units if u != "politeness"}
        if stances <= {"adopt", "ack"}:
            return "accept"
        if stances == {"decline"}:
            return "reject"
        if stances == {"counter"}:
            return "modify"
        if stances <= {"keep", "polite_decline", "need_negation", "decline"}:
            return "decline"
        return "ambiguous"


def _segment(toks: list[str]) -> Optional[list[str]]:
    """Cover the tokens with lexicon units, longest multi-word form first.
    ``None`` as soon as one token belongs to no lexicon."""
    units: list[str] = []
    i = 0
    while i < len(toks):
        for n in range(min(_MAX_PHRASE, len(toks) - i), 0, -1):
            cls = _PHRASES.get(tuple(toks[i:i + n]))
            if cls is not None:
                units.append(cls)
                i += n
                break
        else:
            cls = next((c for c, vocab in _TOKEN_CLASSES if toks[i] in vocab), None)
            if cls is None:
                return None
            units.append(cls)
            i += 1
    return units


def match_keyword(body: str) -> Optional[KeywordMatch]:
    """Deterministic fast path. ``None`` = not a keyword reply (→ model).
    A reply containing "?" is a question ("ok?", "oui ?"), never a keyword."""
    if "?" in body:
        return None
    toks = tokens(body)
    if not toks:
        return None
    units = _segment(toks)
    if units is None:
        return None
    if all(u in ("ack", "politeness") for u in units):
        return KeywordMatch("bare_ack", tuple(units))
    return KeywordMatch("stance", tuple(units))


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
# Commands: "recap …" and "corriger <jour> [décision]" (ADR-0007 §17.2)
# ---------------------------------------------------------------------------
# Checked before keywords. Whole reply only, like keywords. "corriger" alone
# stays the modify keyword; it is a revision command only with a day after it.

_RECAP_WORDS = frozenset({
    "recap", "récap", "recapitulatif", "récapitulatif", "résumé", "resume", "bilan", "summary",
})
_RECAP_PERIODS: dict[str, tuple[str, Optional[str]]] = {
    "jour": ("day", "fr"), "aujourd'hui": ("day", "fr"), "semaine": ("week", "fr"),
    "mois": ("month", "fr"),
    "day": ("day", "en"), "today": ("day", "en"), "week": ("week", "en"), "month": ("month", "en"),
}
_RECAP_LOCALE_HINT = {"summary": "en", "résumé": "fr", "récap": "fr", "bilan": "fr"}


@dataclass(frozen=True)
class RecapCommand:
    period: str                     # day | week | month
    locale: Optional[str] = None    # None → the profile's / default locale


def match_recap_command(body: str) -> Optional[RecapCommand]:
    """``recap`` (this week), ``recap jour|semaine|mois``, ``recap day|week|month``,
    ``summary``… Anything else → ``None``."""
    toks = tokens(body)
    if not toks or len(toks) > 2 or toks[0] not in _RECAP_WORDS:
        return None
    if len(toks) == 1:
        return RecapCommand("week", _RECAP_LOCALE_HINT.get(toks[0]))
    hit = _RECAP_PERIODS.get(toks[1])
    return RecapCommand(*hit) if hit else None


_REVISION_WORDS = {"corriger": "fr", "rectifier": "fr", "fix": "en", "correct": "en"}
WEEKDAYS: dict[str, int] = {
    "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4, "samedi": 5, "dimanche": 6,
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
}
_RELATIVE_DAYS = {"hier": 1, "yesterday": 1, "aujourd'hui": 0, "today": 0}
_REVISION_DECISIONS: dict[str, Decision] = {
    "validation": "accepted", "validé": "accepted", "valide": "accepted", "accepté": "accepted",
    "accepter": "accepted", "oui": "accepted", "accepted": "accepted", "accept": "accepted",
    "yes": "accepted",
    "refus": "rejected", "refusé": "rejected", "refuser": "rejected", "non": "rejected",
    "rejected": "rejected", "reject": "rejected", "refused": "rejected", "no": "rejected",
    "correction": "modified", "corrigé": "modified", "modifié": "modified",
    "corrected": "modified", "modified": "modified",
}
_DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})$")


@dataclass(frozen=True)
class RevisionCommand:
    """"corriger mardi [refus]": the manager flags a wrongly recorded decision.
    ``day`` is a weekday index, a relative offset ("hier") or a (day, month)."""

    weekday: Optional[int] = None
    days_ago: Optional[int] = None
    day_month: Optional[tuple[int, int]] = None
    decision: Optional[Decision] = None
    locale: Optional[str] = None
    ref: str = ""                   # the day as typed, echoed in replies

    def target_date(self, today) -> Optional[object]:
        from datetime import date as _date

        if self.days_ago is not None:
            return today - timedelta(days=self.days_ago)
        if self.weekday is not None:
            return today - timedelta(days=(today.weekday() - self.weekday) % 7)
        if self.day_month is not None:
            d, m = self.day_month
            try:
                candidate = _date(today.year, m, d)
            except ValueError:
                return None
            return candidate if candidate <= today else candidate.replace(year=today.year - 1)
        return None


def match_revision_command(body: str) -> Optional[RevisionCommand]:
    toks = tokens(body)
    if not (2 <= len(toks) <= 3) or toks[0] not in _REVISION_WORDS:
        return None
    locale = _REVISION_WORDS[toks[0]]
    day = toks[1]
    kwargs: dict = {"locale": locale, "ref": toks[1]}
    if day in WEEKDAYS:
        kwargs["weekday"] = WEEKDAYS[day]
    elif day in _RELATIVE_DAYS:
        kwargs["days_ago"] = _RELATIVE_DAYS[day]
    elif _DATE_RE.match(day):
        d, m = _DATE_RE.match(day).groups()
        kwargs["day_month"] = (int(d), int(m))
    else:
        return None
    if len(toks) == 3:
        decision = _REVISION_DECISIONS.get(toks[2])
        if decision is None:
            return None
        kwargs["decision"] = decision
    return RevisionCommand(**kwargs)


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
    """What the model must return for a free-text reply: the manager's STANCE
    toward the recommendation it was shown, never the decision (ADR-0007 §19).
    The decision is derived by `decision_for_stance`. Anything that does not
    validate is a typed ``llm_unmappable`` result: no decision is recorded."""

    model_config = ConfigDict(extra="ignore")

    stance: Literal[
        "adopt_proposal", "decline_proposal", "keep_current", "counter_value", "unclear", "none"
    ]
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
    """What the rules need about the manager's pending recommendations."""

    pending_count: int
    latest_dispatched_at: Optional[datetime]
    now: datetime
    # What the latest pending recommendation proposes (`proposal_from_recommendation`).
    # Read by the stance mapping; "unknown" when it cannot be told.
    proposal: str = "unknown"

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


# When a reply has several readings, the confirmation proposes the first of
# these that is possible. A refusal is the strongest signal in a mixed reply
# ("non ok"); a correction outranks a plain yes ("oui corriger").
_READING_PRIORITY: tuple[Decision, ...] = ("rejected", "modified", "accepted")


def resolve_stances(
    units: Iterable[tuple[str, ...]],
    kind: str,
    *,
    source: DecisionSource,
    origin: str,
    confidence: float = 1.0,
) -> Resolution:
    """Stances → decision, for the lexicon and the model alike.

    ``units``: for each part of the reply, the stances it can express. Each part
    narrows the decisions the reply can mean (``decision_for_stance`` under the
    proposal ``kind``); the reply means what every part allows.

    * exactly one decision, derivable, confidence ≥ threshold → ``record``;
    * several decisions (two readings, or parts that contradict each other)
      → ``confirm`` (why ``two_readings`` / ``readings_conflict``);
    * a stance that needs the proposal's direction when it is unknown →
      ``confirm``, reading as if a change was proposed (why ``proposal_unknown``);
    * below the confidence threshold → ``confirm`` (why ``below_confidence_threshold``);
    * ``unclear`` → nothing written, the manager is asked for the decision
      itself (no reading to confirm, why ``stance_unclear``);
    * ``none`` / no stance → nothing (why ``no_stance``).
    """
    units = [tuple(u) for u in units if u]
    stances = {s for u in units for s in u}
    if not units or stances <= {"none"}:
        return Resolution("none", why="no_stance", confidence=confidence)
    if "unclear" in stances:
        return Resolution("none", why="stance_unclear", confidence=confidence)

    possible: Optional[set[str]] = None
    union: set[str] = set()
    direction_unknown = False
    for readings in units:
        decisions: set[str] = set()
        for s in readings:
            d = decision_for_stance(s, kind)
            if d is None:
                direction_unknown = True
                d = decision_for_stance(s, "add")  # the usual case, for the question only
            if d is not None:
                decisions.add(d)
        union |= decisions
        possible = decisions if possible is None else possible & decisions

    if possible and len(possible) == 1 and not direction_unknown:
        (decision,) = possible
        if confidence >= DECISION_CONFIDENCE_THRESHOLD:
            return Resolution("record", decision, source, confidence=confidence)  # type: ignore[arg-type]
        return Resolution("confirm", decision, origin=origin, confidence=confidence,  # type: ignore[arg-type]
                          why="below_confidence_threshold")

    pool = possible or union
    reading = next(d for d in _READING_PRIORITY if d in pool)
    if direction_unknown:
        why = "proposal_unknown"
    else:
        why = "two_readings" if possible else "readings_conflict"
    return Resolution("confirm", reading, origin=origin, confidence=confidence, why=why)  # type: ignore[arg-type]


def resolve_keyword(match: KeywordMatch, ctx: PendingContext) -> Resolution:
    """Lexicon match → decision, through the stance mapping. A bare
    acknowledgement goes to rule (b)."""
    if match.kind == "bare_ack":
        return resolve_bare_ack(ctx)
    return resolve_stances(
        (stance_readings(u, ctx.proposal) for u in match.units),
        ctx.proposal, source=DecisionSource.keyword, origin="keyword_ambiguous",
    )


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


def resolve_model(stance: Optional[str], confidence: float, kind: str = "unknown") -> Resolution:
    """A model stance, through the same mapping as the lexicon. A derived
    decision is written only at or above the threshold — for ``modified`` too
    (stricter than the minimum asked for accepted/rejected): nothing the model
    infers is written unconfirmed below it."""
    if stance not in STANCES:
        return Resolution("none", why="no_stance", confidence=confidence)
    return resolve_stances([(stance,)], kind, source=DecisionSource.model_auto,
                           origin="model", confidence=confidence)


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
    "revision_info": {
        "fr": "{day} : {recorded} Pour changer, répondez « corriger {ref} validation », « corriger {ref} refus » ou « corriger {ref} correction ».",
        "en": "{day}: {recorded} To change it, reply \"fix {ref} accepted\", \"fix {ref} rejected\" or \"fix {ref} corrected\".",
    },
    "revision_question": {
        "fr": "{day} : je remplace {old} par {new}, c'est bien ça ?",
        "en": "{day}: I'm replacing {old} with {new}, is that right?",
    },
    "revision_same": {
        "fr": "{day} : {recorded} Rien ne change.",
        "en": "{day}: {recorded} Nothing changes.",
    },
    "revision_none": {
        "fr": "Aucune décision enregistrée le {day}.",
        "en": "No decision recorded on {day}.",
    },
    "revision_several": {
        "fr": "Plusieurs recommandations le {day} : impossible de savoir laquelle corriger par message. Rien n'est modifié.",
        "en": "Several recommendations on {day}: I can't tell which one to fix by message. Nothing changed.",
    },
    "revision_done": {
        "fr": "Corrigé. {recorded}",
        "en": "Fixed. {recorded}",
    },
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


def decision_word(decision: str, locale: Optional[str] = "fr") -> str:
    """"un refus" / "a refusal" — the noun phrase used in confirmation copy."""
    return _DECISION_WORD[_loc(locale)][decision]


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
    "recap_served",           # "recap …" command answered (ADR-0007 §17.2)
    "revision_info",          # "corriger mardi" without a new decision, or nothing to fix
    "revision_requested",     # "corriger mardi refus": confirmation asked, nothing written
    "revised",                # revision confirmed → decision replaced (source manager_revision)
    "revision_declined",      # revision not confirmed → nothing changed
)
NON_REPLY_RESULTS: tuple[str, ...] = ("confirmation_expired", "revision_expired")

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
    # Decisions the manager fixed from the recap ("corriger mardi"): the human
    # audit of the capture. Not counted as decisions written.
    revisions: int = 0

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
        if result == "revised":
            m.revisions += 1
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
