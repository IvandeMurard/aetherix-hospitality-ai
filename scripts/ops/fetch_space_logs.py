"""Fetch HuggingFace Space logs via API"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import requests

# Load .env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# Get HuggingFace token
hf_token = os.getenv("HF_TOKEN")
if not hf_token:
    print("[ERROR] HF_TOKEN not found in .env")
    sys.exit(1)

REPO_ID = "IvandeMurard/fb-agent-api"
BASE_URL = f"https://huggingface.co/api/spaces/{REPO_ID}/logs"

print("=" * 60)
print("FETCHING HUGGINGFACE SPACE LOGS")
print("=" * 60)
print(f"\nSpace: {REPO_ID}")

headers = {
    "Authorization": f"Bearer {hf_token}"
}

# Fetch application logs
print("\n" + "=" * 60)
print("APPLICATION LOGS (run)")
print("=" * 60)
try:
    response = requests.get(f"{BASE_URL}/run", headers=headers, stream=True, timeout=10)
    if response.status_code == 200:
        # Read first 2000 characters
        content = ""
        for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
            content += chunk
            if len(content) > 2000:
                break
        print(content[:2000])
        if len(content) > 2000:
            print("\n... (truncated, see full logs at https://huggingface.co/spaces/IvandeMurard/fb-agent-api/logs)")
    else:
        print(f"[ERROR] Failed to fetch logs: {response.status_code}")
        print(response.text[:500])
except Exception as e:
    print(f"[ERROR] Failed to fetch logs: {e}")

print("\n" + "=" * 60)
print("BUILD LOGS")
print("=" * 60)
try:
    response = requests.get(f"{BASE_URL}/build", headers=headers, stream=True, timeout=10)
    if response.status_code == 200:
        content = ""
        for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
            content += chunk
            if len(content) > 2000:
                break
        print(content[:2000])
        if len(content) > 2000:
            print("\n... (truncated)")
    else:
        print(f"[ERROR] Failed to fetch build logs: {response.status_code}")
except Exception as e:
    print(f"[ERROR] Failed to fetch build logs: {e}")

print("\n" + "=" * 60)
print("FULL LOGS URL")
print("=" * 60)
print(f"  https://huggingface.co/spaces/{REPO_ID}/logs")
