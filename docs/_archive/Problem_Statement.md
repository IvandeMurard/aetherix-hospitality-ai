# F&B Operations Agent - Problem Statement

## 1. QUEL PROBLÈME PRÉCIS RÉSOUT TON AGENT?

L'agent résout le problème de la prévision des besoins en staffing pour 
les opérations F&B, permettant aux managers de passer de prédictions 
manuelles basées sur expérience, réservations, et patterns historiques 
(70% accuracy) à des prévisions AI-powered (85%+ accuracy) intégrant 
automatiquement events locaux, météo, et similarité vectorielle de patterns.

**Impact concret :**
- **Temps :** Managers passent 5-8h/semaine sur staffing planning → 
  réduction 70% via automation (2h/semaine)
- **Qualité service :** 30% des schedules incorrects (sur/sous-staffing) → 
  impacte expérience guest, moral équipe, coûts labor
- **Stress & confiance :** Managers doutent constamment, surtout avant 
  gros events → data-backed decisions réduisent stress, augmentent confiance

**Résultat :** Manager réinvestit 5-6h/semaine gagnées dans leadership 
d'équipe et moments high-touch avec guests, plutôt que spreadsheets.

**Vision produit (Roadmap post-MVP) :**
- **Phase 1 (MVP):** Staffing forecasting avec voice-first UX
- **Phase 2 (V2):** + F&B inventory optimization (inspired by Guac AI - 
  réduction waste via demand prediction)
- **Phase 3 (Platform):** + Logistics (salles, équipement) → Operations 
  Copilot multi-domain pour hospitality

**Alignment stratégique Mews :** Cette vision converge avec Mews Operations 
Agent (multi-domain orchestration), en commençant focused MVP puis scaling 
iterativement.
## 2. POUR QUI? (Persona détaillé)

**Primary Persona:**
- Nom: Marc Dubois (fictif mais réaliste)
- Âge: 38-45 ans
- Role: F&B Manager ou Operations Manager
- Experience: 8-15 ans dans hospitality
- Restaurant type: Mid-high end (80-150 covers/service)
- Tech comfort: Modéré (utilise POS, Excel, 7shifts, Toasts, MarketMan, OpenTable, pas de code)
- Pain points:
  - Passe 2-3h par semaine sur staffing planning
  - Stressé avant gros events (concerts, festivals)
  - Pas confiant dans predictions (always second-guessing)
  - Frustré par outils actuels (too many apps, pas smart)
  - Pressure du owner (contrôle costs, mais service quality)

## 3. SITUATION ACTUELLE DOULOUREUSE

**Workflow actuel (sans agent):**
1. Marc ouvre Excel spreadsheet (ou 7shifts direct)
2. Regarde historical covers:
   - Last 3-4 weeks, same day of week
   - Maybe notes dans Google Calendar
3. Checks events manually:
   - Google "concerts Paris November"
   - Regarde weather forecast
1. Déduit les besoins en staffing d'après les réservations, l'intuition, données
2. Envoi le schedule à 7shifts
3. Le jour J arrive:
   - Soit trop de staff → coûts inutiles, staff frustré
   - Soit pas assez → service dégradé, guests unhappy
7. Damage control:
   - Call staff last minute (souvent refuse)
   - OU turn away walk-ins (revenue loss)

**Note:** Même si planning base est fait mensuellement lors de prise de poste,
les ajustements sont fréquents (2-3x/semaine) en réponse à :
- Events imprévus (concerts annoncés, conférences)
- Weather changes (pluie = plus indoor dining)
- Absences staff (maladie, urgences)
- Walk-ins unexpected (groupe large)

Agent cible ces **ajustements fréquents**, pas planning initial.

**Métriques du problème:**
- Time wasted: 5-8h/semaine (planning + corrections + stress mental)
- Error rate: 30% des predictions incorrectes (industry baseline)
- Revenue impact:
  -15% quand sous-staffé (turned away guests, bad reviews)
  +8-10% coûts when over-staffed (unnecessary labor) 
- Stress level: High (always doubting, pressure from owner)

## 4. SITUATION DÉSIRÉE (après agent)

**Nouveau workflow (avec agent):**
1. Marc ouvre dashboard (8am, 2 jours avant service)
2. Agent a déjà préparé prediction basée sur: - Historical patterns (Qdrant vector search) - Events nearby dans 5km (PredictHQ API) - Weather forecast - Day of week, season, holidays
3. Marc voit: "Saturday dinner: 145 covers (88% confidence)"
4. Agent explique reasoning: "Based on 3 similar patterns:
   - Coldplay concert Nov 2023 (142 covers, 3.2km away)
   - U2 concert June 2024 (151 covers, 3.2km away)
   - Rainy Saturday Oct 2024 (138 covers, no events)"
1. Marc valide en 1 click (ou ajuste manuellement)
2. Agent suggère staffing: 8 servers, 2 hosts, 3 kitchen
3. Marc approves → [Future Phase 2: auto-push to 7shifts]

