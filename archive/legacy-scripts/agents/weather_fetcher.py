"""
Weather Fetcher Agent
Fetches weather forecast from OpenWeatherMap API
"""

import os
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict, Optional
import requests

load_dotenv()

class WeatherFetcher:
    def __init__(self):
        self.api_key = os.getenv("OPENWEATHER_API_KEY") or os.getenv("WEATHER_API_KEY")
        self.base_url = "https://api.openweathermap.org/data/2.5"
        
        if not self.api_key:
            print("⚠️  OPENWEATHER_API_KEY not found in environment variables")
            print("   Please add OPENWEATHER_API_KEY to your .env file")
            print("   Get your API key at: https://openweathermap.org/api")
            # Don't raise error, allow testing with mock data
    
    def fetch_weather(
        self, 
        city: str = "Paris",
        country: str = "FR",
        date: Optional[str] = None
    ) -> Dict:
        """
        Fetch current weather or forecast for a city
        
        Args:
            city: City name (e.g., "Paris")
            country: Country code (e.g., "FR")
            date: Optional date in format "YYYY-MM-DD" (for forecast)
        
        Returns:
            Dictionary with weather information
        """
        location = f"{city},{country}"
        
        if not self.api_key:
            print(f"🌤️  Weather API key not configured, using mock data")
            return self._get_mock_weather(city)
        
        try:
            # For current weather
            if not date or date == datetime.now().strftime("%Y-%m-%d"):
                url = f"{self.base_url}/weather"
                params = {
                    "q": location,
                    "appid": self.api_key,
                    "units": "metric",
                    "lang": "fr"
                }
            else:
                # For forecast (5-day forecast)
                url = f"{self.base_url}/forecast"
                params = {
                    "q": location,
                    "appid": self.api_key,
                    "units": "metric",
                    "lang": "fr"
                }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if "list" in data:  # Forecast data
                    # Find the forecast for the target date
                    target_date = datetime.strptime(date, "%Y-%m-%d").date()
                    for item in data["list"]:
                        item_date = datetime.fromtimestamp(item["dt"]).date()
                        if item_date == target_date:
                            weather_data = item
                            break
                    else:
                        # Use first available forecast
                        weather_data = data["list"][0]
                else:  # Current weather
                    weather_data = data
                
                # Extract weather info
                weather_main = weather_data["weather"][0]["main"]
                weather_desc = weather_data["weather"][0]["description"]
                temp = weather_data["main"]["temp"]
                feels_like = weather_data["main"]["feels_like"]
                humidity = weather_data["main"]["humidity"]
                
                # Format description in French
                weather_text = f"{weather_desc.capitalize()}, {int(temp)}°C"
                
                result = {
                    "description": weather_text,
                    "main": weather_main,
                    "temperature": int(temp),
                    "feels_like": int(feels_like),
                    "humidity": humidity,
                    "city": city,
                    "country": country
                }
                
                print(f"🌤️  Weather fetched: {weather_text}")
                return result
            else:
                print(f"   ⚠️  Weather API Error: {response.status_code}")
                return self._get_mock_weather(city)
                
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️  Weather request failed: {e}")
            return self._get_mock_weather(city)
    
    def _get_mock_weather(self, city: str) -> Dict:
        """Return mock weather data for testing"""
        import random
        conditions = ["Ensoleillé", "Nuageux", "Pluvieux", "Partiellement nuageux"]
        temps = [8, 12, 15, 18, 22, 25]
        
        condition = random.choice(conditions)
        temp = random.choice(temps)
        
        result = {
            "description": f"{condition}, {temp}°C",
            "main": condition.lower(),
            "temperature": temp,
            "feels_like": temp - 2,
            "humidity": 60,
            "city": city,
            "country": "FR"
        }
        
        print(f"🌤️  Weather (mock): {result['description']}")
        return result

# Test
if __name__ == "__main__":
    fetcher = WeatherFetcher()
    
    # Test with current weather
    weather = fetcher.fetch_weather("Paris", "FR")
    
    print(f"\n📊 Weather Details:")
    print(f"   City: {weather.get('city')}")
    print(f"   Description: {weather.get('description')}")
    print(f"   Temperature: {weather.get('temperature')}°C")
    print(f"   Feels like: {weather.get('feels_like')}°C")
    print(f"   Humidity: {weather.get('humidity')}%")
