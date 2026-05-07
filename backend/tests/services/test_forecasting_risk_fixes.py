"""Tests for HOS-133 — Forecasting risk fixes (R1–R3, R6–R8).

Coverage:
- R1: PredictionResult.is_mock field, to_dict() includes is_mock, _build_prompt warning
- R2: _get_baseline_demand typed error handling (ProgrammingError vs OperationalError)
- R3: detect_for_property() returns DemandAnomaly ORM instances (DoD requirement)
- R6: labor_budget_gbp_per_day field name unambiguous; alert message says "daily"
- R7: calculate_recommendation is a coroutine function (async contract)
- R8: _format_and_upsert wraps INSERT+UPDATE in begin_nested (atomic transaction)
"""
from __future__ import annotations

import inspect
import json
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import sqlalchemy.exc

# Stub heavy optional dependencies ONLY if genuinely missing.
# HOS-162: the unguarded `if _mod not in sys.modules` form pollutes sys.modules
# globally for the rest of the pytest session — installed pandas/prophet then
# get replaced by MagicMocks because this file imports before any test that
# actually imports pandas, breaking captation_service / data_transformer / etc.
for _mod in ("pandas", "prophet", "qdrant_client", "redis", "twilio"):
    if _mod not in sys.modules:
        try:
            __import__(_mod)
        except ImportError:
            sys.modules[_mod] = MagicMock()

from app.core.exceptions import AnomalyDetectionError  # noqa: E402
from app.db.models import DemandAnomaly  # noqa: E402
from app.services.anomaly_detection import AnomalyDetectionService  # noqa: E402
from app.services.prediction_engine import (  # noqa: E402
    PredictionEngine,
    PredictionResult,
)
from app.services.reasoning_service import ReasoningService  # noqa: E402
from app.services.staffing_service import StaffingConfig, StaffingService  # noqa: E402

# ===========================================================================
# R1 — PredictionResult.is_mock + _build_prompt warning
# ===========================================================================

class TestPredictionResultIsMock:
    def test_is_mock_defaults_to_false(self):
        result = PredictionResult(predicted=80, lower=70, upper=90, confidence=0.85, date="2026-07-14")
        assert result.is_mock is False

    def test_is_mock_can_be_set_true(self):
        result = PredictionResult(
            predicted=45, lower=38, upper=52, confidence=0.85, date="2026-07-14", is_mock=True
        )
        assert result.is_mock is True

    def test_to_dict_includes_is_mock_false(self):
        result = PredictionResult(predicted=80, lower=70, upper=90, confidence=0.85, date="2026-07-14")
        d = result.to_dict()
        assert "is_mock" in d
        assert d["is_mock"] is False

    def test_to_dict_includes_is_mock_true(self):
        result = PredictionResult(
            predicted=45, lower=38, upper=52, confidence=0.85, date="2026-07-14", is_mock=True
        )
        d = result.to_dict()
        assert d["is_mock"] is True


class TestPredictUntrainedReturnsMock:
    @pytest.mark.asyncio
    async def test_untrained_engine_returns_is_mock_true(self):
        engine = PredictionEngine()
        result = await engine.predict(date(2026, 7, 14))
        assert result.is_mock is True

    @pytest.mark.asyncio
    async def test_untrained_engine_returns_sentinel_covers(self):
        engine = PredictionEngine()
        result = await engine.predict(date(2026, 7, 14))
        assert result.predicted == 45


class TestBuildPromptMockWarning:
    def test_mock_warning_present_when_is_mock_true(self):
        service = ReasoningService(llm=MagicMock())
        prompt = service._build_prompt(
            45, 0.85, date(2026, 7, 14), "dinner", {}, [], None, is_mock=True
        )
        assert "WARNING" in prompt

    def test_no_mock_warning_when_is_mock_false(self):
        service = ReasoningService(llm=MagicMock())
        prompt = service._build_prompt(
            80, 0.85, date(2026, 7, 14), "dinner", {}, [], None, is_mock=False
        )
        assert "WARNING" not in prompt


# ===========================================================================
# R2 — _get_baseline_demand typed error handling
# ===========================================================================

class TestGetBaselineDemandErrorHandling:
    @pytest.mark.asyncio
    async def test_programming_error_returns_fallback_silently(self):
        """ProgrammingError (table missing in dev/test) → silent fallback to 1000.00."""
        service = AnomalyDetectionService()
        db = MagicMock()
        db.execute = AsyncMock(
            side_effect=sqlalchemy.exc.ProgrammingError("SELECT 1", {}, None)
        )
        result = await service._get_baseline_demand(
            db, uuid.uuid4(), uuid.uuid4(),
            datetime(2026, 7, 14, 20, 0, tzinfo=timezone.utc),
        )
        assert result == Decimal("1000.00")

    @pytest.mark.asyncio
    async def test_operational_error_raises_anomaly_detection_error(self):
        """Connection errors → AnomalyDetectionError (not silent 1000.00)."""
        service = AnomalyDetectionService()
        db = MagicMock()
        db.execute = AsyncMock(
            side_effect=sqlalchemy.exc.OperationalError("connection refused", {}, None)
        )
        with pytest.raises(AnomalyDetectionError):
            await service._get_baseline_demand(
                db, uuid.uuid4(), uuid.uuid4(),
                datetime(2026, 7, 14, 20, 0, tzinfo=timezone.utc),
            )

    @pytest.mark.asyncio
    async def test_missing_row_returns_fallback(self):
        """No captation_rate row found → fallback to 1000.00 (not an error)."""
        service = AnomalyDetectionService()
        db = MagicMock()
        db.execute = AsyncMock(
            return_value=MagicMock(fetchone=MagicMock(return_value=None))
        )
        result = await service._get_baseline_demand(
            db, uuid.uuid4(), uuid.uuid4(),
            datetime(2026, 7, 14, 20, 0, tzinfo=timezone.utc),
        )
        assert result == Decimal("1000.00")


