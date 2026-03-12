import os
import sys

REQUIRED_KEYS = [
    "ANTHROPIC_API_KEY",
    "BACKBOARD_API_KEY",
    "BACKBOARD_PROJECT_ID",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_WHATSAPP_NUMBER",
    "APALEO_CLIENT_ID",
    "APALEO_CLIENT_SECRET"
]

def verify():
    missing = [key for key in REQUIRED_KEYS if not os.getenv(key)]
    
    if missing:
        print("❌ CRITICAL: Missing required environment variables:")
        for m in missing:
            print(f"  - {m}")
        sys.exit(1)
    
    print("✅ Environment verification successful. All required keys found.")

if __name__ == "__main__":
    verify()
