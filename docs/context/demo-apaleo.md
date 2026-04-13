# Démo Apaleo — Contexte & Décisions

> Chargé par les sessions PM, Architect, Dev, SM quand la démo est en scope.
> **Mettre à jour :** après chaque décision sur le scope, l'infra, ou le script de la démo.
> Dernière mise à jour : 2026-04-13

---

## Objectif

Publier une démo end-to-end sur le repo public GitHub dans le cadre d'une candidature
chez Apaleo (AI Engineer / Product Builder). Audience cible : Lennart Reents + équipe AI Apaleo.

**Ce qui impressionne cette audience :** MCP Server intégré + raisonnement expliqué + pipeline
qui tourne — pas une UI soignée.

---

## État actuel (2026-04-13)

| Composant | Statut | Notes |
|-----------|--------|-------|
| Backend FastAPI | Fonctionnel | 30 services, 13 routes, 22 tests verts |
| Apaleo OAuth2 client | Fonctionnel | HOS-136 corrigé, imports MCP au niveau module |
| GET /pms/mcp/probe | Fonctionnel | Health-check synchrone MCP — argument fort pour Apaleo |
| WhatsApp Twilio | Fonctionnel sur mock | HOS-132 hardened |
| Prophet forecast | Mock uniquement | Bloquant pour démo réelle |
| Credentials Apaleo sandbox | Absents du .env | Bloquant #1 |
| Pipeline end-to-end | Jamais tournée sur données réelles | Bloquant #2 |
| demo_script.md | Legacy (Mistral/Qdrant 2025) | À réécrire pour Claude/pgvector |
| Composio MCP (Claude Desktop) | Cassé — CLI breaking change | Non bloquant pour démo |

---

## Bloquants (ordre de priorité)

1. **Credentials Apaleo sandbox dans .env** — sans ça, rien ne peut tourner sur des données réelles
2. **Prophet sur données réelles** — dataset synthétique réaliste acceptable pour démo
3. **demo_script.md réécrit** — le script legacy crée une contradiction avec le README actuel
4. **Loom 90s** — artifact le plus important pour la candidature

---

## Pipeline démo cible

```
Apaleo sandbox (GET réservations/occupancy)
    → Backend FastAPI (ApaleoMCPClient + ApaleoAdapter)
    → Prophet forecast (données réelles ou synthétiques réalistes)
    → Claude Sonnet reasoning (explainability)
    → WhatsApp message (recommandation + "Why?")
    → [optionnel] Réponse manager "Why?" → Claude explique
```

---

## Décisions à trancher (avec PM et Architect)

- [ ] Scope minimal démo : couverts dîner uniquement ? ou dîner + staffing + "Why?" ?
- [ ] Données : credentials sandbox Apaleo réels vs dataset synthétique (HotWire/Amadeus) ?
- [ ] Infra démo : Docker Compose local uniquement vs endpoint déployé accessible publiquement ?
- [ ] Visual : que montrer dans le Loom pour un produit UI-less ?
- [ ] MCP probe dans démo : inclure GET /pms/mcp/probe comme preuve de connexion ?

---

## Atouts différenciants à mettre en avant

1. `GET /pms/mcp/probe` — preuve d'intégration directe du MCP Server Apaleo (URL https://mcp.apaleo.com/mcp/)
2. F&B forecasting = niche absente du Copilot Apaleo natif (confirmé strategy.md)
3. Multi-LLM fallback + explainability = aligné avec les valeurs AI d'Apaleo
4. Architecture self-improving (Private Memory + Hive Memory) = moat défendable

---

## Référence

- Profil cible : Lennart Reents, AI Engineer Apaleo (post LinkedIn 2026-04-13)
- Repo public : https://github.com/IvandeMurard/aetherix-hospitality-ai
- Branche de travail : claude/ai-demo-publication-mIIl3
