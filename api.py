from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Distance, VectorParams
from mistralai import Mistral
import uuid

from agents.analyzer import AnalyzerAgent
from agents.pattern_search import PatternSearcher
from agents.predictor import PredictorAgent

load_dotenv()

# Initialiser FastAPI
app = FastAPI(
    title="F&B Operations Agent API",
    description="API de prédiction F&B (covers + staff + confiance) basée sur Qdrant + Mistral",
    version="1.0.0",
)

# Instancier les agents une seule fois (réutilisés à chaque requête)
analyzer = AnalyzerAgent()
pattern_searcher = PatternSearcher()
predictor = PredictorAgent()

# Seed Qdrant in-memory on startup
def seed_qdrant_on_startup():
    """Seed in-memory Qdrant with historical data"""
    qdrant = pattern_searcher.qdrant
    collection_name = pattern_searcher.collection_name
    
    # Create collection if needed
    try:
        qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
        )
    except:
        pass  # Collection exists
    
    # Check if already seeded
    try:
        result = qdrant.scroll(collection_name=collection_name, limit=1)
        if len(result[0]) > 0:
            print("✅ Qdrant already seeded")
            return
    except:
        pass
    
    # Seed data
    print("🌱 Seeding Qdrant with historical data...")
    mistral = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))
    
    scenarios = [
        {"date": "2024-01-15", "day": "Saturday", "event_type": "concert", "event_name": "Coldplay concert nearby", "event_magnitude": "large", "distance": "500m", "weather": "clear, 22°C", "actual_covers": 95, "usual_covers": 60, "variance": "+58%", "staffing": 6, "notes": "High demand from concert attendees"},
        {"date": "2024-02-10", "day": "Saturday", "event_type": "festival", "event_name": "Jazz festival downtown", "event_magnitude": "medium", "distance": "800m", "weather": "sunny, 20°C", "actual_covers": 82, "usual_covers": 60, "variance": "+37%", "staffing": 5, "notes": "Steady flow throughout evening"},
        {"date": "2024-03-22", "day": "Friday", "event_type": "sports", "event_name": "Football match nearby", "event_magnitude": "large", "distance": "1km", "weather": "cloudy, 18°C", "actual_covers": 88, "usual_covers": 55, "variance": "+60%", "staffing": 6, "notes": "Pre-match crowd, quick service needed"},
        {"date": "2024-04-14", "day": "Sunday", "event_type": "fair", "event_name": "Food festival", "event_magnitude": "medium", "distance": "600m", "weather": "sunny, 24°C", "actual_covers": 70, "usual_covers": 45, "variance": "+56%", "staffing": 4, "notes": "Families, relaxed pace"},
        {"date": "2024-05-18", "day": "Saturday", "event_type": "concert", "event_name": "Rock concert", "event_magnitude": "large", "distance": "400m", "weather": "clear, 23°C", "actual_covers": 92, "usual_covers": 60, "variance": "+53%", "staffing": 6, "notes": "Young crowd, high energy"},
        {"date": "2024-06-08", "day": "Saturday", "event_type": "wedding", "event_name": "Wedding season peak", "event_magnitude": "small", "distance": "0m", "weather": "sunny, 26°C", "actual_covers": 75, "usual_covers": 60, "variance": "+25%", "staffing": 5, "notes": "In-house wedding party"},
        {"date": "2024-07-20", "day": "Saturday", "event_type": "festival", "event_name": "Summer music festival", "event_magnitude": "large", "distance": "700m", "weather": "hot, 30°C", "actual_covers": 85, "usual_covers": 60, "variance": "+42%", "staffing": 5, "notes": "Hot weather, drinks high demand"},
        {"date": "2024-08-25", "day": "Friday", "event_type": "corporate", "event_name": "Conference dinner", "event_magnitude": "medium", "distance": "0m", "weather": "clear, 25°C", "actual_covers": 78, "usual_covers": 55, "variance": "+42%", "staffing": 5, "notes": "Business crowd, wine focus"},
        {"date": "2024-09-14", "day": "Saturday", "event_type": "sports", "event_name": "Marathon event", "event_magnitude": "large", "distance": "1.5km", "weather": "cool, 17°C", "actual_covers": 65, "usual_covers": 60, "variance": "+8%", "staffing": 4, "notes": "Post-race crowd, late arrival"},
        {"date": "2024-10-30", "day": "Saturday", "event_type": "holiday", "event_name": "Halloween weekend", "event_magnitude": "medium", "distance": "0m", "weather": "rainy, 12°C", "actual_covers": 68, "usual_covers": 60, "variance": "+13%", "staffing": 4, "notes": "Theme-driven bookings"}
    ]
    
    points = []
    for idx, scenario in enumerate(scenarios):
        text = f"{scenario['day']} {scenario['event_type']}: {scenario['event_name']}. Distance: {scenario['distance']}, Weather: {scenario['weather']}. Resulted in {scenario['actual_covers']} covers (usual: {scenario['usual_covers']}, variance: {scenario['variance']}). Staffing: {scenario['staffing']}."
        embedding_response = mistral.embeddings.create(model="mistral-embed", inputs=[text])
        embedding = embedding_response.data[0].embedding
        point = PointStruct(id=str(uuid.uuid4()), vector=embedding, payload=scenario)
        points.append(point)
    
    qdrant.upsert(collection_name=collection_name, points=points)
    print(f"✅ Seeded {len(scenarios)} scenarios!")

# Seed on startup
@app.on_event("startup")
async def startup_event():
    seed_qdrant_on_startup()


# ---------- Modèles d'entrée / sortie ----------

class PredictionRequest(BaseModel):
    date: str           # ex: "2024-11-15"
    events: str         # ex: "Soirée DJ, promo cocktails, match de foot à 600m"
    weather: str        # ex: "Pluie faible, 12°C"


class PredictionResponse(BaseModel):
    date: str
    events: str
    weather: str
    expected_covers: int
    recommended_staff: int
    confidence: int
    key_factors: List[str]


# ---------- Endpoint principal ----------

@app.post("/predict", response_model=PredictionResponse)
def predict_covers(req: PredictionRequest) -> PredictionResponse:
    """
    Endpoint de prédiction :
    - Input : date future, événements prévus, météo
    - Process : Analyzer -> Qdrant vector search -> Predictor
    - Output : covers, staff, score de confiance
    """

    # 1) Construire une description compréhensible par l’agent
    event_description = (
        f"Date: {req.date}. "
        f"Events: {req.events}. "
        f"Weather forecast: {req.weather}."
    )

    # 2) Analyse + embedding
    analysis = analyzer.analyze(event_description)

    # 3) Recherche des patterns similaires dans Qdrant
    similar_patterns = pattern_searcher.search_similar_patterns(
        analysis["embedding"],
        limit=3,
    )

    # 4) Prédiction (covers / staff / confiance)
    prediction = predictor.predict(
        event_description=event_description,
        features=analysis["features"],
        similar_patterns=similar_patterns,
    )

    # (Optionnel pour l’API : génération audio)
    # voice_file = predictor.generate_voice_output(event_description, prediction)

    # 5) Normaliser la réponse
    return PredictionResponse(
        date=req.date,
        events=req.events,
        weather=req.weather,
        expected_covers=int(prediction["expected_covers"]),
        recommended_staff=int(prediction["recommended_staff"]),
        confidence=int(prediction["confidence"]),
        key_factors=prediction["key_factors"],
    )
