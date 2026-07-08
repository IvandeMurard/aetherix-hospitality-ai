"""HOS-311 — the observability helpers must be strict no-ops when unconfigured.

CI, unit tests and local dev import instrumented services (prediction_engine,
whatsapp_service, guardrails) without calling configure_observability(); every
helper must be inert and side-effect free in that state.
"""
from __future__ import annotations

from unittest.mock import patch

from app.core import observability as obs


class TestUnconfiguredNoOps:
    # `_enabled` is process-global and other tests may boot the app (lifespan
    # calls configure_observability), so each test pins the state explicitly
    # instead of assuming suite ordering.

    def test_span_is_usable_context_manager(self):
        with patch.object(obs, "_enabled", False):
            with obs.span("prophet.train", rows=365) as s:
                assert s is None  # nullcontext yields None

    def test_guardrail_trip_is_silent(self):
        # Must not raise, must not require logfire configuration.
        with patch.object(obs, "_enabled", False):
            obs.guardrail_trip("forecast_guardrail", "hotel-1", "low_confidence", "detail")

    def test_span_active_when_enabled(self):
        if obs.logfire is None:
            return  # logfire not installed — nothing to assert
        with patch.object(obs, "_enabled", True):
            cm = obs.span("prophet.predict", target_date="2026-07-08")
        from contextlib import nullcontext
        assert not isinstance(cm, nullcontext)


class TestLogfireMissing:
    def test_all_helpers_survive_without_logfire(self):
        with patch.object(obs, "logfire", None):
            assert obs.configure_observability(app=None) is False
            with obs.span("x"):
                pass
            obs.guardrail_trip("g", "h", "r")
