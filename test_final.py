import requests

print("🧪 Test final du pipeline...\n")

url = "http://127.0.0.1:8000/predict"
payload = {
    "date": "2024-11-20",
    "events": "Concert Coldplay au Stade de France",
    "weather": "Ensoleillé, 22°C"
}

try:
    response = requests.post(url, json=payload)
    result = response.json()
    
    print("✅ API FONCTIONNE!")
    print(f"   Covers: {result['expected_covers']}")
    print(f"   Staff: {result['recommended_staff']}")
    print(f"   Confiance: {result['confidence']}%")
    print("\n🎉 PRÊT POUR LA DÉMO!")
    
except Exception as e:
    print(f"❌ Erreur: {e}")
    print("💡 Lance l'API : uvicorn api:app --reload --port 8000")

