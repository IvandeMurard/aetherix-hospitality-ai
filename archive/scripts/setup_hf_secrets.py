"""
Script to configure HuggingFace Spaces environment variables via API
Alternative method if UI Settings menu is not accessible

Usage:
1. Get your HuggingFace token from: https://huggingface.co/settings/tokens
2. Add it to .env: HF_TOKEN=your_token_here
3. Run: python scripts/setup_hf_secrets.py
"""

import os
import sys
import io
from pathlib import Path

# Configure UTF-8 encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Try to import huggingface_hub
try:
    from huggingface_hub import HfApi
except ImportError:
    print("ERROR: huggingface_hub not installed")
    print("\nInstall it with:")
    print("  pip install huggingface_hub")
    print("\nOr add to requirements.txt and install:")
    print("  pip install -r requirements.txt")
    sys.exit(1)

from dotenv import load_dotenv

# Load .env to get API keys
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# HuggingFace Space configuration
REPO_ID = "IvandeMurard/fb-agent-api"

# Variables to set
VARIABLES = {
    "QDRANT_URL": os.getenv("QDRANT_URL"),
    "QDRANT_API_KEY": os.getenv("QDRANT_API_KEY"),
    "MISTRAL_API_KEY": os.getenv("MISTRAL_API_KEY"),
    "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
    "SUPABASE_URL": os.getenv("SUPABASE_URL"),
    "SUPABASE_KEY": os.getenv("SUPABASE_KEY"),
}

def setup_secrets():
    """Add secrets to HuggingFace Space"""
    print("=" * 60)
    print("HUGGINGFACE SPACES - SECRETS CONFIGURATION")
    print("=" * 60)
    print(f"\nSpace: {REPO_ID}")
    print("\nThis script will add the following secrets:")
    
    # Check which variables are available
    missing = []
    for key, value in VARIABLES.items():
        if value:
            print(f"  [OK] {key}: {'*' * min(len(value), 20)}... (length: {len(value)})")
        else:
            print(f"  [X] {key}: NOT FOUND in .env")
            missing.append(key)
    
    if missing:
        print(f"\n[WARN] Warning: {len(missing)} variable(s) not found in .env:")
        for key in missing:
            print(f"   - {key}")
        print("\nThese will be skipped.")
    
    # Get HuggingFace token
    hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
    if not hf_token:
        print("\n" + "=" * 60)
        print("ERROR: HuggingFace token not found")
        print("=" * 60)
        print("\nPlease set one of these environment variables:")
        print("  - HF_TOKEN")
        print("  - HUGGINGFACE_TOKEN")
        print("\nOr add it to your .env file:")
        print("  HF_TOKEN=your_huggingface_token_here")
        print("\nGet your token from: https://huggingface.co/settings/tokens")
        return False
    
    print(f"\n[OK] HuggingFace token found (length: {len(hf_token)})")
    
    # Initialize API
    try:
        api = HfApi(token=hf_token)
        print("[OK] API initialized")
    except Exception as e:
        print(f"[X] Failed to initialize API: {e}")
        return False
    
    # Add secrets
    print("\n" + "=" * 60)
    print("ADDING SECRETS...")
    print("=" * 60)
    
    success_count = 0
    for key, value in VARIABLES.items():
        if not value:
            print(f"\n[SKIP] Skipping {key} (not in .env)")
            continue
        
        try:
            # Add as secret (sensitive data)
            api.add_space_secret(
                repo_id=REPO_ID,
                key=key,
                value=value
            )
            print(f"[OK] Added secret: {key}")
            success_count += 1
        except Exception as e:
            print(f"[X] Failed to add {key}: {e}")
    
    print("\n" + "=" * 60)
    print(f"SUMMARY: {success_count}/{len([v for v in VARIABLES.values() if v])} secrets added")
    print("=" * 60)
    
    if success_count > 0:
        print("\n[OK] Secrets configured successfully!")
        print("\n[WARN] IMPORTANT: Restart your Space for changes to take effect:")
        print(f"   https://huggingface.co/spaces/{REPO_ID}")
        print("   Go to 'App' tab → Click 'Restart' button")
    
    return success_count > 0


if __name__ == "__main__":
    # Check if huggingface_hub is installed
    try:
        import huggingface_hub
    except ImportError:
        print("ERROR: huggingface_hub not installed")
        print("\nInstall it with:")
        print("  pip install huggingface_hub")
        exit(1)
    
    setup_secrets()
