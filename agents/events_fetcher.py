"""
Events Fetcher Agent
Récupère les événements prévus à Paris
"""

import requests
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

class EventsFetcher:
    def __init__(self):
        # Option 1: PredictHQ (meilleur mais payant après essai)
        # self.api_key = os.getenv("PREDICTHQ_API_KEY")
        
        # Option 2: Serper (recherche Google)
        self.serper_key = os.getenv("SERPER_API_KEY")
    
    def get_events(self, date: str, city: str = "Paris") -> str:
        """
        Récupère les événements majeurs pour une date donnée
        """
        # Pour l'instant, simulation simple
        # TODO: Intégrer vraie API d'événements
        
        query = f"événements concerts match {city} {date}"
        
        url = "https://google.serper.dev/search"
        payload = {"q": query}
        headers = {
            "X-API-KEY": self.serper_key,
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            # Parser les résultats
            events = []
            for result in data.get("organic", [])[:3]:
                events.append(result["title"])
            
            events_text = ", ".join(events) if events else "Aucun événement majeur"
            print(f"🎪 Events found: {events_text}")
            return events_text
        else:
            return "Pas d'événements détectés"

# Test
if __name__ == "__main__":
    fetcher = EventsFetcher()
    events = fetcher.get_events("2024-11-20", "Paris")
    print(f"✅ Events: {events}")
