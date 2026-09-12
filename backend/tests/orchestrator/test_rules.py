"""Unit tests for orchestrator/rules.py (ADR-0004 D7 · HOS-189).

The recall loop is the orchestrator's only non-deterministic-looking behaviour,
so the rule that drives it is tested in isolation, without a database, an
embedding provider, or a model call.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from orchestrator import rules
from orchestrator.rules import RecallOutcome


def hit(similarity):
    return SimpleNamespace(similarity=similarity, reflection="r")


# ---------------------------------------------------------------------------
# top_similarity
# ---------------------------------------------------------------------------

def test_top_similarity_picks_the_maximum():
    assert rules.top_similarity([hit(0.41), hit(0.92), hit(0.63)]) == 0.92


def test_top_similarity_of_nothing_is_none():
    assert rules.top_similarity([]) is None


def test_hit_without_usable_similarity_is_ignored_not_zeroed():
    """A missing signal is not a weak signal.

    Treating it as 0.0 would make a wiring bug look like a thin corpus and
    trigger a pointless second call to the memory node on every run.
    """
    assert rules.top_similarity([SimpleNamespace(reflection="no similarity")]) is None
    assert rules.top_similarity([SimpleNamespace(similarity=None), hit(0.8)]) == 0.8


# ---------------------------------------------------------------------------
# select_recall_k
# ---------------------------------------------------------------------------

def test_first_attempt_above_floor_stops():
    d = rules.select_recall_k(attempt=1, similarity=0.85)
    assert not d.should_retry
    assert d.outcome is RecallOutcome.SUFFICIENT


def test_first_attempt_below_floor_widens_k():
    d = rules.select_recall_k(attempt=1, similarity=0.42)
    assert d.should_retry
    assert d.next_k == rules.RECALL_K_WIDENED
    assert d.outcome is RecallOutcome.WIDENED


def test_exactly_at_the_floor_is_sufficient():
    """The floor is inclusive. Stated as a test so a later edit has to mean it."""
    d = rules.select_recall_k(attempt=1, similarity=rules.RECALL_SIMILARITY_FLOOR)
    assert not d.should_retry
    assert d.outcome is RecallOutcome.SUFFICIENT


def test_budget_exhausted_after_the_last_permitted_attempt():
    d = rules.select_recall_k(attempt=rules.MAX_RECALL_ATTEMPTS, similarity=0.10)
    assert not d.should_retry
    assert d.outcome is RecallOutcome.BUDGET_EXHAUSTED


def test_empty_recall_is_not_retried():
    """Widening k over an empty corpus returns the same nothing, one call later."""
    d = rules.select_recall_k(attempt=1, similarity=None)
    assert not d.should_retry
    assert d.outcome is RecallOutcome.EMPTY


def test_budget_cannot_be_exceeded_by_any_similarity_sequence():
    """No value at the last attempt authorises another call. The bound is hard."""
    for sim in (0.0, 0.1, 0.5, 0.69, 0.7, 1.0, None):
        d = rules.select_recall_k(attempt=rules.MAX_RECALL_ATTEMPTS, similarity=sim)
        assert not d.should_retry, f"similarity={sim} escaped the recall budget"


def test_attempt_is_one_based():
    with pytest.raises(ValueError):
        rules.select_recall_k(attempt=0, similarity=0.5)


def test_the_rule_is_deterministic():
    """Same input, same decision — every time. No model call hides in here."""
    first = rules.select_recall_k(attempt=1, similarity=0.42)
    for _ in range(100):
        again = rules.select_recall_k(attempt=1, similarity=0.42)
        assert again == first
