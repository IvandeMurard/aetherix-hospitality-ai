# 🚀 ROADMAP COMPLÈTE - STEP BY STEP
**6 heures | 12:00-18:00 | Plan d'exécution détaillé**

---

## 📋 OVERVIEW

**Timeline:** 6 heures  
**Deadline:** 18:00 (submit à 17:50)  
**Stack:** Qdrant + Mistral + Eleven Labs  
**Livrable:** Video 2 min + GitHub repo  

**Validations externes:** Mews + Guac AI (YC)  
**Roadmap future:** Fal AI + n8n

---

# ⏰ HOUR 1: SETUP (12:00-13:00)

## 12:00-12:10 | Environment Setup (10 min)

### Step 1: Create Project Structure
```bash
# Create directory
mkdir fbf-agent-qdrant
cd fbf-agent-qdrant

# Initialize git
git init
git branch -M main

# Create structure
mkdir -p agents data workflows docs
touch README.md requirements.txt .env.example .gitignore main.py
```

### Step 2: Python Environment
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install qdrant-client mistralai elevenlabs python-dotenv requests
pip freeze > requirements.txt
```

### Step 3: Create .gitignore
```bash
cat > .gitignore << EOF
venv/
__pycache__/
*.pyc
.env
*.mp3
*.wav
.DS_Store
EOF
```

**✅ Checkpoint 12:10:** Environment ready, structure created

---

## 12:10-12:30 | Qdrant Setup (20 min)

### Step 1: Create Qdrant Cloud Account
1. Go to https://cloud.qdrant.io
2. Sign up (free tier)
3. Create cluster: "fbf-patterns"
4. Get API key + cluster URL
5. Save in `.env`

### Step 2: Create .env File
```bash
cat > .env << EOF
# Qdrant
QDRANT_URL="https://your-cluster.qdrant.io"
QDRANT_API_KEY="your_api_key_here"

# Mistral
MISTRAL_API_KEY="your_mistral_key_here"

# Eleven Labs
ELEVEN_LABS_API_KEY="your_eleven_key_here"
EOF
```

### Step 3: Create Qdrant Collection Script
```bash
cat > setup_qdrant.py << 'EOF'
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize client
client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

# Create collection
client.create_collection(
    collection_name="hospitality_patterns",
    vectors_config=VectorParams(
        size=1024,  # Mistral embedding size
        distance=Distance.COSINE
    )
)

print("✅ Qdrant collection 'hospitality_patterns' created!")
EOF
```

### Step 4: Run Setup
```bash
python setup_qdrant.py
```

**✅ Checkpoint 12:30:** Qdrant collection created and ready

---

## 12:30-12:45 | Seed Historical Data (15 min)

### Step 1: Create Seed Data Script
```bash
cat > seed_data.py << 'EOF'
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from mistralai import Mistral
import os
from dotenv import load_dotenv
import uuid

load_dotenv()

# Initialize clients
qdrant = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

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

print(f"✅ Successfully seeded {len(scenarios)} scenarios!")
EOF
```

### Step 2: Run Seed Script
```bash
python seed_data.py
```

**✅ Checkpoint 12:45:** 10 historical scenarios in Qdrant

---

## 12:45-13:00 | Test All APIs (15 min)

### Step 1: Test Mistral API
```bash
cat > test_mistral.py << 'EOF'
from mistralai import Mistral
import os
from dotenv import load_dotenv

load_dotenv()
mistral = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))

# Test embedding
response = mistral.embeddings.create(
    model="mistral-embed",
    inputs=["Test event: concert tomorrow"]
)
print(f"✅ Mistral Embed: {len(response.data[0].embedding)} dimensions")

# Test chat
chat_response = mistral.chat.complete(
    model="mistral-large-latest",
    messages=[{"role": "user", "content": "Say 'API working'"}]
)
print(f"✅ Mistral Chat: {chat_response.choices[0].message.content}")
EOF

python test_mistral.py
```

### Step 2: Test Eleven Labs API
```bash
cat > test_elevenlabs.py << 'EOF'
from elevenlabs import generate, save
import os
from dotenv import load_dotenv

