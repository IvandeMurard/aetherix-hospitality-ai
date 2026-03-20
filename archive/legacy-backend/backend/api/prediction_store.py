# -*- coding: utf-8 -*-
"""
Service de stockage des prédictions pour le feedback loop.
Permet de lier les prédictions aux feedbacks via UUID Supabase.
"""

import logging
from datetime import date
from typing import Optional, List
from uuid import UUID, uuid5, NAMESPACE_DNS

logger = logging.getLogger(__name__)


def convert_restaurant_id(restaurant_id: str) -> str:
    """
    Convertit un restaurant_id string en UUID déterministe.
    'hotel_main' → toujours le même UUID.
    """
    try:
        # Si c'est déjà un UUID valide, l'utiliser
        uid = UUID(restaurant_id)
        return str(uid)
    except (ValueError, TypeError):
        # Sinon, générer un UUID déterministe via uuid5
        uid = uuid5(NAMESPACE_DNS, str(restaurant_id))
        return str(uid)


def transform_patterns_for_storage(patterns: List[dict]) -> List[dict]:
    """
    Transforme les patterns de /predict au format Supabase similar_patterns.
    """
    if not patterns:
        return []

    transformed = []
    for p in patterns[:5]:  # Max 5 patterns
        transformed.append({
            "date": str(p.get("date", "")),
            "covers": p.get("actual_covers", p.get("covers", 0)),
            "similarity": p.get("similarity", 0.0),
            "day_of_week": (p.get("metadata") or {}).get("day_of_week", p.get("day_of_week", ""))
        })
    return transformed


def transform_factors_for_storage(confidence_factors: List[str]) -> List[dict]:
    """
    Transforme les confidence_factors en format PredictionFactor.
    Pour MVP, on stocke le nom avec valeurs par défaut.
    """
    if not confidence_factors:
        return []

    return [
        {
            "name": factor,
            "value": 0,
            "impact_pct": 0
        }
        for factor in confidence_factors
    ]


def store_prediction_for_feedback(
    restaurant_id: str,
    service_date: date,
    service_type: str,
    predicted_covers: int,
    confidence: float,
    range_low: int,
    range_high: int,
    estimated_mape: Optional[float] = None,
    patterns: Optional[List[dict]] = None,
    confidence_factors: Optional[List[str]] = None
) -> Optional[str]:
    """
    Enregistre une prédiction dans Supabase pour le feedback loop.

    Returns:
        UUID string si succès, None si échec ou Supabase non configuré.
    """
    try:
        from backend.api.routes import get_supabase
        supabase = get_supabase()
    except Exception as e:
        logger.warning(f"[PREDICTION_STORE] Supabase not available: {e}")
        return None

    try:
        # Préparer les données
        prediction_data = {
            "restaurant_id": convert_restaurant_id(restaurant_id),
            "service_date": str(service_date),
            "service_type": service_type,
            "predicted_covers": predicted_covers,
            "confidence": confidence,
            "range_low": range_low,
            "range_high": range_high,
            "estimated_mape": estimated_mape,
            "factors": transform_factors_for_storage(confidence_factors or []),
            "similar_patterns": transform_patterns_for_storage(patterns or [])
        }

        # Insérer en base
        result = supabase.table("predictions").insert(prediction_data).execute()

        if result.data and len(result.data) > 0:
            prediction_id = result.data[0].get("id")
            logger.info(f"[PREDICTION_STORE] Stored prediction {prediction_id}")
            return str(prediction_id)
        else:
            logger.warning("[PREDICTION_STORE] Insert returned no data")
            return None

    except Exception as e:
        logger.warning(f"[PREDICTION_STORE] Failed to store prediction: {e}")
        return None
