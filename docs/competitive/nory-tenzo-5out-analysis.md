# Nory / Tenzo / 5-Out — Competitive Analysis

**Date :** 2026-07-10
**Owner :** PM
**Type :** Concurrents adjacents restaurant-first (forecast + labor)
**Source veille :** Déjà résumés en synthèse dans `docs/competitive/concurrence.md` (09/07, Story 16.13 AC3) — ce doc apporte le detail factuel (fiches produit, case studies, architecture) qui manquait à cette synthèse, et corrige un point de cadrage sur Tenzo.
**Status :** Nory + 5-Out → **W16** (priorité 2, monitoring tactique) · Tenzo → **W15** (priorité 1, escaladé — signal hôtelier réel à confirmer)

---

## TL;DR

Trois plateformes AI forecasting + labor pour restaurants, toutes matures et financées. **Nory** et **5-Out** restent strictement restaurant/POS — zéro signal hôtelier trouvé même en creusant les pages produit. **Tenzo** casse ce pattern : page `/solutions-hotels/` dédiée + **IHG** cité comme client — c'est potentiellement le trigger que `concurrence.md` liste comme condition d'érosion de la thèse ("un acteur shippe une intégration PMS profonde + capture rate hôtelier"). **Deux éléments décisifs restent non-vérifiés** suite à une panne outil (classifier WebFetch indisponible en session) : (1) la profondeur réelle de l'offre hôtelier Tenzo (F&B seul, ou occupancy-aware avec PMS ?), (2) la nature exacte de leur "MCP (AI connector)" — standard Anthropic réel ou nom réutilisé pour une couche interne. **À confirmer prochaine session avant d'ajuster la position défensive.**

---

## Nory — restaurant-only, confirmé

