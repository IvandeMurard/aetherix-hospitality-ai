# Demo Script — Aetherix Hospitality AI
**Audience : Apaleo (Lennart Reents) · Format : repo clone + docker compose up**

---

## Pitch (30 secondes)

Aetherix est un agent opérationnel pour les hôtels. Il surveille en continu l'occupancy, le calendrier local, et la météo — et envoie au directeur F&B une alerte WhatsApp avant chaque service avec la prédiction de couverts et la recommandation de staffing. Le manager dit "OK" ou "non" depuis son téléphone. Aucune interface à apprendre.

**Différenciation Apaleo :** Aetherix parle MCP nativement. Il liste les 237 endpoints Apaleo via streamable-HTTP en moins de 500 ms, sans SDK propriétaire.

---

## Stack réelle (post-audit 2026-04-14)

| Couche | Technologie |
|--------|-------------|
| Backend | FastAPI + Python 3.11 (async) |
| Forecast | Prophet (Meta) — time-series covers + regressors |
| LLM reasoning | Claude Sonnet 4.6 (Anthropic) — explainability |
| Fallback LLM | Gemini 2.0 Flash (automatique si Claude fail) |
| Embeddings | Mistral mistral-embed (1024d) |
| Vecteurs | pgvector sur Supabase (fb_patterns + operational_memory) |
| PMS | Apaleo — OAuth2 + MCP Server streamable-HTTP |
| Alertes | WhatsApp via Twilio (push-first, UI-less) |
| DB | PostgreSQL (Supabase) |
| Cache | Redis (Upstash) |

---

## Prérequis

```bash
git clone https://github.com/ivandemurard/aetherix-hospitality-ai
cd aetherix-hospitality-ai
cp backend/.env.example .env
# Remplir au minimum : ANTHROPIC_API_KEY
# Pour la démo Apaleo en live : APALEO_CLIENT_ID, APALEO_CLIENT_SECRET
# Pour WhatsApp : TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER
```

---

## Démo reproductible — 5 étapes

### Étape 1 — Lancer la stack

```bash
docker compose up --build
```

Résultat attendu :
- Backend : http://localhost:8000/docs
- Swagger OpenAPI : http://localhost:8000/api/openapi.json
- Health : `GET /health → {"status": "ok"}`

Logs startup :
```
INFO  Providers initialised: llm=claude/claude-sonnet-4-6 embedding=MistralEmbeddingProvider
INFO  APScheduler started with 2 jobs
```

---

### Étape 2 — Vérifier la connexion MCP Apaleo (Decision #12)

```bash
curl http://localhost:8000/api/v1/pms/mcp/probe
```

Résultat attendu (avec credentials Apaleo sandbox) :
```json
{
  "status": "connected",
  "tools_count": 237,
  "latency_ms": 312,
  "sample_tools": ["APALEO_GET_RESERVATIONS", "APALEO_GET_OCCUPANCY_METRICS", "..."]
}
```

Sans credentials → `"status": "not_configured"` (non-bloquant pour le reste de la démo).

**Point clé Apaleo :** transport streamable-HTTP, OAuth2 bearer, zéro SDK tiers.

---

### Étape 3 — Entraîner Prophet sur données synthétiques (DEMO_MODE)

```bash
# S'assurer que DEMO_MODE=true dans .env
curl -X POST http://localhost:8000/api/v1/predictions/train \
  -H "Content-Type: application/json" \
  -d '{}'
```

Résultat attendu :
```json
{
  "status": "ok",
  "rows_trained": 365,
  "demo_mode": true,
  "model_saved_to": ".../demo_data/prophet_model.json",
  "message": "Prophet model trained on 365 days from demo_data/prophet_training.json. is_mock will be false on subsequent /predict calls."
}
```

Le dataset synthétique simule un hôtel 4* parisien (2025) avec :
- Saisonnalité : été +30%, Noël +20%, mardi creux -15%
- Weekly : vendredi/samedi +25%, lundi -20%
- 12 événements fictifs (Fête Nationale, Saint-Sylvestre, Fashion Week…)
- Baseline : 68 couverts dîner, range 47–157

**Mode live :** remplacer `DEMO_MODE=false` — l'endpoint appelle `ApaleoMCPAdapter.get_historical_data()` sur la fenêtre `start_date → end_date`.

---

### Étape 4 — Obtenir une prédiction F&B (covers + staffing)

```bash
curl -X POST http://localhost:8000/api/v1/predictions/predict \
  -H "Content-Type: application/json" \
  -d '{
    "hotel_id": "demo_hotel",
    "target_date": "2025-07-14",
    "service_type": "dinner",
    "context": {
      "weather": {"condition": "Clear", "temp": 28},
      "events": [{"type": "Fête Nationale"}],
      "occupancy": 0.95
    }
  }'
```

