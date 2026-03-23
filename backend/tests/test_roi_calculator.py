"""Tests for Story 3.3b: Calculate Financial ROI for Detected Anomalies.

Covers all acceptance criteria:
  AC 2  — revenue_opportunity = captation_rate × additional_covers × avg_spend
  AC 3  — labor_cost = headcount × hourly_rate × window_hours
  AC 4  — net_roi = revenue_opportunity - labor_cost
  AC 5  — roi_positive flag sets status
  AC 6  — ROI fields written back to anomaly row
  AC 7  — configurable rates from config.py defaults
  AC 8  — idempotency: re-run updates fields without duplicates
  AC 9  — auto-chain in worker (smoke test)
  AC 10 — POST /api/v1/anomalies/roi returns 202

Test categories:
  1. Unit — recommended_headcount() scale
  2. Unit — calculate_for_anomaly() revenue / labor / net-roi
  3. Unit — lull handling (all zeros)
  4. Unit — status promotion: roi_positive vs remains detected
  5. Integration — run_for_property() with mocked DB
  6. Integration — idempotency (re-run)
  7. Integration — POST /roi route returns 202
  8. Unit — auto-chain smoke test (worker imports roi_calculator)
"""
from __future__ import annotations

import uuid
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import (
    DEFAULT_AVG_SPEND_PER_COVER,
    DEFAULT_CAPTATION_RATE,
    DEFAULT_STAFF_HOURLY_RATE,
)
from app.core.error_handlers import problem_details_handler
from app.services.roi_calculator import ROICalculatorService


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def svc() -> ROICalculatorService:
    return ROICalculatorService()


# ===========================================================================
# 1. Unit — recommended_headcount() scale
# ===========================================================================

class TestHeadownScale:
    """AC: Headcount scale table."""

    def test_headcount_scale_lull(self, svc: ROICalculatorService):
        """Lull (deviation ≤ 0) → 0 extra heads."""
        assert svc.recommended_headcount(-5.0) == 0
        assert svc.recommended_headcount(0.0) == 0

    def test_headcount_scale_low_surge(self, svc: ROICalculatorService):
        """20–35 % surge → 1 extra head."""
        assert svc.recommended_headcount(20.0) == 1
        assert svc.recommended_headcount(25.0) == 1
        assert svc.recommended_headcount(34.9) == 1

    def test_headcount_scale_medium_surge(self, svc: ROICalculatorService):
        """35–55 % surge → 2 extra heads."""
        assert svc.recommended_headcount(35.0) == 2
        assert svc.recommended_headcount(45.0) == 2
        assert svc.recommended_headcount(54.9) == 2

    def test_headcount_scale_high_surge(self, svc: ROICalculatorService):
        """55–80 % surge → 3 extra heads."""
        assert svc.recommended_headcount(55.0) == 3
        assert svc.recommended_headcount(70.0) == 3
        assert svc.recommended_headcount(79.9) == 3

    def test_headcount_scale_max_surge(self, svc: ROICalculatorService):
        """> 80 % surge → 4 extra heads (cap)."""
        assert svc.recommended_headcount(80.0) == 4
        assert svc.recommended_headcount(120.0) == 4
        assert svc.recommended_headcount(500.0) == 4


# ===========================================================================
# 2. Unit — calculate_for_anomaly() revenue opportunity
# ===========================================================================

class TestRevenueOpportunityCalculation:
    """AC 2: revenue_opportunity = captation_rate × additional_covers × avg_spend."""

    def test_revenue_opportunity_basic_surge(self, svc: ROICalculatorService):
        """Simple surge: 100 extra covers × 0.7 captation × £40 = £2800."""
        result = svc.calculate_for_anomaly(
            direction="surge",
            deviation_pct=25.0,
            expected_demand=1100.0,
            baseline_demand=1000.0,
            avg_spend_per_cover=40.0,
            staff_hourly_rate=14.0,
            captation_rate=0.7,
        )
        assert result["revenue_opp"] == pytest.approx(2800.0, abs=0.01)

    def test_revenue_opportunity_uses_default_captation_rate(
        self, svc: ROICalculatorService
    ):
        """Default captation rate (0.7) is applied when not specified."""
        result = svc.calculate_for_anomaly(
            direction="surge",
            deviation_pct=25.0,
            expected_demand=1100.0,
            baseline_demand=1000.0,
            avg_spend_per_cover=DEFAULT_AVG_SPEND_PER_COVER,
            staff_hourly_rate=DEFAULT_STAFF_HOURLY_RATE,
        )
        expected_rev = DEFAULT_CAPTATION_RATE * 100.0 * DEFAULT_AVG_SPEND_PER_COVER
        assert result["revenue_opp"] == pytest.approx(expected_rev, abs=0.01)

    def test_revenue_opportunity_zero_additional_covers(self, svc: ROICalculatorService):
        """When expected_demand == baseline_demand, revenue_opp = 0."""
        result = svc.calculate_for_anomaly(
            direction="surge",
            deviation_pct=25.0,
            expected_demand=1000.0,
            baseline_demand=1000.0,
            avg_spend_per_cover=40.0,
            staff_hourly_rate=14.0,
        )
        assert result["revenue_opp"] == 0.0


