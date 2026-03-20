"""
Seed Qdrant with pattern embeddings using Mistral Embed
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from mistralai import Mistral
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# Load environment from project root
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Config
DATA_PATH = Path(__file__).parent.parent / "data" / "processed" / "patterns.json"
COLLECTION_NAME = "fb_patterns"
EMBEDDING_MODEL = "mistral-embed"
EMBEDDING_DIM = 1024
BATCH_SIZE = 50  # Mistral batch limit

def get_clients():
    """Initialize Mistral and Qdrant clients"""
    mistral_key = os.getenv("MISTRAL_API_KEY")
    if not mistral_key:
        raise ValueError("MISTRAL_API_KEY not found in environment variables")
    
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_key = os.getenv("QDRANT_API_KEY")
    if not qdrant_url or not qdrant_key:
        raise ValueError("QDRANT_URL and QDRANT_API_KEY must be set in environment variables")
    
    mistral = Mistral(api_key=mistral_key)
    
    qdrant = QdrantClient(
        url=qdrant_url,
        api_key=qdrant_key
    )
    return mistral, qdrant

def create_collection(qdrant: QdrantClient):
    """Create or recreate collection"""
    collections = [c.name for c in qdrant.get_collections().collections]
    
    if COLLECTION_NAME in collections:
        print(f"Deleting existing collection '{COLLECTION_NAME}'...")
        qdrant.delete_collection(COLLECTION_NAME)
    
    print(f"Creating collection '{COLLECTION_NAME}'...")
    qdrant.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE)
    )

def pattern_to_context(pattern: dict) -> str:
    """
    Convert pattern to embeddable context string.
    
    Note: Does not include 'actual_covers' as this is the value to predict,
    not a contextual feature. This ensures query embeddings (from demand_predictor.py)
    are semantically compatible with indexed pattern embeddings.
    """
    events_str = ", ".join([e["type"] for e in pattern.get("events", [])]) or "None"
    weather = pattern.get("weather", {})
    
    return f"""Date: {pattern['date']} ({pattern['day_of_week']})
Service: {pattern['service_type']}
Day type: {pattern['day_type']}
Hotel occupancy: {pattern['hotel_occupancy']}
Guests in house: {pattern['guests_in_house']}
Weather: {weather.get('condition', 'Unknown')}, {weather.get('temperature', 'N/A')}°C
Events nearby: {events_str}
Holiday: {pattern.get('holiday_name', 'None') if pattern.get('is_holiday') else 'None'}"""

def embed_batch(mistral: Mistral, texts: list[str]) -> list[list[float]]:
    """Get embeddings for a batch of texts"""
    response = mistral.embeddings.create(
        model=EMBEDDING_MODEL,
        inputs=texts
    )
    return [item.embedding for item in response.data]

def seed_qdrant():
    """Main seeding function"""
    # Verify environment variables first
    mistral_key = os.getenv("MISTRAL_API_KEY")
    if not mistral_key or mistral_key.strip() == "":
        print("ERROR: MISTRAL_API_KEY is not set or is empty in .env file")
        print("Please add your Mistral AI API key to the .env file:")
        print("  MISTRAL_API_KEY=your_api_key_here")
        sys.exit(1)
    
    print("Loading patterns...")
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        patterns = json.load(f)
    print(f"Loaded {len(patterns)} patterns")
    
    mistral, qdrant = get_clients()
    create_collection(qdrant)
    
    print(f"Generating embeddings and upserting (batch size: {BATCH_SIZE})...")
    
    total_upserted = 0
    for i in range(0, len(patterns), BATCH_SIZE):
        batch = patterns[i:i + BATCH_SIZE]
        
        # Generate context strings
        contexts = [pattern_to_context(p) for p in batch]
        
        # Get embeddings
        embeddings = embed_batch(mistral, contexts)
        
        # Prepare points
        points = [
            PointStruct(
                id=idx + i,  # Unique integer ID
                vector=embedding,
                payload={
                    "pattern_id": p["pattern_id"],
                    "date": p["date"],
                    "day_of_week": p["day_of_week"],
                    "service_type": p["service_type"],
                    "day_type": p["day_type"],
                    "hotel_occupancy": p["hotel_occupancy"],
                    "guests_in_house": p["guests_in_house"],
                    "actual_covers": p["actual_covers"],
                    "weather_condition": p.get("weather", {}).get("condition"),
                    "weather_temp": p.get("weather", {}).get("temperature"),
                    "events": [e["type"] for e in p.get("events", [])],
                    "is_holiday": p.get("is_holiday", False),
                    "holiday_name": p.get("holiday_name"),
                    "context_str": contexts[idx]  # Store for debugging
                }
            )
            for idx, (p, embedding) in enumerate(zip(batch, embeddings))
        ]
        
        # Upsert
        qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
        total_upserted += len(points)
        print(f"  Upserted {total_upserted}/{len(patterns)} patterns")
    
    # Verify
    count = qdrant.count(collection_name=COLLECTION_NAME).count
    print(f"\n{'='*50}")
    print(f"SEEDING COMPLETE")
    print(f"{'='*50}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Total points: {count}")
    print(f"{'='*50}")

if __name__ == "__main__":
    seed_qdrant()
