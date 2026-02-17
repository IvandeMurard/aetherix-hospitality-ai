# -*- coding: utf-8 -*-
"""
Script pour entraîner le modèle Prophet et le sauvegarder.
"""

import pandas as pd
from pathlib import Path
import sys
from dotenv import load_dotenv

# Add backend to path for imports
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path.parent))

# Load .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

from backend.ml.prediction_engine import PredictionEngine

# Config
TRAINING_DATA_CSV = Path(__file__).parent.parent / "backend" / "data" / "training_data.csv"
MODEL_PATH = Path(__file__).parent.parent / "backend" / "ml" / "models" / "prophet_model.json"


def main():
    print("=" * 60)
    print("Training Prophet Model")
    print("=" * 60)
    
    # Vérifier que le fichier de données existe
    if not TRAINING_DATA_CSV.exists():
        print(f"ERROR: Training data file not found: {TRAINING_DATA_CSV}")
        print("\nPlease run prepare_training_data.py first to generate training_data.csv")
        sys.exit(1)
    
    # Charger les données
    print(f"\nLoading training data from {TRAINING_DATA_CSV}...")
    df = pd.read_csv(TRAINING_DATA_CSV)
    
    # Vérifier les colonnes requises
    if 'ds' not in df.columns or 'y' not in df.columns:
        print("ERROR: DataFrame must have 'ds' and 'y' columns")
        print(f"Found columns: {df.columns.tolist()}")
        sys.exit(1)
    
    # Convertir ds en datetime si nécessaire
    df['ds'] = pd.to_datetime(df['ds'])
    
    print(f"Loaded {len(df)} data points")
    print(f"Date range: {df['ds'].min()} to {df['ds'].max()}")
    print(f"Covers range: {df['y'].min()} to {df['y'].max()}")
    
    # Vérifier les régresseurs disponibles
    regressors_available = []
    if 'weather_score' in df.columns:
        regressors_available.append('weather_score')
    if 'event_impact' in df.columns:
        regressors_available.append('event_impact')
    if 'occupancy' in df.columns:
        regressors_available.append('occupancy')
    
    print(f"\nAvailable regressors: {regressors_available}")
    
    # Créer et entraîner le modèle
    print("\nCreating PredictionEngine...")
    engine = PredictionEngine()
    
    print("Training model...")
    try:
        engine.train(
            df,
            include_weather='weather_score' in df.columns,
            include_events='event_impact' in df.columns,
            include_occupancy='occupancy' in df.columns
        )
        print("✓ Model trained successfully")
    except Exception as e:
        print(f"ERROR: Training failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Sauvegarder le modèle
    print(f"\nSaving model to {MODEL_PATH}...")
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        engine.save_model(str(MODEL_PATH))
        print(f"✓ Model saved successfully")
    except Exception as e:
        print(f"ERROR: Failed to save model: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Test de prédiction
    print("\n" + "=" * 60)
    print("Testing prediction...")
    print("=" * 60)
    
    # Utiliser la dernière date + 1 jour pour tester
    last_date = df['ds'].max()
    test_date = (last_date + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Préparer les features pour le test
    test_features = {}
    if 'weather_score' in df.columns:
        test_features['weather_score'] = df['weather_score'].mean()
    if 'event_impact' in df.columns:
        test_features['event_impact'] = df['event_impact'].mean()
    if 'occupancy' in df.columns:
        test_features['occupancy'] = df['occupancy'].mean()
    
    try:
        result = engine.predict(test_date, test_features)
        print(f"\nTest prediction for {test_date}:")
        print(f"  Predicted covers: {result.predicted}")
        print(f"  Range: {result.lower} - {result.upper}")
        print(f"  Confidence: {result.confidence:.2%}")
        print("✓ Prediction test successful")
    except Exception as e:
        print(f"WARNING: Prediction test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Training complete!")
    print("=" * 60)
    print(f"\nModel saved to: {MODEL_PATH}")
    print(f"You can now use this model in the prediction endpoint.")


if __name__ == "__main__":
    main()
