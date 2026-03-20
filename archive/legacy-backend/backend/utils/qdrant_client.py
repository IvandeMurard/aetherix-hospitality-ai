# -*- coding: utf-8 -*-
"""
Qdrant Vector Database Client
Handles pattern storage and similarity search
"""

import os
import asyncio
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from dotenv import load_dotenv

load_dotenv()

class QdrantManager:
    def __init__(self):
        self.url = os.getenv("QDRANT_URL")
        self.api_key = os.getenv("QDRANT_API_KEY")
        
        if self.url and self.api_key:
            self.client = QdrantClient(
                url=self.url,
                api_key=self.api_key
            )
            self.mode = "cloud"
        else:
            # Use in-memory for local development
            # Warn if production but keys are missing
            if os.getenv("ENVIRONMENT") == "production":
                import warnings
                warnings.warn(
                    "QDRANT_URL and QDRANT_API_KEY not set in production. "
                    "Using in-memory database. This is not recommended for production. "
                    "See .env.example for reference."
                )
            self.client = QdrantClient(":memory:")
            self.mode = "memory"
    
    async def test_connection(self) -> dict:
        """
        Test Qdrant connection (async wrapper for synchronous client)
        """
        try:
            # Run synchronous operation in thread pool to avoid blocking
            collections = await asyncio.to_thread(self.client.get_collections)
            return {
                "status": "success",
                "message": "Qdrant connected successfully",
                "collections": len(collections.collections),
                "mode": self.mode
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    def create_collection(self, collection_name: str, vector_size: int = 1536):
        """
        Create a new collection for patterns
        """
        try:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
            )
            return {"status": "success", "collection": collection_name}
        except Exception as e:
            return {"status": "error", "message": str(e)}