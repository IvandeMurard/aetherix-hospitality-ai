"""
Autonomous F&B Operations Agent (MOCK VERSION)
"""

from agents.mock_data_fetcher import MockDataFetcher
from agents.analyzer import AnalyzerAgent
from agents.pattern_search import PatternSearcher
from agents.predictor import PredictorAgent

class AutonomousAgent:
    def __init__(self):
        self.data_fetcher = MockDataFetcher()
        self.analyzer = AnalyzerAgent()
        self.pattern_searcher = PatternSearcher()
        self.predictor = PredictorAgent()
    
    def predict_for_date(self, date: str, city: str = "Paris") -> dict:
        """
        Prédiction autonome avec données simulées
        """
        print(f"\n🤖 Autonomous Agent running for {date} in {city}...\n")
        
        # 1. Données simulées
        weather = self.data_fetcher.get_weather()
        events = self.data_fetcher.get_events(date)
        
        # 2. Pipeline de prédiction (RÉEL)
        event_description = f"Date: {date}. Events: {events}. Weather: {weather}."
        
        analysis = self.analyzer.analyze(event_description)
        similar_patterns = self.pattern_searcher.search_similar_patterns(
            analysis["embedding"], limit=3
        )
        prediction = self.predictor.predict(
            event_description, analysis["features"], similar_patterns
        )
        
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
    result = agent.predict_for_date("2024-11-23", "Paris")
    
    print("\n" + "="*60)
    print("🎯 AUTONOMOUS AGENT RESULT")
    print("="*60)
    print(f"Date: {result['date']}")
    print(f"Weather: {result['weather']}")
    print(f"Events: {result['events']}")
    print(f"Expected covers: {result['expected_covers']}")
    print(f"Recommended staff: {result['recommended_staff']}")
    print(f"Confidence: {result['confidence']}%")
    print("="*60)