**Positionnement** : "agentic AI restaurant operating system" — "a crew of AI assistants that predict demand, build staffing plans, manage ordering and payroll." Cible : marques indépendantes, réseaux franchisés, groupes enterprise restaurant (PF Chang's, Black Sheep Coffee, Grind, etc.). **Aucune mention hôtel, PMS, ou occupancy-driven forecasting** sur la homepage ni les pages produit (Business Intelligence, Inventory, Workforce Management, Payroll).

**Traction chiffrée (case studies publiées)** :
- Black Sheep Coffee (130 sites) : 98% forecast accuracy, <1% labour cost variance
- Tasty African Food : 98.5% forecast accuracy, 75% waste reduction
- Roasting Plant : 18% réduction labour cost, payroll 2 jours → 1 heure
- Passyunk Avenue : 26% réduction labour cost (95 employés)

**Lecture** : produit mûr, profondeur réelle, mais structurellement restaurant-first (POS comme source unique, aucune notion d'occupancy hôtelière). Pas de signal d'expansion vers l'hôtellerie détecté.

## 5-Out — restaurant-only, confirmé

**Positionnement** : "AI Restaurant Forecasting Software to Boost Profit." Sales forecasting (jusqu'à 21 jours, croisant historique + météo + événements locaux + tendances social media), labor optimization, smart purchasing, prep planning automation. Cible : QSR, fine dining, ghost kitchens, bars/cafés — tous restaurant, aucune mention hôtel.

**Lecture** : le plus proche d'Aetherix sur la **méthode** (fusion multi-signaux pour un forecast covers/ventes), mais toujours restaurant-only. Aucun détail technique/architecture disclosed (pas de mention MCP, pas de case studies chiffrées trouvées au-delà de témoignages qualitatifs).

## Tenzo (gotenzo.com — ⚠️ pas tenzo.ai, collision de nom avec une plateforme de recrutement IA) — signal hôtelier réel, profondeur non confirmée

**Positionnement** : "PerformanceOps" — suite unifiée (pas des produits séparés) : Aggregate / Analyse / Automate / Predict / Act / AI. Cible explicitement plus large que Nory/5-Out : "independent operators, multi-site enterprise groups, **hotels with F&B operations**." 90+ intégrations POS/labour/inventory/reviews.

**Ce qui change la donne** : une page dédiée `/solutions-hotels/` existe, et **IHG** apparaît dans la liste clients (aux côtés de Caravan, TGI Friday's, Honest Burgers, Super 8, Generator). C'est le signal le plus proche trouvé à ce jour d'un acteur restaurant-forecasting qui revendique explicitement le marché hôtelier.

**Case studies chiffrées (scope non-hôtelier confirmé, contexte restaurant/pub)** :
- Fitz Group : -3pt prime cost
- Fat Hippo : -11% bottom-line
- Generator (hostel/hybrid) : -75% temps de reporting
- Incipio : £100k/an économies labor
- Camino : -5pt labor cost

**Architecture** : mention d'un "MCP (AI connector)" décrit comme "structured, intelligent data layer" qui réconcilie les formats de données avant de nourrir des LLMs. **Non confirmé si c'est le Model Context Protocol (standard Anthropic, gouverné désormais par la Linux Foundation/AAIF, cf. veille 07-06) ou un nom interne réutilisé** — distinction importante : si c'est du vrai MCP, Tenzo devient un acteur MCP-natif de plus dans l'écosystème F&B (à recouper avec la thèse cross-cutting "MCP industry consensus" déjà trackée) ; si c'est un nom marketing, aucun changement de lecture.

### ⚠️ À vérifier — bloqué par panne outil cette session

Deux fetches ciblés ont échoué (classifier WebFetch indisponible, panne transitoire signalée par le système, pas liée au site) :
1. **`gotenzo.com/solutions-hotels/`** — contenu détaillé : est-ce que l'offre hôtelier Tenzo intègre l'occupancy (PMS) et le capture rate (part des clients hôtel qui dînent sur place), ou reste-t-elle une analytics F&B classique appliquée aux points de vente d'un hôtel (POS-only, sans le signal occupancy) ? **C'est la question qui détermine si le trigger d'érosion de `concurrence.md` (raison n°1) est réellement déclenché.**
2. **`gotenzo.com/product-ai/`** — nature exacte du "MCP (AI connector)".

**Action prochaine session** : refaire ces deux fetches en priorité avant toute mise à jour de position défensive.

## Mesh-wide check (Anima · Tacet · Orchestrateur)

Aucun signal trouvé sur les trois — pas de guest cognition (Anima), pas de données environnementales/capteurs (Tacet), pas de pattern multi-agent routing (Orchestrateur) au-delà de la couche de données Tenzo mentionnée ci-dessus. Vérification faite sur pages produit, pas seulement homepage (cf. règle process établie 06-23).

## Verdict — ajuste `concurrence.md`, ne l'invalide pas

La thèse de `concurrence.md` (§"Pourquoi le F&B hôtelier reste un espace ouvert", raison n°1 — "ils sont construits pour le restaurant, pas pour l'hôtel") **reste globalement valide pour Nory et 5-Out** (confirmé, zéro ambiguïté). Elle est **à nuancer pour Tenzo** : le tableau de `concurrence.md` le décrit comme "Restaurants & chaînes... BI-first" sans mentionner sa page hôtel dédiée ni IHG — cadrage à corriger dès confirmation du point ⚠️ ci-dessus. Si Tenzo s'avère occupancy-aware côté hôtellerie, c'est le signal le plus proche d'une érosion de la raison n°1 trouvé à ce jour, plus proche qu'Avero (qui reste analytics rétrospectif) sur l'angle "actif et en expansion vers l'hôtel".

## Sources

- [Nory](https://www.nory.ai/) — homepage + pages produit
- [5-Out](https://www.5out.io/) — homepage (⚠️ pas 5out.ai, domaine erroné)
- [Tenzo](https://www.gotenzo.com/) — homepage (⚠️ pas tenzo.ai, collision de nom confirmée avec une plateforme de recrutement IA sans rapport)
- `docs/competitive/concurrence.md` — synthèse comparative existante (09/07, Story 16.13 AC3)