# ===========================================================================
# R3 — detect_for_property() returns DemandAnomaly ORM instances (DoD)
# ===========================================================================

class TestDetectForPropertyReturnType:
    @pytest.mark.asyncio
    async def test_returns_demand_anomaly_instances(self):
        """DoD: isinstance(result[0], DemandAnomaly) must be True."""
        service = AnomalyDetectionService()
        prop_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        db = MagicMock()

        window_start = datetime(2026, 7, 14, 20, 0, tzinfo=timezone.utc)
        window_end = window_start + timedelta(hours=4)
        returned_id = str(uuid.uuid4())

        with patch.object(service, "generate_windows", return_value=[(window_start, window_end)]):
            with patch.object(
                service, "_get_baseline_demand", new_callable=AsyncMock, return_value=Decimal("1000.00")
            ):
                with patch.object(
                    service, "_get_weather_for_window", new_callable=AsyncMock, return_value=None
                ):
                    with patch.object(
                        service, "_get_events_for_window",
                        new_callable=AsyncMock, return_value=[MagicMock()],
                    ):
                        with patch(
                            "app.services.anomaly_detection.event_modifier",
                            return_value=(0.5, ["Tech conference"]),
                        ):
                            with patch.object(
                                service, "_bulk_upsert",
                                new_callable=AsyncMock, return_value=[returned_id],
                            ):
                                result = await service.detect_for_property(db, prop_id, tenant_id)

        assert len(result) == 1
        assert isinstance(result[0], DemandAnomaly)

    @pytest.mark.asyncio
    async def test_no_anomalies_returns_empty_list(self):
        """When no windows are generated, returns []."""
        service = AnomalyDetectionService()
        db = MagicMock()
        with patch.object(service, "generate_windows", return_value=[]):
            result = await service.detect_for_property(db, uuid.uuid4(), uuid.uuid4())
        assert result == []


# ===========================================================================
# R6 — StaffingConfig field naming and alert message unit
# ===========================================================================

class TestStaffingConfigFieldNaming:
    def test_field_is_named_per_day(self):
        """R6: no ambiguity — field must include time unit in name."""
        cfg = StaffingConfig()
        assert hasattr(cfg, "labor_budget_gbp_per_day")

    def test_no_ambiguous_bare_field(self):
        cfg = StaffingConfig()
        assert not hasattr(cfg, "labor_budget_gbp")

    @pytest.mark.asyncio
    async def test_budget_warning_mentions_daily(self):
        """R6: alert message explicitly states 'daily' time unit."""
        service = StaffingService()
        # Set tiny budget and high shift cost so budget is exceeded
        cfg = StaffingConfig(labor_budget_gbp_per_day=100.0, avg_shift_cost=200.0)
        with patch.object(service, "_dispatch_budget_alert", new_callable=AsyncMock):
            result = await service.calculate_recommendation(10, cfg)
        assert result["warnings"], "Expected a budget warning"
        assert "daily" in result["warnings"][0].lower()


# ===========================================================================
# R7 — calculate_recommendation async contract
# ===========================================================================

class TestStaffingServiceAsyncContract:
    def test_calculate_recommendation_is_coroutine(self):
        """R7: must be awaitable — no RuntimeError from sync callers possible."""
        assert inspect.iscoroutinefunction(StaffingService.calculate_recommendation)

    @pytest.mark.asyncio
    async def test_runs_without_error_in_async_context(self):
        service = StaffingService()
        with patch.object(service, "_dispatch_budget_alert", new_callable=AsyncMock):
            result = await service.calculate_recommendation(50)
        assert "servers" in result
        assert "warnings" in result


# ===========================================================================
# R8 — _format_and_upsert wraps INSERT+UPDATE in atomic transaction
# ===========================================================================

class TestRecommendationFormatterAtomicity:
    @pytest.mark.asyncio
    async def test_format_and_upsert_uses_begin_nested(self):
        """R8: both DB statements must be wrapped in begin_nested for atomicity."""
        from app.services.recommendation_formatter import RecommendationFormatterService

        service = RecommendationFormatterService()

        nested_ctx = MagicMock()
        nested_ctx.__aenter__ = AsyncMock(return_value=None)
        nested_ctx.__aexit__ = AsyncMock(return_value=False)

        db = MagicMock()
        db.begin_nested = MagicMock(return_value=nested_ctx)
        db.execute = AsyncMock()

        row = (
            str(uuid.uuid4()),   # anomaly_id
            str(uuid.uuid4()),   # tenant_id
            str(uuid.uuid4()),   # property_id
            "surge",             # direction
            json.dumps([{"label": "Tech conference", "weight": 0.9}]),  # triggering_factors
            100.0,               # roi_revenue_opp
            50.0,                # roi_labor_cost
            50.0,                # roi_net
            datetime(2026, 7, 14, 20, 0, tzinfo=timezone.utc),   # window_start
            datetime(2026, 7, 14, 23, 59, tzinfo=timezone.utc),  # window_end
            25.0,                # deviation_pct
        )

        result = await service._format_and_upsert(db, row)

        assert result is True
        db.begin_nested.assert_called_once()
