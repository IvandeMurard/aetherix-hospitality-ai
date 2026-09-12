"""Orchestrator decision rules — plain functions over validated numbers.

ADR-0004 D7: the agentic loop lives in ``orchestrator/``, not in ``app/services``.

These functions are deliberately isolated from :mod:`orchestrator.agent` for one
reason: they are the only part of the orchestrator whose behaviour looks
non-deterministic from outside (the same request can call a node once or twice),
so they are the part that most needs to be deterministic and testable on its own.
Every function here is pure — no I/O, no clock, no model call. The same inputs
always produce the same decision, and ``tests/orchestrator/test_rules.py``
asserts it.

Why recall similarity and not forecast confidence
-------------------------------------------------
HOS-189 offers two candidate loop signals: ``top_similarity < 0.7`` on memory
recall, or ``confidence < 0.6`` on the forecast. Only the first belongs here.
``confidence < 0.6`` is already owned downstream by
``app/services/forecast_guardrail.py`` (Epic 12 G-4 / HOS-251), which degrades
rather than blanks the recommendation. A retry on the same signal in the
orchestrator would be a second, competing authority over one threshold — the
exact coupling ADR-0004 exists to prevent. Recall weakness has no such owner:
nothing downstream reacts to a thin memory hit, so reacting to it is the
orchestrator's job.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Optional

# ---------------------------------------------------------------------------
# Thresholds. These are orchestration policy, not tuning knobs — see HOS-335
# (frozen rules) before making any of them writable from a learning loop.
# ---------------------------------------------------------------------------

#: Below this top-hit cosine similarity, the recall is judged too thin to ground
#: the reasoning step, and is retried once with a wider k.
#:
#: Interacts with the node's own filter: ``MemoryRecallService.recall`` drops
#: hits under ``min_similarity=0.50`` before the orchestrator ever sees them.
#: So the band in which this loop actually fires is ``0.50 <= sim < 0.70``.
#: Under 0.50 the node returns nothing and the loop reports ``EMPTY`` rather
#: than widening — correctly, since a wider k over a corpus with no hit above
#: the node's own floor returns the same nothing. The orchestrator does not
#: override that filter: node-side relevance policy belongs to the node
#: (ADR-0004 D1).
RECALL_SIMILARITY_FLOOR = 0.7

#: k on the first recall attempt.
RECALL_K_DEFAULT = 5

#: k on the widened retry.
RECALL_K_WIDENED = 10

#: Hard stop. The loop may call the memory node at most this many times per run.
#: A bound, not a guideline: the agent has no say in it.
MAX_RECALL_ATTEMPTS = 2


class RecallOutcome(str, Enum):
    """Why the recall loop stopped. Every exit path carries one of these.

    A free-string reason would make the trace unqueryable, which is precisely
    what HOS-331 needs it to be when it lands the run object on the ledger.
    """

    #: First attempt cleared the floor — no retry needed.
    SUFFICIENT = "sufficient"
    #: A widened retry ran and its result is what we kept.
    WIDENED = "widened"
    #: Still below the floor after the last permitted attempt.
    BUDGET_EXHAUSTED = "budget_exhausted"
    #: Recall returned nothing at all; widening an empty result changes nothing.
    EMPTY = "empty"
    #: No structured recall was wired in, so there is no similarity to judge.
    SIGNAL_UNAVAILABLE = "signal_unavailable"


@dataclass(frozen=True)
class RecallDecision:
    """Outcome of one pass of the recall loop.

    ``next_k`` is ``None`` when the loop must stop; ``outcome`` always says why.
    """

    next_k: Optional[int]
    outcome: RecallOutcome

    @property
    def should_retry(self) -> bool:
        return self.next_k is not None


def top_similarity(hits: Iterable[Any]) -> Optional[float]:
    """Highest ``similarity`` among *hits*, or ``None`` when there are none.

    Reads the attribute defensively so the orchestrator stays decoupled from
    ``MemoryHit`` itself (ADR-0004: no ``app.*`` imports in this package). A hit
    without a usable similarity is ignored rather than treated as 0.0 — a
    missing signal is not a weak signal, and conflating them would trigger
    retries on a wiring bug.
    """
    values = [
        float(s)
        for s in (getattr(h, "similarity", None) for h in hits)
        if isinstance(s, (int, float))
    ]
    return max(values) if values else None


def select_recall_k(attempt: int, similarity: Optional[float]) -> RecallDecision:
    """Decide whether to call the memory node again, and with what k.

    :param attempt: 1-based count of recall calls already made in this run.
    :param similarity: top similarity of the attempt just completed, or ``None``
        when the recall returned no hits.

    The rule, in full:

    * no hits at all      → stop (``EMPTY``); a wider k over an empty corpus
      returns the same nothing;
    * at or above floor   → stop (``SUFFICIENT``);
    * below floor, budget → retry at :data:`RECALL_K_WIDENED` (``WIDENED``);
    * below floor, spent  → stop (``BUDGET_EXHAUSTED``).

    The budget check is evaluated before the threshold comparison can authorise
    another call, so no sequence of similarity values can produce more than
    :data:`MAX_RECALL_ATTEMPTS` calls.
    """
    if attempt < 1:
        raise ValueError(f"attempt is 1-based, got {attempt}")

    if similarity is None:
        return RecallDecision(next_k=None, outcome=RecallOutcome.EMPTY)

    if similarity >= RECALL_SIMILARITY_FLOOR:
        outcome = RecallOutcome.SUFFICIENT if attempt == 1 else RecallOutcome.WIDENED
        return RecallDecision(next_k=None, outcome=outcome)

    if attempt >= MAX_RECALL_ATTEMPTS:
        return RecallDecision(next_k=None, outcome=RecallOutcome.BUDGET_EXHAUSTED)

    return RecallDecision(next_k=RECALL_K_WIDENED, outcome=RecallOutcome.WIDENED)
