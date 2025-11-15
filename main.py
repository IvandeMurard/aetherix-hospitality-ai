# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
import os
from qdrant_client import QdrantClient
from mistralai.client import MistralClient

app = FastAPI(title="F&B Operations Agent")

# Initialize clients
qdrant_client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)
mistral_client = MistralClient(api_key=os.getenv("MISTRAL_API_KEY"))

class PredictionRequest(BaseModel):
    date: str  # Format: "2024-11-20"
    events: List[str]  # ["Concert au Stade de France", "Salon Tech"]
    weather: str  # "sunny", "rainy", "cloudy"
    temperature: Optional[float] = 20.0

class PredictionResponse(BaseModel):
    date: str
    predicted_occupancy: float
    staff_recommendation: dict
    food_recommendations: dict
    confidence_score: float
    similar_patterns: List[dict]

@app.post("/predict", response_model=PredictionResponse)
async def predict_operations(request: PredictionRequest):
    """
    Prédiction des besoins en staff et F&B basée sur patterns historiques
    """
    try:
        # 1. Créer l'embedding de la requête
        query_text = f"Date: {request.date}, Events: {', '.join(request.events)}, Weather: {request.weather}, Temp: {request.temperature}°C"
        
        embedding_response = mistral_client.embeddings(
            model="mistral-embed",
            input=[query_text]
        )
        query_vector = embedding_response.data[0].embedding
        
        # 2. Recherche dans Qdrant
        search_results = qdrant_client.search(
            collection_name="hospitality_patterns",
            query_vector=query_vector,
            limit=5
        )
        
        # 3. Analyser les patterns similaires
        similar_patterns = []
        total_occupancy = 0
        total_staff = 0
        total_food_waste = 0
        
        for result in search_results:
            pattern = result.payload
            similar_patterns.append({
                "date": pattern.get("date"),
                "occupancy": pattern.get("occupancy_rate"),
                "similarity": result.score
            })
            
            # Pondération par score de similarité
            weight = result.score
            total_occupancy += pattern.get("occupancy_rate", 0) * weight
            total_staff += pattern.get("staff_needed", 0) * weight
            total_food_waste += pattern.get("food_waste_kg", 0) * weight
        
        # 4. Calcul des prédictions
        total_weight = sum(r.score for r in search_results)
        predicted_occupancy = total_occupancy / total_weight if total_weight > 0 else 0.5
        predicted_staff = total_staff / total_weight if total_weight > 0 else 10
        predicted_waste = total_food_waste / total_weight if total_weight > 0 else 5
        
        # 5. Recommandations
        staff_recommendation = {
            "servers": int(predicted_staff * 0.6),
            "kitchen": int(predicted_staff * 0.3),
            "management": int(predicted_staff * 0.1),
            "total": int(predicted_staff)
        }
        
        food_recommendations = {
            "prep_portions": int(100 * predicted_occupancy),
            "expected_waste_kg": round(predicted_waste, 2),
            "inventory_alert": "High demand expected" if predicted_occupancy > 0.7 else "Normal demand"
        }
        
        confidence_score = min(search_results[0].score if search_results else 0.5, 1.0)
        
        return PredictionResponse(
            date=request.date,
            predicted_occupancy=round(predicted_occupancy, 2),
            staff_recommendation=staff_recommendation,
            food_recommendations=food_recommendations,
            confidence_score=round(confidence_score, 2),
            similar_patterns=similar_patterns[:3]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "F&B Operations Agent"}