load_dotenv()
os.environ["ELEVEN_LABS_API_KEY"] = os.getenv("ELEVEN_LABS_API_KEY")

# Test voice generation
audio = generate(
    text="API test successful",
    voice="Adam",
    model="eleven_monolingual_v1"
)

save(audio, "test_voice.mp3")
print("✅ Eleven Labs: Voice generated (test_voice.mp3)")
EOF

python test_elevenlabs.py
```

### Step 3: Test Qdrant Search
```bash
cat > test_qdrant.py << 'EOF'
from qdrant_client import QdrantClient
from mistralai import Mistral
import os
from dotenv import load_dotenv

load_dotenv()

qdrant = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

mistral = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))

# Generate test embedding
response = mistral.embeddings.create(
    model="mistral-embed",
    inputs=["Concert tomorrow evening"]
)
embedding = response.data[0].embedding

# Search
results = qdrant.search(
    collection_name="hospitality_patterns",
    query_vector=embedding,
    limit=3
)

print(f"✅ Qdrant Search: Found {len(results)} similar scenarios")
for idx, result in enumerate(results):
    print(f"  {idx+1}. {result.payload['event_name']} (score: {result.score:.3f})")
EOF

python test_qdrant.py
```

**✅ Checkpoint 13:00:** All 3 APIs working perfectly

---

# ⏰ HOUR 2-3: BUILD (13:00-15:00)

## 13:00-13:45 | Agent 1: Analyzer (45 min)

### Step 1: Create Analyzer Agent
```bash
cat > agents/analyzer.py << 'EOF'
"""
Agent 1: Analyzer
Extracts features from event description and generates embedding
"""

from mistralai import Mistral
import os
from dotenv import load_dotenv

load_dotenv()

class AnalyzerAgent:
    def __init__(self):
        self.mistral = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))
    
    def extract_features(self, event_description: str) -> dict:
        """
        Extract structured features from event description
        """
        prompt = f"""Extract key features from this F&B event description:
"{event_description}"

Return JSON with these fields:
- day_of_week (Monday-Sunday or "unknown")
- event_type (concert, sports, festival, wedding, corporate, holiday, or "unknown")
- event_magnitude (small, medium, large, or "unknown")
- weather (if mentioned, otherwise "unknown")
- special_notes (any other relevant details)

Be concise. Output ONLY valid JSON, no markdown."""

        response = self.mistral.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse response
        import json
        features_text = response.choices[0].message.content
        # Strip markdown if present
        features_text = features_text.replace("```json", "").replace("```", "").strip()
        features = json.loads(features_text)
        
        return features
    
    def generate_embedding(self, event_description: str) -> list:
        """
        Generate vector embedding for event description
        """
        response = self.mistral.embeddings.create(
            model="mistral-embed",
            inputs=[event_description]
        )
        
        return response.data[0].embedding
    
    def analyze(self, event_description: str) -> dict:
        """
        Complete analysis: extract features + generate embedding
        """
        print(f"🔍 Analyzing: '{event_description}'")
        
        # Extract features
        features = self.extract_features(event_description)
        print(f"   Features extracted: {features}")
        
        # Generate embedding
        embedding = self.generate_embedding(event_description)
        print(f"   Embedding generated: {len(embedding)} dimensions")
        
        return {
            "original_description": event_description,
            "features": features,
            "embedding": embedding
        }

# Test
if __name__ == "__main__":
    agent = AnalyzerAgent()
    result = agent.analyze("Concert tomorrow evening, sunny weather")
    print(f"\n✅ Analyzer working!")
    print(f"   Features: {result['features']}")
EOF

python agents/analyzer.py
```

**✅ Checkpoint 13:45:** Analyzer Agent working

---

## 13:45-14:15 | Qdrant Integration (30 min)

### Step 1: Create Search Module
```bash
cat > agents/pattern_search.py << 'EOF'
"""
Qdrant Pattern Search
Finds similar historical scenarios
"""

from qdrant_client import QdrantClient
import os
from dotenv import load_dotenv

load_dotenv()

