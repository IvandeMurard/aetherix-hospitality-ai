"""
Autonomous F&B Operations Agent
Entre juste une date → Récupère météo + événements → Prédit
"""

from agents.weather_fetcher import WeatherFetcher
from agents.events_fetcher import EventsFetcher
from agents.analyzer import AnalyzerAgent
from agents.pattern_search import PatternSearcher
from agents.predictor import PredictorAgent

class AutonomousAgent:
    def __init__(self):
        self.weather_fetcher = WeatherFetcher()
        self.events_fetcher = EventsFetcher()
        self.analyzer = AnalyzerAgent()
        self.pattern_searcher = PatternSearcher()
        self.predictor = PredictorAgent()
    
    def predict_for_date(self, date: str, city: str = "Paris") -> dict:
        """
        Prédiction autonome : juste une date en entrée
        """
        print(f"\n🤖 Autonomous Agent running for {date} in {city}...\n")
        
        # 1. Récupérer météo automatiquement
        weather = self.weather_fetcher.get_weather(city)
        
        # 2. Récupérer événements automatiquement
        events = self.events_fetcher.get_events(date, city)
        
        # 3. Construire la description
        event_description = (
            f"Date: {date}. "
            f"Events: {events}. "
            f"Weather forecast: {weather}."
        )
        
        # 4. Pipeline de prédiction
        analysis = self.analyzer.analyze(event_description)
        similar_patterns = self.pattern_searcher.search_similar_patterns(
            analysis["embedding"],
            limit=3
        )
        prediction = self.predictor.predict(
            event_description=event_description,
            features=analysis["features"],
            similar_patterns=similar_patterns
        )
        
        # 5. Génération voice (si ElevenLabs rechargé)
        try:
            voice_file = self.predictor.generate_voice_output(
                event_description, 
                prediction
            )
            prediction["voice_file"] = voice_file
        except Exception as e:
            print(f"⚠️ Voice generation skipped: {e}")
            prediction["voice_file"] = None
        
        return {
            "date": date,
            "city": city,
            "weather": weather,
            "events": events,
            **prediction
        }

# Test
if __name__ == "__main__":
    agent = AutonomousAgent()
    result = agent.predict_for_date("2024-11-20", "Paris")
    
    print("\n" + "="*60)
    print("🎯 AUTONOMOUS AGENT RESULT")
    print("="*60)
    print(f"Date: {result['date']}")
    print(f"Weather: {result['weather']}")
    print(f"Events: {result['events']}")
    print(f"Expected covers: {result['expected_covers']}")
    print(f"Recommended staff: {result['recommended_staff']}")
    print(f"Confidence: {result['confidence']}%")
    print(f"Key factors: {result['key_factors']}")
    print("="*60)