**Métriques de succès:**
* Time saved: 70% reduction (1.5-2h/semaine au lieu de 5-8h)
- Accuracy improved: 85-88% correct predictions (vs 70% baseline)
- Revenue protected: +10-15% via better staffing
  - No more turned-away guests (sous-staffing)
  - No more over-staffing waste
- Stress reduced: Manager confident, data-backed decisions

## 5. MÉTRIQUE DE SUCCÈS #1 (North Star)

**Primary metric:** Staffing prediction accuracy (MAPE - Mean Absolute Percentage Error)

**Industry Benchmarks (Source: Fourth, CloudFoodManager, Imperia SCM):**
- Manual scheduling: 20-35% MAPE (65-80% accuracy)
  - Typical: Last year's numbers, averages, manager intuition
  - Slow, error-prone, misses demand drivers (weather, events, channel mix)
- Automated/AI scheduling: 8-18% MAPE (82-92% accuracy)
  - Well-implemented systems using POS history, reservations, weather, events
  - Improvement: Automation cuts forecast error by roughly half

**Our Targets (Conservative):**
- **Baseline:** 70% accuracy (30% MAPE) - Manager manual predictions
  - Mid-range of industry manual scheduling (20-35% MAPE)
- **MVP target:** 85% accuracy (15% MAPE) - AI-powered predictions
  - Mid-range of industry AI tools (8-18% MAPE)
  - Conservative estimate (could achieve 88-90% with optimization)
- **Improvement:** +15 percentage points accuracy
  - Aligned with industry "cut error by half" standard

**Measurement Method:**
- Post-service validation: Compare predicted covers vs actual covers (POS data)
- Calculate MAPE: Avg(|Predicted - Actual| / Actual) × 100%
- Track weekly rolling average (30-day window)

**Why this metric:**
- ✅ Industry-standard measure (MAPE used by Fourth, CloudFoodManager, etc.)
- ✅ Directly tied to problem (bad predictions = over/under-staffing)
- ✅ Quantifiable and objective (POS data available)
- ✅ Demonstrates AI value (70% → 85% = clear improvement)

**Secondary metrics:**
- Time saved per week (self-reported by manager)
- Manager satisfaction (NPS-style: "would you recommend?")
- Revenue impact (calculated via POS: reduced under-staffing loss, over-staffing waste)

**Sources:**
- Fourth: "Restaurant Forecasting: A Comprehensive Guide" (https://uk.fourth.com/article/restaurant-forecasting-a-comprehensive-guide)
- Fourth: "Labor Forecasting for Restaurants" (https://www.fourth.com/article/labor-forecasting-for-restaurants)
- CloudFoodManager: "How Food Service Management Tools Improve Staff Scheduling" (https://cloudfoodmanager.com/how-food-service-management-tools-improve-staff-scheduling/)
- Imperia SCM: "MAPE and Supply Chain Forecasting" (https://imperiascm.com/blog/mape-and-supply-chain-forecasting-how-to-measure-and-enhance-accuracy)

## 6. WHY NOW? (Timing / Market context)
- AI tools costs dropping drastically
  - Mistral: $1/1M tokens (vs OpenAI $20/1M)
  - Qdrant: Free tier generous (vs Pinecone $70/month)
  
- Voice interfaces mature
  - ElevenLabs Conversational AI (launched 2024)
  - Managers expect "Copilot for restaurants"
  
- Hospitality labor shortage
  - Post-COVID staffing crisis
  - Optimization devient critical (not nice-to-have)
  
- Manager expectations rising
  - Everyone uses ChatGPT now
  - Expect AI in their work tools

## 7. DIFFERENTIATION (vs alternatives)

**Current alternatives:**
1. Excel + intuition
   - ❌ Error-prone (30% incorrect)
   - ❌ Time-consuming (5-8h/semaine)
   - ❌ No event awareness
   
2. 7shifts (scheduling tool)
   - ✅ Good for creating schedules
   - ❌ No prediction capability
   - ❌ Manager doit deviner staffing needs
   
3. Generic BI tools (Tableau, Looker)
   - ✅ Good for historical analysis
   - ❌ Not AI-powered (no predictions)
   - ❌ Steep learning curve
   - ❌ Expensive ($200+/month)
   - ❌ Not hospitality-specific
   
**Our edge:**
- AI-native avec voice-first UX
  - Manager parle pendant service (hands-free)
  - Natural language ("predict Saturday dinner")
  
- Hospitality-specific
  - Trained on restaurant patterns (not generic forecasting)
  - Understands events, weather, seasonality
  
- Augmented human (not black box)
  - Manager garde contrôle (approve/reject)
  - Explainable AI (reasoning visible)
  - Trust-building critical en hospitality
  
- Affordable
  - <$10/restaurant/month (vs $200+ BI tools)
  - Accessible pour independent restaurants (not just chains)
-