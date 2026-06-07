"""EVAL-2 wiring (HOS-217) — AgentAbstention sentinel + groundable wiring.

Covers the additive slice: the sentinel's falsy/frozen contract, recommendation
`confidence_below_threshold`, parser `parser_low_confidence`, and the 3 WhatsApp
variant builders — asserting they NEVER leak a raw reason code (PM caveat).
"""
from __future__ import annotations

import dataclasses

import pytest

from app.services.abstention import ABSTENTION_REASONS, AgentAbstention
from app.services.receipts import ReceiptsService
from app.services.staffing_service import StaffingService


class _FakeFeedback:
    """Duck-typed stand-in for FeedbackIntent (only confidence + intent are read)."""

    def __init__(self, confidence: float, intent: str = "free_form"):
        self.confidence = confidence
        self.intent = intent


def _assert_no_raw_codes(msg: str) -> None:
    for code in ABSTENTION_REASONS:
        assert code not in msg, f"raw code {code!r} leaked into variant: {msg!r}"


# ---------------------------------------------------------------------------
# Sentinel contract (ADR §D6.a)
# ---------------------------------------------------------------------------

class TestSentinel:
    def test_is_falsy(self):
        a = AgentAbstention(reason="confidence_below_threshold", layer="recommendation")
        assert bool(a) is False
        assert not a

    def test_truthiness_branch_treats_as_no_result(self):
        a = AgentAbstention(reason="parser_low_confidence", layer="parser")
        assert ("abstained" if not a else "ok") == "abstained"

    def test_is_frozen(self):
        a = AgentAbstention(reason="data_quality_alert", layer="forecast")
        with pytest.raises(dataclasses.FrozenInstanceError):
            a.reason = "x"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Recommendation abstention (additive optional confidence)
# ---------------------------------------------------------------------------

class TestRecommendationAbstention:
    @pytest.mark.asyncio
    async def test_abstains_below_threshold(self):
        r = await StaffingService().calculate_recommendation(80, confidence=0.35)
        assert isinstance(r, AgentAbstention)
        assert r.reason == "confidence_below_threshold"
        assert r.layer == "recommendation"
        assert r.human_message  # localized, non-empty

    @pytest.mark.asyncio
    async def test_returns_dict_above_threshold(self):
        r = await StaffingService().calculate_recommendation(80, confidence=0.9)
        assert isinstance(r, dict)
        assert "servers" in r

    @pytest.mark.asyncio
    async def test_no_confidence_is_non_breaking(self):
        r = await StaffingService().calculate_recommendation(80)
        assert isinstance(r, dict)  # existing callers (no confidence) unchanged


# ---------------------------------------------------------------------------
# Parser abstention (additive helper, parse_inbound unchanged)
# ---------------------------------------------------------------------------

class TestParserAbstention:
    def test_low_confidence_abstains(self):
        a = ReceiptsService.abstention_for_feedback(_FakeFeedback(0.4))
        assert isinstance(a, AgentAbstention)
        assert a.reason == "parser_low_confidence"
        assert a.layer == "parser"

    def test_confident_returns_none(self):
        assert ReceiptsService.abstention_for_feedback(_FakeFeedback(0.9)) is None


# ---------------------------------------------------------------------------
# WhatsApp variants (ADR §D6.d) — i18n copy, never raw codes
# ---------------------------------------------------------------------------

class TestWhatsAppVariants:
    def test_full_variant(self):
        msg = ReceiptsService._full_abstention_variant("cold_start_no_cohort", "cold_start_no_cohort")
        assert "données insuffisantes" in msg
        _assert_no_raw_codes(msg)

    def test_partial_variant(self):
        msg = ReceiptsService._partial_abstention_variant("92 couverts", "confidence_below_threshold")
        assert "voici les prévisions" in msg
        assert "pas confiant" in msg
        _assert_no_raw_codes(msg)

    def test_drift_variant(self):
        msg = ReceiptsService._drift_alert_variant("Receipt normal du jour.", "drift_detected_high")
        assert "Avis qualité" in msg
        _assert_no_raw_codes(msg)

    @pytest.mark.parametrize("reason", ABSTENTION_REASONS)
    def test_variants_never_leak_any_code(self, reason):
        _assert_no_raw_codes(ReceiptsService._full_abstention_variant(reason, reason))
        _assert_no_raw_codes(ReceiptsService._partial_abstention_variant("X", reason))
        _assert_no_raw_codes(ReceiptsService._drift_alert_variant("Y", reason))
