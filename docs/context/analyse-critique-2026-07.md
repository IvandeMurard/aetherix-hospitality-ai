# Analyse critique — Aetherix + Tacet (juillet 2026)

> Audit exhaustif réalisé le 07/07/2026 (session Claude Code). Portée : repo Aetherix complet + `tacet-app`.
> Objectif : évaluer la pertinence de continuer, la différenciation, la valeur en recherche d'emploi, et prioriser les 90 prochains jours.
> Plan d'action dérivé : [`docs/planning/plan-90j-proof-visibility.md`](../planning/plan-90j-proof-visibility.md)

---

## TL;DR

Le projet est au-dessus du niveau portfolio classique — la discipline d'ingénierie (eval-gates CI bloquants, guardrails runtime typés, 11 ADRs, ratio tests/code 1.13) est rare et non commoditisée. Trois problèmes structurels :

1. **Zéro utilisateur réel** après 8 mois et 862 commits — aucun des 5 maillons de la chaîne de valeur n'est prouvé empiriquement.
2. **Invisibilité publique** : repo principal privé, le lien GitHub du case study (ivandemurard.com/aetherix) renvoie un 404 pour tout visiteur.
3. **Déséquilibre docs/code** : 58 300 lignes de docs (292 fichiers .md) pour 16 500 lignes de code applicatif (ratio 3.5:1) — risque de "fiction-driven development" : le Mesh 4 nœuds est à ~80 % une construction documentaire (Anima et Orchestrateur = documents ; Tacet = prototype 1 400 lignes).

**Décision : continuer, mais réallouer l'effort — moins d'architecture, plus de preuve empirique et de visibilité.**

---

## Constats factuels

### Aetherix
- ~16 500 lignes app / ~18 600 lignes tests / 37 services / 21 routes / 11 ADRs / CI verte (schema drift + eval-gate bloquant).
- Code échantillonné propre (Prophet en `asyncio.to_thread`, providers en `Protocol` runtime-checkable).
- Frontend : 10 fichiers .tsx (thin assumé, mais faible pour démontrer).
- **MAPE 15.09 % synthétique = structurellement circulaire** : `scripts/ops/generate_demo_data.py` génère les couverts à partir de `weather_score`/`event_impact`/`occupancy`, et Prophet reçoit exactement ces 3 régresseurs. Le modèle retrouve la formule génératrice — ce chiffre ne prouve rien sur données réelles et ne doit plus être mis en avant. Attendu réel : MAPE J+1 20-35 %.

### Tacet (`tacet-app`, public)
- ~1 400 lignes, 2 fichiers de test, pas de CI, dernier commit 10/06/2026.
- Moteur acoustique (heatmap polaire 360 rayons + shielding par polygones) réel et testable.
- **README surclame** : le "Decentralized Mesh P2P (Triangulation)" n'existe nulle part dans le code ; le "3D ray-tracing" est un lancer de rayons 2D sur empreintes de bâtiments. Branding "defense/Urban ISR" contre-productif pour l'hôtellerie de luxe.
- C'est le seul repo public → vitrine par défaut, et elle dessert le niveau réel du travail.

---

## Chaîne de valeur — 5 maillons, état de preuve

| # | Maillon | État | Détail |
|---|---------|------|--------|
| 1 | **Les données existent** | ❌ Non prouvé — maillon le plus faible | Apaleo ne fournit pas les couverts restaurant. Tout repose sur l'historique POS (Phase 4, non construit) ou un capture rate jamais validé. |
| 2 | **Le forecast est bon** | ❌ Inconnu | Seul benchmark = synthétique circulaire. La vraie métrique : delta vs baseline naïve (moyenne des 4 derniers mêmes jours de semaine). Si Prophet ne bat pas la baseline de 5+ pts, pas de raison de payer. |
| 3 | **Le forecast change une décision** | ⚠️ Douteux à J+1 | Plannings figés J+7/J+14 (contraintes légales FR). Un forecast J+1 sert achats/mise en place, pas vraiment le staffing. Tension non tranchée entre horizon prédit (J+1) et horizon décisionnel (J+7+) — question produit majeure absente des ADRs. |
| 4 | **Le manager adopte** | ⚠️ Plausible, non testé | WhatsApp = bon canal. Seuil d'alerte auto-défini : acceptance < 30 %. |
| 5 | **L'économie tient** | ❌ Non calculé | Coût LLM+infra/propriété/mois vs pricing (HOS-179 ouvert). |

**Verdict : système bien construit, valeur non prouvée. Trois maillons (2, 3, 5) sont prouvables sans pilote** — voir protocole dans le plan 90j.

---

## Différenciation réelle (non commoditisée)

- Positionnement "execution node à bounded context strict + orchestrateur séparé" (ADR-0004) — thèse d'architecture agentique mûre.
- Eval-by-design en gate CI **bloquant** avec Prophet déterministe prouvé (Décision #29, canari 3 runs, variance 0.00pp) — quasi inexistant en projet solo, matériel d'article technique.
- Guardrails runtime typés (ADR-0009, invariant NFR2) + gestion d'incident sécurité réelle documentée (Q2-01 : filter-repo + rotation 11/11 clés).
- Distribution push-first WhatsApp + MCP-native ("glue, not replacement").

## Risques de crédibilité

- Mesh présenté comme existant → un interviewer technique le perce en 10 min. À présenter comme north star assumée, avec périmètre construit vs vision explicite.
- Volume assisté par IA (branches `claude/*`, 292 docs) : atout ("j'industrialise le travail agentique") **uniquement si chaque décision est défendable à l'oral**.
- Concurrence frontale non adressée : Nory, Tenzo, 5-Out font forecast F&B + staffing ; menace plateforme si Apaleo/Mews shippent un forecast natif.

## Wedge produit & moat (positionnement)

- **Forecast et Daily Receipt ne sont pas antinomiques — hiérarchie** : le Receipt (rituel quotidien de confiance) est la surface produit, le forecast est le moteur qui le rend crédible. Conséquences : north-star = `recommendation_acceptance_rate` + `weekly_operational_usage` (le MAPE devient exigence interne de qualité, pas le pitch) ; le marketing mène avec le rituel.
- **Moat** = mémoire cognitive par propriété (contexte + signal + feedback), PMS-agnostic (schéma canonique Décision #28), effet réseau multi-propriété (Hive prior). C'est ce qui survit si les PMS shippent un forecast natif. À articuler dans un doc positionnement (action au plan).

## Valeur recherche d'emploi

Dossier de niveau staff-engineering judgment (evals, guardrails, ADRs, incident response) — plus convaincant que du LeetCode, à condition de : (1) rendre le travail visible publiquement (méta-repo), (2) remplacer les claims par des mesures, (3) pouvoir tout défendre à l'oral. Cibles : Mews, Apaleo, Lighthouse, Amenitiz, Nory, Tenzo, équipes applied-AI.
