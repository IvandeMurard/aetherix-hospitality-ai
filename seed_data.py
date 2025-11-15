from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Distance, VectorParams
from mistralai import Mistral
import os
from dotenv import load_dotenv
import uuid

load_dotenv()

# Initialize clients  
qdrant = QdrantClient(":memory:")

# Create collection if it doesn't exist
try:
    qdrant.create_collection(
        collection_name="hospitality_patterns",
        vectors_config=VectorParams(
            size=1024,  # Mistral embedding size
            distance=Distance.COSINE
        )
    )
    print("OK Collection created!")
except Exception as e:
    # Collection might already exist, that's ok
    print(f"INFO Collection setup: {e}")

mistral = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))

# Historical scenarios
scenarios = [
    {
        "date": "2024-01-15",
        "day": "Saturday",
        "event_type": "concert",
        "event_name": "Coldplay concert nearby",
        "event_magnitude": "large",
        "distance": "500m",
        "weather": "clear, 22°C",
        "actual_covers": 95,
        "usual_covers": 60,
        "variance": "+58%",
        "staffing": 6,
        "notes": "High demand from concert attendees"
    },
    {
        "date": "2024-02-10",
        "day": "Saturday",
        "event_type": "festival",
        "event_name": "Jazz festival downtown",
        "event_magnitude": "medium",
        "distance": "800m",
        "weather": "sunny, 20°C",
        "actual_covers": 82,
        "usual_covers": 60,
        "variance": "+37%",
        "staffing": 5,
        "notes": "Steady flow throughout evening"
    },
    {
        "date": "2024-03-22",
        "day": "Friday",
        "event_type": "sports",
        "event_name": "Football match nearby",
        "event_magnitude": "large",
        "distance": "1km",
        "weather": "cloudy, 18°C",
        "actual_covers": 88,
        "usual_covers": 55,
        "variance": "+60%",
        "staffing": 6,
        "notes": "Pre-match crowd, quick service needed"
    },
    {
        "date": "2024-04-14",
        "day": "Sunday",
        "event_type": "fair",
        "event_name": "Food festival",
        "event_magnitude": "medium",
        "distance": "600m",
        "weather": "sunny, 24°C",
        "actual_covers": 70,
        "usual_covers": 45,
        "variance": "+56%",
        "staffing": 4,
        "notes": "Families, relaxed pace"
    },
    {
        "date": "2024-05-18",
        "day": "Saturday",
        "event_type": "concert",
        "event_name": "Rock concert",
        "event_magnitude": "large",
        "distance": "400m",
        "weather": "clear, 23°C",
        "actual_covers": 92,
        "usual_covers": 60,
        "variance": "+53%",
        "staffing": 6,
        "notes": "Young crowd, high energy"
    },
    {
        "date": "2024-06-08",
        "day": "Saturday",
        "event_type": "wedding",
        "event_name": "Wedding season peak",
        "event_magnitude": "small",
        "distance": "0m",
        "weather": "sunny, 26°C",
        "actual_covers": 75,
        "usual_covers": 60,
        "variance": "+25%",
        "staffing": 5,
        "notes": "In-house wedding party"
    },
    {
        "date": "2024-07-20",
        "day": "Saturday",
        "event_type": "festival",
        "event_name": "Summer music festival",
        "event_magnitude": "large",
        "distance": "700m",
        "weather": "hot, 30°C",
        "actual_covers": 85,
        "usual_covers": 60,
        "variance": "+42%",
        "staffing": 5,
        "notes": "Hot weather, drinks high demand"
    },
    {
        "date": "2024-08-25",
        "day": "Friday",
        "event_type": "corporate",
        "event_name": "Conference dinner",
        "event_magnitude": "medium",
        "distance": "0m",
        "weather": "clear, 25°C",
        "actual_covers": 78,
        "usual_covers": 55,
        "variance": "+42%",
        "staffing": 5,
        "notes": "Business crowd, wine focus"
    },
    {
        "date": "2024-09-14",
        "day": "Saturday",
        "event_type": "sports",
        "event_name": "Marathon event",
        "event_magnitude": "large",
        "distance": "1.5km",
        "weather": "cool, 17°C",
        "actual_covers": 65,
        "usual_covers": 60,
        "variance": "+8%",
        "staffing": 4,
        "notes": "Post-race crowd, late arrival"
    },
    {
        "date": "2024-10-30",
        "day": "Saturday",
        "event_type": "holiday",
        "event_name": "Halloween weekend",
        "event_magnitude": "medium",
        "distance": "0m",
        "weather": "rainy, 12°C",
        "actual_covers": 68,
        "usual_covers": 60,
        "variance": "+13%",
        "staffing": 4,
        "notes": "Theme-driven bookings"
    }
]

# Generate embeddings and upload
points = []

for idx, scenario in enumerate(scenarios):
    # Create text description for embedding
    text = f"{scenario['day']} {scenario['event_type']}: {scenario['event_name']}. " \
           f"Distance: {scenario['distance']}, Weather: {scenario['weather']}. " \
           f"Resulted in {scenario['actual_covers']} covers (usual: {scenario['usual_covers']}, " \
           f"variance: {scenario['variance']}). Staffing: {scenario['staffing']}."
    
    # Generate embedding with Mistral
    print(f"Generating embedding {idx+1}/10...")
    embedding_response = mistral.embeddings.create(
        model="mistral-embed",
        inputs=[text]
    )
    
    embedding = embedding_response.data[0].embedding
    
    # Create point
    point = PointStruct(
        id=str(uuid.uuid4()),
        vector=embedding,
        payload=scenario
    )
    
    points.append(point)

# Upload to Qdrant
print("Uploading to Qdrant...")
qdrant.upsert(
    collection_name="hospitality_patterns",
    points=points
)

print(f"OK Successfully seeded {len(scenarios)} scenarios!")
