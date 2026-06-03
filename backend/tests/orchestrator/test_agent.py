"""Tests for orchestrator/agent.py (ADR-0004 · HOS-184).

AC5 — linter rule: no app.* imports in orchestrator/
AC6 — unit tests with injected mock services
"""
from __future__ import annotations

import ast
import pathlib
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# AC5 — architecture boundary: orchestrator/ must not import from app.*
# ---------------------------------------------------------------------------

def test_no_app_imports_in_orchestrator():
    """Fail if any orchestrator/ file imports from app.* (AST-based, ADR-0004)."""
    orch_root = pathlib.Path(__file__).parents[2] / "orchestrator"
    violations: list[str] = []
    for py_file in orch_root.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        rel = str(py_file.relative_to(orch_root.parent))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and (node.module == "app" or node.module.startswith("app.")):
                    violations.append(f"{rel}:{node.lineno} from {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "app" or alias.name.startswith("app."):
                        violations.append(f"{rel}:{node.lineno} import {alias.name}")
    assert not violations, (
        f"orchestrator/ must not import from app.*  (ADR-0004): {violations}"
    )


# ---------------------------------------------------------------------------
# AC6 — unit tests for OrchestratorAgent.get_forecast
# ---------------------------------------------------------------------------

def _make_forecast_stub(covers=42, confidence=0.85, is_mock=False, lower=38, upper=46):
    return SimpleNamespace(
        predicted=covers,
        confidence=confidence,
        is_mock=is_mock,
        lower=lower,
        upper=upper,
    )


def _make_agent(profile=None, constitution_builder=None):
    from orchestrator.agent import OrchestratorAgent

    forecaster = MagicMock()
    forecaster.predict = AsyncMock(return_value=_make_forecast_stub())

    rag = MagicMock()
    rag.build_context_string = MagicMock(return_value="saturday dinner busy")
    rag.find_similar_patterns = AsyncMock(return_value=[
        {"payload": {"pattern_text": "rugby match", "outcome_description": "+15%"}}
    ])

    reasoner = MagicMock()
    reasoner.generate_explanation = AsyncMock(return_value={
        "summary": "Busy night — rugby match nearby.",
        "details": [],
    })

    staffer = MagicMock()
    staffer.calculate_recommendation = AsyncMock(return_value={"front_of_house": 4})

    memory = MagicMock()
    memory.get_relevant_context = AsyncMock(return_value="Last rugby night: +18% covers.")

    profile_loader = AsyncMock(return_value=profile)

    return OrchestratorAgent(
        forecaster=forecaster,
        rag=rag,
        reasoner=reasoner,
        staffer=staffer,
        memory=memory,
        profile_loader=profile_loader,
        constitution_builder=constitution_builder,
    )


class TestOrchestratorAgentGetForecast:
    @pytest.mark.asyncio
    async def test_happy_path_output_shape(self):
        agent = _make_agent()
        result = await agent.get_forecast(
            tenant_id="hotel_abc",
            target_date=date(2026, 6, 1),
            service_type="dinner",
            context={"weather": {}, "events": [], "occupancy": 0.9},
        )
        assert result["tenant_id"] == "hotel_abc"
        assert result["date"] == "2026-06-01"
        assert result["service_type"] == "dinner"
        assert result["prediction"]["covers"] == 42
        assert result["prediction"]["confidence"] == 0.85
        assert result["reasoning"] == "Busy night — rugby match nearby."
        assert result["staffing_recommendation"] == {"front_of_house": 4}
        assert len(result["historical_patterns"]) == 1

    @pytest.mark.asyncio
    async def test_constitution_builder_called_when_profile_present(self):
        fake_profile = object()
        builder = MagicMock(return_value="You are a luxury hotel assistant.")
        agent = _make_agent(profile=fake_profile, constitution_builder=builder)
        await agent.get_forecast(
            tenant_id="hotel_abc",
            target_date=date(2026, 6, 1),
            service_type="dinner",
            context={},
        )
        builder.assert_called_once()
        assert builder.call_args[0][0] is fake_profile

    @pytest.mark.asyncio
    async def test_constitution_failure_is_non_fatal(self):
        fake_profile = object()

        def bad_builder(profile, ctx):
            raise RuntimeError("constitution exploded")

        agent = _make_agent(profile=fake_profile, constitution_builder=bad_builder)
        # should not raise
        result = await agent.get_forecast(
            tenant_id="hotel_abc",
            target_date=date(2026, 6, 1),
            service_type="dinner",
            context={},
        )
        assert result["prediction"]["covers"] == 42

    @pytest.mark.asyncio
    async def test_no_constitution_builder_when_no_profile(self):
        builder = MagicMock()
        agent = _make_agent(profile=None, constitution_builder=builder)
        await agent.get_forecast(
            tenant_id="hotel_abc",
            target_date=date(2026, 6, 1),
            service_type="dinner",
            context={},
        )
        builder.assert_not_called()
