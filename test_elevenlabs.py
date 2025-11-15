from elevenlabs.client import ElevenLabs
import os
from dotenv import load_dotenv

load_dotenv()

# Try both possible environment variable names
api_key = os.getenv("ELEVENLABS_API_KEY") or os.getenv("ELEVEN_LABS_API_KEY")
client = ElevenLabs(api_key=api_key)

# Test simple with NEW API
print("🔊 Testing ElevenLabs API...")
audio = client.text_to_speech.convert(
    voice_id="EXAVITQu4vr4xnSDxMaL",  # Sarah voice
    text="This is a test",
    model_id="eleven_multilingual_v2"
)

# Save audio file
filename = "test_voice.mp3"
with open(filename, "wb") as f:
    for chunk in audio:
        if chunk:
            f.write(chunk)

print(f"✅ ElevenLabs working! Check {filename}")

