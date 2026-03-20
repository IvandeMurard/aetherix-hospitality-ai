from prophet import Prophet
import pandas as pd
from datetime import datetime, date
from typing import Optional, List, Dict
import logging
from pathlib import Path
import os

logger = logging.getLogger(__name__)

class PredictionResult:
    """Structured prediction result."""
    def __init__(
        self,
        predicted: int,
        lower: int,
        upper: int,
        confidence: float,
        date: str
    ):
        self.predicted = predicted
        self.lower = lower
        self.upper = upper
        self.confidence = confidence
        self.date = date
    
    def to_dict(self) -> dict:
        return {
            "predicted_covers": self.predicted,
            "range_min": self.lower,
            "range_max": self.upper,
            "confidence": self.confidence,
            "date": self.date
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
    
    def train(
        self,
        df: pd.DataFrame,
        include_weather: bool = True,
        include_events: bool = True,
        include_occupancy: bool = True
    ) -> None:
        """Trains the Prophet model with specified regressors."""
        if 'ds' not in df.columns or 'y' not in df.columns:
            raise ValueError("DataFrame must have 'ds' and 'y' columns")
        
        self.model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=0.80,
            changepoint_prior_scale=0.05
        )
        
        # Add French holidays for pilot location context
        try:
            self.model.add_country_holidays(country_name='FR')
        except Exception as e:
            logger.warning(f"Could not add French holidays: {e}")
        
        self.regressors = []
        for reg in ['weather_score', 'event_impact', 'occupancy']:
            if reg in df.columns:
                self.model.add_regressor(reg)
                self.regressors.append(reg)
        
        self.model.fit(df)
        self.is_trained = True
        logger.info("Prophet model trained successfully")
    
    def predict(
        self,
        target_date: date,
        features: Optional[dict] = None
    ) -> PredictionResult:
        """Predicts covers for a specific date."""
        if not self.is_trained:
            logger.warning("Prophet model not trained. Returning mock prediction for pilot.")
            # Mock result for development/pilot without training
            return PredictionResult(
                predicted=45,
                lower=38,
                upper=52,
                confidence=0.85,
                date=target_date.isoformat()
            )
        
        date_str = target_date.isoformat()
        future = pd.DataFrame({'ds': [pd.to_datetime(target_date)]})
        
        if features:
            for reg in self.regressors:
                future[reg] = features.get(reg, 0.0)
        else:
            for reg in self.regressors:
                future[reg] = 0.0
        
        forecast = self.model.predict(future)
        row = forecast.iloc[0]
        
        predicted = max(0, int(round(row['yhat'])))
        lower = max(0, int(round(row['yhat_lower'])))
        upper = max(0, int(round(row['yhat_upper'])))
        
        confidence = self._compute_confidence(lower, upper, predicted)
        
        return PredictionResult(
            predicted=predicted,
            lower=lower,
            upper=upper,
            confidence=confidence,
            date=date_str
        )

    def _compute_confidence(self, lower: int, upper: int, predicted: int) -> float:
        """Computes confidence score based on interval width."""
        if predicted <= 0: return 0.5
        interval = upper - lower
        rel_interval = interval / predicted
        
        if rel_interval < 0.20: return 0.90
        elif rel_interval < 0.30: return 0.80
        elif rel_interval < 0.40: return 0.70
        elif rel_interval < 0.50: return 0.60
        else: return 0.50

    def save_model(self, path: str) -> None:
        """Saves current model state."""
        if not self.is_trained or not self.model: return
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        from prophet.serialize import model_to_json
        with open(path, 'w') as f:
            f.write(model_to_json(self.model))

    def load_model(self, path: str) -> None:
        """Loads model from path."""
        if not os.path.exists(path): return
        from prophet.serialize import model_from_json
        with open(path, 'r') as f:
            self.model = model_from_json(f.read())
        self.is_trained = True
