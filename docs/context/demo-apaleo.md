# PRD Démo — Aetherix × Apaleo

> **Audience :** Lennart Reents, AI Engineer @ Apaleo — équipe AI
> **Objectif :** démontrer un pipeline agentique F&B end-to-end intégrant le MCP Server Apaleo officiel
> **Format livrable :** Loom 90 secondes + repo GitHub public
> **Date cible :** Avril 2026
> **Dernière mise à jour :** 2026-04-13 — Session PM

---

## 1. Boucle agentique — Cycle complet J-1 14h00

### Trigger

Cron interne (APScheduler) à **14h00 J-1** pour chaque hôtel actif.
> Rationnel : les webhooks Apaleo couvrent les changements de réservation, pas les triggers temporels. Déclenchement manuel alternatif : `POST /api/v1/notifications/send-daily`.

---

### Étape 1 — Validation connexion MCP

```
GET /pms/mcp/probe
```

- Vérifie APALEO_CLIENT_ID, APALEO_CLIENT_SECRET, APALEO_MCP_SERVER_URL
- Acquiert un token OAuth2 (client_credentials flow)
- Ouvre une session MCP streamable-HTTP, appelle `list_tools` (handshake)
- Retourne : `{"status": "ok", "latency_ms": 187, "tools_available": 42}`
- Si échec → fallback `ApaleoPMSAdapter` (raw REST identique)

---

### Étape 2 — Fetch données PMS via MCP

```
POST /pms/sync?use_mcp=true&property_id=IIQJ&date=2026-04-17
```

MCP tools appelés (via `ApaleoMCPAdapter`) :
- `APALEO_GET_OCCUPANCY_METRICS` → taux d'occupation J (ex : 78 %)
- `APALEO_GET_RESERVATIONS` → réservations confirmées dîner (ex : 142)
- `APALEO_GET_REVENUE_METRICS` → pace revenue vs baseline

---

### Étape 3 — Contexte externe

- **Météo** : WeatherAPI → température, précipitations J (ex : 18 °C, ciel dégagé)
- **Événements locaux** : PredictHQ → events dans rayon 5 km pour J (ex : PSG–Barça 20h45, stade à 1,8 km, 45 000 spectateurs)
- Assemblés dans `context: Dict` transmis au moteur

---

### Étape 4 — Forecast Prophet

```python
forecast = PredictionEngine().predict(
    target_date=date(2026, 4, 17),
    features={
        "occupancy_pct": 78,
        "day_of_week": 3,        # jeudi
        "weather_temp": 18,
        "weather_type": "clear",
        "event_proximity_km": 1.8,
        "event_attendance": 45000,
    }
)
# → predicted_covers=87, confidence=0.81, is_mock=False
```

---

### Étape 5 — RAG — Patterns similaires (pgvector)

```python
patterns = await RAGService().find_similar_patterns(
    context_query="jeudi soir, match PSG, occupancy 78 %, météo claire",
    service_type="dinner"
)
# → 3 patterns historiques (score cosine > 0.75)
# ex : "2025-11-07 : 91 couverts, match PSG, occupancy 82 %" — score 0.89
```

Embedding Mistral 1024d, collection `fb_patterns`, index HNSW sur Supabase pgvector.

---

### Étape 6 — Mémoire (MemoryService)

```python
memory_ctx = await MemoryService().get_relevant_context(
    tenant_id="hotel-pullman-paris",
    query="jeudi soir match football"
)
# → "2025-11-14 : manager avait refusé reco +2 staff.
#    Résultat réel : 88 couverts, service débordé."
```

Alimente le prompt Claude comme signal comportemental du manager.

---

### Étape 7 — Raisonnement Claude Sonnet

```python
reasoning = await ReasoningService().generate_explanation(
    predicted_covers=87,
    confidence=0.81,
    target_date=date(2026, 4, 17),
    service_type="dinner",
    context=context,
    similar_patterns=patterns,
    cognitive_context=memory_ctx,
)
# → {"summary": "...", "confidence_factors": [...], "claude_used": True}
```

Claude synthétise : Prophet + RAG + mémoire → explication WhatsApp (3 lignes) + chain-of-thought complet (réservé au "Pourquoi ?").

---

### Étape 8 — Staffing

```python
staffing = await StaffingService().calculate_recommendation(87)
# → {"recommended": 6, "current_planned": 5, "delta": +1}
```

---

### Étape 9 — Format message WhatsApp

```
🍽️ Aetherix | Demain soir (jeu 17 avr)

Prévision : 87 couverts (+23 % vs sem. dernière)
Staff recommandé : 6 personnes (vous avez planifié 5)
🔴 Alerte : Match PSG à 1,8 km — arrivée attendue 19h30

Répondre *Pourquoi ?* pour l'explication complète
```

---

### Étape 10 — Push + Logging

- `WhatsAppService` envoie via Twilio (whatsapp: + E.164)
- `ActionLogger` log l'action (Décision #7 — toutes les actions agent logguées)
- `MemoryService` stocke la recommandation pour signal de feedback futur

