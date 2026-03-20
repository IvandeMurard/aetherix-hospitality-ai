"""
Seed Qdrant with historical F&B scenarios.

Connection priority:
  1. QDRANT_URL + QDRANT_API_KEY (cloud or self-hosted)
  2. localhost:6333              (local Docker)
  3. :memory:                   (demo / CI only — data is lost on exit)

Embedding priority:
  1. Mistral embed (MISTRAL_API_KEY set) — 1024-dim, best quality
  2. Local bag-of-words hash      — 1024-dim deterministic, no API needed

Usage:
    python seed_data.py
    python seed_data.py --dry-run   # print scenarios without writing
"""

import argparse
import hashlib
import math
import os
import uuid
from collections import Counter

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

load_dotenv()

VECTOR_SIZE = 1024
COLLECTION_NAME = "hospitality_patterns"

# ---------------------------------------------------------------------------
# Historical scenarios (source of truth)
# ---------------------------------------------------------------------------

SCENARIOS = [
    {"date": "2024-01-15", "day": "Saturday",  "event_type": "concert",   "event_name": "Coldplay concert nearby",    "event_magnitude": "large",  "distance": "500m",  "weather": "clear, 22°C",  "actual_covers": 95, "usual_covers": 60, "variance": "+58%", "staffing": 6, "notes": "High demand from concert attendees, peak at 8pm"},
    {"date": "2024-02-10", "day": "Saturday",  "event_type": "festival",  "event_name": "Jazz festival downtown",     "event_magnitude": "medium", "distance": "800m",  "weather": "sunny, 20°C",  "actual_covers": 82, "usual_covers": 60, "variance": "+37%", "staffing": 5, "notes": "Steady flow throughout evening"},
    {"date": "2024-03-22", "day": "Friday",    "event_type": "sports",    "event_name": "Football match nearby",      "event_magnitude": "large",  "distance": "1km",   "weather": "cloudy, 18°C", "actual_covers": 88, "usual_covers": 55, "variance": "+60%", "staffing": 6, "notes": "Pre-match crowd, quick service needed"},
    {"date": "2024-04-14", "day": "Sunday",    "event_type": "festival",  "event_name": "Food festival",              "event_magnitude": "medium", "distance": "600m",  "weather": "sunny, 24°C",  "actual_covers": 70, "usual_covers": 45, "variance": "+56%", "staffing": 4, "notes": "Families, relaxed pace, outdoor seating busy"},
    {"date": "2024-05-18", "day": "Saturday",  "event_type": "concert",   "event_name": "Rock concert",               "event_magnitude": "large",  "distance": "400m",  "weather": "clear, 23°C",  "actual_covers": 92, "usual_covers": 60, "variance": "+53%", "staffing": 6, "notes": "Young crowd, high energy, bar demand very high"},
    {"date": "2024-06-08", "day": "Saturday",  "event_type": "wedding",   "event_name": "In-house wedding",           "event_magnitude": "small",  "distance": "0m",    "weather": "sunny, 26°C",  "actual_covers": 75, "usual_covers": 60, "variance": "+25%", "staffing": 5, "notes": "In-house wedding party, private dining room"},
    {"date": "2024-07-20", "day": "Saturday",  "event_type": "festival",  "event_name": "Summer music festival",      "event_magnitude": "large",  "distance": "700m",  "weather": "hot, 30°C",    "actual_covers": 85, "usual_covers": 60, "variance": "+42%", "staffing": 5, "notes": "Hot weather, drinks demand very high, light meals"},
    {"date": "2024-08-25", "day": "Friday",    "event_type": "corporate", "event_name": "Conference dinner",          "event_magnitude": "medium", "distance": "0m",    "weather": "clear, 25°C",  "actual_covers": 78, "usual_covers": 55, "variance": "+42%", "staffing": 5, "notes": "Business crowd, wine focus, late seating"},
    {"date": "2024-09-14", "day": "Saturday",  "event_type": "sports",    "event_name": "Marathon event",             "event_magnitude": "large",  "distance": "1.5km", "weather": "cool, 17°C",   "actual_covers": 65, "usual_covers": 60, "variance": "+8%",  "staffing": 4, "notes": "Post-race crowd arrives late, carb-heavy orders"},
    {"date": "2024-10-30", "day": "Saturday",  "event_type": "holiday",   "event_name": "Halloween weekend",          "event_magnitude": "medium", "distance": "0m",    "weather": "rainy, 12°C",  "actual_covers": 68, "usual_covers": 60, "variance": "+13%", "staffing": 4, "notes": "Theme-driven bookings, cocktail demand up"},
    {"date": "2024-11-28", "day": "Thursday",  "event_type": "holiday",   "event_name": "Thanksgiving dinner service","event_magnitude": "medium", "distance": "0m",    "weather": "cold, 8°C",    "actual_covers": 72, "usual_covers": 55, "variance": "+31%", "staffing": 5, "notes": "Multi-generational families, long seatings"},
    {"date": "2024-12-24", "day": "Tuesday",   "event_type": "holiday",   "event_name": "Christmas Eve gala dinner",  "event_magnitude": "large",  "distance": "0m",    "weather": "clear, 4°C",   "actual_covers": 94, "usual_covers": 60, "variance": "+57%", "staffing": 6, "notes": "Fully booked, set menu, champagne service"},
]


