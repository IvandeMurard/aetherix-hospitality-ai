"""Unit tests for the Prophet training orchestrator — P0-1 / Decision #13.

Split into two tiers:
  Tier 1 (no app imports): DataTransformer + pure logic — always run.
  Tier 2 (requires full app stack): skipped when optional deps unavailable.
  Integration test (full endpoint): CI only — requires full env.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Tier 1 — Pure unit tests (no app import chain)
# ---------------------------------------------------------------------------

class TestDataTransformer:
    """DataTransformer is a standalone class with no external deps."""

    def _get_transformer(self):
        from app.services.data_transformer import DataTransformer
        return DataTransformer

    def test_empty_records_returns_empty_df(self):
        DataTransformer = self._get_transformer()
        df = DataTransformer.stay_records_to_prophet([])
        assert df.empty
        assert list(df.columns) == ["ds", "y"]

    def test_aggregates_by_date(self):
        DataTransformer = self._get_transformer()
        records = [
            {"arrival": "2025-06-15T14:00:00Z", "adults": 2, "children": 0},
            {"arrival": "2025-06-15T18:00:00Z", "adults": 1, "children": 1},
            {"arrival": "2025-06-16T10:00:00Z", "adults": 3, "children": 0},
        ]
        df = DataTransformer.stay_records_to_prophet(records)
        assert len(df) == 2
        june_15 = df[df["ds"].dt.date == date(2025, 6, 15)]["y"].iloc[0]
        assert june_15 == 4  # 2+0 + 1+1

    def test_records_without_arrival_skipped(self):
        DataTransformer = self._get_transformer()
        records = [
            {"arrival": "", "adults": 2, "children": 0},
            {"arrival": "2025-07-01T00:00:00Z", "adults": 3, "children": 0},
        ]
        df = DataTransformer.stay_records_to_prophet(records)
        assert len(df) == 1

    def test_single_record_single_row(self):
        DataTransformer = self._get_transformer()
        records = [{"arrival": "2025-08-01T12:00:00Z", "adults": 4, "children": 2}]
        df = DataTransformer.stay_records_to_prophet(records)
        assert len(df) == 1
        assert df.iloc[0]["y"] == 6

    def test_missing_adults_defaults_to_zero(self):
        DataTransformer = self._get_transformer()
        records = [{"arrival": "2025-09-01T00:00:00Z"}]
        df = DataTransformer.stay_records_to_prophet(records)
        assert len(df) == 1
        assert df.iloc[0]["y"] == 0


# ---------------------------------------------------------------------------
# Tier 2 — Tests requiring the predictions module (skip if import fails)
# ---------------------------------------------------------------------------

def _try_import_predictions():
    """Returns the predictions module or None if deps are missing."""
    try:
        import app.api.routes.predictions as m
        return m
    except (ImportError, ModuleNotFoundError, TypeError):
        return None


_pred_mod = _try_import_predictions()
_skip_if_no_pred = pytest.mark.skipif(
    _pred_mod is None,
    reason="predictions module deps not available in this env (requires full stack — run in CI)"
)


class TestLoadDemoDataframe:
    @_skip_if_no_pred
    def test_loads_synthetic_data(self, tmp_path: Path):
        rows = [{"ds": f"2025-01-{i:02d}", "y": 40 + i} for i in range(1, 100)]
        demo_file = tmp_path / "prophet_training.json"
        demo_file.write_text(json.dumps(rows))

        original = _pred_mod._DEMO_DATA
        _pred_mod._DEMO_DATA = demo_file
        try:
            df = _pred_mod._load_demo_dataframe()
            assert len(df) == 99
            assert "_source" in df.columns
            assert (df["_source"] == "synthetic").all()
        finally:
            _pred_mod._DEMO_DATA = original

    @_skip_if_no_pred
    def test_missing_demo_file_raises(self, tmp_path: Path):
        original = _pred_mod._DEMO_DATA
        _pred_mod._DEMO_DATA = tmp_path / "nonexistent.json"
        try:
            with pytest.raises(FileNotFoundError):
                _pred_mod._load_demo_dataframe()
        finally:
            _pred_mod._DEMO_DATA = original


class TestDataSourceEnum:
    @_skip_if_no_pred
    def test_enum_values(self):
        from app.api.routes.predictions import DataSource
        assert DataSource.synthetic.value == "synthetic"
        assert DataSource.mcp_sandbox.value == "mcp_sandbox"
        assert DataSource.hybrid.value == "hybrid"


class TestComputeInSampleMape:
    @_skip_if_no_pred
    def test_returns_none_when_not_trained(self):
        from app.api.routes.predictions import _compute_in_sample_mape
        forecaster = MagicMock()
        forecaster.is_trained = False
        forecaster.model = None
        assert _compute_in_sample_mape(forecaster, pd.DataFrame()) is None

    @_skip_if_no_pred
    def test_returns_float_on_valid_forecaster(self):
        from app.api.routes.predictions import _compute_in_sample_mape
        df = pd.DataFrame({
            "ds": pd.date_range("2025-01-01", periods=10),
            "y": [40, 45, 42, 38, 50, 55, 48, 44, 46, 43],
        })
        mock_forecast = df[["ds"]].copy()
        mock_forecast["yhat"] = df["y"] * 1.05
        mock_model = MagicMock()
        mock_model.predict = MagicMock(return_value=mock_forecast)
        forecaster = MagicMock()
        forecaster.is_trained = True
        forecaster.model = mock_model
        mape = _compute_in_sample_mape(forecaster, df)
        assert mape is not None
        assert 0 <= mape <= 1

    @_skip_if_no_pred
    def test_returns_none_on_exception(self):
        from app.api.routes.predictions import _compute_in_sample_mape
        forecaster = MagicMock()
        forecaster.is_trained = True
        forecaster.model = MagicMock()
        forecaster.model.predict.side_effect = RuntimeError("boom")
        df = pd.DataFrame({"ds": pd.date_range("2025-01-01", 3), "y": [10, 20, 30]})
        assert _compute_in_sample_mape(forecaster, df) is None


class TestHybridMerge:
    @pytest.mark.asyncio
    @_skip_if_no_pred
    async def test_hybrid_uses_mcp_over_synthetic_on_overlap(self, tmp_path: Path):
        from unittest.mock import patch
        from app.api.routes.predictions import DataSource, TrainRequest, _build_training_dataframe

        synthetic_rows = [{"ds": f"2025-01-{i:02d}", "y": 10} for i in range(1, 50)]
        demo_file = tmp_path / "synth.json"
        demo_file.write_text(json.dumps(synthetic_rows))

        original = _pred_mod._DEMO_DATA
        _pred_mod._DEMO_DATA = demo_file

        mcp_df = pd.DataFrame({
            "ds": pd.date_range("2025-01-01", periods=10),
            "y": [99] * 10,
            "_source": ["mcp_sandbox"] * 10,
        })
        try:
            with patch("app.api.routes.predictions._load_mcp_dataframe",
                       new=AsyncMock(return_value=mcp_df)):
                body = TrainRequest(property_id="DEMO", data_source=DataSource.hybrid)
                df = await _build_training_dataframe(body)
                jan_1 = df[df["ds"].dt.date == date(2025, 1, 1)]
                assert not jan_1.empty
                assert jan_1["y"].iloc[0] == 99
        finally:
            _pred_mod._DEMO_DATA = original
