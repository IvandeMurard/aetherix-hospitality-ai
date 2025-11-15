import requests
import json

url = "http://localhost:8000/predict"

payload = {
    "date": "2024-11-20",
    "events": ["Concert Stade de France", "Salon VivaTech"],
    "weather": "sunny",
    "temperature": 22
}

response = requests.post(url, json=payload)
print(json.dumps(response.json(), indent=2))
