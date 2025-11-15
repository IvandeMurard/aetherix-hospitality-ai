"""
Weather Fetcher Agent
Récupère la météo en temps réel pour Paris
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

class WeatherFetcher:
    def __init__(self):
        self.api_key = os.getenv("OPENWEATHER_API_KEY")
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"
    
    def get_weather(self, city: str = "Paris") -> str:
        """
        Récupère la météo actuelle pour une ville
        """
        params = {
            "q": city,
            "appid": self.api_key,
            "units": "metric",
            "lang": "fr"
        }
        
        response = requests.get(self.base_url, params=params)
        data = response.json()
        
        if response.status_code == 200:
            temp = data["main"]["temp"]
            weather = data["weather"][0]["description"]
            
            weather_text = f"{weather.capitalize()}, {temp:.0f}°C"
            print(f"🌤️ Weather fetched: {weather_text}")
            return weather_text
        else:
            return "Unknown weather"

# Test
if __name__ == "__main__":
    fetcher = WeatherFetcher()
    weather = fetcher.get_weather("Paris")
    print(f"✅ Weather: {weather}")
