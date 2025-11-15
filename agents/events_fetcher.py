"""
Events Fetcher Agent
Récupère les événements prévus à Paris via PredictHQ
"""

import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

class EventsFetcher:
    def __init__(self):
        self.api_key = os.getenv("PREDICTHQ_API_KEY")
        self.base_url = "https://api.predicthq.com/v1/events/"
    
    def get_events(self, date: str, city: str = "Paris") -> str:
        """
        Récupère les événements majeurs pour une date donnée à Paris
        """
        print(f"🎪 Fetching events for {date} in {city}...")
        
        # Convertir date en format ISO
        target_date = datetime.strptime(date, "%Y-%m-%d")
        date_from = target_date.strftime("%Y-%m-%d")
        date_to = (target_date + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Paramètres de recherche
        params = {
            "location_around.origin": "48.8566,2.3522",  # Coordonnées Paris
            "location_around.offset": "20km",
            "active.gte": date_from,
            "active.lte": date_to,
            "category": "concerts,sports,festivals,performing-arts",
            "limit": 5,
            "sort": "rank"  # Événements les plus importants
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }
        
        try:
            response = requests.get(self.base_url, params=params, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                events_list = []
                
                for event in data.get("results", []):
                    title = event.get("title", "Unknown event")
                    category = event.get("category", "event")
                    rank = event.get("rank", 0)
                    
                    events_list.append(f"{title} ({category})")
                    print(f"   - {title} (rank: {rank})")
                
                if events_list:
                    events_text = ", ".join(events_list[:3])  # Top 3 événements
                    return events_text
                else:
                    return "Pas d'événements majeurs détectés"
            
            elif response.status_code == 401:
                print(f"❌ Authentication error. Check your PREDICTHQ_API_KEY")
                return "Erreur d'authentification PredictHQ"
            
            else:
                print(f"❌ Error: {response.status_code}")
                return "Erreur lors de la récupération des événements"
        
        except Exception as e:
            print(f"❌ Exception: {e}")
            return "Erreur de connexion à PredictHQ"

# Test
if __name__ == "__main__":
    fetcher = EventsFetcher()
    
    # Test avec une date future
    events = fetcher.get_events("2024-11-20", "Paris")
    print(f"\n✅ Events found: {events}")
