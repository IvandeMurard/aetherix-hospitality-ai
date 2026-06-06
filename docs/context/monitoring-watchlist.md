# Aetherix — Competitive & Strategic Monitoring Watchlist

**Purpose:** monitor récurrents qui ne sont pas des "décisions ouvertes" (pas closeable) mais nécessitent surveillance continue. Évite que CLAUDE.md §Décisions ouvertes devienne un cimetière de canaris perpétuels.

**Cadence:** revue mensuelle minimum, idéalement embarquée dans veille Cowork hebdo (chaque lundi : check chaque item, log triggers détectés).

**Process update:** chaque item a (1) un niveau de priorité, (2) des triggers explicites, (3) une mitigation pré-cadrée. Quand un trigger se déclenche → ouvrir une vraie Décision (ADR / Décision ouverte CLAUDE.md / story Linear selon nature).

---

## Priorité 1 — surveillance critique

### W1 — Conduit.ai (concurrent adjacent hospitality)

**Profil rapide** : YC W24 · 15 employés · SF · 1000+ brands · Marriott customer · YC funding (part de pool $152.6M avec Duve/Chatlyn/Canary).
**Analyse complète** : `docs/competitive/conduit-ai-analysis.md`
**Risque** : extension "internal agents" vers F&B forecasting native OU claim mindshare marketing "F&B analytics" sans tech derrière OU client Marriott refusant Aetherix car "on a déjà notre AI hospitality".

**Triggers à monitorer chaque lundi** :
- Annonces produit *"Predictive analytics"*, *"F&B forecasting"*, *"Staffing recommendations"*, *"Demand prediction"*
- Embauches LinkedIn : "ML engineer", "data scientist", "forecast", "operations research", "time-series"
- Partenariats PMS publics : Apaleo Marketplace, Mews Marketplace, Opera, Cloudbeds
- Marriott press release mentionnant Conduit scope expansion
- Funding rounds individuels (Series A+ = signal agressivité GTM)
- Roadmap / changelog publique (actuellement absent → première publication = signal majeur)

**Mitigation pré-cadrée** :
- Si trigger "F&B forecasting" → counter-narrative immédiat sur vertical depth + eval-by-design + accelerate Phase 3 pilote
- Si trigger "Apaleo partnership" → outreach Apaleo Marketplace + activer notre listing en urgence
- Si trigger "funding round" → outreach YC founder-to-founder (Cole Rubin, Punn Kam) pour explorer partnership

### W2 — Apaleo Copilot scope F&B (canari sur PMS bedrock)

**Profil rapide** : Apaleo confirmé first PMS MCP à ITB Berlin 2026. Risque que Copilot étende vers F&B forecasting/staffing → fermerait la niche Aetherix sur le PMS bedrock (Décisions #1, #7, #21).
**Évidence** : `docs/competitive/apaleo-mcp-mapping.md` (HOS-197)

**Triggers à monitorer chaque mois** :
- Annonces Apaleo Copilot (presse Apaleo, blog officiel)
- Releases MCP tools liés à covers / staffing / F&B prediction
- Embauches Apaleo "operations AI" / "F&B product"
- Modifications de leur Marketplace (nouveaux modules F&B natifs)

**Mitigation pré-cadrée** :
- Shipper pilote HOS-176 Phase 3 avant Q4 2026
- Outreach Apaleo Marketplace pour position de complément (pas concurrent)
- Accélérer Aetherix MCP v1 pour interop défensif

## Priorité 2 — monitoring tactique

### W3 — Meuze.ai (F&B restaurants, pivot hospitality risk)

**Profil rapide** : LangGraph multi-agent, federated learning revendiqué live, customer base restaurants/QSR chains.
**Risque** : pivot vers hôtels (Accor/Marriott/IHG avec restaurants intégrés).

**Triggers** :
- Meuze pivot hospitality dans presse / Marketplace Apaleo/Mews
- Embauches sales hospitality côté Meuze
- Annonces funding Meuze (signal agressivité GTM)
- Design partner hôtelier annoncé publiquement
- Connecteur PMS ajouté (Mews/Apaleo)

**Mitigation** : reposition narrative *"hotel-native, PMS+POS-aware"* (vs Meuze POS-only restaurants). Accélérer Federated Hive narrative annonce.

### W4 — Mews Agent scope expansion

**Profil rapide** : Mews lancé "AI-native OS" 27/05/2026 avec Mews Agent (guest messaging autonome). Risque extension agent vers ops back-of-house (housekeeping, staff, F&B briefing).

**Triggers** :
- Mews Marketplace : modules "staff planning" ou "F&B forecast" natifs
- Communications produit Mews mentionnant "operations agent" ou "back-of-house"
- Embauches Mews côté "operational AI" / "F&B product"
- Mews Unfold prochain (annonce annuelle — 2027 ?)

**Mitigation** : Mews partner form (déjà à soumettre Day 1 Phase 3). Repositionner Aetherix comme F&B vertical app on top of Mews OS.

### W5 — Jengu.ai (front-of-house adjacent)

**Profil rapide** : agents IA custom hospitality, focus comm guest + pricing + voice bots. Pas mention F&B ops.
**Risque** : extension vers ops F&B (convergence probable 12-18 mois).

**Triggers** :
- Funding round publique
- Features F&B / staffing dans roadmap
- PMS specific integrations annoncées

**Mitigation** : speed Phase 3 pilote pour capture mindshare "AI for hospitality F&B" avant convergence.

## Priorité 3 — veille distante

### W6 — TravelOS / Agentic Hospitality (MCP intermédiaire)

**Profil rapide** : nouveau serveur MCP couche intermédiaire CRS/PMS, mai 2026.
**Analyse complète** : `docs/competitive/travelos-mcp-analysis.md` (HOS-198)
**Cadence** : trimestrielle.

### W7 — Aven Hospitality / SynXis (enterprise CRS MCP)

**Profil rapide** : ex-Sabre, MCP across SynXis CRS + Booking Engine, Early Access Q2 2026.
**Cadence** : trimestrielle (long-cycle enterprise).

### W8 — Hyperspell / GBrain (infra layer concurrents)

**Profil rapide** : horizontal memory + context infrastructure (pas hospitality-specific).
**Cadence** : trimestrielle si signal d'entrée hospitality.

### W9 — Lighthouse / SiteMinder MCP distribution

**Profil rapide** : convergence MCP côté distribution OTA / channel manager.
**Cadence** : trimestrielle (cycles OTA/channel)

---

## Process Cowork — intégration veille hebdo

**Suggestion add à prompt Cowork lundi matin** :

> *"Avant de générer la veille hebdo, vérifie l'état des triggers documentés dans `docs/context/monitoring-watchlist.md` (sections W1-W9). Pour chaque item priorité 1 (W1, W2) : scan presse, LinkedIn, GitHub, Marketplaces concernés ce mois-ci. Si trigger détecté → flagger explicitement dans output veille avec section dédiée 'TRIGGERS DÉCLENCHÉS' avant le triage normal des articles."*

Permet d'éviter qu'un trigger soit noyé dans 60 articles génériques. Format de sortie veille reste inchangé sinon.

---

## Maintenance

- Quand un item perd pertinence (concurrent disparu, pivot durable hors-scope, etc.) → archiver dans section ## Archived avec date
- Quand un nouvel acteur émerge → l'ajouter en priorité 2 ou 3 par défaut, promouvoir vers 1 si trigger clair
- Revue annuelle complète chaque janvier — re-priorisation globale
