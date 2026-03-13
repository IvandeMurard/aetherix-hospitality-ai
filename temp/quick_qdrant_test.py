import os
from qdrant_client import QdrantClient
from dotenv import load_dotenv

def test_qdrant():
    # Load from root .env because backend .env is incomplete
    load_dotenv(dotenv_path="c:/Users/IVAN/Documents/fb-agent-mvp/.env")
    
    url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")
    
    print(f"Testing Qdrant Cloud at: {url}")
    if not url or not api_key:
        print("Error: QDRANT_URL or QDRANT_API_KEY not found in root .env")
        return

    try:
        client = QdrantClient(url=url, api_key=api_key)
        collections = client.get_collections()
        print("Success! Connected to Qdrant Cloud.")
        print(f"Available collections: {[c.name for c in collections.collections]}")
        
        if "fb_patterns" in [c.name for c in collections.collections]:
            count = client.count(collection_name="fb_patterns")
            print(f"Collection 'fb_patterns' exists with {count.count} points.")
        else:
            print("Warning: 'fb_patterns' collection NOT found.")
            
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    test_qdrant()
