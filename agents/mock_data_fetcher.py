"""
Mock Data Fetcher (sans API externes)
Simule événements et météo pour démo
"""

from datetime import datetime
import random

class MockDataFetcher:
    
    EVENTS_PARIS = {
        "weekday": [
            "Afterwork au Trocadéro",
            "Exposition au Grand Palais",
            "Concert jazz à La Villette"
        ],
        "weekend": [
            "Concert Coldplay au Stade de France",
            "PSG vs Marseille au Parc des Princes",
            "Festival Lollapalooza à l'Hippodrome",
            "Marathon de Paris",
            "Salon VivaTech Paris Expo"
        ],
        "special": [
            "Fête de la Musique - citywide",
            "14 Juillet fireworks at Eiffel Tower",
            "Fashion Week Paris",
            "Roland Garros tournament"
        ]
    }
    
    WEATHER_OPTIONS = [
        "Ensoleillé, 22°C",
        "Nuageux, 18°C",
        "Pluie légère, 15°C",
        "Ciel dégagé, 25°C",
        "Orageux, 19°C"
    ]
    
    def get_events(self, date: str) -> str:
        """Simule événements basés sur la date"""
        dt = datetime.strptime(date, "%Y-%m-%d")
        
        # Weekend = plus d'événements majeurs
        if dt.weekday() >= 5:  # Samedi/Dimanche
            events = random.sample(self.EVENTS_PARIS["weekend"], 2)
        else:
            events = random.sample(self.EVENTS_PARIS["weekday"], 1)
        
        events_text = ", ".join(events)
        print(f"🎪 Events simulés: {events_text}")
        return events_text
    
    def get_weather(self) -> str:
        """Simule météo aléatoire"""
        weather = random.choice(self.WEATHER_OPTIONS)
        print(f"🌤️ Météo simulée: {weather}")
        return weather

# Test
if __name__ == "__main__":
    fetcher = MockDataFetcher()
    events = fetcher.get_events("2024-11-23")  # Samedi
    weather = fetcher.get_weather()
    print(f"\n✅ Mock data working!")
