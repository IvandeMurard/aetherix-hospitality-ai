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