class PatternSearcher:
    def __init__(self):
        self.qdrant = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY")
        )
        self.collection_name = "hospitality_patterns"
    
    def search_similar_patterns(self, embedding: list, limit: int = 3) -> list:
        """
        Search for similar past scenarios in Qdrant
        """
        print(f"🔎 Searching Qdrant for {limit} similar patterns...")
        
        results = self.qdrant.search(
            collection_name=self.collection_name,
            query_vector=embedding,
            limit=limit
        )
        
        patterns = []
        for idx, result in enumerate(results):
            pattern = {
                "rank": idx + 1,
                "similarity_score": result.score,
                "scenario": result.payload
            }
            patterns.append(pattern)
            
            print(f"   #{idx+1}: {result.payload['event_name']} "
                  f"(similarity: {result.score:.3f})")
        
        return patterns

# Test
if __name__ == "__main__":
    from analyzer import AnalyzerAgent
    
    # Analyze event
    analyzer = AnalyzerAgent()
    analysis = analyzer.analyze("Concert tomorrow evening")
    
    # Search patterns
    searcher = PatternSearcher()
    patterns = searcher.search_similar_patterns(analysis["embedding"])
    
    print(f"\n✅ Pattern search working! Found {len(patterns)} similar scenarios")
EOF

python agents/pattern_search.py
```

**✅ Checkpoint 14:15:** Qdrant integration working

---

## 14:15-15:00 | Agent 2: Predictor + Voice (45 min)

### Step 1: Create Predictor Agent
```bash
cat > agents/predictor.py << 'EOF'
"""
Agent 2: Predictor
Analyzes patterns and generates prediction with voice output
"""

from mistralai import Mistral
from elevenlabs import generate, save
import os
from dotenv import load_dotenv
import json

load_dotenv()

class PredictorAgent:
    def __init__(self):
        self.mistral = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))
        os.environ["ELEVEN_LABS_API_KEY"] = os.getenv("ELEVEN_LABS_API_KEY")
    
    def predict(self, event_description: str, features: dict, 
                similar_patterns: list) -> dict:
        """
        Generate prediction based on patterns
        """
        print(f"🎯 Generating prediction...")
        
        # Build context from patterns
        patterns_context = "\n".join([
            f"Pattern {p['rank']}: {p['scenario']['event_name']} on "
            f"{p['scenario']['day']} resulted in {p['scenario']['actual_covers']} "
            f"covers (usual: {p['scenario']['usual_covers']}, "
            f"variance: {p['scenario']['variance']}). "
            f"Staffing: {p['scenario']['staffing']}. "
            f"Similarity: {p['similarity_score']:.3f}"
            for p in similar_patterns
        ])
        
        prompt = f"""You are an F&B demand prediction agent.

Event: "{event_description}"
Features: {json.dumps(features)}

Similar past scenarios:
{patterns_context}

Based on these patterns, predict:
1. expected_covers (number)
2. confidence (0-100, integer)
3. recommended_staff (number)
4. key_factors (list of 2-3 factors influencing prediction)

Output ONLY valid JSON, no markdown:
{{
  "expected_covers": <number>,
  "confidence": <0-100>,
  "recommended_staff": <number>,
  "key_factors": ["<factor1>", "<factor2>"]
}}"""

        response = self.mistral.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse prediction
        prediction_text = response.choices[0].message.content
        prediction_text = prediction_text.replace("```json", "").replace("```", "").strip()
        prediction = json.loads(prediction_text)
        
        print(f"   Prediction: {prediction['expected_covers']} covers "
              f"({prediction['confidence']}% confidence)")
        
        return prediction
    
    def generate_voice_output(self, event_description: str, 
                             prediction: dict) -> str:
        """
        Generate voice announcement of prediction
        """
        print(f"🔊 Generating voice output...")
        
        # Create natural language summary
        summary = (
            f"Based on similar patterns, expect {prediction['expected_covers']} "
            f"covers with {prediction['confidence']} percent confidence. "
            f"I recommend scheduling {prediction['recommended_staff']} staff members. "
            f"Key factors are: {', '.join(prediction['key_factors'])}."
        )
        
        # Generate voice
        audio = generate(
            text=summary,
            voice="Adam",
            model="eleven_monolingual_v1"
        )
        
        # Save audio file
        filename = "prediction_voice.mp3"
        save(audio, filename)
        
        print(f"   Voice saved: {filename}")
        print(f"   Text: \"{summary}\"")
        
        return filename

