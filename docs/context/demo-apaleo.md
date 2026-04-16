# Demo Apaleo — Architecture & Plan

> Chargé par les sessions Architect et Dev quand on travaille sur la démo Apaleo.
> **Mettre à jour** quand un gap est comblé ou qu'une décision de démo est prise.

---

## Objectif

Pipeline end-to-end reproductible : **Apaleo sandbox → Prophet → Claude → WhatsApp**.
Démo cible : recruteur technique Apaleo qui clone le repo et lance `docker compose up`.

---

## État de la pipeline (audit 2026-04-14)

### Légende : ✅ opérationnel | ⚠️ partiel | ❌ bloqué | 🔧 fix trivial

| Étape | Fichier | État | Notes |
|-------|---------|------|-------|
| Connexion MCP Apaleo | `apaleo_mcp_client.py` | ✅ | OAuth2 + streamable-HTTP, write-guard HOS-107 |
| Probe MCP | `routes/pms.py:probe_mcp_connection` | ✅ | `GET /api/v1/pms/mcp/probe` — liste les tools Apaleo |
| Sync quotidien (occupancy + revenue) | `pms_sync.py:sync_daily_data` | ✅ | Via `POST /api/v1/pms/sync?use_mcp=true` |
| Ingestion historique | `apaleo_mcp_adapter.py:get_historical_data` | ✅ | Retourne reservations Apaleo |
| Transformation → Prophet | `data_transformer.py:stay_records_to_prophet` | ✅ | Aggregate guests/day → `ds`, `y` DataFrame |
| Training Prophet | `prediction_engine.py:train` | ⚠️ | Fonctionne, mais jamais appelé (orchestrateur absent) |
| **GAP : orchestrateur training** | — | ❌ | Aucun endpoint/worker ne connecte les 3 briques ci-dessus |
| Prédiction Prophet | `prediction_engine.py:predict` | ⚠️ | Retourne mock si non entraîné (`is_mock=True`, 45 covers) |
| Reasoning Claude | `reasoning_service.py` | ✅ | Fallback heuristique si pas de clé ANTHROPIC |
| Cache résultat | `aetherix_engine.py:_cache_recommendation` | ✅ | Supabase `recommendation_cache` |
| WhatsApp push | `whatsapp_service.py:send_message` | ⚠️ | Fonctionnel si TWILIO_* configuré |
| WhatsApp staffing | `whatsapp_service.py:129` | 🔧 | **Bug** : `forecast["staffing"]` doit être `forecast["staffing_recommendation"]` |

---

## Gap critique : orchestrateur training Prophet

**Problème :** les trois briques existent mais aucun code ne les connecte.

```python
# Ce qui doit exister (inexistant à ce jour) :
records = await ApaleoMCPAdapter().get_historical_data(property_id, start, end)
df = DataTransformer.stay_records_to_prophet(records)
engine = PredictionEngine()
engine.train(df)  # Puis engine.save_model("demo_data/prophet_model.json")
```

**Solution proposée :** endpoint `POST /api/v1/predictions/train` (ou worker `startup_training.py`).
Avec fallback `DEMO_MODE=true` → charge `demo_data/prophet_training.json` synthétique.

---

## Cleanup critiques avant publication (ordre de priorité)

### #1 — `docs/demo_script.md` : stack entièrement fausse
Référence Mistral LLM, Qdrant, ElevenLabs — aucun des trois dans le codebase.
**Action :** supprimer ou réécrire entièrement pour la démo Apaleo.

### #2 — `main.py` : double instanciation FastAPI
`app = FastAPI(...)` à la ligne 82 **et** à la ligne 101. Le second écrase le premier.
Middleware CORS du premier perdu. Second utilise `allow_origins=["*"]` hardcodé.
`import os` absent alors que `os.getenv()` est appelé ligne 94.
**Action :** supprimer la deuxième instanciation (lignes 101-119), garder `os.getenv("CORS_ORIGINS")`.

