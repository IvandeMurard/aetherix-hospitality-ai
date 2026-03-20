"""
Create payload index on service_type field in Qdrant collection
This enables efficient filtering by service_type without warnings
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PayloadSchemaType

# Load environment from project root
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Config
COLLECTION_NAME = "fb_patterns"
INDEX_FIELD = "service_type"

def create_index():
    """Create payload index on service_type field"""
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_key = os.getenv("QDRANT_API_KEY")
    
    if not qdrant_url or not qdrant_key:
        print("ERROR: QDRANT_URL and QDRANT_API_KEY must be set in environment variables")
        sys.exit(1)
    
    print("=" * 60)
    print("CREATING QDRANT PAYLOAD INDEX")
    print("=" * 60)
    print(f"\nCollection: {COLLECTION_NAME}")
    print(f"Field: {INDEX_FIELD}")
    print(f"Type: keyword (for exact match filtering)")
    
    # Initialize Qdrant client
    qdrant = QdrantClient(
        url=qdrant_url,
        api_key=qdrant_key
    )
    
    # Check if collection exists
    collections = [c.name for c in qdrant.get_collections().collections]
    if COLLECTION_NAME not in collections:
        print(f"\nERROR: Collection '{COLLECTION_NAME}' not found")
        print(f"Available collections: {collections}")
        sys.exit(1)
    
    print(f"\n[OK] Collection '{COLLECTION_NAME}' found")
    
    # Create payload index
    try:
        print(f"\nCreating index on field '{INDEX_FIELD}'...")
        qdrant.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name=INDEX_FIELD,
            field_schema=PayloadSchemaType.KEYWORD
        )
        print(f"[OK] Index created successfully on '{INDEX_FIELD}'")
        
        # Verify the index was created
        collection_info = qdrant.get_collection(COLLECTION_NAME)
        if hasattr(collection_info, 'payload_schema') and collection_info.payload_schema:
            print(f"\n[OK] Index verified in collection schema")
            if INDEX_FIELD in collection_info.payload_schema:
                print(f"  - {INDEX_FIELD}: {collection_info.payload_schema[INDEX_FIELD]}")
        else:
            print(f"\n[INFO] Index created (schema info may not be immediately available)")
        
    except Exception as e:
        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
            print(f"\n[INFO] Index on '{INDEX_FIELD}' already exists")
            print("[OK] No action needed - index is ready for use")
        else:
            print(f"\n[ERROR] Failed to create index: {e}")
            import traceback
            print(f"\nTraceback:")
            print(traceback.format_exc())
            sys.exit(1)
    
    print("\n" + "=" * 60)
    print("INDEX CREATION COMPLETE")
    print("=" * 60)
    print("\nThe index is now available for filtering queries.")
    print("You can now use service_type filters without warnings.")

if __name__ == "__main__":
    create_index()
