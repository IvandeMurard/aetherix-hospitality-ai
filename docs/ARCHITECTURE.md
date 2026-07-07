# Aetherix — Architecture (pointeur)

> **Version :** 0.3.0 · **Dernière mise à jour :** 07/07/2026
> L'ancienne version de ce document (v0.2.0, fév. 2026, 1 000+ lignes) contenait des sections obsolètes (Streamlit, Render.com) et divergeait des décisions actées. Elle a été remplacée par ce pointeur : **la vérité architecturale vit dans les sources ci-dessous, pas ici.**

---

## Où trouver quoi

| Question | Source de vérité |
|---|---|
| Stack, décisions actées (index #1–#31), roadmap, env vars | [`CLAUDE.md`](../CLAUDE.md) (racine) |
| Détail des décisions architecturales | [`docs/context/decisions-architecturales.md`](context/decisions-architecturales.md) |
| Architecture cross-repos du Mesh (Aetherix · Tacet · Orchestrateur · Anima) | [`docs/mesh-architecture.md`](mesh-architecture.md) — **SOURCE DE VÉRITÉ CROSS-REPOS** |
| Décisions structurantes datées (ADR) | [`docs/adr/`](adr/) — 0001 → 0012 |
| Catalogue de toute la documentation | [`docs/INDEX.md`](INDEX.md) |
| Audit critique + plan 90 jours (juil. 2026) | [`context/analyse-critique-2026-07.md`](context/analyse-critique-2026-07.md) · [`planning/plan-90j-proof-visibility.md`](planning/plan-90j-proof-visibility.md) |

## Résumé en 10 lignes

**Aetherix** est le nœud d'exécution F&B du Hospitality Agentic Mesh : forecast de couverts (Prophet + régresseurs météo/événements/occupancy), recommandations staffing, mémoire opérationnelle par propriété (pgvector), et livraison push-first ("Daily Receipts" WhatsApp via Twilio). Il **recommande, le manager valide** — aucune action autonome (Décision #6), pas d'orchestration dans les services (ADR-0004 : l'orchestrateur est un composant séparé).

- **Backend** FastAPI + Python async (Fly.io `cdg`) — Thin Frontend / Fat Backend (Décision #8)
- **Données** Supabase Postgres + pgvector (Mistral 1024d, HNSW) · Redis Upstash (session)
- **LLM** Claude Sonnet via abstraction `LLMProvider` multi-backend (Décisions #9/#10)
- **PMS** Apaleo (OAuth2, read-only Phase 0) via adapter + schéma canonique (ADR-0006 amendé, Décision #28)
- **MCP Server** (`backend/app/mcp_server.py`) — tools atomiques uniquement
- **Fiabilité** : eval-by-design en gate CI bloquant (ADR-0007, Décision #29) + guardrails runtime typés (ADR-0009, invariant NFR2 : tout trip loggé avec raison typée)

## Arborescence code

Voir `CLAUDE.md` §Fichiers clés. Entrées principales : `backend/app/services/` (exécution F&B), `backend/app/providers/` (abstraction LLM/embeddings), `backend/orchestrator/` (proto-orchestrateur Phase 3), `scripts/ci/` (gates), `.github/workflows/` (CI + eval-gate + veille).
