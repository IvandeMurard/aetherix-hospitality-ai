"""
Autonomous Agent - Complete F&B Operations Agent
Combines all agents for end-to-end prediction
"""

import os
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict, Optional

from agents.analyzer import AnalyzerAgent
from agents.pattern_search import PatternSearcher
from agents.predictor import PredictorAgent
from agents.events_fetcher import EventsFetcher
from agents.weather_fetcher import WeatherFetcher

load_dotenv()

class AutonomousAgent:
    def __init__(self):
        """Initialize all agents"""
        print("🤖 Initializing Autonomous Agent...")
        self.analyzer = AnalyzerAgent()
        self.pattern_searcher = PatternSearcher()
        self.predictor = PredictorAgent()
        self.events_fetcher = EventsFetcher()
        self.weather_fetcher = WeatherFetcher()
        print("✅ All agents initialized\n")
    
    def predict_for_date(
        self,
        date: str,
        location: str = "Paris, France",
        city: str = "Paris",
        country: str = "FR"
    ) -> Dict:
        """
        Complete autonomous prediction for a specific date
        
        Args:
            date: Date in format "YYYY-MM-DD"
            location: Location string for events (e.g., "Paris, France")
            city: City name for weather
            country: Country code for weather
        
        Returns:
            Complete prediction dictionary
        """
        print(f"🤖 Autonomous Agent running for {date} in {location}...\n")
        
        # Step 1: Fetch weather
        print("=" * 60)
        print("STEP 1: Fetching Weather")
        print("=" * 60)
        weather = self.weather_fetcher.fetch_weather(city, country, date)
        weather_text = weather.get("description", "Unknown")
        
        # Step 2: Fetch events
        print("\n" + "=" * 60)
        print("STEP 2: Fetching Events")
        print("=" * 60)
        events = self.events_fetcher.fetch_events(date, location)
        
        # Build events description
        if events:
            event_names = [e.get("title", "Unknown") for e in events[:5]]
            events_text = ", ".join(event_names)
        else:
            events_text = "No major events found"
        
        # Step 3: Build event description
        event_description = (
            f"Date: {date}. "
            f"Events: {events_text}. "
            f"Weather forecast: {weather_text}."
        )
        
        # Step 4: Analyze
        print("\n" + "=" * 60)
        print("STEP 3: Analyzing Event")
        print("=" * 60)
        analysis = self.analyzer.analyze(event_description)
        
        # Step 5: Search patterns
        print("\n" + "=" * 60)
        print("STEP 4: Searching Similar Patterns")
        print("=" * 60)
        similar_patterns = self.pattern_searcher.search_similar_patterns(
            analysis["embedding"],
            limit=3
        )
        
        # Step 6: Generate prediction
        print("\n" + "=" * 60)
        print("STEP 5: Generating Prediction")
        print("=" * 60)
        prediction = self.predictor.predict(
            event_description=event_description,
            features=analysis["features"],
            similar_patterns=similar_patterns
        )
        
        # Step 7: Compile results
        result = {
            "date": date,
            "location": location,
            "weather": weather_text,
            "weather_details": weather,
            "events": events,
            "events_text": events_text,
            "features": analysis["features"],
            "similar_patterns": similar_patterns,
            "prediction": prediction
        }
        
        # Display results
        print("\n" + "=" * 60)
        print("🎯 AUTONOMOUS AGENT RESULT")
        print("=" * 60)
        print(f"Date: {result['date']}")
        print(f"Weather: {result['weather']}")
        print(f"Events: {result['events_text']}")
        print(f"\nExpected covers: {prediction['expected_covers']}")
        print(f"Recommended staff: {prediction['recommended_staff']}")
        print(f"Confidence: {prediction['confidence']}%")
        print(f"\nKey factors:")
        for i, factor in enumerate(prediction['key_factors'], 1):
            print(f"  {i}. {factor}")
        print("=" * 60)
        
        return result

# Test
if __name__ == "__main__":
    agent = AutonomousAgent()
    
    # Test with a specific date
    test_date = "2024-11-20"
    result = agent.predict_for_date(
        date=test_date,
        location="Paris, France",
        city="Paris",
        country="FR"
    )
    
    print(f"\n✅ Autonomous Agent completed successfully!")
    print(f"   Prediction saved in result dictionary")