Résultat attendu (is_mock=false après training) :
```json
{
  "hotel_id": "demo_hotel",
  "target_date": "2025-07-14",
  "service_type": "dinner",
  "predicted_covers": 108,
  "confidence": 0.80,
  "range_min": 91,
  "range_max": 125,
  "is_mock": false,
  "reasoning_summary": "Fête Nationale + forte chaleur + occupancy 95% → pic attendu...",
  "claude_used": true,
  "staffing_recommendation": {
    "servers": 9,
    "kitchen": 5,
    "hosts": 2,
    "rationale": "Demand +35% vs baseline — add 2 servers vs usual service."
  }
}
```

---

### Étape 5 — Simuler une alerte WhatsApp manager

Le service WhatsApp envoie automatiquement les alertes via Twilio. Pour tester manuellement :

```bash
# Prérequis : ajouter TWILIO_SKIP_SIGNATURE_VALIDATION=true dans .env
# (évite le rejet 403 sans signature HMAC Twilio réelle)

# Simuler un webhook Twilio inbound (message "forecast" du manager)
curl -X POST http://localhost:8000/api/v1/webhooks/twilio/whatsapp \
  -d "From=whatsapp%3A%2B33612345678&Body=forecast"
```

Réponse envoyée au manager (format WhatsApp) :
```
📊 *Demand Forecast: Dinner Today*
━━━━━━━━━━━━━━━━━━
• *Predicted Covers:* 108
• *Confidence:* 80%
• *Range:* 91 - 125

📝 *Rationale:*
Fête Nationale + forte chaleur + occupancy 95%...
```

---

## Architecture agentic — pipeline complet

```
Apaleo MCP Server                    Claude Sonnet 4.6
(237 endpoints)                      (reasoning + explainability)
       │                                      │
       ▼                                      │
ApaleoMCPAdapter                             ▼
(get_historical_data)          ReasoningService.generate_explanation()
       │                                      │
       ▼                                      │
DataTransformer                              ▼
(stay_records_to_prophet)       RAGService (pgvector fb_patterns)
       │                                      │
       ▼                                      │
PredictionEngine (Prophet) ──────────────────┘
(train + predict)                             │
       │                                      │
       └──────────────► AetherixEngine.get_forecast()
                                              │
                               ┌──────────────┘
                               │
                    StaffingService.calculate_recommendation()
                               │
                    WhatsApp push via Twilio
                    (manager phone ← alert)
```

---

## Points à mettre en avant pour Apaleo

1. **MCP natif** — `streamable_http_client.py` + OAuth2 bearer, zéro SDK tiers. `GET /pms/mcp/probe` liste 237 tools en < 500ms.
2. **Agentic-first** — pas de dashboard à apprendre. Le manager reçoit la recommandation sur son téléphone et approuve ou corrige en répondant.
3. **Human-in-the-loop** — 63% des directeurs F&B veulent garder le contrôle (source : étude marché). Aetherix ne prend jamais d'action sans validation.
4. **Multi-LLM** — Claude Sonnet primary, Gemini fallback automatique. Swap sans réécriture via `LLMProvider` abstrait.
5. **Mémoire opérationnelle** — chaque correction du manager (« trop haut », « non ») est vectorisée dans pgvector et améliore les prochaines prédictions.

---

## Checklist avant démo

- [ ] `docker compose up` → health OK
- [ ] `GET /health → 200`
- [ ] `POST /predictions/train` → `rows_trained: 365`
- [ ] `POST /predictions/predict` → `is_mock: false` (**ne pas redémarrer Docker entre étape 3 et 4**)
- [ ] `GET /pms/mcp/probe` → (optionnel, nécessite credentials Apaleo sandbox)
- [ ] Swagger accessible : http://localhost:8000/docs
- [ ] `TWILIO_SKIP_SIGNATURE_VALIDATION=true` dans `.env` si simulation étape 5

---

## Variables minimales pour la démo

```bash
# .env (minimum viable)
DEMO_MODE=true
ANTHROPIC_API_KEY=sk-ant-...
MISTRAL_API_KEY=...                        # requis pour RAG / mémoire vectorielle

# Simulation webhook WhatsApp (étape 5 sans Twilio réel)
TWILIO_SKIP_SIGNATURE_VALIDATION=true

# Optionnel — Apaleo MCP live
APALEO_CLIENT_ID=...
APALEO_CLIENT_SECRET=...
APALEO_MCP_SERVER_URL=https://mcp.apaleo.com/mcp/

# Optionnel — WhatsApp push réel
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```