# ===========================================================================
# 3. Unit — labor cost calculation
# ===========================================================================

class TestLaborCostCalculation:
    """AC 3: labor_cost = recommended_headcount × hourly_rate × window_hours."""

    def test_labor_cost_1_head_4_hours(self, svc: ROICalculatorService):
        """25 % surge → 1 head × £14/h × 4h = £56."""
        result = svc.calculate_for_anomaly(
            direction="surge",
            deviation_pct=25.0,
            expected_demand=1250.0,
            baseline_demand=1000.0,
            avg_spend_per_cover=40.0,
            staff_hourly_rate=14.0,
        )
        assert result["labor_cost"] == pytest.approx(1 * 14.0 * 4.0, abs=0.01)

    def test_labor_cost_4_heads_high_surge(self, svc: ROICalculatorService):
        """100 % surge → 4 heads × £14/h × 4h = £224."""
        result = svc.calculate_for_anomaly(
            direction="surge",
            deviation_pct=100.0,
            expected_demand=2000.0,
            baseline_demand=1000.0,
            avg_spend_per_cover=40.0,
            staff_hourly_rate=14.0,
        )
        assert result["labor_cost"] == pytest.approx(4 * 14.0 * 4.0, abs=0.01)

    def test_labor_cost_custom_hourly_rate(self, svc: ROICalculatorService):
        """Custom hourly rate is applied correctly."""
        result = svc.calculate_for_anomaly(
            direction="surge",
            deviation_pct=40.0,   # → 2 heads
            expected_demand=1400.0,
            baseline_demand=1000.0,
            avg_spend_per_cover=40.0,
            staff_hourly_rate=20.0,
        )
        assert result["labor_cost"] == pytest.approx(2 * 20.0 * 4.0, abs=0.01)


# ===========================================================================
# 4. Unit — lull handling (all zeros)
# ===========================================================================

class TestLullHandling:
    """For lulls: revenue_opp = 0, labor_cost = 0, net_roi = 0."""

    def test_lull_all_zeros(self, svc: ROICalculatorService):
        result = svc.calculate_for_anomaly(
            direction="lull",
            deviation_pct=-30.0,
            expected_demand=700.0,
            baseline_demand=1000.0,
            avg_spend_per_cover=40.0,
            staff_hourly_rate=14.0,
        )
        assert result["revenue_opp"] == 0.0
        assert result["labor_cost"] == 0.0
        assert result["net_roi"] == 0.0


# ===========================================================================
# 5. Unit — net_roi and status promotion
# ===========================================================================

class TestNetROIStatus:
    """AC 4 & 5: net_roi calculation and status flag."""

    def test_net_roi_positive_sets_roi_positive(self, svc: ROICalculatorService):
        """When net_roi > 0 the caller (run_for_property) sets status='roi_positive'."""
        result = svc.calculate_for_anomaly(
            direction="surge",
            deviation_pct=25.0,       # 1 head → £56 labor
            expected_demand=1100.0,   # 100 extra covers → £2800 revenue
            baseline_demand=1000.0,
            avg_spend_per_cover=40.0,
            staff_hourly_rate=14.0,
        )
        assert result["net_roi"] > 0, "Expected positive net ROI"
        assert result["net_roi"] == pytest.approx(
            result["revenue_opp"] - result["labor_cost"], abs=0.01
        )

    def test_net_roi_zero_or_negative_keeps_detected(
        self, svc: ROICalculatorService
    ):
        """Very small surge with high labor cost → net_roi <= 0."""
        # Only 1 extra cover at £40, captured at 70 % → £28 revenue
        # 1 head × £14 × 4h = £56 labor → net = -28
        result = svc.calculate_for_anomaly(
            direction="surge",
            deviation_pct=25.0,
            expected_demand=1001.0,   # 1 extra cover
            baseline_demand=1000.0,
            avg_spend_per_cover=40.0,
            staff_hourly_rate=14.0,
        )
        assert result["net_roi"] < 0, "Expected negative net ROI"

    def test_net_roi_equals_revenue_minus_labor(self, svc: ROICalculatorService):
        """net_roi == revenue_opp - labor_cost (AC 4 formula)."""
        result = svc.calculate_for_anomaly(
            direction="surge",
            deviation_pct=60.0,
            expected_demand=1600.0,
            baseline_demand=1000.0,
            avg_spend_per_cover=50.0,
            staff_hourly_rate=15.0,
        )
        expected_net = result["revenue_opp"] - result["labor_cost"]
        assert result["net_roi"] == pytest.approx(expected_net, abs=0.01)


