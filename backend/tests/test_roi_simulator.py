"""Unit tests for the public ROI simulator — P0-3.

Pure-logic tests: no DB, no HTTP client required. The endpoint is stateless.
"""
from __future__ import annotations

import pytest


def _try_import():
    try:
        import app.api.routes.roi as m
        return m
    except (ImportError, ModuleNotFoundError, TypeError):
        return None


_mod = _try_import()
_skip = pytest.mark.skipif(_mod is None, reason="roi route deps unavailable")


class TestROISimulator:
    @_skip
    @pytest.mark.asyncio
    async def test_savings_monotonic_in_fb_revenue(self):
        from app.api.routes.roi import ROISimulateRequest, simulate_roi

        small = await simulate_roi(ROISimulateRequest(
            rooms_count=80, avg_cover_revenue_eur=45,
            labor_cost_per_hour_eur=20, annual_fb_revenue_eur=500_000,
        ))
        large = await simulate_roi(ROISimulateRequest(
            rooms_count=80, avg_cover_revenue_eur=45,
            labor_cost_per_hour_eur=20, annual_fb_revenue_eur=5_000_000,
        ))
        assert large.total_annual_savings_eur > small.total_annual_savings_eur

    @_skip
    @pytest.mark.asyncio
    async def test_low_bound_below_high_bound(self):
        from app.api.routes.roi import ROISimulateRequest, simulate_roi

        r = await simulate_roi(ROISimulateRequest(
            rooms_count=120, avg_cover_revenue_eur=55,
            labor_cost_per_hour_eur=22, annual_fb_revenue_eur=1_200_000,
        ))
        assert r.total_annual_savings_low_eur <= r.total_annual_savings_eur
        assert r.total_annual_savings_eur <= r.total_annual_savings_high_eur

    @_skip
    @pytest.mark.asyncio
    async def test_disclaimers_are_present(self):
        from app.api.routes.roi import ROISimulateRequest, simulate_roi

        r = await simulate_roi(ROISimulateRequest(
            rooms_count=80, avg_cover_revenue_eur=45,
            labor_cost_per_hour_eur=20, annual_fb_revenue_eur=900_000,
        ))
        assert len(r.disclaimers) >= 3
        joined = " ".join(r.disclaimers).lower()
        assert "synthetic" in joined or "simulated" in joined

    @_skip
    @pytest.mark.asyncio
    async def test_resort_factor_higher_than_city_on_labor(self):
        from app.api.routes.roi import PropertyType, ROISimulateRequest, simulate_roi

        common = dict(
            rooms_count=150, avg_cover_revenue_eur=50,
            labor_cost_per_hour_eur=22, annual_fb_revenue_eur=2_000_000,
        )
        city = await simulate_roi(ROISimulateRequest(
            **common, property_type=PropertyType.city,
        ))
        resort = await simulate_roi(ROISimulateRequest(
            **common, property_type=PropertyType.resort,
        ))
        assert resort.labor_cost_reduction.annual_eur > city.labor_cost_reduction.annual_eur

    @_skip
    @pytest.mark.asyncio
    async def test_source_metrics_reference_backtest(self):
        from app.api.routes.roi import ROISimulateRequest, simulate_roi

        r = await simulate_roi(ROISimulateRequest(
            rooms_count=80, avg_cover_revenue_eur=45,
            labor_cost_per_hour_eur=20, annual_fb_revenue_eur=1_000_000,
        ))
        assert "mape_j1_backtest" in r.source_metrics
        assert r.source_metrics["backtest_report"].endswith(".json")

    @_skip
    def test_request_rejects_out_of_range(self):
        from pydantic import ValidationError

        from app.api.routes.roi import ROISimulateRequest

        with pytest.raises(ValidationError):
            ROISimulateRequest(
                rooms_count=0,  # below minimum
                avg_cover_revenue_eur=45,
                labor_cost_per_hour_eur=20,
                annual_fb_revenue_eur=1_000_000,
            )
