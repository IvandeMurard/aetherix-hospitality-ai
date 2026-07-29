# Digest veille — mars/avril 2026

> Compression des rapports hebdomadaires antérieurs au trimestre courant (Story 16.2 / HOS-302, AC4).
> Originaux conservés dans [`docs/_archive/veille/`](../_archive/veille/).

## Synthèse

Les rapports automatisés de la période (23/03 → 27/04, 2 reports + 5 drafts) sont tous vides : **aucun article n'a franchi le seuil de pertinence 7/10** sur la fenêtre. Deux lectures :

1. Le pipeline `veille_proactive.py` fonctionnait (génération hebdo régulière) mais ses sources RSS étaient trop généralistes pour le seuil — la qualité des rapports s'améliore à partir de juin (cf. `2026-06-08-veille.md` et suivants) après l'élargissement de la lentille full-Mesh.
2. Le seul contenu retenu de la période est la note manuelle **Andrew Chen — agent-first distribution** (22/03, archivée : [`docs/_archive/veille/2026-03-22-andrew-chen-agent-first-distribution.md`](../_archive/veille/2026-03-22-andrew-chen-agent-first-distribution.md)) — thèse : la distribution se déplace vers les agents (SEO → AEO), cohérente avec le pari MCP-native d'Aetherix (middleware `agent_tracking.py`, P1-5).

## Signaux durables extraits de la période (sources : notes manuelles + mémoire marché Q2)

- **Apaleo** reste le PMS API-first de référence pour la distribution agentique (candidature + MCP probe validés sur la période, Décisions #12/#21).
- La **commoditisation des wrappers LLM** se confirme — c'est la période où la thèse "la différenciation = evals + guardrails + mémoire propriétaire" s'est formée (aboutissant à la Décision #22 eval-by-design, 04/06).

## Veille courante

Rapports actifs (≤ 3 mois) : `docs/veille/2026-06-*.md`, `2026-07-*.md` · Watchlist : [`docs/context/monitoring-watchlist.md`](../context/monitoring-watchlist.md) · Automatisation : `.github/workflows/veille-hebdomadaire.yml` (lundi 8h30, réparé 07/07 — fix `_env_loader` sys.path).
