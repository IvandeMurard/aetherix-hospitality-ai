import pandas as pd
from typing import List, Dict, Any
from datetime import datetime

class DataTransformer:
    """
    Utility to transform PMS raw data into ML-ready formats.
    Focus: Apaleo Stay Records to Prophet (ds, y).
    """
    
    @staticmethod
    def stay_records_to_prophet(records: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Aggregates guest counts by date for Prophet training.
        """
        if not records:
            return pd.DataFrame(columns=['ds', 'y'])
            
        data = []
        for rec in records:
            arrival = rec.get("arrival", "")
            # Arrival usually comes as ISO string
            if arrival:
                ds = arrival[:10] # Extract YYYY-MM-DD
                # Summing up total guests (adults + children) as a proxy for covers
                total_guests = rec.get("adults", 0) + rec.get("children", 0)
                data.append({"ds": ds, "y": total_guests})
                
        df = pd.DataFrame(data)
        if df.empty:
            return pd.DataFrame(columns=['ds', 'y'])
            
        # Group by date to get daily totals
        df['ds'] = pd.to_datetime(df['ds'])
        daily_df = df.groupby('ds')['y'].sum().reset_index()
        
        return daily_df

    @staticmethod
    def add_external_features(df: pd.DataFrame, weather_data: Dict[str, float]) -> pd.DataFrame:
        """
        Joins external features (e.g. weather score) for multivariable forecasting.
        """
        # Simplification: Applying same weather score or joining on date
        df['weather_score'] = df['ds'].map(lambda x: weather_data.get(x.strftime('%Y-%m-%d'), 0.5))
        return df
