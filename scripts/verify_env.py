import os
import sys

from dotenv import load_dotenv

# Load environment variables from a local .env file if present.
# This lets you run the verifier directly on staging/localhost without
# having to export everything into the shell first.
load_dotenv()

REQUIRED_KEYS = [
    "ANTHROPIC_API_KEY",
    "BACKBOARD_API_KEY",
    "BACKBOARD_PROJECT_ID",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_WHATSAPP_NUMBER",
    "APALEO_CLIENT_ID",
    "APALEO_CLIENT_SECRET",
    "DATABASE_URL",
    "SECRET_KEY",
]


def verify() -> None:
    missing = [key for key in REQUIRED_KEYS if not os.getenv(key)]

    if missing:
        print("❌ CRITICAL: Missing required environment variables:")
        for m in missing:
            print(f"  - {m}")
        sys.exit(1)

    print("✅ Environment verification successful. All required keys found.")


if __name__ == "__main__":
    verify()
