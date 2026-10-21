"""HOS-357 / HOS-354 — pure rules: what is a question, which staffing figure a
reply states. Every form is pinned here: a change to either rule must change a
test. Nothing here calls a model or a DB.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.manager_decision import (
    REPLY_RESULTS,
    PendingContext,
    Proposal,
    StaffFigure,
    describe_staff_figure,
    figure_confirmation_question,
    is_question,
    read_staff_figure,
    recorded_message,
)
from app.services.receipts import FeedbackIntent, ReceiptsService, resolve_question

ADD_3 = Proposal("add", 3)
ADD_2 = Proposal("add", 2)
REDUCE_2 = Proposal("reduce", 2)
UNKNOWN = Proposal()


# ---------------------------------------------------------------------------
# is_question
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("body", [
    "pourquoi ?", "pourquoi", "Pourquoi 3 extras ? 2 suffisent", "ok mais pourquoi ?",
    "why?", "why so many", "combien de couverts mardi", "comment tu calcules",
    "how many covers tonight", "hmm ok?", "oui ?", "?", "pourquoi pas ?",
    "c'est pour quel service ?",
])
def test_is_a_question(body):
    assert is_question(body)


@pytest.mark.parametrize("body", [
    "pourquoi pas",                 # a lukewarm yes (golden parser-confirm-whynot-fr-001)
    "Pourquoi pas, on y va",
    "why not",
    "oui", "non merci", "plutôt 2 extras", "ok", "👍", "",
    "on fait comment ce soir",      # the interrogative must open the reply
])
def test_is_not_a_question(body):
    assert not is_question(body)


# ---------------------------------------------------------------------------
# read_staff_figure
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("body, proposal, delta", [
    # a figure that says it is a delta
    ("plutôt 2 extras", ADD_3, 2),
    ("2 extras suffisent", ADD_3, 2),
    ("1 extra", ADD_3, 1),
    ("+1 seulement", ADD_3, 1),
    ("1 serveur de plus", ADD_3, 1),
    ("2 de plus", ADD_3, 2),
    ("2 extras au lieu de 3", ADD_3, 2),
    ("1 de moins", REDUCE_2, -1),
    ("2 extras de moins", ADD_3, -2),
    ("-1", REDUCE_2, -1),
    ("make it 1 more", ADD_3, 1),
    ("2 extra staff is enough", ADD_3, 2),
    ("plutôt 2 extras", UNKNOWN, 2),       # the unit says the direction
    ("plutôt 4 renforts", ADD_3, 4),
    # the proposal's own figure lends its unit to a number in the same reply
    ("pourquoi 3 extras ? 2 suffisent", ADD_3, 2),
    ("pourquoi +3 ? 2 suffisent", ADD_3, 2),
    ("pourquoi 2 de moins ? 1 suffit", REDUCE_2, -1),
    # covers and staff in one reply: only the staff figure
    ("dinner covers 180, 2 extras would have been enough", ADD_3, 2),
    ("on a fait 40 couverts, 1 extra aurait suffi", ADD_3, 1),
])
def test_reads_the_delta(body, proposal, delta):
    assert read_staff_figure(body, proposal) == StaffFigure(delta=delta)


@pytest.mark.parametrize("body, proposal, n", [
    ("plutôt 2", ADD_3, 2),                          # extras? covers? never guessed
    ("pourquoi ? plutôt 2", ADD_3, 2),
    ("plutôt 4 au lieu de 5 👀", ADD_2, 4),
    ("mais 3 serveurs au lieu de 4", ADD_2, 3),      # 3 servers: extra, or a total?
    ("pourquoi 3 serveurs ? 2 suffisent", ADD_3, 2),  # a role noun lends no unit
    ("ok mais plutôt 40", ADD_2, 40),
])
def test_asks_the_unit_of_a_bare_number_in_a_counter(body, proposal, n):
    assert read_staff_figure(body, proposal) == StaffFigure(unit_unknown=n)


@pytest.mark.parametrize("body, proposal", [
    ("pourquoi 3 extras ?", ADD_3),                  # the proposal's own figure
    ("ok pour 3 extras", ADD_3),
    ("2 de moins", REDUCE_2),
    ("mais 3 serveurs au lieu de 4", ADD_3),         # 3 = the proposal, 4 = replaced
    ("yes but make it 2 cooks not 3", ADD_2),
    ("all good, see you at 6", ADD_2),               # no counter in the reply
    ("ok pour moi, merci pour le brief de 19h", ADD_2),
    ("on se voit à 19h30 ?", ADD_2),
    ("le 23/10 plutôt", ADD_2),                      # a date
    ("120 pax tonight", ADD_2),                      # covers
    ("on attend plutôt 95 couverts ce soir", ADD_2),
    ("plutôt 60 extras", ADD_2),                     # beyond any headcount
    ("0 extra", ADD_3),                              # "no extra" is a stance
    ("2 extras ou 1 de moins", ADD_3),               # two counters: not read
    ("on a 2 mariages ce soir", ADD_2),              # a number with another noun
    ("pourquoi ?", ADD_3),
    ("", ADD_3),
])
def test_reads_nothing(body, proposal):
    assert read_staff_figure(body, proposal) is None


# ---------------------------------------------------------------------------
# Copy: the figure is quoted back
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("delta, proposal, locale, text", [
    (2, ADD_3, "fr", "Je note 2 extras au lieu de 3, c'est bien ça ?"),
    (1, ADD_3, "fr", "Je note 1 extra au lieu de 3, c'est bien ça ?"),
    (-1, REDUCE_2, "fr", "Je note 1 de moins au lieu de 2, c'est bien ça ?"),
    (1, REDUCE_2, "fr", "Je note 1 extra au lieu de 2 de moins, c'est bien ça ?"),
    (2, UNKNOWN, "fr", "Je note 2 extras, c'est bien ça ?"),
    (2, ADD_3, "en", "I'm noting 2 extra staff instead of 3, is that right?"),
    (-1, REDUCE_2, "en", "I'm noting 1 fewer instead of 2, is that right?"),
])
def test_figure_confirmation_question(delta, proposal, locale, text):
    assert figure_confirmation_question(delta, proposal, locale) == text


def test_recorded_message_quotes_the_figure_of_a_correction_only():
    assert recorded_message("modified", "fr", 2) == "Correction enregistrée : 2 extras."
    assert recorded_message("modified", "en", -1) == "Correction recorded: 1 fewer."
    assert recorded_message("modified", "fr") == "Correction enregistrée."
    assert recorded_message("rejected", "fr", 2) == "Refus enregistré."


def test_describe_staff_figure():
    assert [describe_staff_figure(d) for d in (1, 2, -1, -3)] == [
        "1 extra", "2 extras", "1 de moins", "3 de moins"]


def test_question_answered_is_a_reply_result():
    assert "question_answered" in REPLY_RESULTS


# ---------------------------------------------------------------------------
# resolve_question — whatever the reading, never a write
# ---------------------------------------------------------------------------

NOW = datetime(2030, 1, 15, 12, 0, tzinfo=timezone.utc)
CTX = PendingContext(pending_count=1, latest_dispatched_at=NOW - timedelta(hours=1), now=NOW,
                     proposal="add")


def _feedback(source, stance=None, confidence=1.0, **kw):
    return FeedbackIntent(intent="free_form", stance=stance, actual_value=None, notes="",
                          confidence=confidence, source=source, **kw)


@pytest.mark.parametrize("feedback, decision", [
    (_feedback("staff_figure", "counter_value", retained_delta_staff=2), "modified"),
    (_feedback("llm", "adopt_proposal", 0.99), "accepted"),
    (_feedback("llm", "decline_proposal", 0.99), "rejected"),
    (_feedback("llm", "keep_current", 0.95), "rejected"),
    (_feedback("llm", "counter_value", 0.5), "modified"),
])
def test_a_position_in_a_question_is_always_confirmed(feedback, decision):
    res = resolve_question(feedback, CTX)
    assert (res.action, res.decision, res.origin) == ("confirm", decision, "question")


@pytest.mark.parametrize("feedback", [
    _feedback("llm", "none", 0.99),
    _feedback("llm", "unclear", 0.9),
    _feedback("llm_error"),
    _feedback("llm_unmappable"),
    _feedback("figure_unit", figure_unit_unknown=2),
])
def test_a_question_without_a_position_writes_and_asks_nothing(feedback):
    assert resolve_question(feedback, CTX).action == "none"


# ---------------------------------------------------------------------------
# parse_inbound in question mode
# ---------------------------------------------------------------------------

class _NoModel:
    async def complete(self, *a, **kw):
        raise AssertionError("the model must not be called")


class _Model:
    def __init__(self, answer: str):
        self.answer = answer
        self.calls = 0

    async def complete(self, *a, **kw):
        self.calls += 1
        return self.answer


@pytest.mark.asyncio
async def test_question_figure_is_read_without_the_model():
    fb = await ReceiptsService(db=None, llm=_NoModel()).parse_inbound(
        "pourquoi 3 extras ? 2 suffisent", ADD_3, question=True)
    assert (fb.source, fb.stance, fb.retained_delta_staff) == ("staff_figure", "counter_value", 2)


@pytest.mark.asyncio
async def test_question_bare_number_is_not_sent_to_the_model():
    fb = await ReceiptsService(db=None, llm=_NoModel()).parse_inbound(
        "pourquoi ? plutôt 2", ADD_3, question=True)
    assert (fb.source, fb.figure_unit_unknown) == ("figure_unit", 2)


@pytest.mark.asyncio
async def test_covers_in_a_question_are_not_a_correction():
    model = _Model('{"stance": "none", "confidence": 0.9, "corrected_value": 140}')
    fb = await ReceiptsService(db=None, llm=model).parse_inbound(
        "pourquoi 140 covers ?", ADD_3, question=True)
    assert fb.source == "llm" and model.calls == 1   # the covers regex is skipped
    assert fb.actual_value is None                     # the forecast quoted, not corrected


@pytest.mark.asyncio
async def test_outside_a_question_the_figure_rides_with_the_model_reading():
    model = _Model('{"stance": "counter_value", "confidence": 0.95}')
    fb = await ReceiptsService(db=None, llm=model).parse_inbound("plutôt 2 extras", ADD_3)
    assert (fb.source, fb.stance, fb.retained_delta_staff) == ("llm", "counter_value", 2)