---

### Flow "Pourquoi ?" (inbound)

```
Manager → "Pourquoi ?"
  ↓
POST /webhook/whatsapp  (Twilio webhook)
  ↓
WhatsAppService.handle_inbound_message()
  ↓
MemoryService.log_interaction("why_requested")
  ↓
ReasoningService.generate_explanation(full_chain_of_thought=True)
  ↓
Claude → 5 bullet points :
  • Prophet forecast : +23 % vs baseline jeudi (regresseur event activé)
  • 3 patterns similaires (score moyen 0.84) : 88–94 couverts
  • Événement : PSG–Barça, 45 K spectateurs, 1,8 km
  • Météo favorable : 18 °C, dégagé → terrasse probable +12 %
  • Mémoire : 14 nov 2025 — débordé avec 5 staff (88 couverts réels)
  ↓
Twilio → push WhatsApp réponse
```

---

### Flow "What if?" (simulation — Phase 2, hors scope démo)

```
Manager → "Et si -10 % occupancy ?"
  ↓
QueryParser.parse_intent() → {type: simulation, param: occupancy, delta: -0.10}
  ↓
AetherixEngine.get_forecast(modified_context)
  ↓
→ "Avec 70 % d'occupation (-10 %) : prévision 78 couverts, 5 staff suffisent."
```

---

## 2. Script démo Loom — 90 secondes

### Scénario