def _scenario_text(s: dict) -> str:
    return (
        f"{s['day']} {s['event_type']}: {s['event_name']}. "
        f"Distance: {s['distance']}, Weather: {s['weather']}. "
        f"Resulted in {s['actual_covers']} covers "
        f"(usual: {s['usual_covers']}, variance: {s['variance']}). "
        f"Staffing: {s['staffing']}. Notes: {s['notes']}."
    )


# ---------------------------------------------------------------------------
# Embedding backends
# ---------------------------------------------------------------------------

def _local_embed(text: str) -> list[float]:
    """
    Deterministic 1024-dim vector built from character n-gram hashing.
    Not semantically rich, but consistent and requires zero dependencies.
    Only used when MISTRAL_API_KEY is not set.
    """
    vec = [0.0] * VECTOR_SIZE
    words = text.lower().split()
    tokens = words + [a + b for a, b in zip(words, words[1:])]  # unigrams + bigrams
    for token in tokens:
        h = int(hashlib.md5(token.encode()).hexdigest(), 16)
        idx = h % VECTOR_SIZE
        vec[idx] += 1.0
    # L2-normalise
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _mistral_embed(texts: list[str]) -> list[list[float]]:
    from mistralai import Mistral
    client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))
    resp = client.embeddings.create(model="mistral-embed", inputs=texts)
    return [d.embedding for d in resp.data]


# ---------------------------------------------------------------------------
# Qdrant connection
# ---------------------------------------------------------------------------

def _connect_qdrant() -> tuple[QdrantClient, str]:
    """Return (client, mode_description)."""
    url = os.getenv("QDRANT_URL", "").strip()
    key = os.getenv("QDRANT_API_KEY", "").strip()

    if url:
        client = QdrantClient(url=url, api_key=key or None)
        return client, f"cloud/self-hosted ({url})"

    try:
        client = QdrantClient(host="localhost", port=6333, timeout=3)
        client.get_collections()  # ping
        return client, "localhost:6333"
    except Exception:
        pass

    return QdrantClient(":memory:"), "in-memory (data lost on exit)"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed(dry_run: bool = False) -> None:
    client, mode = _connect_qdrant()
    use_mistral = bool(os.getenv("MISTRAL_API_KEY"))
    embed_mode = "Mistral embed (1024-dim)" if use_mistral else "local hash embed (1024-dim, no API)"

    print(f"\n  Qdrant   : {mode}")
    print(f"  Embedder : {embed_mode}")
    print(f"  Scenarios: {len(SCENARIOS)}")

    if dry_run:
        print("\n  [dry-run] — no data written.\n")
        for s in SCENARIOS:
            print(f"    {s['date']}  {s['day']:<9}  {s['event_type']:<10}  {s['event_name']}")
        return

    # Create / verify collection
    try:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"\n  Collection '{COLLECTION_NAME}' created.")
    except Exception:
        print(f"\n  Collection '{COLLECTION_NAME}' already exists — upserting.")

    # Generate embeddings
    texts = [_scenario_text(s) for s in SCENARIOS]
    if use_mistral:
        print("  Generating Mistral embeddings (batch) ...")
        vectors = _mistral_embed(texts)
    else:
        print("  Generating local hash embeddings ...")
        vectors = [_local_embed(t) for t in texts]

    # Build and upsert points
    points = [
        PointStruct(id=str(uuid.uuid4()), vector=vec, payload=scenario)
        for vec, scenario in zip(vectors, SCENARIOS)
    ]
    client.upsert(collection_name=COLLECTION_NAME, points=points)

    # Verify
    count = client.count(collection_name=COLLECTION_NAME).count
    print(f"  Seeded {count} points into '{COLLECTION_NAME}'.")
    if mode == "in-memory (data lost on exit)":
        print("  NOTE: in-memory only — set QDRANT_URL to persist across runs.")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Qdrant with F&B historical scenarios")
    parser.add_argument("--dry-run", action="store_true", help="Print scenarios without writing")
    args = parser.parse_args()

    print("=" * 60)
    print("  SEED — F&B Hospitality Patterns")
    print("=" * 60)
    seed(dry_run=args.dry_run)