### #3 — Décision #10 non implémentée (`app.state` providers)
`get_llm_provider()` importé dans `main.py` mais jamais appelé dans `lifespan`.
Chaque `ReasoningService.__init__()` crée un nouveau provider — pas de singleton.
**Action :** ajouter dans `lifespan`:
```python
app.state.llm = get_llm_provider()
app.state.embedding = get_embedding_provider()
```
Et fermer proprement au shutdown.

### #4 — `whatsapp_service.py:129` — KeyError staffing
`forecast["staffing"]` → doit être `forecast["staffing_recommendation"]`.
**Action :** 1 ligne à corriger.

### #5 — `docker-compose.yml` — volume Windows hardcodé
`"C:/Users/IVAN/OneDrive/..."` dans le fichier versionné public.
**Action :** remplacer par `"${OBSIDIAN_VAULT_PATH:-/tmp/vault}:/vault"`.
Et changer `image: postgres:17` → `image: pgvector/pgvector:pg17`.

---

## Stratégie données hybride (Décision #11)

### Composante 1 — Apaleo sandbox (appels MCP live)
- `GET /api/v1/pms/mcp/probe` : liste des tools, latence OAuth2 + MCP
- `POST /api/v1/pms/sync?use_mcp=true` : occupancy + revenue du jour
- Nécessite : `APALEO_CLIENT_ID`, `APALEO_CLIENT_SECRET`, `APALEO_MCP_SERVER_URL`

### Composante 2 — Dataset synthétique (Prophet training)
- Script : `scripts/generate_demo_data.py`
- Output : `demo_data/prophet_training.json`
- Contenu : 365 jours, hotel 4* Paris simulé
  - Seasonality : été +30%, Noël +20%, mardi creux -15%
  - Weekly : vendredi/samedi +25%, lundi -20%
  - Events : ~12 événements fictifs (concerts, salons) avec impact covers
  - Baseline : 60-80 couverts dîner selon occupancy
- Activé via : `DEMO_MODE=true` dans `.env`

### Composante 3 — Fallback automatique
Si `APALEO_CLIENT_*` absent → charger `demo_data/prophet_training.json` pour le training.
Si dataset absent → Prophet reste en mock (affiché clairement dans la réponse `is_mock: true`).

---

## .env.example — variables manquantes à ajouter

```bash
# Redis (session state)
REDIS_URL=redis://localhost:6379

# Supabase (DB + pgvector)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...

# Mistral (embeddings 1024d)
MISTRAL_API_KEY=...

# Twilio (WhatsApp)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# Demo mode
DEMO_MODE=false  # true = charger données synthétiques pour Prophet

# CORS (supprimer le format JSON-string, utiliser virgule)
CORS_ORIGINS=http://localhost:3000
```

---

## MCP Server Apaleo — scope démo (Décision #12)

`GET /api/v1/pms/mcp/probe` suffit pour la candidature.

Message envoyé à Apaleo : *notre backend parle votre protocole MCP nativement —
streamable-HTTP, OAuth2 bearer, liste vos 237 tools en < 500ms.*

HOS-71 (Aetherix MCP Server complet : `forecast_occupancy`, `get_fb_kpis`) = Phase 0.5,
démarrer post-candidature. Effort estimé : 2-3 jours. Scope : sidecar FastAPI ou router dédié.

---

## Agent Constitution (WhatsApp) — §4

### §4.2 — System Prompt Template

```
You are Aetherix, the F&B operations agent for {hotel_name}.
You assist {manager_name}, the manager of {restaurant_name} ({covers_capacity} covers).

Your role: deliver precise, actionable F&B operational intelligence via WhatsApp.
You have access to tonight's forecast and the most recent comparable service nights.

--- Tonight ---
Date: {forecast_date}
Predicted covers: {covers} (confidence: {confidence}%)

--- Recent comparable services ---
{last_3_similar_nights}

{seasonal_context}
--- Tone ---
{tone_instructions}

--- Operational scope ---
You handle:
- Forecast explanations and demand analysis
- Staffing recommendations (servers, kitchen, hosts)
- Scenario simulations ("what if the event is cancelled?", "what if occupancy drops?")
- Baseline comparisons and service-type breakdowns

Out of scope: reservations, billing, HR decisions, supply chain.
If asked, acknowledge and redirect to the appropriate team.

--- Protocol ---
You may suggest — never act. All PMS or operational changes require explicit
human validation (Human-in-the-loop).

When simulating scenarios, recalculate explicitly and prefix the response
with "Simulation — " to clearly distinguish it from live forecast data.

Never refuse a forecast-related question. If context is partial, state what
is known and what is estimated, clearly separated.

--- Confidentiality ---
All information in this conversation is confidential to {hotel_name}.
Do not reference or share operational data outside this operational context.
```