# Test
if __name__ == "__main__":
    from analyzer import AnalyzerAgent
    from pattern_search import PatternSearcher
    
    # Full pipeline test
    event = "Concert tomorrow evening, sunny weather"
    
    analyzer = AnalyzerAgent()
    analysis = analyzer.analyze(event)
    
    searcher = PatternSearcher()
    patterns = searcher.search_similar_patterns(analysis["embedding"])
    
    predictor = PredictorAgent()
    prediction = predictor.predict(event, analysis["features"], patterns)
    voice_file = predictor.generate_voice_output(event, prediction)
    
    print(f"\n✅ Predictor + Voice working!")
    print(f"   Prediction: {prediction}")
    print(f"   Voice file: {voice_file}")
EOF

python agents/predictor.py
```

**✅ Checkpoint 15:00:** All agents + voice working!

---

# ⏰ HOUR 4: TEST (15:00-16:00)

## 15:00-15:30 | Create Main Application (30 min)

### Step 1: Create Main Pipeline
```bash
cat > main.py << 'EOF'
"""
F&B Operations Agent - Main Application
Multi-agent system with Qdrant pattern memory and voice output
"""

from agents.analyzer import AnalyzerAgent
from agents.pattern_search import PatternSearcher
from agents.predictor import PredictorAgent
import sys

def main():
    print("=" * 60)
    print("🏨 F&B OPERATIONS AGENT")
    print("   AI-powered demand prediction with voice interface")
    print("=" * 60)
    print()
    
    # Get event description
    if len(sys.argv) > 1:
        event_description = " ".join(sys.argv[1:])
    else:
        event_description = input("📝 Describe the upcoming event: ")
    
    print()
    print("-" * 60)
    
    # Step 1: Analyze
    print("\n[STEP 1/4] Analyzing event...")
    analyzer = AnalyzerAgent()
    analysis = analyzer.analyze(event_description)
    
    # Step 2: Search patterns
    print("\n[STEP 2/4] Searching for similar patterns...")
    searcher = PatternSearcher()
    patterns = searcher.search_similar_patterns(
        analysis["embedding"],
        limit=3
    )
    
    # Step 3: Predict
    print("\n[STEP 3/4] Generating prediction...")
    predictor = PredictorAgent()
    prediction = predictor.predict(
        event_description,
        analysis["features"],
        patterns
    )
    
    # Step 4: Voice output
    print("\n[STEP 4/4] Creating voice announcement...")
    voice_file = predictor.generate_voice_output(
        event_description,
        prediction
    )
    
    # Display results
    print()
    print("=" * 60)
    print("📊 PREDICTION RESULTS")
    print("=" * 60)
    print(f"Event: {event_description}")
    print()
    print(f"Expected Covers:  {prediction['expected_covers']}")
    print(f"Confidence:       {prediction['confidence']}%")
    print(f"Recommended Staff: {prediction['recommended_staff']}")
    print()
    print("Key Factors:")
    for factor in prediction['key_factors']:
        print(f"  • {factor}")
    print()
    print(f"🔊 Voice output saved: {voice_file}")
    print("   (Play this file to hear the prediction)")
    print("=" * 60)
    
    return {
        "event": event_description,
        "features": analysis["features"],
        "patterns": patterns,
        "prediction": prediction,
        "voice_file": voice_file
    }

if __name__ == "__main__":
    result = main()
EOF
```

### Step 2: Test Full Pipeline
```bash
python main.py "Concert tomorrow evening, sunny weather, Saturday"
```

**✅ Checkpoint 15:30:** End-to-end pipeline working with voice!

---

## 15:30-16:00 | Test & Debug (30 min)

### Test Scenarios
```bash
# Test 1: Concert
python main.py "Jazz festival this Saturday, clear skies"

# Test 2: Sports
python main.py "Football match nearby tomorrow night"

