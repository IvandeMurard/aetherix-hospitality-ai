"""Memory isolation + poisoning-contract security suite (HOS-295, plan #2).

Two invariants that protect a design-partner's data:

1. **Tenant isolation** — every ``operational_memory`` read is scoped by
   ``hotel_id`` as a *bound parameter*. A cross-tenant recall is structurally
   impossible: the filter is not optional and the tenant id is never f-string
   interpolated. (The exhaustive recall behaviour lives in
   ``tests/test_memory_recall_service.py``; here we pin the security invariant.)
2. **Poisoning contract** — an aberrant ``actual_covers`` value is bounded before
   it can reach retraining: ``reject`` blocks ingestion, ``flag`` ingests but
   tags. (Exhaustive bounds cases live in ``tests/services/test_feedback_guard.py``;
   here we pin the security contract severity→ingestion.)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.feedback_guard import evaluate
from app.services.memory_recall_service import MemoryRecallService

_EMB = [0.1] * 1024


def _capturing_db() -> tuple[MagicMock, dict]:
    """AsyncSession mock that records the (sql, params) of the last execute()."""
    captured: dict = {}

    async def _execute(sql, params=None):
        captured["sql"] = str(sql)
        captured["params"] = params or {}
        result = MagicMock()
        result.fetchall.return_value = []
        result.fetchone.return_value = None
        return result

    db = MagicMock()
    db.execute = AsyncMock(side_effect=_execute)
    return db, captured


# ---------------------------------------------------------------------------
# 1. Tenant isolation — hotel_id is always a bound filter
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_recall_private_always_scopes_by_hotel_id():
    db, captured = _capturing_db()
    svc = MemoryRecallService(db)

    await svc._recall_private(
        "hotel_a", _EMB, 5, 0.5, ("feedback", "reflection"), None, False
    )

    assert "hotel_id = :hotel_id" in captured["sql"], (
        "recall must always filter operational_memory by hotel_id"
    )
    assert captured["params"]["hotel_id"] == "hotel_a"
    # the tenant id must be bound, never interpolated into the SQL text
    assert "hotel_a" not in captured["sql"]


@pytest.mark.asyncio
async def test_cosine_dedup_scopes_by_hotel_id():
    db, captured = _capturing_db()
    svc = MemoryRecallService(db)

    await svc.check_cosine_dedup("hotel_b", _EMB)

    assert "hotel_id = :hotel_id" in captured["sql"]
    assert captured["params"]["hotel_id"] == "hotel_b"
    assert "hotel_b" not in captured["sql"]


@pytest.mark.asyncio
async def test_cold_start_fallback_stays_within_tenant():
    """Cold-start falls back to fb_patterns — scoped to the SAME hotel, never
    another hotel's private memory (Décision #2 privacy boundary)."""
    db = MagicMock()
    # private recall returns nothing → triggers cold-start
    empty = MagicMock()
    empty.fetchall.return_value = []
    db.execute = AsyncMock(return_value=empty)
    svc = MemoryRecallService(db)

    with patch("app.services.rag_service.RAGService") as MockRag:
        instance = MockRag.return_value
        instance.find_similar_patterns_by_embedding = AsyncMock(return_value=[])
        await svc.recall("hotel_c", _EMB)

    instance.find_similar_patterns_by_embedding.assert_awaited_once()
    assert instance.find_similar_patterns_by_embedding.await_args.kwargs["tenant_id"] == "hotel_c"


# ---------------------------------------------------------------------------
# 2. Poisoning contract — severity maps to ingestion behaviour
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value,seats,turns,hist,severity,ingested",
    [
        (100, 50, 4.5, None, "ok", True),        # plausible → ingested
        (-5, 50, 4.5, None, "reject", False),    # negative → blocked
        (400, 50, 4.5, None, "reject", False),   # over capacity ceiling → blocked
        (100, 50, 4.5, 20, "flag", True),        # legit surge > history → tagged, not blocked
    ],
)
def test_poisoning_severity_contract(value, seats, turns, hist, severity, ingested):
    verdict = evaluate(value, total_seats=seats, turns_sum=turns, historical_max=hist)
    assert verdict.severity == severity
    # Security contract: only 'reject' blocks a value from reaching retraining.
    assert (verdict.severity != "reject") is ingested
