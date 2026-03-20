# -*- coding: utf-8 -*-
"""
Moteur de prédiction basé sur Prophet (Meta).
Calcul déterministe — même input = même output.
"""

from prophet import Prophet
import pandas as pd
from datetime import datetime
from typing import Optional, List
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class PredictionResult:
    """Résultat de prédiction structuré"""
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
    Moteur Prophet pour prévision de couverts.
    
    Usage:
        engine = PredictionEngine()
        engine.train(historical_df)
        result = engine.predict("2026-02-20", features={"weather_score": 0.3})
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
        include_occupancy: bool = False
    ) -> None:
        """
        Entraîne le modèle Prophet.
        
        Args:
            df: DataFrame avec colonnes obligatoires:
                - ds: date (YYYY-MM-DD ou datetime)
                - y: couverts réels (int)
                Et colonnes optionnelles (régresseurs):
                - weather_score: float 0-1 (1 = mauvais temps)
                - event_impact: float 0-1 (1 = événement majeur)
                - occupancy: float 0-1 (taux d'occupation hôtel)
        """
        logger.info(f"Training Prophet model on {len(df)} data points")
        
        # Validation
        if 'ds' not in df.columns or 'y' not in df.columns:
            raise ValueError("DataFrame must have 'ds' and 'y' columns")
        
        # Créer le modèle
        self.model = Prophet(
            yearly_seasonality=True,   # Saisonnalité annuelle (été/hiver)
            weekly_seasonality=True,   # Saisonnalité hebdo (lundi ≠ samedi)
            daily_seasonality=False,   # Pas utile pour couverts journaliers
            interval_width=0.80,       # Intervalle de confiance 80%
            changepoint_prior_scale=0.05  # Sensibilité aux changements de tendance
        )
        
        # Ajouter les jours fériés français
        try:
            self.model.add_country_holidays(country_name='FR')
        except Exception as e:
            logger.warning(f"Could not add French holidays: {e}")
        
        # Ajouter régresseurs si présents dans les données
        self.regressors = []
        
        if include_weather and 'weather_score' in df.columns:
            self.model.add_regressor('weather_score')
            self.regressors.append('weather_score')
            logger.info("Added weather_score regressor")
        
        if include_events and 'event_impact' in df.columns:
            self.model.add_regressor('event_impact')
            self.regressors.append('event_impact')
            logger.info("Added event_impact regressor")
        
        if include_occupancy and 'occupancy' in df.columns:
            self.model.add_regressor('occupancy')
            self.regressors.append('occupancy')
            logger.info("Added occupancy regressor")
        
        # Entraîner
        self.model.fit(df)
        self.is_trained = True
        logger.info("Prophet model trained successfully")
    
    def predict(
        self,
        date: str,
        features: Optional[dict] = None
    ) -> PredictionResult:
        """
        Prédit le nombre de couverts pour une date.
        
        Args:
            date: Date au format YYYY-MM-DD
            features: Dict de régresseurs optionnels
                - weather_score: float 0-1
                - event_impact: float 0-1
                - occupancy: float 0-1
        
        Returns:
            PredictionResult avec predicted, lower, upper, confidence
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")
        
        # Créer le DataFrame de prédiction
        future = pd.DataFrame({'ds': [pd.to_datetime(date)]})
        
        # Ajouter les régresseurs
        if features:
            for regressor in self.regressors:
                if regressor in features:
                    future[regressor] = features[regressor]
                else:
                    # Valeur par défaut si non fournie
                    future[regressor] = 0.0
                    logger.warning(f"Regressor {regressor} not provided, using 0.0")
        else:
            # Aucune feature fournie, mettre des valeurs par défaut
            for regressor in self.regressors:
                future[regressor] = 0.0
        
        # Prédire
        forecast = self.model.predict(future)
        row = forecast.iloc[0]
        
        # Extraire les valeurs
        predicted = max(0, int(round(row['yhat'])))  # Pas de couverts négatifs
        lower = max(0, int(round(row['yhat_lower'])))
        upper = max(0, int(round(row['yhat_upper'])))
        
        # Calculer la confiance basée sur l'intervalle
        confidence = self._compute_confidence(lower, upper, predicted)
        
        return PredictionResult(
            predicted=predicted,
            lower=lower,
            upper=upper,
            confidence=confidence,
            date=date
        )
    
    def predict_batch(
        self,
        dates: List[str],
        features_per_date: Optional[dict[str, dict]] = None
    ) -> List[PredictionResult]:
        """
        Prédit pour plusieurs dates.
        
        Args:
            dates: Liste de dates YYYY-MM-DD
            features_per_date: Dict {date: {feature: value}}
        
        Returns:
            Liste de PredictionResult
        """
        results = []
        for date in dates:
            features = features_per_date.get(date) if features_per_date else None
            results.append(self.predict(date, features))
        return results
    
    def _compute_confidence(
        self,
        lower: int,
        upper: int,
        predicted: int
    ) -> float:
        """
        Calcule un score de confiance basé sur l'intervalle.
        Intervalle étroit = haute confiance.
        """
        if predicted == 0:
            return 0.5
        
        interval = upper - lower
        relative_interval = interval / predicted
        
        # Mapping: intervalle relatif -> confiance
        # <20% du prédit = très confiant
        # 20-40% = confiant
        # >40% = peu confiant
        if relative_interval < 0.20:
            return 0.90
        elif relative_interval < 0.30:
            return 0.80
        elif relative_interval < 0.40:
            return 0.70
        elif relative_interval < 0.50:
            return 0.60
        else:
            return 0.50
    
    def save_model(self, path: str) -> None:
        """Sauvegarde le modèle entraîné (JSON ou pickle)"""
        if not self.is_trained:
            raise RuntimeError("No trained model to save")
        
        # Créer le dossier parent si nécessaire
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        # Essayer d'abord prophet.serialize (Prophet 1.1.5+)
        try:
            from prophet.serialize import model_to_json
            with open(path, 'w') as f:
                f.write(model_to_json(self.model))
            logger.info(f"Model saved to {path} (JSON)")
        except ImportError:
            # Fallback: utiliser pickle
            import pickle
            with open(path, 'wb') as f:
                pickle.dump(self.model, f)
            logger.info(f"Model saved to {path} (pickle)")
    
    def load_model(self, path: str) -> None:
        """Charge un modèle sauvegardé"""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Model file not found: {path}")
        
        # Essayer d'abord prophet.serialize (Prophet 1.1.5+)
        try:
            from prophet.serialize import model_from_json
            with open(path, 'r') as f:
                self.model = model_from_json(f.read())
            logger.info(f"Model loaded from {path} (JSON)")
        except (ImportError, ValueError):
            # Fallback: utiliser pickle
            import pickle
            with open(path, 'rb') as f:
                self.model = pickle.load(f)
            logger.info(f"Model loaded from {path} (pickle)")
        
        self.is_trained = True


# Singleton pour l'application
_engine_instance: Optional[PredictionEngine] = None


def get_prediction_engine() -> PredictionEngine:
    """Retourne l'instance singleton du moteur"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = PredictionEngine()
    return _engine_instance
