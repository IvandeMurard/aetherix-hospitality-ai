from qdrant_client import QdrantClient

from qdrant_client.models import Distance, VectorParams

import os

from dotenv import load_dotenv

# Load environment variables

load_dotenv()

client = QdrantClient(

    url=os.getenv("QDRANT_URL"),

    api_key=os.getenv("QDRANT_API_KEY")

)

client.create_collection(

    collection_name="hospitality_patterns",

    vectors_config=VectorParams(

        size=1024,

        distance=Distance.COSINE

    )

)

print("✅ Qdrant collection 'hospitality_patterns' created!")
