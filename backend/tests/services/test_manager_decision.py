"""Décision #38 / ADR-0007 §16 — pure decision-capture rules.

Every keyword form is pinned here: a change to the fast path's vocabulary must
change a test. Ambiguous forms must go to confirmation, never to a guess.
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
    RESPONSE_WINDOW,
    ClassifierOutput,
    DecisionSource,
    PendingContext,
    compute_capture_metrics,
    confirmation_question,
    is_bare_ack,
    match_confirmation_answer,
    match_keyword,
    parse_model_json,
    resolve_bare_ack,
    proposes_change,
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
# (c) keyword fast path — every documented form
# ---------------------------------------------------------------------------

ACCEPT_FORMS = [
    "accept", "Accept", "ACCEPT", "  accept  ", "accepted", "accepter", "accepté",
    "j'accepte", "J’accepte", "oui", "Oui !", "yes", "yep", "ouais",
    "validé", "valide", "Validé 👌", "valider", "validated", "approved", "agreed", "go",
    "✅", "✔️", "ok validé", "OK validé !", "je valide", "c'est validé", "ok pour moi",
    "d'accord", "ok d'accord", "go for it", "agreed thx!!", "oui 👍", "yes thanks",
]
REJECT_FORMS = [
    "reject", "REJECT", " reject ", "rejected", "rejeter", "rejeté", "refuse", "refusé",
    "refuser", "je refuse", "refused", "decline", "declined", "non", "Non.", "no", "NO",
    "nope", "nan", "❌", "👎", "pas d'accord", "not ok", "non non",
]
MODIFY_FORMS = ["corriger", "CORRIGER", "correct", "modifier", "modify", "✏️", "✏️ merci", "ajuster"]
# "Decline / keep as is" (PO clarification 24/09/2026, ADR-0007 §17.8): rejected
# when the recommendation proposes a change; confirmation otherwise.
DECLINE_FORMS = [
    "non merci", "Non merci !", "no thanks", "no thank you", "nan merci", "non merci beaucoup",
    "non merci on garde tel quel", "on garde tel quel", "tel quel", "on garde comme ça",
    "keep as is", "keep it as is", "as is",
]
AMBIGUOUS_FORMS = [
    # "pas besoin": we don't need the extra staff | no need to change anything
    "pas besoin", "no need", "pas nécessaire",
    # a refusal token next to an acceptance / ack token
    "non ok", "ok non", "oui non", "no ok", "👎 merci", "bof", "non corriger",
]
BARE_ACK_FORMS = [
    "ok", "OK", "okay", "ok merci", "ok thanks", "merci", "thanks", "thank you", "thx",
    "parfait", "perfect", "parfait, merci beaucoup", "great", "super", "top", "cool",
    "noted", "noté", "compris", "understood", "got it", "bien reçu", "👍", "👍👍 merci",
    "👌", "🙏", "👍🏽",
]
NOT_KEYWORD_FORMS = [
    "", "   ", "maybe", "acc", "oui mais 3 serveurs", "ok mais plutôt 40", "no, make it 120 instead",
    "yes, let's go with that", "no problem, we'll follow it", "nope, ignore that",
    "non, pas d'accord avec ça", "d'accord sur le principe, mais 3 serveurs au lieu de 4",
    "ok pour moi, merci pour le brief de 19h", "je", "covers: 80",
    # a question is never a keyword
    "ok?", "oui ?", "non?", "hmm ok?",
]


@pytest.mark.parametrize("body", ACCEPT_FORMS)
def test_accept_forms(body):
    assert match_keyword(body).kind == "accept"
    assert parse_action(body) == ActionType.accept


@pytest.mark.parametrize("body", REJECT_FORMS)
def test_reject_forms(body):
    assert match_keyword(body).kind == "reject"
    assert parse_action(body) == ActionType.reject


@pytest.mark.parametrize("body", MODIFY_FORMS)
def test_modify_forms(body):
    # What the text fallback asks for ("Répondez … CORRIGER") and the Receipt's ✏️.
    assert match_keyword(body).kind == "modify"
    assert parse_action(body) == ActionType.modify
    res = resolve_keyword(match_keyword(body), _ctx())
    assert (res.action, res.decision, res.source) == ("record", "modified", DecisionSource.keyword)


def test_accept_plus_modify_is_ambiguous_proposing_modified():
    m = match_keyword("oui corriger")
    assert (m.kind, m.proposed) == ("ambiguous", "modified")


@pytest.mark.parametrize("body", AMBIGUOUS_FORMS)
def test_ambiguous_forms_go_to_confirmation(body):
    m = match_keyword(body)
    assert m.kind == "ambiguous"
    assert parse_action(body) == ActionType.ambiguous
    res = resolve_keyword(m, _ctx())
    assert res.action == "confirm" and res.origin == "keyword_ambiguous"
    assert res.decision == "rejected"  # the reading proposed; the manager has the last word


@pytest.mark.parametrize("body", DECLINE_FORMS)
def test_decline_forms_reject_a_recommendation_that_proposes_a_change(body):
    m = match_keyword(body)
    assert m.kind == "decline"
    assert parse_action(body) == ActionType.decline
    ctx = PendingContext(1, NOW - timedelta(hours=1), NOW, latest_proposes_change=True)
    res = resolve_keyword(m, ctx)
    assert (res.action, res.decision, res.source) == ("record", "rejected", DecisionSource.keyword)


@pytest.mark.parametrize("proposes,reading,why", [
    (False, "accepted", "no_change_proposed"),   # "keep as is" of a no-change recommendation
    (None, "rejected", "change_unknown"),        # cannot be told → ask, never guess
])
def test_decline_forms_confirm_otherwise(proposes, reading, why):
    ctx = PendingContext(1, NOW - timedelta(hours=1), NOW, latest_proposes_change=proposes)
    res = resolve_keyword(match_keyword("non merci on garde tel quel"), ctx)
    assert (res.action, res.decision, res.origin, res.why) == ("confirm", reading, "keyword_ambiguous", why)


@pytest.mark.parametrize("headcount,expected", [(2, True), (-1, True), (0, False), (None, None)])
def test_proposes_change(headcount, expected):
    assert proposes_change(headcount) is expected


@pytest.mark.parametrize("body", BARE_ACK_FORMS)
def test_bare_ack_forms(body):
    assert match_keyword(body).kind == "bare_ack"
    assert is_bare_ack(body)
    # A bare ack is not a decision keyword: parse_action leaves it to rule (b).
    assert parse_action(body) == ActionType.unknown


@pytest.mark.parametrize("body", NOT_KEYWORD_FORMS)
def test_longer_replies_are_not_keywords(body):
    assert match_keyword(body) is None
    assert parse_action(body) == ActionType.unknown


def test_thumbs_up_is_ack_but_check_mark_is_accept():
    # Documented choice: 👍 may answer the Receipt (rule b), ✅ answers "validate?".
    assert match_keyword("👍").kind == "bare_ack"
    assert match_keyword("✅").kind == "accept"


def test_tokenisation():
    assert tokens("👍👍 merci!!") == ["👍", "👍", "merci"]
    assert tokens("J’accepte.") == ["j'accepte"]
    assert tokens("👍🏽") == ["👍"]


def test_keyword_resolution_sources():
    assert resolve_keyword(match_keyword("oui"), _ctx()).source == DecisionSource.keyword
    assert resolve_keyword(match_keyword("non"), _ctx()).decision == "rejected"


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
# Model resolution (HITL threshold)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("decision", ["accepted", "rejected", "modified"])
def test_model_at_threshold_records(decision):
    res = resolve_model(decision, DECISION_CONFIDENCE_THRESHOLD)
    assert (res.action, res.source) == ("record", DecisionSource.model_auto)


@pytest.mark.parametrize("decision", ["accepted", "rejected", "modified"])
def test_model_below_threshold_confirms(decision):
    res = resolve_model(decision, DECISION_CONFIDENCE_THRESHOLD - 0.01)
    assert (res.action, res.decision, res.origin) == ("confirm", decision, "model")


@pytest.mark.parametrize("decision", ["none", None, "maybe"])
def test_model_without_decision_records_nothing(decision):
    assert resolve_model(decision, 0.99).action == "none"


def test_classifier_schema_rejects_out_of_taxonomy():
    ok = parse_model_json('{"decision":"accepted","confidence":0.9}', ClassifierOutput)
    assert ok.decision == "accepted" and ok.intent == "free_form"
    for bad in ('{"decision":"yes","confidence":0.9}', '{"decision":"accepted","confidence":2}',
                '{"confidence":0.9}', "not json"):
        with pytest.raises(ValueError):
            parse_model_json(bad, ClassifierOutput)


def test_markdown_fence_is_stripped():
    out = parse_model_json('```json\n{"decision":"none","confidence":0.3}\n```', ClassifierOutput)
    assert out.decision == "none"


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
