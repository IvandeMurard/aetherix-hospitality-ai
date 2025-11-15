"""
Test script to verify .env file loading
"""

from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

print("=" * 60)
print("🔍 CHECKING ENVIRONMENT VARIABLES")
print("=" * 60)

# Check all expected keys
keys_to_check = {
    "PREDICTHQ_API_KEY": "PredictHQ",
    "OPENWEATHER_API_KEY": "OpenWeatherMap",
    "MISTRAL_API_KEY": "Mistral AI",
    "MISTRAL_API_kEY": "Mistral AI (lowercase k - typo?)",
    "QDRANT_API_KEY": "Qdrant",
    "ELEVENLABS_API_KEY": "ElevenLabs",
    "QDRANT_URL": "Qdrant URL"
}

print("\n📋 Environment Variables Status:\n")

for key, description in keys_to_check.items():
    value = os.getenv(key)
    if value:
        # Show first 10 chars and last 4 chars for security
        masked = f"{value[:10]}...{value[-4:]}" if len(value) > 14 else "***"
        print(f"✅ {key:25} ({description:20}) = {masked}")
    else:
        print(f"❌ {key:25} ({description:20}) = NOT FOUND")

print("\n" + "=" * 60)
print("💡 TIPS:")
print("=" * 60)
print("1. Make sure .env file is in the project root")
print("2. Variable names are CASE-SENSITIVE")
print("3. No spaces around the = sign")
print("4. Format: KEY=\"value\" or KEY=value")
print("=" * 60)
