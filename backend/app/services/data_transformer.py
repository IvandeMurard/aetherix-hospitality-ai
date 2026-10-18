"""PMS data to ML-ready frames — HOS-281 (Décision #28, ADR-0006 §9).

Reads the vendor-neutral PMS layer only (``providers/pms/base.py``). No field
of any PMS's native payload appears here: each adapter maps its own format to
``NormalizedReservation``, so a new PMS feeds the forecast without a change to
this file.
"""
from typing import Dict, Iterable

import pandas as pd

from app.providers.pms.base import NormalizedReservation


class DataTransformer:
    """Utility to transform canonical PMS data into ML-ready formats (Prophet ds, y)."""

    @staticmethod
    def reservations_to_prophet(reservations: Iterable[NormalizedReservation]) -> pd.DataFrame:
        """Daily guest totals by arrival date, a proxy for covers.

        Same rule as before HOS-281: reservations without an arrival date are
        skipped; guests = adults + children; one row per arrival day.
        """
        data = [{"ds": r.arrival.isoformat(), "y": r.guests} for r in reservations if r.arrival is not None]
        if not data:
            return pd.DataFrame(columns=['ds', 'y'])

        df = pd.DataFrame(data)
        df['ds'] = pd.to_datetime(df['ds'])
        return df.groupby('ds')['y'].sum().reset_index()

    @staticmethod
    def add_external_features(df: pd.DataFrame, weather_data: Dict[str, float]) -> pd.DataFrame:
        """
        Joins external features (e.g. weather score) for multivariable forecasting.
        """
        # Simplification: Applying same weather score or joining on date
        df['weather_score'] = df['ds'].map(lambda x: weather_data.get(x.strftime('%Y-%m-%d'), 0.5))
        return df