**Hôtel Pullman Paris (sandbox Apaleo IIQJ), mercredi 14h00.**
PSG–Barça annoncé jeudi 20h45 au Parc des Princes (1,8 km de l'hôtel).
L'agent tourne automatiquement. Le manager est sur WhatsApp.

---

### Storyboard (90 s)

| Timing | Ce qu'on voit | Narration |
|--------|--------------|-----------|
| 0:00–0:10 | Split-screen : terminal uvicorn \| JSON watch \| phone WhatsApp | "Voici Aetherix — un agent F&B qui tourne sans interface. Il va prédire les couverts de demain soir et les pousser au manager." |
| 0:10–0:22 | `curl .../pms/mcp/probe` → `{"status": "ok", "tools": 42, "latency_ms": 187}` | "D'abord, la connexion directe au MCP Server Apaleo — officiel, streamable-HTTP, OAuth2." |
| 0:22–0:38 | Logs : MCP sync → occupancy 78 % → réservations 142 → event PSG détecté | "L'agent récupère occupancy et réservations via MCP, puis détecte le match PSG à 1,8 km." |
| 0:38–0:55 | Logs AetherixEngine : Prophet 87 covers (81 %) → pgvector 3 patterns → Claude reasoning | "Prophet forecast, 3 patterns historiques similaires en pgvector, puis Claude Sonnet synthétise." |
| 0:55–1:10 | Phone : WhatsApp reçoit le message | "Le manager reçoit la recommandation — push WhatsApp, pas de dashboard." |
| 1:10–1:30 | Manager tape "Pourquoi ?" → logs webhook → Claude → réponse WhatsApp visible | "Il répond 'Pourquoi ?' — Claude explique en temps réel. Human-in-the-loop." |

---

### Données

**Décision : Apaleo sandbox OAuth réel en priorité.**
- Si sandbox disponible : authentification réelle (client_id IIQJ, scope MCP activé)
- Fallback si indisponible le jour J : `ApaleoPMSAdapter` mock mode avec données synthétiques Paris réalistes (occupancy 78 %, 142 resas dîner, event PSG injecté manuellement)
- **Le MCP probe tourne dans les deux cas** — preuve d'intégration même en fallback

---

## 3. Format Loom — Démontrer l'expérience UI-less

### Benchmark agents UI-less / push-first

| Produit | Format démo | Leçon |
|---------|-------------|-------|
| **Linear AI** | Terminal + état résultant (issue créée) | L'agent travaille à l'écran, pas un replay |
| **Harvey AI** | Terminal + document output | La vitesse d'exécution = le spectacle |
| **Dust.tt** | Logs d'appel API + output structuré JSON | Transparence = confiance pour les devs |
| **Intercom Fin** | Conversation thread seule | Le canal IS l'interface — pas besoin d'autre chose |

**Leçon synthèse :** Pour une audience AI Engineer, le terminal scrollant = la meilleure "UI". Aucune fioriture nécessaire. La densité d'information visible en temps réel est plus convaincante qu'un dashboard épuré.

---

### Setup split-screen recommandé

```
┌──────────────────────┬──────────────────────┬──────────────────┐
│  Terminal (uvicorn)  │  JSON live (watch)   │  WhatsApp phone  │
│                      │                      │                  │
│ INFO  MCP probe ok   │  {                   │  [notification]  │
│ INFO  sync IIQJ      │    "covers": 87,     │                  │
│ INFO  Prophet 87cv   │    "confidence":0.81,│  🍽️ Aetherix...  │
│ DEBUG Claude: "PSG   │    "staff_delta": +1 │  87 couverts     │
│        +23%, 3 pat." │  }                   │  Répondre...     │
│ INFO  WA pushed      │                      │                  │
└──────────────────────┴──────────────────────┴──────────────────┘
```

**Colonne 1 — Terminal uvicorn** : `uvicorn app.main:app --log-level debug`
**Colonne 2 — JSON watch** :
```bash
watch -n1 'curl -s -H "Authorization: Bearer $TOKEN" \
  localhost:8000/api/v1/predictions/latest | jq .prediction'
```
**Colonne 3 — Phone** : screenshare iPhone/Android ou Twilio sandbox console (navigateur)

---

### Rendre le raisonnement Claude visible sans UI

Ajouter une ligne de log DEBUG dans `ReasoningService.generate_explanation()` :

```python
logger.debug(
    "Claude reasoning summary: %s",
    explanation[:200]  # premiers 200 chars suffisent
)
```

Cela fait défiler la chain-of-thought Claude dans le terminal pendant la démo — visible, impressionnant, sans aucune UI.

---

### Construire un terminal-style viewer ?

**Non.** Pas nécessaire pour cette démo. L'effort de dev ne vaut pas la valeur ajoutée pour une audience AI Engineer qui lit les logs directement. Si un viewer est construit un jour, ce sera pour les managers — pas pour la démo candidature.

---

## 4. Scope minimal — Décisions tranchées

### Périmètre fonctionnel

| Feature | Décision | Justification |
|---------|----------|---------------|
| Couverts dîner forecast | **IN** | Core value prop |
| Staffing recommendation | **IN** | Impact direct manager, déjà implémenté |
| "Pourquoi ?" flow | **IN** | Signature human-in-the-loop — ne pas couper |
| MCP probe live | **IN** | Signal fort pour Apaleo — argument d'ouverture |
| "What if?" simulation | **OUT** | Phase 2 — complexifie sans ROI pour la démo |
| Petit-déjeuner | **OUT** | Phase 2 — dilue le scénario |
| Weather simulation | **OUT** | Contexte supportant, pas la démonstration principale |

### Données

**Apaleo sandbox OAuth réel + mock fallback automatique.**

Argument pour le réel : `GET /pms/mcp/probe → {"status": "ok"}` en live = preuve irréfutable d'intégration MCP. Aucun slide ne remplace ça.

### Stack démo — État actuel

| Composant | Fichier | Statut | Action requise |
|-----------|---------|--------|----------------|
| `ApaleoMCPAdapter` | `services/apaleo_mcp_adapter.py` | Implémenté | Aucune |
| `GET /pms/mcp/probe` | `api/routes/pms.py` | Implémenté | Tester avec creds réels |
| `AetherixEngine` | `services/aetherix_engine.py` | Implémenté | Aucune |
| `ReasoningService` + Claude | `services/reasoning_service.py` | Implémenté | Ajouter log DEBUG reasoning |
| `WhatsApp` Twilio | `services/whatsapp_service.py` | Implémenté | Tester avec sandbox Twilio |
| Cron trigger 14h00 | — | **Manquant** | Ajouter APScheduler ou déclencher manuellement |
| Script `demo_run.sh` | — | **Manquant** | Créer (probe → sync → push) |
| Log verbeux Claude | `services/reasoning_service.py` | **Manquant** | +1 ligne logger.debug |

### Actions Dev prioritaires (hors scope PM)

1. Vérifier `APALEO_MCP_SERVER_URL=https://mcp.apaleo.com/mcp/` dans `.env`
2. Tester `GET /pms/mcp/probe` avec creds IIQJ → doit retourner `status: ok`
3. Ajouter `logger.debug("Claude reasoning: %s", explanation[:200])` dans `ReasoningService`
4. Créer `scripts/demo_run.sh` : probe → sync → `POST /api/v1/notifications/send-daily`
5. Tester WhatsApp end-to-end avec Twilio sandbox

---

## Checklist avant enregistrement Loom

- [ ] `GET /pms/mcp/probe` retourne `{"status": "ok"}` (OAuth + handshake MCP)
- [ ] `POST /pms/sync?use_mcp=true` retourne des données (réelles ou mock réaliste)
- [ ] `AetherixEngine` retourne 87 couverts ± scénario PSG
- [ ] Log DEBUG reasoning Claude visible dans le terminal
- [ ] WhatsApp reçoit le message (Twilio sandbox ou phone réel)
- [ ] "Pourquoi ?" déclenche la réponse Claude complète via webhook
- [ ] Split-screen configuré (terminal + JSON watch + phone)
- [ ] Police terminal > 16pt, couleurs contrastées (lisible à la compression Loom)
- [ ] Token JWT valide pour les appels curl de démo

---

*Auteur : Agent PM Aetherix*
*Source : session PM 2026-04-13 — missions 1–4 complétées*