# ===========================================================================
# 6. Integration — run_for_property() with mocked DB
# ===========================================================================

class TestRunForProperty:
    """AC 6, 8: ROI fields written back to anomaly rows; idempotency."""

    @pytest.fixture
    def property_id(self) -> uuid.UUID:
        return uuid.uuid4()

    def _make_db_mock(
        self,
        property_id: uuid.UUID,
        anomaly_rows: list,
        avg_spend: float = DEFAULT_AVG_SPEND_PER_COVER,
        hourly_rate: float = DEFAULT_STAFF_HOURLY_RATE,
    ) -> AsyncMock:
        """Build a mock AsyncSession that returns the given anomaly rows."""
        db = AsyncMock()
        db.commit = AsyncMock()

        # First execute call: property rate lookup
        rate_result = MagicMock()
        rate_result.fetchone.return_value = (avg_spend, hourly_rate)

        # Second execute call: anomaly rows
        anomaly_result = MagicMock()
        anomaly_result.fetchall.return_value = anomaly_rows

        # Subsequent UPDATE calls return None
        update_result = MagicMock()
        update_result.fetchone.return_value = None

        db.execute = AsyncMock(
            side_effect=[rate_result, anomaly_result] + [update_result] * len(anomaly_rows)
        )
        return db

    @pytest.mark.asyncio
    async def test_roi_fields_written_for_surge(self, svc, property_id):
        """ROI fields (revenue_opp, labor_cost, net_roi) are written to DB."""
        # Row format: (id, direction, deviation_pct, expected_demand, baseline_demand)
        anomaly_id = str(uuid.uuid4())
        rows = [(anomaly_id, "surge", 25.0, 1100.0, 1000.0)]
        db = self._make_db_mock(property_id, rows)

        await svc.run_for_property(db, property_id)

        db.commit.assert_called_once()
        # 3 execute calls: rate lookup + anomaly fetch + 1 update
        assert db.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_status_set_roi_positive_when_net_positive(self, svc, property_id):
        """Status is set to 'roi_positive' when net_roi > 0."""
        anomaly_id = str(uuid.uuid4())
        rows = [(anomaly_id, "surge", 25.0, 1100.0, 1000.0)]
        db = self._make_db_mock(property_id, rows)

        await svc.run_for_property(db, property_id)

        # Inspect the UPDATE call params
        update_call = db.execute.call_args_list[2]
        params = update_call[0][1]  # positional args: (text_stmt, params)
        assert params["status"] == "roi_positive"

    @pytest.mark.asyncio
    async def test_status_remains_detected_when_net_nonpositive(
        self, svc, property_id
    ):
        """Status stays 'detected' when net_roi <= 0 (micro-surge)."""
        anomaly_id = str(uuid.uuid4())
        # 1 extra cover × 0.7 × £40 = £28 revenue; 1 head × £14 × 4 = £56 → net = -28
        rows = [(anomaly_id, "surge", 25.0, 1001.0, 1000.0)]
        db = self._make_db_mock(property_id, rows)

        await svc.run_for_property(db, property_id)

        update_call = db.execute.call_args_list[2]
        params = update_call[0][1]
        assert params["status"] == "detected"

    @pytest.mark.asyncio
    async def test_no_update_when_no_detected_anomalies(self, svc, property_id):
        """When no 'detected' anomalies exist, no UPDATE is executed."""
        db = self._make_db_mock(property_id, [])
        # Anomaly fetch returns empty; execute is called only twice (rate + fetch)
        updated = await svc.run_for_property(db, property_id)
        assert updated == 0
        db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_idempotency_reruns_update_fields(self, svc, property_id):
        """Re-running run_for_property on same data issues UPDATE (not INSERT)."""
        anomaly_id = str(uuid.uuid4())
        rows = [(anomaly_id, "surge", 25.0, 1100.0, 1000.0)]

        # First run
        db1 = self._make_db_mock(property_id, rows)
        count1 = await svc.run_for_property(db1, property_id)

        # Second run — same anomaly row still in 'detected' (test mock)
        db2 = self._make_db_mock(property_id, rows)
        count2 = await svc.run_for_property(db2, property_id)

        assert count1 == 1
        assert count2 == 1  # idempotent: updates 1 row again (no duplicate)

    @pytest.mark.asyncio
    async def test_lull_anomaly_net_roi_is_zero(self, svc, property_id):
        """Lull anomaly rows get roi = 0/0/0 and status stays 'detected'."""
        anomaly_id = str(uuid.uuid4())
        rows = [(anomaly_id, "lull", -30.0, 700.0, 1000.0)]
        db = self._make_db_mock(property_id, rows)

        await svc.run_for_property(db, property_id)

        update_call = db.execute.call_args_list[2]
        params = update_call[0][1]
        assert params["net_roi"] == 0.0
        assert params["status"] == "detected"

    @pytest.mark.asyncio
    async def test_uses_property_rate_overrides(self, svc, property_id):
        """Property-specific rates are used when available."""
        anomaly_id = str(uuid.uuid4())
        rows = [(anomaly_id, "surge", 25.0, 1100.0, 1000.0)]
        # Custom rates: £60 / h, £20 / staff-hour
        db = self._make_db_mock(property_id, rows, avg_spend=60.0, hourly_rate=20.0)

        await svc.run_for_property(db, property_id)

        update_call = db.execute.call_args_list[2]
        params = update_call[0][1]
        # revenue_opp = 0.7 × 100 × 60 = £4200; labor = 1 × 20 × 4 = £80
        assert params["revenue_opp"] == pytest.approx(4200.0, abs=0.01)
        assert params["labor_cost"] == pytest.approx(80.0, abs=0.01)


