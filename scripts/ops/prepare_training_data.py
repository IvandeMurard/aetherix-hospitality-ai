# -*- coding: utf-8 -*-
"""
Transforme les patterns Qdrant en séries temporelles pour Prophet.
"""

import pandas as pd
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict
from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# Config
COLLECTION_NAME = "fb_patterns"  # Utiliser fb_patterns comme dans le projet
DATA_SOURCE_JSON = Path(__file__).parent.parent / "backend" / "data" / "processed" / "patterns.json"
OUTPUT_CSV = Path(__file__).parent.parent / "backend" / "data" / "training_data.csv"


def fetch_patterns_from_qdrant() -> List[Dict]:
    """Récupère tous les patterns depuis Qdrant"""
    try:
        from qdrant_client import QdrantClient
        
        qdrant_url = os.getenv("QDRANT_URL")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")
        
        if not qdrant_url or not qdrant_api_key:
            print("QDRANT_URL or QDRANT_API_KEY not set, skipping Qdrant fetch")
            return []
        
        client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        
        # Scroll through all points
        patterns = []
        offset = None
        
        while True:
            results = client.scroll(
                collection_name=COLLECTION_NAME,
                limit=100,
                offset=offset,
                with_payload=True
            )
            
            points, offset = results
            if not points:
                break
                
            for point in points:
                patterns.append(point.payload)
        
        print(f"Fetched {len(patterns)} patterns from Qdrant")
        return patterns
    except Exception as e:
        print(f"Error fetching from Qdrant: {e}")
        return []


def load_patterns_from_json() -> List[Dict]:
    """Charge les patterns depuis patterns.json"""
    if not DATA_SOURCE_JSON.exists():
        print(f"Patterns file not found: {DATA_SOURCE_JSON}")
        return []
    
    with open(DATA_SOURCE_JSON, 'r', encoding='utf-8') as f:
        patterns = json.load(f)
    
    print(f"Loaded {len(patterns)} patterns from {DATA_SOURCE_JSON}")
    return patterns


def derive_weather_score(weather: Dict) -> float:
    """Dérive weather_score (0-1, 1 = mauvais temps) depuis weather.condition"""
    condition = weather.get("condition", "").lower() if isinstance(weather, dict) else ""
    
    if condition in ["rain", "heavy rain", "snow"]:
        return 0.9
    elif condition == "cloudy":
        return 0.5
    else:
        return 0.1


def derive_event_impact(events: List) -> float:
    """Dérive event_impact (0-1, 1 = événement majeur) depuis events"""
    if not events or len(events) == 0:
        return 0.0
    
    # Impact basé sur le nombre d'événements
    # 1 event = 0.3, 2 events = 0.6, 3+ = 1.0
    return min(1.0, len(events) * 0.3)


def patterns_to_timeseries(patterns: List[Dict]) -> pd.DataFrame:
    """
    Convertit les patterns en DataFrame pour Prophet.
    
    Chaque pattern doit avoir:
    - date (YYYY-MM-DD)
    - actual_covers
    - weather (dict avec condition)
    - events (list)
    - hotel_occupancy
    """
    records = []
    
    for pattern in patterns:
        # Extraire la date
        date_str = pattern.get('date')
        if not date_str:
            continue
        
        # Extraire les couverts
        covers = pattern.get('actual_covers')
        if covers is None:
            continue
        
        # Extraire features optionnelles
        weather = pattern.get('weather', {})
        weather_score = derive_weather_score(weather)
        
        events = pattern.get('events', [])
        event_impact = derive_event_impact(events)
        
        occupancy = pattern.get('hotel_occupancy', 0.0)
        # Normaliser occupancy si nécessaire (déjà 0-1 dans patterns.json)
        if occupancy > 1.0:
            occupancy = occupancy / 100.0
        
        records.append({
            'ds': pd.to_datetime(date_str),
            'y': int(covers),
            'weather_score': float(weather_score),
            'event_impact': float(event_impact),
            'occupancy': min(1.0, float(occupancy))
        })
    
    if not records:
        return pd.DataFrame()
    
    df = pd.DataFrame(records)
    df = df.sort_values('ds').reset_index(drop=True)
    
    return df


def generate_synthetic_data(
    start_date: str = "2024-01-01",
    days: int = 365,
    base_covers: int = 45
) -> pd.DataFrame:
    """
    Génère des données synthétiques si pas assez de patterns réels.
    Utile pour tester le modèle.
    """
    import random
    
    records = []
    start = datetime.strptime(start_date, "%Y-%m-%d")
    
    for i in range(days):
        date = start + timedelta(days=i)
        
        # Base
        covers = base_covers
        
        # Saisonnalité hebdomadaire
        dow = date.weekday()
        if dow == 5:  # Samedi
            covers *= 1.4
        elif dow == 6:  # Dimanche
            covers *= 1.2
        elif dow == 4:  # Vendredi
            covers *= 1.3
        elif dow == 0:  # Lundi
            covers *= 0.8
        
        # Saisonnalité mensuelle
        month = date.month
        if month in [7, 8]:  # Été
            covers *= 1.2
        elif month in [1, 2]:  # Hiver
            covers *= 0.85
        elif month == 12:  # Décembre (fêtes)
            covers *= 1.3
        
        # Ajouter du bruit
        covers *= random.uniform(0.85, 1.15)
        
        # Features aléatoires pour simulation
        weather_score = random.uniform(0, 0.5)  # Généralement beau
        event_impact = random.uniform(0, 0.2) if random.random() > 0.9 else 0
        occupancy = random.uniform(0.5, 0.95)
        
        records.append({
            'ds': date,
            'y': int(round(covers)),
            'weather_score': weather_score,
            'event_impact': event_impact,
            'occupancy': occupancy
        })
    
    return pd.DataFrame(records)


if __name__ == "__main__":
    print("=" * 60)
    print("Preparing training data for Prophet")
    print("=" * 60)
    
    # Option 1: Depuis Qdrant (si disponible)
    patterns = fetch_patterns_from_qdrant()
    
    # Option 2: Depuis patterns.json (fallback ou si Qdrant vide)
    if not patterns:
        print("\nFetching from Qdrant failed or empty, trying patterns.json...")
        patterns = load_patterns_from_json()
    
    # Option 3: Données synthétiques si toujours vide
    if not patterns:
        print("\nNo patterns found, generating synthetic data for testing...")
        df = generate_synthetic_data(days=365, base_covers=45)
    else:
        # Convertir patterns en DataFrame
        df = patterns_to_timeseries(patterns)
    
    if df.empty:
        print("ERROR: No data to process!")
        exit(1)
    
    print(f"\nGenerated {len(df)} data points")
    print(f"\nDate range: {df['ds'].min()} to {df['ds'].max()}")
    print(f"\nCovers range: {df['y'].min()} to {df['y'].max()}")
    print(f"\nFirst few rows:")
    print(df.head())
    print(f"\nStatistics:")
    print(df.describe())
    
    # Sauvegarder
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\n{'=' * 60}")
    print(f"Saved to {OUTPUT_CSV}")
    print(f"{'=' * 60}")
