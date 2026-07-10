# Nory / Tenzo / 5-Out — Competitive Analysis

**Date :** 2026-07-10
**Owner :** PM
**Type :** Concurrents adjacents restaurant-first (forecast + labor)
**Source veille :** Déjà résumés en synthèse dans `docs/competitive/concurrence.md` (09/07, Story 16.13 AC3) — ce doc apporte le detail factuel (fiches produit, case studies, architecture) qui manquait à cette synthèse, et corrige un point de cadrage sur Tenzo.
**Status :** Nory + 5-Out → **W16** (priorité 2, monitoring tactique) · Tenzo → **W15** (priorité 2, downgradé après confirmation — voir verdict)

---

## TL;DR

Trois plateformes AI forecasting + labor pour restaurants, toutes matures et financées. **Nory** et **5-Out** restent strictement restaurant/POS — zéro signal hôtelier trouvé même en creusant les pages produit. **Tenzo** cible bien les hôtels (page `/solutions-hotels/` dédiée) mais **confirmé 07-10** : cette offre reste de l'agrégation de données multi-outlets (room service, events, restaurant, bar, minibar) **sans occupancy, sans PMS, sans capture rate** — exactement la limite structurelle que `concurrence.md` nomme comme raison n°1. Le trigger d'érosion n'est **pas** déclenché. Leur "MCP (AI connector)" est en revanche du **vrai Model Context Protocol** confirmé — un acteur MCP-natif de plus dans l'écosystème F&B, à recouper avec la thèse cross-cutting "MCP industry consensus".

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

## Tenzo (gotenzo.com — ⚠️ pas tenzo.ai, collision de nom avec une plateforme de recrutement IA) — cible les hôtels, mais reste sans occupancy/PMS (confirmé)

**Positionnement** : "PerformanceOps" — suite unifiée (pas des produits séparés) : Aggregate / Analyse / Automate / Predict / Act / AI. Cible explicitement plus large que Nory/5-Out : "independent operators, multi-site enterprise groups, **hotels with F&B operations**." 90+ intégrations POS/labour/inventory/reviews.

**Confirmé 07-10 — page `/solutions-hotels/` lue en détail** : le pitch hôtelier de Tenzo est *"get visibility into your hotel F&B operations"* via agrégation multi-revenue-centers — *"varied and spread out revenue centres: room service, conference and events, restaurant, bars, mini bars and more"*, tout ramené dans un seul endroit ("the glue between your various systems"). **Aucune mention d'occupancy-driven forecasting, d'intégration PMS (Apaleo/Mews/Opera), ni de capture rate.** C'est de l'agrégation/BI multi-outlets, pas un forecast conditionné par le taux d'occupation de l'hôtel. **IHG n'apparaît pas sur cette page** — les logos cités sont Generator & Freehand (hostel/aparthotel), Fitz Group, Fat Hippo, Incipio, NONA (IHG visible ailleurs sur le site en logo générique, mais pas rattaché à un case study hôtelier F&B).

**Case studies chiffrées (contexte restaurant/pub/hostel, pas hôtel classique avec PMS)** :
- Fitz Group : -3pt prime cost
- Fat Hippo : -11% bottom-line
- Generator (hostel/hybrid) : -75% temps de reporting
- Incipio : £100k/an économies labor
- Camino : -5pt labor cost

**Architecture — confirmé 07-10** : le "MCP (AI connector)" **est bien le Model Context Protocol réel**, pas un nom réutilisé. Citations directes : *"Built on open standards — MCP means any compatible AI can plug in, today and in the future"* ; *"Works with Claude, ChatGPT, and other leading LLMs"* ; *"No proprietary lock-in — switch models as better ones emerge, without rebuilding your data layer."* Architecture bidirectionnelle : agrège les données opérationnelles (sales/labour/inventory/reviews/reservations) et les expose en langage naturel interrogeable par n'importe quel LLM compatible MCP. Tenzo est donc un acteur MCP-natif confirmé de plus dans l'écosystème F&B — à recouper avec la thèse cross-cutting "MCP industry consensus" déjà trackée (Simple Booking, X, Anthropic/Linux Foundation AAIF, etc., veille 07-02/07-06).

## Mesh-wide check (Anima · Tacet · Orchestrateur)

Aucun signal trouvé sur les trois — pas de guest cognition (Anima), pas de données environnementales/capteurs (Tacet), pas de pattern multi-agent routing (Orchestrateur) au-delà de la couche de données Tenzo mentionnée ci-dessus. Vérification faite sur pages produit, pas seulement homepage (cf. règle process établie 06-23).

## Verdict — confirme `concurrence.md`, avec une nuance de cadrage sur Tenzo

La thèse de `concurrence.md` (§"Pourquoi le F&B hôtelier reste un espace ouvert", raison n°1 — "ils sont construits pour le restaurant, pas pour l'hôtel") **reste valide pour les trois acteurs, Tenzo compris**. Tenzo cible bien commercialement les hôtels (page dédiée, hostels/aparthotels clients), mais son produit reste structurellement une agrégation BI multi-outlets — **aucun des deux signaux qui feraient basculer la thèse (occupancy, capture rate PMS) n'est présent**. Le seul ajustement de cadrage : le tableau `concurrence.md` disait "Restaurants & chaînes" pour Tenzo sans mentionner leur ambition hôtelière explicite (page dédiée) — corrigé, mais la conclusion structurelle ne change pas. Avero reste le concurrent le plus proche côté ancrage hôtelier réel (même s'il reste analytics rétrospectif, pas prédictif à boucle fermée).

**Point positif indépendant** : la confirmation MCP réel chez Tenzo enrichit la thèse cross-cutting "MCP devient table stakes, pas différenciateur" (déjà trackée) — un signal de plus que la vraie bataille se joue sur la profondeur F&B verticale (occupancy + memory + boucle fermée), pas sur MCP-native en soi.

## Sources

- [Nory](https://www.nory.ai/) — homepage + pages produit
- [5-Out](https://www.5out.io/) — homepage (⚠️ pas 5out.ai, domaine erroné)
- [Tenzo](https://www.gotenzo.com/) — homepage + `/solutions-hotels/` + `/product-ai/` (⚠️ pas tenzo.ai, collision de nom confirmée avec une plateforme de recrutement IA sans rapport)
- `docs/competitive/concurrence.md` — synthèse comparative existante (09/07, Story 16.13 AC3)
