import asyncio
import logging
import os
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
from prophet import Prophet

from app.core.demo_events import demo_emit

logger = logging.getLogger(__name__)

# HOS-274 canary — no-op touch to force the eval-gate forecast run (Prophet-in-CI
# stability measurement before flipping the gate to blocking). Reverted after.

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
    ):
        self.predicted = predicted
        self.lower = lower
        self.upper = upper
        self.confidence = confidence
        self.date = date
        self.is_mock = is_mock

    def to_dict(self) -> dict:
        return {
            "predicted_covers": self.predicted,
            "range_min": self.lower,
            "range_max": self.upper,
            "confidence": self.confidence,
            "date": self.date,
            "is_mock": self.is_mock,
        }

class PredictionEngine:
    """
    Prophet engine for covers forecasting.
    Source of truth for numerical predictions in Phase 2.
    """
    
    def __init__(self):
        self.model: Optional[Prophet] = None
        self.is_trained = False
        self.regressors = []
    
    async def train(
        self,
        df: pd.DataFrame,
        include_weather: bool = True,
        include_events: bool = True,
        include_occupancy: bool = True
    ) -> None:
        """Trains the Prophet model with specified regressors."""
        if 'ds' not in df.columns or 'y' not in df.columns:
            raise ValueError("DataFrame must have 'ds' and 'y' columns")

        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=0.80,
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
        await asyncio.to_thread(model.fit, df)

        self.model = model
        self.regressors = regressors
        self.is_trained = True
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
        )
        asyncio.get_running_loop().create_task(demo_emit("prophet"))
        return result

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