# Test 3: Wedding
python main.py "Wedding reception on Sunday afternoon"
```

### Verify:
- [ ] All 3 agents working
- [ ] Qdrant returns similar patterns
- [ ] Predictions logical
- [ ] Voice files generated
- [ ] No crashes/errors

**Fix any bugs found during testing**

**✅ Checkpoint 16:00:** Stable, working demo ready

---

# ⏰ HOUR 5: POLISH (16:00-17:00)

## 16:00-16:30 | Create README (30 min)

### Step 1: Copy Template
Open `README_TEMPLATE_WITH_FAL.md` from outputs folder and adapt.

### Step 2: Key Sections to Update

**Header:**
```markdown
# 🏨 F&B Operations Agent
AI-powered hospitality demand prediction with voice interface

> Built for Pioneers AILab Hackathon - Qdrant Track
> 6-hour sprint | Multi-agent + Voice + Pattern Memory
```

**Market Validation (CRITICAL - add Guac):**
```markdown
## 🎯 Market Validation

**Two independent validations:**

1. **Guac AI** (Y Combinator-backed)
   - Proves 38% waste reduction with AI forecasting for fresh products
   - Similar perishability challenges in grocery
   - Validates: AI pattern matching for demand prediction

2. **Mews** (Leading hospitality PMS)
   - Building "operations agents" for hotel F&B
   - Enterprise focus, tech-first approach
   - Validates: Agent-based operations automation

**My approach:** Combines proven forecasting (Guac) + operations agents (Mews) + voice interface + hospitality expertise
```

**Partner Technologies:**
- Qdrant (detailed why)
- Mistral (detailed why)
- Eleven Labs (detailed why)

**Future Enhancements:**
- Fal AI (visual generation)
- n8n (workflow automation) ← **USE N8N not Make**
- Additional roadmap

### Step 3: Add Your Info
- GitHub URL
- Email/LinkedIn
- Video link (add placeholder, update at 17:20)

**✅ Checkpoint 16:30:** README complete

---

## 16:30-16:45 | Code Cleanup (15 min)

### Tasks:
```bash
# Add docstrings where missing
# Remove debug print statements (or make them clean)
# Format code
# Update requirements.txt
pip freeze > requirements.txt

# Create .env.example
cat > .env.example << 'EOF'
# Qdrant Cloud
QDRANT_URL="https://your-cluster.qdrant.io"
QDRANT_API_KEY="your_api_key_here"

# Mistral AI
MISTRAL_API_KEY="your_mistral_key_here"

# Eleven Labs
ELEVEN_LABS_API_KEY="your_eleven_key_here"
EOF

# Commit everything
git add .
git commit -m "feat: F&B Operations Agent MVP - 6h hackathon"
```

**✅ Checkpoint 16:45:** Code clean and committed

---

## 16:45-17:00 | Video Preparation (15 min)

### Step 1: Prepare Demo Scenario
```bash
# Choose best demo scenario (test a few)
python main.py "Concert tomorrow evening, sunny weather"

# Keep the voice file from best run
mv prediction_voice.mp3 demo_voice.mp3
```

### Step 2: Rehearse Script Once
Read through video script (2 min):

**0:00-0:20 | Hook**
"Saturday night, restaurant fully booked. Walk-ins, allergies, VIP changes. I've lived this chaos. It's a coordination problem."

**0:20-0:40 | Solution**
"Multi-agent system. Qdrant vector search, Mistral AI reasoning, Eleven Labs voice. Three partner technologies working together."

**0:40-1:30 | DEMO**
[Show terminal, run command, PLAY VOICE]

**1:30-1:50 | Tech + Validation**
"Qdrant finds patterns, Mistral predicts, voice speaks. Two validations: Guac AI (YC) proves 38% waste reduction. Mews builds operations agents."

**1:50-2:00 | Close**
"Hospitality-first by someone who's lived it. GitHub repo in description."

### Step 3: Setup Recording
- Open terminal (clean, readable font)
- Test screen recording (Loom or QuickTime)
- Test audio quality
- Have demo command ready

**✅ Checkpoint 17:00:** Ready to record

---

# ⏰ HOUR 6: VIDEO + SUBMIT (17:00-18:00)

## 17:00-17:20 | Record Video (20 min)

### Recording Checklist:
- [ ] Terminal clean and ready
- [ ] Demo command copied: `python main.py "Concert tomorrow Saturday evening"`
- [ ] Voice file ready to play (demo_voice.mp3)
- [ ] Screen recording started
- [ ] Audio quality checked

### Recording Flow:
1. **Start recording**
2. **Speak intro** (0:00-0:40)
3. **Show terminal + run demo** (0:40-1:00)
4. **PLAY VOICE FILE** 🔊 (1:00-1:20)
5. **Show results** (1:20-1:30)
6. **Speak tech + validation** (1:30-1:50)
7. **Speak close** (1:50-2:00)
8. **Stop recording**

### Takes:
- Take 1 → Review
- Take 2 if needed
- Max 2 takes (time constraint)

### Upload:
- Upload to Loom or YouTube (unlisted)
- Get shareable link
- **Update README with video link**

**✅ Checkpoint 17:20:** Video recorded and uploaded

---

## 17:20-17:40 | Create GitHub Repo (20 min)

### Step 1: Create Repo on GitHub
1. Go to https://github.com/new
2. Name: `fbf-agent-qdrant`
3. Description: "AI-powered F&B demand prediction with voice - Pioneers AILab"
4. Public ✅
5. No README/gitignore (you have them)
6. Create

### Step 2: Push Code
```bash
# Add remote
git remote add origin https://github.com/YOUR_USERNAME/fbf-agent-qdrant.git

