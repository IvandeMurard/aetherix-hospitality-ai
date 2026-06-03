"""Update Git remote for HuggingFace Spaces with current token"""
import os
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# Get token
token = os.getenv("HF_TOKEN")
if not token:
    print("[ERROR] HF_TOKEN not found in .env")
    sys.exit(1)

# Update remote
remote_url = f"https://IvandeMurard:{token}@huggingface.co/spaces/IvandeMurard/fb-agent-api"
result = subprocess.run(
    ["git", "remote", "set-url", "space", remote_url],
    capture_output=True,
    text=True
)

if result.returncode == 0:
    print("[OK] Git remote 'space' updated successfully")
    print(f"[INFO] Remote URL: https://IvandeMurard:***@huggingface.co/spaces/IvandeMurard/fb-agent-api")
else:
    print(f"[ERROR] Failed to update remote: {result.stderr}")
    sys.exit(1)