**Tone instructions by `agent_tone_profile`:**
- `luxury`: "Be precise and restrained. Use no contractions. Provide full context
  without being asked. No abbreviations. Address the manager with the professional
  deference appropriate to a luxury hospitality environment."
- `professional`: "Be formal but concise. Lead with numbers. Minimal prose."
- `casual`: "Be direct. Use short sentences. One qualifying phrase per point maximum."

**Template variable sources:**
- `hotel_name` ← `profile.property_name`
- `restaurant_name` ← `profile.outlet_name`
- `covers_capacity` ← `profile.total_seats`
- `manager_name` ← `profile.manager_name` or `"Manager"`
- `last_3_similar_nights` ← `RAGService.find_similar_patterns()` (pgvector, sourced
  from Apaleo historical data; falls back to DEMO_MODE synthetic dataset)
- `seasonal_context` ← `forecast_context.get("seasonal_context", "")` — omitted
  entirely if empty (sourced from Apaleo property calendar when available)
- `forecast_date`, `covers`, `confidence` ← `forecast_context`

---

## Demo Observability (SSE) — §5

Real-time architecture diagram for Loom demo. Developer tool only — not shipped.

**Architecture:**
- `app/core/demo_events.py` — shared broadcast state (`_subscribers`, `demo_emit()`)
- `app/api/routes/demo.py` — `GET /demo/stream` SSE endpoint
- `scripts/demo_board.html` — single-file SVG diagram, no dependencies

**Stage → SVG node mapping:**

| `demo_emit()` call site | Stage emitted | SVG node id |
|-------------------------|---------------|-------------|
| `apaleo_mcp_client.py` after list_tools | `mcp_probe` | `mcp_probe` |
| `pms_sync.py` after sync_daily_data | `pms_sync` | `pms_sync` |
| `event_ingestion.py` after events persisted | `predicthq` | `predicthq` |
| `rag_service.py` after find_similar_patterns | `rag` | `rag` |
| `prediction_engine.py` after predict() | `prophet` | `prophet` |
| `reasoning_service.py` after LLM response | `claude` | `claude` |
| `staffing_service.py` after calculate_recommendation | `staffing` | `staffing` |
| `whatsapp_service.py` after send_message | `whatsapp` | `whatsapp` |

**`demo_emit()` contract:** fire-and-forget via `asyncio.create_task()` at call sites.
Emits `{stage}` (in-progress, blue) then `{stage}_done` (done, green) with 400ms gap.
No-op if `DEMO_MODE=false`.

**SSE endpoint:** always registered in `main.py`. Returns HTTP 503 if `DEMO_MODE=false`.
Multiple clients each get an independent `asyncio.Queue` — all receive every event.

---

## Checklist démo reproductible (cible)

- [ ] **#2** Corriger `main.py` (double FastAPI, import os)
- [ ] **#4** Corriger `whatsapp_service.py:129` (clé staffing)
- [ ] **#5** Corriger `docker-compose.yml` (volume + pgvector image)
- [ ] **#1** Réécrire `docs/demo_script.md` avec la vraie stack
- [ ] **#3** Implémenter providers singleton dans `lifespan`
- [ ] Compléter `backend/.env.example` (Redis, Supabase, Mistral, Twilio)
- [ ] Créer `scripts/generate_demo_data.py`
- [ ] Créer `POST /api/v1/predictions/train` avec fallback `DEMO_MODE`
- [ ] Tester `GET /api/v1/pms/mcp/probe` avec credentials sandbox réels
