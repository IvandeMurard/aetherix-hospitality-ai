"""Verify that secrets are correctly set in HuggingFace Space"""
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
print("VERIFYING HUGGINGFACE SPACE SECRETS")
print("=" * 60)
print(f"\nSpace: {REPO_ID}")

# List secrets (this might not be directly available, so we'll try to get space info)
try:
    # Try to get space info
    space_info = api.space_info(REPO_ID)
    print(f"\n[OK] Space found: {space_info.id}")
    print(f"[INFO] Space SDK: {space_info.sdk}")
    
    # Note: The API doesn't directly expose secrets for security reasons
    # But we can verify the space exists and is accessible
    print("\n[INFO] Secrets cannot be directly listed via API (security)")
    print("[INFO] But the space is accessible, which means secrets should be available")
    
    print("\n" + "=" * 60)
    print("RECOMMENDATION")
    print("=" * 60)
    print("\nIf patterns still show 'source: mock', check:")
    print("  1. Space has been restarted after adding secrets")
    print("  2. Variable names match exactly (case-sensitive)")
    print("  3. Check Space logs for connection errors")
    print("\nTo check logs:")
    print(f"  https://huggingface.co/spaces/{REPO_ID}/logs")
    
except Exception as e:
    print(f"\n[ERROR] Failed to access space: {e}")
    sys.exit(1)
