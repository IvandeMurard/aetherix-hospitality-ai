"""Check HuggingFace Space logs for debugging"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

try:
    from huggingface_hub import HfApi
except ImportError:
    print("[ERROR] huggingface_hub not installed")
    print("Install with: pip install huggingface_hub")
    sys.exit(1)

# Get HuggingFace token
hf_token = os.getenv("HF_TOKEN")
if not hf_token:
    print("[ERROR] HF_TOKEN not found in .env")
    sys.exit(1)

# Initialize API
api = HfApi(token=hf_token)
REPO_ID = "IvandeMurard/fb-agent-api"

print("=" * 60)
print("HUGGINGFACE SPACE LOGS")
print("=" * 60)
print(f"\nSpace: {REPO_ID}")
print("\nTo view logs, go to:")
print(f"  https://huggingface.co/spaces/{REPO_ID}/logs")
print("\nLook for:")
print("  - [INIT] messages showing Qdrant/Mistral client initialization")
print("  - [PATTERNS] messages showing which search method is used")
print("  - Any error messages about Qdrant connection")
