import asyncio
import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
from prophet import Prophet

from app.core.demo_events import demo_emit
from app.core.observability import span as obs_span

logger = logging.getLogger(__name__)

class PredictionResult:
    """Structured prediction result."""
    def __init__(
        self,
        predicted: int,
        lower: int,
        upper: int,
        confidence: float,
        date: str,
        is_mock: bool = False,
        calibrated: Optional[dict] = None,
    ):
        self.predicted = predicted
        # Prophet's own interval at INTERVAL_NOMINAL_LEVEL — *uncalibrated*:
        # its coverage was measured below nominal (ADR-0007 §18.2).
        self.lower = lower
        self.upper = upper
        self.nominal_level = INTERVAL_NOMINAL_LEVEL
        self.confidence = confidence
        self.date = date
        self.is_mock = is_mock
        # Recalibrated interval + provenance, or None when no calibration
        # applies to this model (see PredictionEngine._calibrated_block).
        self.calibrated = calibrated

    def to_dict(self) -> dict:
        return {
            "predicted_covers": self.predicted,
            "range_min": self.lower,
            "range_max": self.upper,
            "interval_nominal_level": self.nominal_level,
            "calibrated_interval": self.calibrated,
            "confidence": self.confidence,
            "date": self.date,
            "is_mock": self.is_mock,
        }


# Nominal level of Prophet's interval (interval_width). The name says what it
# is: a nominal level, not a measured coverage.
INTERVAL_NOMINAL_LEVEL = 0.80
# Calibrations are keyed on this forecaster identity (configuration below).
FORECASTER_ID = "prophet-predictionengine-v1"

class PredictionEngine:
    """
    Prophet engine for covers forecasting.
    Source of truth for numerical predictions in Phase 2.
    """
    
    def __init__(self):
        self.model: Optional[Prophet] = None
        self.is_trained = False
        self.regressors = []
        # What the model was trained on (synthetic | mcp_sandbox | hybrid |
        # unknown). A calibration applies only to a model trained on the same
        # kind of data it was measured on (ADR-0007 §18.2).
        self.data_source = "unknown"
    
    async def train(
        self,
        df: pd.DataFrame,
        include_weather: bool = True,
        include_events: bool = True,
        include_occupancy: bool = True,
        data_source: str = "unknown",
    ) -> None:
        """Trains the Prophet model with specified regressors."""
        if 'ds' not in df.columns or 'y' not in df.columns:
            raise ValueError("DataFrame must have 'ds' and 'y' columns")

        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=INTERVAL_NOMINAL_LEVEL,
            changepoint_prior_scale=0.05,
        )

        try:
            model.add_country_holidays(country_name='FR')
        except Exception as e:
            logger.warning("Could not add French holidays: %s", e)

        regressors: list[str] = []
        for reg in ['weather_score', 'event_impact', 'occupancy']:
            if reg in df.columns:
                model.add_regressor(reg)
                regressors.append(reg)

        # Prophet.fit() is CPU-bound — run in a thread to avoid blocking the event loop.
        with obs_span("prophet.train", rows=len(df), regressors=regressors):
            await asyncio.to_thread(model.fit, df)

        self.model = model
        self.regressors = regressors
        self.is_trained = True
        self.data_source = data_source
        logger.info("Prophet model trained successfully")
    
    async def predict(
        self,
        target_date: date,
        features: Optional[dict] = None,
    ) -> PredictionResult:
        """Predicts covers for a specific date."""
        if not self.is_trained:
            logger.warning("Prophet model not trained. Returning mock prediction for pilot.")
            return PredictionResult(
                predicted=45,
                lower=38,
                upper=52,
                confidence=0.85,
                date=target_date.isoformat(),
                is_mock=True,
            )

        future = pd.DataFrame({'ds': [pd.to_datetime(target_date)]})
        for reg in self.regressors:
            future[reg] = features.get(reg, 0.0) if features else 0.0

        # Prophet.predict() is CPU-bound — run in a thread to avoid blocking the event loop.
        with obs_span("prophet.predict", target_date=target_date.isoformat()):
            forecast = await asyncio.to_thread(self.model.predict, future)
        row = forecast.iloc[0]

        predicted = max(0, int(round(row['yhat'])))
        lower = max(0, int(round(row['yhat_lower'])))
        upper = max(0, int(round(row['yhat_upper'])))
        confidence = self._compute_confidence(lower, upper, predicted)

        result = PredictionResult(
            predicted=predicted,
            lower=lower,
            upper=upper,
            confidence=confidence,
            date=target_date.isoformat(),
            calibrated=self._calibrated_block(float(row['yhat'])),
        )
        asyncio.get_running_loop().create_task(demo_emit("prophet"))
        return result

    def calibration(self):
        """The active calibration for this forecaster *and* this model's
        training data, or None. A synthetic-series calibration never applies
        to a model trained on real data, and vice versa."""
        from app.services.forecast_calibration import load_active

        cal = load_active(FORECASTER_ID)
        if cal is None or cal.training_data_source != self.data_source:
            return None
        return cal

    def _calibrated_block(self, yhat: float) -> Optional[dict]:
        try:
            cal = self.calibration()
        except Exception:  # noqa: BLE001 — never block a forecast on calibration I/O
            logger.warning("calibration lookup failed (non-fatal)", exc_info=True)
            return None
        if cal is None:
            return None
        lo, hi = cal.interval(yhat)
        return {
            "lower": max(0, int(round(lo))),
            "upper": max(0, int(round(hi))),
            "nominal_level": cal.nominal_level,
            "calibration_version": cal.version,
            "provenance": cal.provenance,
            "measured_coverage": (cal.coverage_after or {}).get("coverage"),
            "measured_n": (cal.coverage_after or {}).get("n"),
            "label": (
                "synthetic-calibrated" if cal.provenance == "synthetic" else "calibrated-on-realised"
            ),
        }

    def _compute_confidence(self, lower: int, upper: int, predicted: int) -> float:
        """Computes confidence score based on interval width."""
        if predicted <= 0:
            return 0.5
        interval = upper - lower
        rel_interval = interval / predicted

        if rel_interval < 0.20:
            return 0.90
        elif rel_interval < 0.30:
            return 0.80
        elif rel_interval < 0.40:
            return 0.70
        elif rel_interval < 0.50:
            return 0.60
        else:
            return 0.50

    def save_model(self, path: str) -> None:
        """Saves current model state."""
        if not self.is_trained or not self.model:
            return
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        from prophet.serialize import model_to_json
        with open(path, 'w') as f:
            f.write(model_to_json(self.model))
        # Sidecar: the training data source survives a restart, so the
        # calibration match stays correct after load_model.
        with open(f"{path}.meta.json", "w") as f:
            json.dump({"data_source": self.data_source, "forecaster": FORECASTER_ID}, f)

    def load_model(self, path: str) -> None:
        """Loads model from path."""
        if not os.path.exists(path):
            return
        from prophet.serialize import model_from_json
        with open(path, 'r') as f:
            self.model = model_from_json(f.read())
        self.is_trained = True
        # Restore the regressor list from the deserialized model. Without this,
        # predict() omits the regressor columns the model expects and Prophet
        # raises "Regressor '<name>' missing from dataframe" on every loaded model.
        self.regressors = list(getattr(self.model, "extra_regressors", {}).keys())
        meta_path = f"{path}.meta.json"
        self.data_source = "unknown"
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r') as f:
                    self.data_source = json.load(f).get("data_source") or "unknown"
            except Exception:  # noqa: BLE001 — unknown source = no calibration applies
                logger.warning("model sidecar unreadable: %s", meta_path)
