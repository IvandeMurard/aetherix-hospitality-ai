from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from mistralai import Mistral
import os
import asyncio
from typing import List, Dict, Any, Optional
from datetime import date

class RAGService:
    """
    RAG Service for pattern retrieval from Qdrant.
    Used for providing contextual explanations and historical context.
    """
    
    def __init__(self):
        self.qdrant_url = os.getenv("QDRANT_URL")
        self.qdrant_key = os.getenv("QDRANT_API_KEY")
        self.mistral_key = os.getenv("MISTRAL_API_KEY")
        
        self.qdrant_client = QdrantClient(url=self.qdrant_url, api_key=self.qdrant_key) if self.qdrant_url else None
        self.mistral_client = Mistral(api_key=self.mistral_key) if self.mistral_key else None

    async def get_embedding(self, text: str) -> List[float]:
        """Fetches embedding from Mistral."""
        if not self.mistral_client:
            return [0.0] * 1024 # Dummy for dev
        
        response = await asyncio.to_thread(
            self.mistral_client.embeddings.create,
            model="mistral-embed",
            inputs=[text]
        )
        return response.data[0].embedding

    async def find_similar_patterns(
        self, 
        query_text: str, 
        service_type: str, 
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """Searches Qdrant for similar patterns based on context string."""
        if not self.qdrant_client:
            return []
            
        embedding = await self.get_embedding(query_text)
        
        search_filter = Filter(
            must=[
                FieldCondition(
                    key="service_type",
                    match=MatchValue(value=service_type)
                )
            ]
        )
        
        results = await asyncio.to_thread(
            self.qdrant_client.query_points,
            collection_name="fb_patterns",
            query=embedding,
            query_filter=search_filter,
            limit=limit,
            with_payload=True
        )
        
        return [
            {
                "id": p.id,
                "score": p.score,
                "payload": p.payload
            } for p in results.points
        ]

    def build_context_string(self, target_date: date, service_type: str, context: Dict[str, Any]) -> str:
        """Helper to build a standardized context string for embedding query."""
        weather = context.get('weather', {})
        events = context.get('events', [])
        events_str = ", ".join([e.get('type', 'Event') for e in events]) or "None"
        
        return f"""Date: {target_date.isoformat()}
Service: {service_type}
Weather: {weather.get('condition', 'Unknown')}
Events: {events_str}
Hotel Occupancy: {context.get('occupancy', 0.8)}
"""
