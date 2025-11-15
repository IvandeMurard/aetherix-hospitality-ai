# 🏨 F&B Operations Agent

> AI-powered hospitality demand prediction with voice interface and pattern memory

[![Built for Pioneers AILab](https://img.shields.io/badge/Hackathon-Pioneers%20AILab-blue)](https://pioneers.io)
[![Qdrant Track](https://img.shields.io/badge/Track-Qdrant-red)](https://qdrant.tech)
[![Built in 6h](https://img.shields.io/badge/Built%20in-6%20hours-green)](.)

**Demo Video:** [Watch 2-min demo →](YOUR_VIDEO_LINK)

---

# 🚀 DÉMO RAPIDE (5 MIN)

## Lancement

1. **API** : `uvicorn api:app --reload --port 8000`

2. **Interface** : `streamlit run demo_app.py`

3. **Ouvrir** : http://localhost:8501

## Test API direct

```bash
python test_final.py
```

## Technologies

- ✅ Mistral AI (embeddings + LLM)
- ✅ Qdrant (vector search - local)
- ✅ ElevenLabs (voice - intégré)

---

## 🎯 The Problem

Saturday night, 7:30 PM. Restaurant fully booked.

**Suddenly:**
- 3 walk-ins arrive
- 2 allergy requests
- 1 VIP menu modification

The manager juggles between kitchen coordination, reservation systems, and stressed servers.

**This isn't a people problem. It's a coordination problem.**

As a former server, I've lived this chaos. Traditional forecasting tools provide numbers, but they don't *act*. They inform, but don't coordinate.

---

## 💡 The Solution

A voice-enabled multi-agent system that:
1. **Predicts** F&B demand 48 hours ahead using pattern matching
2. **Recommends** specific actions (procurement, staffing, prep)
3. **Speaks** predictions naturally via voice interface

### Demo Flow

```bash
$ python main.py "Concert tomorrow evening, sunny weather"

🔍 Analyzing event...
   Features: Saturday, concert, large, sunny

🔎 Searching Qdrant for similar patterns...
   #1: Coldplay concert nearby (similarity: 0.89)
   #2: Jazz festival Saturday (similarity: 0.85)
   #3: Rock concert evening (similarity: 0.82)

🎯 Generating prediction...
   Prediction: 90 covers (87% confidence)

🔊 Voice output:
   "Based on similar patterns, expect 90 covers tonight 
    with 87% confidence. I recommend scheduling 6 staff 
    members. Key factors: nearby concert, weekend demand, 
    favorable weather."

📊 RESULTS
Expected Covers:     90
Confidence:          87%
Recommended Staff:   6
Voice file saved:    prediction_voice.mp3
```

---

## 🛠️ Partner Technologies (3+)

### 🔍 Qdrant Vector Search
**Role:** Core pattern memory system

- Stores historical F&B scenarios as vector embeddings
- Retrieves top-3 similar events via semantic similarity
- COSINE distance matching (1024-dimensional vectors)

**Why Qdrant:** Hospitality patterns are nuanced. Traditional databases miss semantic connections. Qdrant finds: *"jazz festival Saturday"* ≈ *"concert Friday evening"* through vector similarity.

---

### 🤖 Mistral AI
**Role:** Embeddings generation + Reasoning engine

**Models used:**
- **Mistral Embed** – Generates 1024-dim embeddings from event descriptions
- **Mistral Large** – Powers both Analyzer and Predictor agents

**Why Mistral:** Fast, accurate embeddings + strong reasoning. Perfect for real-time hospitality decisions where every minute counts.

---

### 🔊 Eleven Labs Voice
**Role:** Natural voice synthesis

- Converts predictions to professional voice ("Adam" model)
- Makes the agent feel like a real assistant
- Hands-free interaction for busy managers

**Why Voice:** Hospitality managers are on their feet, moving between kitchen and floor. Voice output = hands-free, natural interaction. Much more practical than reading terminal logs.

---

**Total: 3 partner tools integrated** ✅

---

## 🏗️ Architecture

```
┌─────────────────┐
│  Event Input    │  "Concert tomorrow evening"
└────────┬────────┘
         ↓
┌─────────────────┐
│  Agent 1        │  Extract features
│  (Analyzer)     │  → Generate Mistral embedding
└────────┬────────┘
         ↓
┌─────────────────┐
│  Qdrant Search  │  Find 3 similar scenarios
│                 │  → Return patterns with scores
└────────┬────────┘
         ↓
┌─────────────────┐
│  Agent 2        │  Analyze patterns
│  (Predictor)    │  → Generate prediction + confidence
└────────┬────────┘
         ↓
┌─────────────────┐
│  Eleven Labs    │  Voice synthesis
│  Voice Output   │  → "Expect 90 covers..."
└────────┬────────┘
         ↓
┌─────────────────┐
│  Terminal       │  Display detailed results
└─────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- API keys: [Qdrant Cloud](https://cloud.qdrant.io), [Mistral AI](https://mistral.ai), [Eleven Labs](https://elevenlabs.io)

### Installation

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/fbf-agent-qdrant
cd fbf-agent-qdrant

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Setup

```bash
# Create Qdrant collection
python setup_qdrant.py

# Seed historical data (10 scenarios)
python seed_data.py
```

### Run Demo

```bash
# Interactive mode
python main.py

# Or provide event directly
python main.py "Concert tomorrow evening, sunny weather"

# Agent will:
# 1. Extract features from description
# 2. Search Qdrant for similar patterns
# 3. Generate prediction with confidence
# 4. Speak the prediction (save as .mp3)
# 5. Display detailed results
```

---

## 🎬 Démo Rapide

### Tester l'API

L'API FastAPI est accessible et prête à recevoir des requêtes de prédiction.

#### 1. Lancer l'API

```bash
# Activer l'environnement virtuel
source venv/bin/activate  # Windows: venv\Scripts\activate

# Lancer l'API
python start_api.py
```

L'API sera accessible sur : **http://127.0.0.1:8000**

#### 2. Accéder à la documentation interactive

Ouvrez votre navigateur : **http://127.0.0.1:8000/docs**

Vous verrez l'interface Swagger avec l'endpoint `/predict` prêt à être testé.

#### 3. Tester avec un script Python

```bash
# Test complet du pipeline
python test_full_pipeline.py

# Test de 3 scénarios différents
python test_scenarios.py
```

#### 4. Exemple de requête cURL

```bash
curl -X POST "http://127.0.0.1:8000/predict" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2024-11-20",
    "events": "Concert Coldplay au Stade de France, soirée ensoleillée",
    "weather": "Ciel dégagé, 22°C"
  }'
```

#### 5. Exemple de réponse

```json
{
  "date": "2024-11-20",
  "events": "Concert Coldplay au Stade de France, soirée ensoleillée",
  "weather": "Ciel dégagé, 22°C",
  "expected_covers": 98,
  "recommended_staff": 7,
  "confidence": 88,
  "key_factors": [
    "Large-scale Coldplay concert at Stade de France (historically +53-58% variance)",
    "Favorable weather (22°C, clear skies) likely to extend pre/post-event foot traffic",
    "Wednesday event (vs. weekend in past patterns) may slightly dampen but not negate surge"
  ]
}
```

### Les 3 Outils Utilisés

#### 🔍 **Qdrant** - Recherche Vectorielle
- **Rôle** : Trouve les 3 scénarios historiques les plus similaires
- **Où** : `agents/pattern_search.py`
- **Fonction** : `search_similar_patterns()`
- **Input** : Embedding vectoriel (1024 dimensions)
- **Output** : 3 patterns avec scores de similarité

#### 🤖 **Mistral AI** - Embeddings + Reasoning
- **Rôle** : Génère des embeddings ET des prédictions intelligentes
- **Où** : 
  - `agents/analyzer.py` → Embeddings + extraction de features
  - `agents/predictor.py` → Génération de prédictions
- **Modèles** : 
  - `mistral-embed` pour les embeddings
  - `mistral-large-latest` pour le reasoning
- **Performance** : ~2.5s par requête complète

#### 🔊 **ElevenLabs** - Synthèse Vocale
- **Rôle** : Convertit les prédictions en audio naturel
- **Où** : `agents/predictor.py`
- **Fonction** : `generate_voice_output()`
- **Modèle** : `eleven_multilingual_v2`
- **Voix** : Sarah (voix professionnelle féminine)
- **Format** : MP3 (`prediction_voice.mp3`)

---

## 📊 Example Output

**Input:**
```
"Jazz festival tomorrow night, sunny weather, Saturday"
```

**Qdrant Retrieval:**
```
Top 3 similar scenarios:
1. "Coldplay concert nearby" (similarity: 0.89)
   → 95 covers, +58% variance, 6 staff
   
2. "Saturday night + festival" (similarity: 0.85)
   → 82 covers, +37% variance, 5 staff
   
3. "Outdoor event + clear skies" (similarity: 0.82)
   → 88 covers, +60% variance, 6 staff
```

**Prediction:**
```
Expected covers:     90
Usual baseline:      60
Variance:           +50%
Confidence:          87%
Recommended staff:   6
```

**Key Factors:**
- Nearby festival (500m)
- Weekend demand spike
- Favorable weather

**Voice Output:** 🔊
*"Based on similar patterns, expect 90 covers tonight with 87% confidence. I recommend scheduling 6 staff members. Key factors are the nearby festival, weekend demand, and favorable weather."*

---

## 💪 Why This Approach Works

### Hospitality-First Thinking

Built by someone who's lived the problem. Tech people optimize workflows. I optimize for the waiter's stress, the chef's rhythm, the manager's sanity.

### Pattern Memory > Rules

Traditional systems use if/then rules. This agent learns from actual operational history via Qdrant vector search. More flexible, more accurate.

### Voice = Natural Interface

Managers don't sit at terminals. They move. Voice output means they can hear predictions while coordinating the floor.

---

## 🎯 Market Validation

**Two independent validations of this approach:**

### 1. Guac AI (Y Combinator-backed)

**What they do:** AI demand forecasting for grocery fresh products  
**Results:** 38% waste reduction, 3% sales increase  
**Coverage:** TechCrunch, Progressive Grocer

**Validation:** Proves that AI forecasting can dramatically reduce waste for perishable products. Hospitality F&B has identical perishability challenges.

[Read more →](https://techcrunch.com/guac-ai-yc)

---

### 2. Mews (Leading hospitality PMS)

**What they're building:** "Operations agents" for hotel F&B  
**Approach:** Enterprise focus, tech-first  

**Validation:** Independent convergence on agent-based automation for hospitality operations.

[Learn more →](https://mews.com)

---

### My Differentiation

**Guac approach** (proven forecasting) + **Mews vision** (operations agents) + **Voice interface** (hands-free) + **Hospitality expertise** (lived it)

| Feature | Guac AI | Mews | F&B Agent (Me) |
|---------|---------|------|----------------|
| **Vertical** | Grocery | Hotels (PMS) | F&B Operations |
| **Approach** | Proprietary AI | Agent-based | Multi-agent + Voice |
| **Interface** | Dashboard | Web platform | Voice + Terminal |
| **Team** | Tech-first | Tech-first | Hospitality-first |

---

## 🔮 Future Enhancements

This 6-hour MVP demonstrates core feasibility. Planned V2 features:

### Visual Intelligence with Fal AI 🎨

**Integration planned:** Fal generative AI for visual outputs

**Use cases:**

**1. Restaurant Layout Visualization**
```python
fal.generate_image(
    prompt="Restaurant floor plan, 90 covers, 
            80% occupancy heatmap, professional style"
)
```
→ Visual representation of table allocation, hot zones, traffic flow

**2. Menu Item Forecasting**
```python
fal.generate_image(
    prompt="Top 5 predicted menu items, 
            visual presentation with confidence scores"
)
```
→ Visual menu recommendations with popularity predictions

**3. Kitchen Prep Guides**
```python
fal.generate_image(
    prompt="Kitchen prep checklist for 90 covers, 
            visual workflow diagram"
)
```
→ Step-by-step visual guides for kitchen staff

**Why Fal:** Hospitality is a visual industry. Floor plans, plating, presentation matter. Fal enables the agent to communicate through images, not just text/voice.

**Timeline:** 2-3 weeks post-hackathon

---

### Workflow Automation with n8n ⚙️

**Use cases:**
- Automatic procurement orders (integrate with suppliers)
- Staff scheduling integrations (sync with HR systems)
- PMS bi-directional sync (Mews, Cloudbeds, Opera)
- Email/SMS notifications to team
- Visual workflow builder (accessible for non-technical managers)

**Why n8n:** Open-source, self-hostable, visual workflow design. Perfect for hospitality managers to customize automation without coding.

**Timeline:** 1-2 months post-hackathon

---

### Additional Roadmap (3-6 months)

**Multi-language Support**
- Expand Eleven Labs voices (French, Spanish, German)
- International hospitality coverage

**Advanced Analytics**
- Historical accuracy tracking
- Pattern drift detection
- Continuous learning pipeline
- Multi-department expansion (banquet, room service, bar)

**Mobile Interface**
- iOS/Android apps
- Push notifications for predictions
- Voice commands via device
- Offline mode for unstable connectivity

**Enterprise Features**
- Multi-location management
- Centralized dashboards
- Team collaboration tools
- Advanced permissions
- SLA guarantees

---

## 🧪 Tech Stack

**Core (Current):**
- Python 3.9+
- [Qdrant Cloud](https://qdrant.tech) (vector database)
- [Mistral AI](https://mistral.ai) (embeddings + LLM)
- [Eleven Labs](https://elevenlabs.io) (voice synthesis)

**Supporting:**
- python-dotenv (environment management)
- requests (API calls)

**Future (V2):**
- [Fal AI](https://fal.ai) (visual generation)
- [n8n](https://n8n.io) (workflow automation)
- React + TypeScript (web dashboard)
- PostgreSQL (structured data)
- Redis (caching)

---

## 📈 Performance

**Current MVP:**
- Pattern retrieval: <500ms (Qdrant)
- Prediction generation: ~2-3s (Mistral Large)
- Voice synthesis: ~1-2s (Eleven Labs)
- **Total latency:** 3-6 seconds

**Optimization roadmap:**
- Cache embeddings for common events
- Parallel API calls where possible
- Edge deployment for latency reduction
- Batch processing for multiple predictions

---

## 🎓 Learnings & Insights

### What Worked Well

**1. Hospitality-First Approach**
Understanding the real operational challenges (from personal experience) led to better product decisions than pure tech optimization.

**2. Voice Interface**
Initially seemed like a "nice to have" → became the core differentiator. Hands-free interaction is perfect for hospitality.

**3. Pattern Memory (Qdrant)**
Vector search finds nuanced similarities that rule-based systems miss. "Concert Saturday" ≈ "Festival Friday" through semantic meaning.

### Challenges Encountered

**1. Prediction Confidence**
With only 10 historical scenarios, confidence scores are directional, not statistical. Need 100+ scenarios for real accuracy.

**2. Data Quality**
Historical F&B data is often messy, incomplete, or in disparate systems. Integration layer will be critical in V2.

**3. Voice Latency**
1-2 seconds for voice generation feels slow in real-time interaction. Caching common phrases could help.

---

## 🤝 Contributing

Built in 6 hours for Pioneers AILab Hackathon. Not accepting contributions yet, but feedback welcome!

**Interested in collaborating?**
- Hotels/restaurants for pilot programs
- PMS vendors for integration partnerships
- Investors/advisors in hospitality tech

**Contact:**
- Email: ivandemurard@hotmail.Fr
- LinkedIn: [linkedin.com/in/ivandemurard](https://linkedin.com/in/ivandemurard)
- Twitter: [@IvanMurard](https://twitter.com/ivanMurard)

---

## 📜 License

MIT License - See [LICENSE](LICENSE) file

---

## 🙏 Acknowledgments

- **Qdrant** for vector search infrastructure
- **Mistral AI** for powerful, fast embeddings and reasoning
- **Eleven Labs** for natural voice synthesis
- **Pioneers AILab** for the hackathon opportunity
- **Guac AI** for proving the approach works
- **Mews** for validating agent-based hospitality automation
- Every hospitality worker who's ever experienced the Saturday night chaos

---

## 📺 Demo Video

[**Watch the 2-minute demo →**](YOUR_VIDEO_LINK)

**See:**
- Event input → Qdrant pattern search
- Mistral prediction generation
- Eleven Labs voice output 🔊
- Complete workflow in action

---

## 🚀 What's Next?

**Short-term (1-2 months):**
- [ ] 3-5 pilot hotels recruited
- [ ] Real operational data integration
- [ ] Accuracy tracking dashboard
- [ ] Fal AI visual generation added

**Medium-term (3-6 months):**
- [ ] 20-30 paying customers
- [ ] First revenue: €10-15K MRR
- [ ] n8n workflow automation
- [ ] Mobile app (iOS/Android)

**Long-term (6-12 months):**
- [ ] Enterprise features (multi-location)
- [ ] Advanced analytics & insights
- [ ] Series Seed funding consideration
- [ ] Team expansion (CS + Sales + Engineering)

---

## 💬 Feedback

This was built in 6 hours as a proof of concept. Your feedback matters!

**Questions? Ideas? Interested in a pilot?**

Open an issue or reach out directly: your.email@example.com

---

**Built with ❤️ for the hospitality industry**  
*By someone who's been in the weeds*

---

<p align="center">
  <sub>F&B Operations Agent | Pioneers AILab Hackathon 2024</sub>
</p>