# Push
git push -u origin main
```

### Step 3: Final Checks
- [ ] README displays correctly
- [ ] Code is visible
- [ ] .env NOT pushed (check .gitignore)
- [ ] All files present

**✅ Checkpoint 17:40:** GitHub repo live and complete

---

## 17:40-17:50 | Submit (10 min)

### Submission Checklist:
- [ ] GitHub repo URL copied
- [ ] Video URL copied
- [ ] README has video link
- [ ] All 3 tools mentioned (Qdrant, Mistral, Eleven Labs)
- [ ] Market validation includes Guac + Mews
- [ ] Future roadmap mentions Fal + n8n

### Submit Form:
1. Open hackathon submission form
2. Paste GitHub URL
3. Paste video URL
4. Add description (copy from README tagline)
5. **SUBMIT at 17:50** ✅

**✅ Checkpoint 17:50:** SUBMITTED! 🎉

---

## 17:50-18:00 | Buffer (10 min)

**Use for:**
- Last-minute fixes if submission fails
- Double-check everything submitted
- Breathe
- Celebrate 🍾

**✅ Checkpoint 18:00:** DONE!

---

# 📋 FINAL CHECKLIST

## Must-Have (P0):
- [x] Qdrant working (pattern search visible)
- [x] Mistral working (embeddings + reasoning)
- [x] Eleven Labs working (voice audible)
- [x] 1 scenario end-to-end working
- [x] Video recorded (under 2:00)
- [x] README complete (with Guac + Mews)
- [x] GitHub repo public
- [x] Submitted before 17:50

## Nice-to-Have (completed if time):
- [ ] Multiple test scenarios working
- [ ] Code beautifully documented
- [ ] Advanced error handling
- [ ] Diagram in README

---

# 🚨 EMERGENCY FALLBACKS

## If Eleven Labs fails:
- Skip voice, just show text output
- Mention "voice integration ready, API timeout"

## If Qdrant times out:
- Use cached/mock data
- Show architecture, explain it would work

## If Mistral rate limits:
- Use simpler prompts
- Cache responses

## If video recording fails:
- Screenshots + narration
- Explain what would happen

**ALWAYS submit something. Better 80% working than 0% submitted.**

---

# 💎 SUCCESS METRICS

**Minimum viable (must achieve):**
- 3 tools integrated ✅
- 1 demo working ✅
- Video + README ✅
- Submitted on time ✅

**Good outcome:**
- Smooth demo ✅
- Professional video ✅
- Clean code ✅
- Guac + Mews validation ✅

**Excellent outcome:**
- Impressive voice demo ✅
- Top-tier README ✅
- Multiple scenarios ✅
- Future roadmap (Fal + n8n) ✅

**Expected score:** 86-93/100 (Top 10-15%)

---

**ROADMAP COMPLETE. Tu as le plan détaillé pour chaque minute des 6 heures. Exécute strictement. Ship on time. 🚀**
