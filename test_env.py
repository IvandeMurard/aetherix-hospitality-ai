import os
from dotenv import load_dotenv

load_dotenv()

required_keys = [
    "QDRANT_URL",
    "QDRANT_API_KEY",
    "MISTRAL_API_KEY",
    "ELEVENLABS_API_KEY",
    "PREDICTHQ_API_KEY",
    "OPENWEATHER_API_KEY"
]

print("🔍 Vérification du fichier .env\n")

all_ok = True
for key in required_keys:
    value = os.getenv(key)
    if value and value != "xxxxx":
        print(f"✅ {key}: Trouvée")
    else:
        print(f"❌ {key}: MANQUANTE")
        all_ok = False

print("\n" + "="*50)
if all_ok:
    print("✅ Toutes les clés sont configurées !")
else:
    print("❌ Certaines clés manquent. Vérifie ton .env")
