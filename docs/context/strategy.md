# Positionnement stratégique & Pivot Agent-First

> Chargé par les sessions Veille, PM, Analyst, et Architect quand pertinent.
> Dernière mise à jour : Mars 2026

---

## Pivot Agent-First (Mars 2026)

> "Distribution shifts from top of funnel to top of call stack." — Andrew Chen (a16z)
> "Agent SEO where ranking factors are success rate across thousands of agent runs."

**Implication :** Aetherix doit être callable par des agents IA (Claude, Codex, Cursor) via MCP, pas seulement accessible via dashboard.

Issues actives : **HOS-71** (MCP Server), **HOS-72** (Agent SEO métriques)

**Capabilities MCP candidates :**
- `forecast_occupancy(hotel_id, date_range)`
- `get_stock_alerts(hotel_id)`
- `recommend_menu(hotel_id, context)`
- `get_fb_kpis(hotel_id, period)`

**Métriques Agent SEO à instrumenter :**
- `tool_success_rate` > 99.5%
- `p95_latency` < 500ms
- `schema_stability` = 0 breaking changes par sprint
- `agent_retry_rate` < 1%

---

## Positionnement vs PMS

Apaleo et Mews déploient des Agent Hubs en 2026 (pricing, guest messaging, onboarding). Aetherix est **complémentaire, non concurrent**.

**Périmètre Aetherix :** read-only PMS data + push messaging + explainability + human-in-the-loop.
**Ce que les Agent Hubs ne font pas :** ops decision copilot F&B/staffing avec forecast domain-specific, reco contextualisée, self-improving memory per property.

**Règle absolue :** Ne jamais implémenter de features qui concurrencent les modules natifs Apaleo/Mews (pricing dynamique, guest messaging génériques). Rester dans le périmètre F&B ops + staffing + forecast.

**A2A Communication :** MCP-ready → Aetherix devient une primitive appelable dans les workflows d'autres agents. Exemple : agent revenue Apaleo détecte +18% occupancy → appelle Aetherix `adjust_staffing_reco()`.

---

## Apaleo — Contexte spécifique

- Apaleo a lancé son AI Copilot (A2A, SOPs uploadables) + MCP Server officiel (sept. 2025)
- F&B forecasting/alertes = **absent du Copilot Apaleo = niche ouverte confirmée**
- MCP Server Apaleo couvre réservations, CRM, housekeeping, paiements — pas le F&B
- Compatible plug-and-play avec les clients MCP Anthropic
- **Composio (30/03/2026) :** expose uniquement l'Inventory API (properties/units). PAS occupancy/revenue/reservations. `ApaleoPMSAdapter` (raw REST) reste le path principal pour les données F&B. Accès alpha direct Apaleo = next step.
- **Agent Hub Apaleo** (2 000+ propriétés, 30+ pays) = canal de distribution Phase 1. Rejoindre le MCP Alpha Group dès maintenant (community.apaleo.com).
- **MCP Server :** FastAPI endpoint dédié vs sidecar process séparé — décision non tranchée.

---

## Stickiness — Ce qui rend difficile l'internalisation

1. **Private Memory par hôtel** (2+ ans de données propres) → coût de migration élevé
2. **Hive Memory anonymisée** (patterns cross-hôtels) → impossible à reproduire sans volume
3. **Chain-of-thought hospitality-specific** → ne s'improvise pas avec un LLM générique
4. **Human oversight comme feature produit** → chaque refus de reco améliore le modèle suivant

---

## Défense contre la commoditisation des LLMs

Les LLMs deviennent commodity. Le vrai moat est dans :
1. Données + mémoire per-property (Private + Hive Memory)
2. Domain reasoning spécialisé (RAG sur 495+ patterns F&B)
3. Human oversight comme signal d'entraînement

→ Multi-LLM fallback via `LLMProvider` abstrait (Décision architecturale #9 dans CLAUDE.md)

---

## Acteurs à surveiller

- **DialogShift** (Olga Heuser) — 95%+ automation chat/email/tel hôtels, avance sur MCP
- **Lighthouse / Connect AI** — premier booking direct dans ChatGPT via MCP
- **IDeaS / Duetto** — RMS enterprise (Marriott, Accor), room-only, hors segment PME Aetherix
- **Canary Technologies** — guest management (check-in, upsell), 20K hôtels, adjacent mais pas F&B ops

---

## Référence architecture

- `linq-team/linq-resy-agent` (MIT) — pattern Claude tool-use + webhook + conversation state, à adapter pour Aetherix. (HOS-100)
