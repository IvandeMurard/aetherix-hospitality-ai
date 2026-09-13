"""Aetherix Orchestrator — Phase 3 proto-orchestrator (ADR-0004 · HOS-184).

Architecture rules enforced by CI (tests/orchestrator/test_agent.py):
  - Zero imports from ``app.*`` — all services are constructor-injected.
  - ``app/services/aetherix_engine.py`` delegates here; reverse is forbidden.
  - Phase 4: this module moves to its own repo and calls services exclusively
    via MCP tool calls (no Python imports at all).
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Awaitable, Callable, Optional, Sequence

from orchestrator import rules

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """Proto-orchestrator: coordinates F&B execution-node services.

    All dependencies are injected so this module stays free of ``app.*``
    imports (ADR-0004 isolation boundary). The agentic routing / retry /
    feedback-loop logic will be built here in Phase 3; for now the happy
    path is a straight pipeline identical to the old AetherixEngine.
    """

    def __init__(
        self,
        forecaster: Any,
        rag: Any,
        reasoner: Any,
        staffer: Any,
        memory: Any,
        profile_loader: Callable[[str], Awaitable[Any]],
        constitution_builder: Optional[Callable[[Any, dict[str, Any]], Optional[str]]] = None,
        memory_recall: Optional[Callable[[str, str, int], Awaitable[Sequence[Any]]]] = None,
    ) -> None:
        self._forecaster = forecaster
        self._rag = rag
        self._reasoner = reasoner
        self._staffer = staffer
        self._memory = memory
        self._profile_loader = profile_loader
        self._constitution_builder = constitution_builder
        # Optional structured recall: (tenant_id, query, k) -> hits exposing
        # ``.similarity`` and ``.reflection``. When absent the agent falls back to
        # the flat string recall and reports ``signal_unavailable`` — the loop
        # degrades, it does not fail.
        self._memory_recall = memory_recall

    async def get_forecast(
        self,
        tenant_id: str,
        target_date: date,
        service_type: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Hybrid F&B orchestration: Prophet + RAG + Memory + Reasoning.

        Returns a dict with keys: tenant_id, date, service_type, prediction,
        reasoning, reasoning_detail, staffing_recommendation, historical_patterns.
        """
        # 1. Prediction (Prophet)
        forecast = await self._forecaster.predict(
            target_date, features=context.get("regressors")
        )
        predicted_covers = forecast.predicted
        confidence = forecast.confidence
        is_mock = forecast.is_mock

        # 2. RAG (Historical Patterns)
        context_query = self._rag.build_context_string(target_date, service_type, context)
        patterns = await self._rag.find_similar_patterns(context_query, service_type)

        # 3. Memory retrieval — agentic loop (ADR-0004 D7 / HOS-189)
        memory_context, recall_trace = await self._recall_with_retry(
            tenant_id, context_query
        )

        # 4. Agent Constitution — build system prompt if profile available
        system_prompt: Optional[str] = None
        try:
            profile = await self._profile_loader(tenant_id)
            if profile is not None:
                # HOS-215: surface hotel coordinates in the context so the
                # reasoning layer can compute event distance-to-hotel. Plain dict
                # assignment — no app.* import (Décision #19).
                context.setdefault("hotel_latitude", getattr(profile, "latitude", None))
                context.setdefault("hotel_longitude", getattr(profile, "longitude", None))
            if profile is not None and self._constitution_builder is not None:
                similar_text = (
                    "\n".join(
                        f"- {p['payload'].get('pattern_text', '')} "
                        f"({p['payload'].get('outcome_description', '')})"
                        for p in patterns[:3]
                    )
                    if patterns
                    else ""
                )
                system_prompt = self._constitution_builder(
                    profile,
                    {
                        "date": target_date.isoformat(),
                        "covers": predicted_covers,
                        "confidence": int(confidence * 100),
                        "similar_nights": similar_text,
                    },
                )
        except Exception as exc:
            logger.warning("constitution/profile failed (non-fatal): %s", exc)

        # 5. Reasoning (Claude)
        reasoning = await self._reasoner.generate_explanation(
            predicted_covers,
            confidence,
            target_date,
            service_type,
            context,
            patterns,
            memory_context,
            is_mock=is_mock,
            system_prompt=system_prompt,
        )

        # 6. Staffing
        staffing = await self._staffer.calculate_recommendation(predicted_covers)

        return {
            "tenant_id": tenant_id,
            "date": target_date.isoformat(),
            "service_type": service_type,
            "prediction": {
                "covers": predicted_covers,
                "confidence": confidence,
                "is_mock": is_mock,
                "range_min": forecast.lower,
                "range_max": forecast.upper,
            },
            "reasoning": reasoning["summary"],
            "reasoning_detail": reasoning,
            "staffing_recommendation": staffing,
            "historical_patterns": patterns,
            # What the loop actually did this run. Read by the e2e test, and the
            # hook HOS-331 attaches the run object to.
            "memory_recall": recall_trace,
        }

    # ------------------------------------------------------------------
    # Agentic loop (ADR-0004 D7 · HOS-189)
    # ------------------------------------------------------------------

    async def _recall_with_retry(
        self, tenant_id: str, context_query: str
    ) -> tuple[str, dict[str, Any]]:
        """Call the memory node, and call it again with a wider k if the hit is thin.

        This is the orchestrator's one non-deterministic behaviour, and the thing
        that makes it an orchestrator rather than a pipe: the same request issues
        one recall or two depending on what the first one returned.

        The decision is not taken here. :func:`orchestrator.rules.select_recall_k`
        is a pure function over the returned similarity; this method only performs
        the I/O and records what happened. That split is what lets the retry be
        unit-tested without a database.

        Returns ``(memory_context_text, trace)``. The trace is always populated,
        including on the failure paths, so "why did this run recall twice" is
        answerable from the result alone.
        """
        if self._memory_recall is None:
            # No structured recall wired in: fall back to the flat string path.
            # Degrade, do not fail — an un-wired signal is a deployment fact, not
            # a request error.
            text = await self._memory.get_relevant_context(tenant_id, context_query)
            return text, self._recall_trace(
                attempts=0, k=None, similarity=None,
                outcome=rules.RecallOutcome.SIGNAL_UNAVAILABLE,
            )

        attempt = 0
        k = rules.RECALL_K_DEFAULT
        hits: Sequence[Any] = ()
        similarity: Optional[float] = None
        outcome = rules.RecallOutcome.EMPTY

        while attempt < rules.MAX_RECALL_ATTEMPTS:
            attempt += 1
            try:
                hits = await self._memory_recall(tenant_id, context_query, k)
            except Exception as exc:
                # The forecast and RAG steps have already run. A memory-node
                # failure costs grounding, not the whole recommendation.
                logger.warning(
                    "memory recall failed at k=%s (non-fatal): %s", k, exc
                )
                return "", self._recall_trace(
                    attempts=attempt, k=k, similarity=None,
                    outcome=rules.RecallOutcome.SIGNAL_UNAVAILABLE,
                )

            similarity = rules.top_similarity(hits)
            decision = rules.select_recall_k(attempt, similarity)
            outcome = decision.outcome
            if not decision.should_retry:
                break

            logger.info(
                "recall top_similarity=%.4f below floor %.2f — widening k %s -> %s",
                similarity, rules.RECALL_SIMILARITY_FLOOR, k, decision.next_k,
            )
            k = decision.next_k

        return self._render_hits(hits), self._recall_trace(
            attempts=attempt, k=k, similarity=similarity, outcome=outcome,
        )

    @staticmethod
    def _recall_trace(
        *,
        attempts: int,
        k: Optional[int],
        similarity: Optional[float],
        outcome: "rules.RecallOutcome",
    ) -> dict[str, Any]:
        """Typed-reason trace of one recall loop. No free-string outcomes."""
        return {
            "attempts": attempts,
            "k": k,
            "top_similarity": round(similarity, 4) if similarity is not None else None,
            "outcome": outcome.value,
        }

    @staticmethod
    def _render_hits(hits: Sequence[Any]) -> str:
        """Flatten recall hits into the text shape the reasoning step expects."""
        lines = [
            str(text)
            for text in (getattr(h, "reflection", None) for h in hits)
            if text
        ]
        return "\n".join(lines)