# ===========================================================================
# 7. Integration — POST /api/v1/anomalies/roi returns 202
# ===========================================================================

class TestROIRoute:
    """AC 10: POST /api/v1/anomalies/roi → 202 Accepted."""

    @pytest.fixture
    def app_client(self) -> TestClient:
        from fastapi import FastAPI
        from app.api.routes.anomalies import router
        from app.core.error_handlers import problem_details_handler
        from fastapi import HTTPException

        app = FastAPI()
        app.add_exception_handler(HTTPException, problem_details_handler)

        # Override auth and DB dependencies
        from app.core.security import get_current_user
        from app.db.session import get_db

        async def _fake_user():
            return {"id": str(uuid.uuid4()), "email": "test@aetherix.io"}

        async def _fake_db():
            yield AsyncMock()

        app.dependency_overrides[get_current_user] = _fake_user
        app.dependency_overrides[get_db] = _fake_db
        app.include_router(router, prefix="/api/v1")

        return TestClient(app, raise_server_exceptions=False)

    def test_roi_route_returns_202(self, app_client: TestClient):
        """POST /api/v1/anomalies/roi returns HTTP 202 with expected body."""
        with patch(
            "app.services.roi_calculator.ROICalculatorService.run_full_scan",
            new_callable=AsyncMock,
        ):
            response = app_client.post("/api/v1/anomalies/roi")

        assert response.status_code == 202
        body = response.json()
        assert body["message"] == "ROI calculation triggered"

    def test_roi_route_body_contains_triggered_by(self, app_client: TestClient):
        """Response body includes triggeredBy (camelCase) from current user."""
        with patch(
            "app.services.roi_calculator.ROICalculatorService.run_full_scan",
            new_callable=AsyncMock,
        ):
            response = app_client.post("/api/v1/anomalies/roi")

        assert response.status_code == 202
        body = response.json()
        assert "triggeredBy" in body


# ===========================================================================
# 8. Unit — auto-chain worker smoke test (AC 9)
# ===========================================================================

class TestWorkerChain:
    """AC 9: ROI calculation is chained in anomaly_scan worker."""

    def test_worker_imports_roi_calculator(self):
        """The anomaly_scan worker module imports ROICalculatorService."""
        import app.workers.anomaly_scan as worker_module
        assert hasattr(worker_module, "ROICalculatorService") or hasattr(
            worker_module, "_roi_service"
        ), "Worker must reference ROICalculatorService"

    def test_worker_has_roi_service_instance(self):
        """The worker module holds a _roi_service instance."""
        import app.workers.anomaly_scan as worker_module
        assert hasattr(
            worker_module, "_roi_service"
        ), "_roi_service not found in anomaly_scan worker"

    @pytest.mark.asyncio
    async def test_worker_job_chains_roi(self):
        """_run_anomaly_scan_job calls both anomaly scan and ROI scan."""
        from app.workers.anomaly_scan import _run_anomaly_scan_job

        with patch(
            "app.workers.anomaly_scan._service.run_full_scan",
            new_callable=AsyncMock,
        ) as mock_scan, patch(
            "app.workers.anomaly_scan._roi_service.run_full_scan",
            new_callable=AsyncMock,
        ) as mock_roi, patch(
            "app.workers.anomaly_scan.AsyncSessionLocal",
        ) as mock_session_factory:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_factory.return_value = mock_session

            await _run_anomaly_scan_job()

        mock_scan.assert_called_once()
        mock_roi.assert_called_once()
