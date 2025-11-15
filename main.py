# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from mistralai import Mistral
from elevenlabs.client import ElevenLabs
from elevenlabs import save
import json

load_dotenv()

app = FastAPI(title="F&B Operations Agent")

# Initialize clients
qdrant_client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)
mistral_client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))
elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

class PredictionRequest(BaseModel):
    date: str
    events: List[str]
    weather: str
    temperature: Optional[float] = 20.0
    voice_output: Optional[bool] = False

class PredictionResponse(BaseModel):
    date: str
    predicted_occupancy: float
    staff_recommendation: dict
    food_recommendations: dict
    confidence_score: float
    ai_insights: str
    similar_patterns: List[dict]
    audio_summary: Optional[str] = None

@app.post("/predict", response_model=PredictionResponse)
async def predict_operations(request: PredictionRequest):
    try:
        # 1. Créer l'embedding de la requête
        query_text = f"Date: {request.date}, Events: {', '.join(request.events)}, Weather: {request.weather}, Temp: {request.temperature}°C"
        
        embedding_response = mistral_client.embeddings.create(
            model="mistral-embed",
            inputs=[query_text]
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
                "similarity": round(result.score, 2)
            })
            
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
            "inventory_alert": "High demand" if predicted_occupancy > 0.7 else "Normal"
        }
        
        confidence_score = min(search_results[0].score if search_results else 0.5, 1.0)
        
        # 6. Mistral AI Insights (raisonnement qualitatif)
        context_data = {
            "occupancy": predicted_occupancy,
            "events": request.events,
            "weather": request.weather,
            "similar_days": len(search_results)
        }
        
        chat_response = mistral_client.chat.complete(
            model="mistral-small-latest",
            messages=[
                {
                    "role": "system",
                    "content": "Tu es un expert en gestion d'opérations F&B. Donne des insights courts et actionnables (3-4 phrases max)."
                },
                {
                    "role": "user",
                    "content": f"Prédiction pour {request.date}: Occupation {predicted_occupancy*100:.0f}%, Événements: {', '.join(request.events)}, Météo: {request.weather}. Staff recommandé: {staff_recommendation['total']}. Quels insights clés?"
                }
            ]
        )
        
        ai_insights = chat_response.choices[0].message.content
        
        # 7. Eleven Labs audio (optionnel)
        audio_path = None
        if request.voice_output:
            summary_text = f"Prédiction pour le {request.date}. Taux d'occupation prévu: {predicted_occupancy*100:.0f}%. {ai_insights}"
            
            audio = elevenlabs_client.generate(
                text=summary_text,
                voice="Rachel",
                model="eleven_multilingual_v2"
            )
            
            audio_path = f"audio_output_{request.date}.mp3"
            save(audio, audio_path)
        
        return PredictionResponse(
            date=request.date,
            predicted_occupancy=round(predicted_occupancy, 2),
            staff_recommendation=staff_recommendation,
            food_recommendations=food_recommendations,
            confidence_score=round(confidence_score, 2),
            ai_insights=ai_insights,
            similar_patterns=similar_patterns[:3],
            audio_summary=audio_path
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "F&B Operations Agent"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
