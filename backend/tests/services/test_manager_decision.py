"""Décisions #38, #41 / ADR-0007 §16, §19 — pure decision-capture rules.

Every lexicon form is pinned here against every proposal kind: a change to the
fast path's vocabulary or to the stance → decision mapping must change a test.
Forms with two readings must go to confirmation, never to a guess.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.schemas.webhook import ActionType
from app.services.action_logger import parse_action
from app.services.manager_decision import (
    BUTTON_ACCEPT,
    BUTTON_CONFIRM_NO,
    BUTTON_CONFIRM_YES,
    BUTTON_CORRECT,
    BUTTON_REJECT,
    BUTTON_CONFIRMATIONS,
    BUTTON_DECISIONS,
    DECISION_CONFIDENCE_THRESHOLD,
    PROPOSAL_KINDS,
    RESPONSE_WINDOW,
    STANCES,
    ClassifierOutput,
    DecisionSource,
    PendingContext,
    Proposal,
    compute_capture_metrics,
    confirmation_question,
    is_bare_ack,
    match_confirmation_answer,
    decision_for_stance,
    match_keyword,
    parse_model_json,
    proposal_from_recommendation,
    resolve_bare_ack,
    resolve_keyword,
    resolve_model,
    routed_reason,
    tokens,
    wants_reason_prompt,
)

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


def _ctx(pending: int = 1, ago: timedelta = timedelta(hours=1)) -> PendingContext:
    return PendingContext(pending, NOW - ago if pending else None, NOW)


# ---------------------------------------------------------------------------
# (c) stance lexicon + stance → decision mapping (ADR-0007 §19)
# ---------------------------------------------------------------------------
# The decision is derived from the reply's stance AND what the recommendation
# proposed. Every lexicon form is pinned against every proposal kind: a change
# to the vocabulary or to the mapping must change a row here.

KINDS = ("add", "reduce", "no_change", "unknown")

R = ("record", "rejected")
A = ("record", "accepted")
M = ("record", "modified")
CR = ("confirm", "rejected")
CM = ("confirm", "modified")


def _pctx(kind: str, pending: int = 1) -> PendingContext:
    return PendingContext(pending, NOW - timedelta(hours=1), NOW, proposal=kind)


# The mapping itself, as a table (docstring of `decision_for_stance`).
STANCE_TABLE = {
    #                    add         reduce      no_change   unknown
    "adopt_proposal":   ("accepted", "accepted", "accepted", "accepted"),
    "decline_proposal": ("rejected", "rejected", "rejected", "rejected"),
    "keep_current":     ("rejected", "rejected", "accepted", None),
    "counter_value":    ("modified", "modified", "modified", "modified"),
    "unclear":          (None, None, None, None),
    "none":             (None, None, None, None),
}


@pytest.mark.parametrize("stance", STANCES)
def test_decision_for_stance_table(stance):
    assert tuple(decision_for_stance(stance, k) for k in KINDS) == STANCE_TABLE[stance]


def test_stance_table_covers_every_stance_and_kind():
    assert set(STANCE_TABLE) == set(STANCES)
    assert KINDS == PROPOSAL_KINDS


# Reply × proposal kind → (action, decision). FR and EN, negations, politeness,
# mixed tokens. Columns: add · reduce · no_change · unknown.
REPLY_TABLE = [
    # adopt forms: accepted whatever was proposed
    ("oui", (A, A, A, A)),
    ("Oui !", (A, A, A, A)),
    ("yes", (A, A, A, A)),
    ("J’accepte", (A, A, A, A)),
    ("validé", (A, A, A, A)),
    ("Validé 👌", (A, A, A, A)),
    ("✅", (A, A, A, A)),
    ("✔️", (A, A, A, A)),
    ("ok validé", (A, A, A, A)),
    ("je valide", (A, A, A, A)),
    ("ok pour moi", (A, A, A, A)),
    ("d'accord", (A, A, A, A)),
    ("ok d'accord", (A, A, A, A)),
    ("go for it", (A, A, A, A)),
    ("agreed thx!!", (A, A, A, A)),
    ("oui 👍", (A, A, A, A)),
    ("yes thanks", (A, A, A, A)),
    # decline forms: rejected whatever was proposed ("non" to "keep the usual
    # staffing" asks for a change: still a refusal of the recommendation)
    ("non", (R, R, R, R)),
    ("Non.", (R, R, R, R)),
    ("no", (R, R, R, R)),
    ("nope", (R, R, R, R)),
    ("refusé", (R, R, R, R)),
    ("je refuse", (R, R, R, R)),
    ("pas d'accord", (R, R, R, R)),
    ("not ok", (R, R, R, R)),
    ("non non", (R, R, R, R)),
    ("❌", (R, R, R, R)),
    ("👎 merci", (R, R, R, R)),        # politeness carries no stance
    # counter forms: modified, then "what change?"
    ("corriger", (M, M, M, M)),
    ("CORRIGER", (M, M, M, M)),
    ("✏️", (M, M, M, M)),
    ("✏️ merci", (M, M, M, M)),
    ("modify", (M, M, M, M)),
    # keep-current forms (PO clarification §17.8): reject a change, accept "no change"
    ("tel quel", (R, R, A, CR)),
    ("on garde tel quel", (R, R, A, CR)),
    ("on garde comme ça", (R, R, A, CR)),
    ("keep as is", (R, R, A, CR)),
    ("keep it as is", (R, R, A, CR)),
    ("as is", (R, R, A, CR)),
    # "no thanks": decline or keep current — same decision for a change, two
    # readings for "no change"
    ("non merci", (R, R, CR, CR)),
    ("Non merci !", (R, R, CR, CR)),
    ("nan merci", (R, R, CR, CR)),
    ("no thanks", (R, R, CR, CR)),
    ("no thank you", (R, R, CR, CR)),
    ("non merci beaucoup", (R, R, CR, CR)),
    # the sentence of §17.8, now composed from the lexicon, not listed
    ("non merci on garde tel quel", (R, R, A, CR)),
    ("no thanks, keep as is", (R, R, A, CR)),
    # need negation (open decision closed by §19): rejects ADD, two readings for REDUCE
    ("pas besoin", (R, CR, A, CR)),
    ("no need", (R, CR, A, CR)),
    ("pas nécessaire", (R, CR, A, CR)),
    ("not needed", (R, CR, A, CR)),
    ("pas besoin merci", (R, CR, A, CR)),
    ("no need, thanks", (R, CR, A, CR)),
    # parts that contradict each other → confirmation, refusal read first
    ("non ok", (CR, CR, CR, CR)),
    ("ok non", (CR, CR, CR, CR)),
    ("no ok", (CR, CR, CR, CR)),
    ("oui non", (CR, CR, CR, CR)),
    ("non corriger", (CR, CR, CR, CR)),
    ("oui corriger", (CM, CM, CM, CM)),    # a correction outranks a plain yes
    ("ok on garde tel quel", (CR, CR, A, CR)),
    # hesitation
    ("bof", (CR, CR, CR, CR)),
    # bare acknowledgement → rule (b): one pending, inside the window → accepted
    ("ok", (A, A, A, A)),
    ("merci", (A, A, A, A)),
    ("👍", (A, A, A, A)),
    ("parfait, merci beaucoup", (A, A, A, A)),
]


@pytest.mark.parametrize("body,expected", REPLY_TABLE, ids=[r[0] for r in REPLY_TABLE])
def test_reply_by_proposal_kind(body, expected):
    m = match_keyword(body)
    assert m is not None, body
    got = tuple((r.action, r.decision) for r in (resolve_keyword(m, _pctx(k)) for k in KINDS))
    assert got == expected


@pytest.mark.parametrize("body,expected", REPLY_TABLE, ids=[r[0] for r in REPLY_TABLE])
def test_lexicon_decisions_carry_their_source(body, expected):
    for kind, (action, _) in zip(KINDS, expected):
        res = resolve_keyword(match_keyword(body), _pctx(kind))
        if action == "record":
            assert res.source in (DecisionSource.keyword, DecisionSource.bare_ack_rule)
        else:
            assert res.source is None and res.origin == "keyword_ambiguous" and res.why


def test_confirmation_whys_are_typed():
    assert resolve_keyword(match_keyword("tel quel"), _pctx("unknown")).why == "proposal_unknown"
    assert resolve_keyword(match_keyword("pas besoin"), _pctx("reduce")).why == "two_readings"
    assert resolve_keyword(match_keyword("non merci"), _pctx("no_change")).why == "two_readings"
    assert resolve_keyword(match_keyword("non ok"), _pctx("add")).why == "readings_conflict"


# Replies the lexicon must NOT decide: longer sentences, questions, and replies
# that mention another day — they go to the model, which is shown the
# recommendation's day (and answers `unclear` for another one).
NOT_KEYWORD_FORMS = [
    "", "   ", "maybe", "acc", "oui mais 3 serveurs", "ok mais plutôt 40", "no, make it 120 instead",
    "yes, let's go with that", "no problem, we'll follow it", "nope, ignore that",
    "non, pas d'accord avec ça", "d'accord sur le principe, mais 3 serveurs au lieu de 4",
    "ok pour moi, merci pour le brief de 19h", "je", "covers: 80",
    "on garde", "keep it", "comme ça",           # "keep" what? not a keep-current form
    "pas besoin demain", "non pas ce soir", "oui pour samedi", "no need tomorrow",
    "keep as is on friday", "non merci, mais oui pour demain",
    # a question is never a keyword
    "ok?", "oui ?", "non?", "hmm ok?", "pas besoin ?",
]


@pytest.mark.parametrize("body", NOT_KEYWORD_FORMS)
def test_longer_replies_are_not_keywords(body):
    assert match_keyword(body) is None
    assert parse_action(body) == ActionType.unknown


BARE_ACK_FORMS = [
    "ok", "OK", "okay", "ok merci", "ok thanks", "merci", "thanks", "thank you", "thx",
    "parfait", "perfect", "parfait, merci beaucoup", "great", "super", "top", "cool",
    "noted", "noté", "compris", "understood", "got it", "bien reçu", "👍", "👍👍 merci",
    "👌", "🙏", "👍🏽",
]


@pytest.mark.parametrize("body", BARE_ACK_FORMS)
def test_bare_ack_forms(body):
    assert match_keyword(body).kind == "bare_ack"
    assert is_bare_ack(body)
    # A bare ack is not a decision keyword: parse_action leaves it to rule (b).
    assert parse_action(body) == ActionType.unknown


@pytest.mark.parametrize("body,label", [
    ("oui", ActionType.accept), ("✅", ActionType.accept), ("ok d'accord", ActionType.accept),
    ("non", ActionType.reject), ("👎 merci", ActionType.reject),
    ("corriger", ActionType.modify), ("✏️ merci", ActionType.modify),
    ("non merci", ActionType.decline), ("on garde tel quel", ActionType.decline),
    ("pas besoin", ActionType.decline), ("non merci on garde tel quel", ActionType.decline),
    ("bof", ActionType.ambiguous), ("non ok", ActionType.ambiguous),
    ("oui corriger", ActionType.ambiguous), ("ok on garde tel quel", ActionType.ambiguous),
])
def test_parse_action_is_a_coarse_proposal_independent_label(body, label):
    assert parse_action(body) == label


def test_thumbs_up_is_ack_but_check_mark_is_adopt():
    # Documented choice: 👍 may answer the Receipt (rule b), ✅ answers "validate?".
    assert match_keyword("👍").kind == "bare_ack"
    assert match_keyword("✅").units == ("adopt",)


def test_lexicons_hold_stances_not_single_sentences():
    """PO: "fix the logic, not the example". No lexicon entry is a whole
    sentence patched in for one case; the §17.8 sentence is composed."""
    from app.services import manager_decision as md

    assert not hasattr(md, "DECLINE_KEEP_PHRASES") and not hasattr(md, "AMBIGUOUS_PHRASES")
    assert "non merci on garde tel quel" not in md._PHRASES.values()
    assert all(len(p) <= 4 for p in md._PHRASES)  # forms, not sentences
    assert match_keyword("non merci on garde tel quel").units == ("polite_decline", "keep")


def test_tokenisation():
    assert tokens("👍👍 merci!!") == ["👍", "👍", "merci"]
    assert tokens("J’accepte.") == ["j'accepte"]
    assert tokens("👍🏽") == ["👍"]


# ---------------------------------------------------------------------------
# Proposal derived from the stored recommendation, never from the reply
# ---------------------------------------------------------------------------

NV = "newsvendor"
FB = "fallback_roi_scale"


@pytest.mark.parametrize("headcount,task_class,ra,kind,magnitude", [
    # risk assessment stored (§18.4): its signed delta is authoritative
    (2, "staffing.add", {"recommended_delta_staff": 2, "decision_rule": NV}, "add", 2),
    (-1, "staffing.reduce", {"recommended_delta_staff": -1, "decision_rule": NV}, "reduce", 1),
    (0, "staffing.add", {"recommended_delta_staff": 0, "decision_rule": NV}, "no_change", None),
    # 0 from the ROI scale is not a "keep" message ("reduce by 0") → unknown
    (0, "staffing.reduce", {"recommended_delta_staff": 0, "decision_rule": FB}, "unknown", None),
    (3, "staffing.add", {"recommended_delta_staff": 3, "decision_rule": FB}, "add", 3),
    # stored as text by some drivers
    (2, None, '{"recommended_delta_staff": -2, "decision_rule": "newsvendor"}', "reduce", 2),
    # legacy rows: signed headcount
    (2, None, None, "add", 2),
    (-2, None, None, "reduce", 2),
    (0, None, None, "unknown", None),
    (None, None, None, "unknown", None),
    # contradictions → unknown, never a guess
    (2, "staffing.reduce", None, "unknown", None),
    (-2, "staffing.add", None, "unknown", None),
    (None, None, "not json", "unknown", None),
])
def test_proposal_from_recommendation(headcount, task_class, ra, kind, magnitude):
    p = proposal_from_recommendation(headcount, task_class, ra)
    assert (p.kind, p.magnitude) == (kind, magnitude)


def test_proposal_description_for_the_model():
    ws = datetime(2026, 9, 25, 19, 0, tzinfo=timezone.utc)
    we = datetime(2026, 9, 25, 22, 0, tzinfo=timezone.utc)
    p = proposal_from_recommendation(2, "staffing.add", None, ws, we)
    assert p.describe() == "ADD 2 staff for Friday 25/09 19:00–22:00 (task class staffing.add)"
    assert proposal_from_recommendation(-1, None, None).describe() == "REDUCE staffing by 1"
    keep = proposal_from_recommendation(0, None, {"recommended_delta_staff": 0, "decision_rule": NV})
    assert keep.describe() == "NO CHANGE (keep the usual staffing)"
    assert "not recorded" in Proposal().describe()


# ---------------------------------------------------------------------------
# (b) bare acknowledgement rule
# ---------------------------------------------------------------------------

def test_bare_ack_records_accepted_only_for_one_pending_inside_window():
    res = resolve_bare_ack(_ctx(1, timedelta(hours=1)))
    assert (res.action, res.decision, res.source) == ("record", "accepted", DecisionSource.bare_ack_rule)


def test_bare_ack_at_window_edge_is_inside():
    assert resolve_bare_ack(_ctx(1, RESPONSE_WINDOW)).action == "record"


def test_bare_ack_outside_window_asks():
    res = resolve_bare_ack(_ctx(1, RESPONSE_WINDOW + timedelta(seconds=1)))
    assert (res.action, res.origin, res.why) == ("confirm", "bare_ack", "outside_response_window")


def test_bare_ack_with_several_pending_asks():
    res = resolve_bare_ack(_ctx(2))
    assert (res.action, res.why) == ("confirm", "several_pending")


def test_bare_ack_with_nothing_pending_records_nothing():
    res = resolve_bare_ack(_ctx(0))
    assert (res.action, res.why) == ("none", "no_pending_recommendation")


def test_bare_ack_dispatched_in_the_future_is_not_in_window():
    # Clock skew: a dispatch timestamp after `now` is not trusted as "in window".
    ctx = PendingContext(1, NOW + timedelta(minutes=5), NOW)
    assert resolve_bare_ack(ctx).action == "confirm"


# ---------------------------------------------------------------------------
# Model stance → decision (same mapping, HITL threshold)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("stance", ["adopt_proposal", "decline_proposal", "keep_current", "counter_value"])
@pytest.mark.parametrize("kind", ["add", "reduce", "no_change"])
def test_model_stance_at_threshold_records_the_mapped_decision(stance, kind):
    res = resolve_model(stance, DECISION_CONFIDENCE_THRESHOLD, kind)
    assert (res.action, res.decision, res.source) == (
        "record", decision_for_stance(stance, kind), DecisionSource.model_auto)


@pytest.mark.parametrize("stance", ["adopt_proposal", "decline_proposal", "keep_current", "counter_value"])
def test_model_stance_below_threshold_confirms(stance):
    res = resolve_model(stance, DECISION_CONFIDENCE_THRESHOLD - 0.01, "add")
    assert (res.action, res.decision, res.origin, res.why) == (
        "confirm", decision_for_stance(stance, "add"), "model", "below_confidence_threshold")


def test_model_keep_current_with_unknown_direction_confirms_even_when_sure():
    res = resolve_model("keep_current", 0.99, "unknown")
    assert (res.action, res.decision, res.why) == ("confirm", "rejected", "proposal_unknown")


def test_model_unclear_asks_for_the_decision_and_writes_nothing():
    res = resolve_model("unclear", 0.99, "add")
    assert (res.action, res.why) == ("none", "stance_unclear")


@pytest.mark.parametrize("stance", ["none", None, "maybe", "accepted"])
def test_model_without_stance_records_nothing(stance):
    res = resolve_model(stance, 0.99, "add")
    assert (res.action, res.why) == ("none", "no_stance")


def test_classifier_schema_takes_a_stance_not_a_decision():
    ok = parse_model_json('{"stance":"keep_current","confidence":0.9}', ClassifierOutput)
    assert ok.stance == "keep_current" and ok.intent == "free_form"
    for bad in ('{"stance":"yes","confidence":0.9}', '{"stance":"adopt_proposal","confidence":2}',
                '{"confidence":0.9}', '{"decision":"accepted","confidence":0.9}', "not json"):
        with pytest.raises(ValueError):
            parse_model_json(bad, ClassifierOutput)


def test_markdown_fence_is_stripped():
    out = parse_model_json('```json\n{"stance":"none","confidence":0.3}\n```', ClassifierOutput)
    assert out.stance == "none"


# ---------------------------------------------------------------------------
# Buttons, confirmation answers, reason prompt, routing
# ---------------------------------------------------------------------------

def test_button_payloads_are_fixed_and_total():
    assert BUTTON_DECISIONS == {BUTTON_ACCEPT: "accepted", BUTTON_REJECT: "rejected",
                                BUTTON_CORRECT: "modified"}
    assert BUTTON_CONFIRMATIONS == {BUTTON_CONFIRM_YES: True, BUTTON_CONFIRM_NO: False}


@pytest.mark.parametrize("body,expected", [
    ("oui", True), ("Oui !", True), ("yes", True), ("c'est ça", True), ("exact", True),
    ("👍", True), ("ok", True), ("✅", True),
    ("non", False), ("no", False), ("annuler", False), ("❌", False), ("👎", False),
    ("oui mais non", None), ("plutôt 3 serveurs", None), ("", None), ("oui ?", None),
])
def test_confirmation_answers(body, expected):
    assert match_confirmation_answer(body) is expected


def test_reason_prompt_only_after_reject_or_correction():
    assert wants_reason_prompt("rejected", False)
    assert wants_reason_prompt("modified", False)
    assert not wants_reason_prompt("accepted", False)   # interruption budget
    assert not wants_reason_prompt("rejected", True)    # already given in the reply


def test_reason_routed_only_above_threshold():
    assert routed_reason("policy", 0.9) == "policy"
    assert routed_reason("policy", 0.5) is None
    assert routed_reason("elsewhere", 0.99) is None
    assert routed_reason(None, None) is None


def test_confirmation_copy_is_localised():
    assert confirmation_question("rejected") == "Je note un refus, c'est bien ça ?"
    assert confirmation_question("rejected", "en") == "I'm noting a refusal, is that right?"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def test_capture_metrics():
    events = [
        {"result": "recorded", "decision_source": "button"},
        {"result": "recorded", "decision_source": "keyword"},
        {"result": "recorded", "decision_source": "bare_ack_rule"},
        {"result": "confirmation_requested"},
        {"result": "confirmed", "decision_source": "model_confirmed"},
        {"result": "confirmation_requested"},
        {"result": "confirmation_expired"},
        {"result": "confirmation_requested"},
        {"result": "declined"},
        {"result": "not_recorded", "why": "llm_error"},
        {"result": "reason_captured", "reason_route": "policy"},
        {"result": "reason_captured"},
    ]
    m = compute_capture_metrics(events)
    assert m.replies == 11                   # the expiry is not a reply
    assert m.decision_seeking_replies == 7   # recorded ×3 + requested ×3 + not_recorded
    assert m.decisions_written == 4
    assert m.capture_rate == round(4 / 7, 4)
    assert m.by_source == {"button": 1, "keyword": 1, "bare_ack_rule": 1, "model_confirmed": 1}
    assert m.source_share["button"] == 0.25
    assert m.confirmation_rate == round(1 / 3, 4)
    assert m.confirmation_timeout_rate == round(1 / 3, 4)
    assert m.confirmations_declined == 1
    assert m.not_recorded_by_why == {"llm_error": 1}
    assert (m.reasons_captured, m.reasons_routed) == (2, 1)


def test_capture_metrics_empty():
    m = compute_capture_metrics([])
    assert m.capture_rate is None and m.confirmation_rate is None


def test_decision_rules_never_read_the_outcome():
    """§16.6: decision and outcome stay independent. The pure rules module has
    no access to actual covers — pinned so a future edit has to break a test."""
    import inspect

    import app.services.manager_decision as md

    assert "actual_covers" not in inspect.getsource(md).replace(
        "Nothing in this\n  module reads ``actual_covers``", ""
    )
