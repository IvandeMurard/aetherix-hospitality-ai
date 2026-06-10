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

### W2 — Apaleo Copilot scope F&B (canari sur PMS bedrock) — 🚨 **FIRED 2026-06-08**

**Status update 2026-06-08 — VEILLE TRIGGER DÉCLENCHÉ** : Apaleo a officiellement lancé son AI Copilot (Hospitality Net mai 2026). Scope actuel = ops multi-domaine front + back office : chat interface · check arrivals · extend stays · plan housekeeping · resolve overbookings · assign rooms. **F&B explicite PAS ENCORE**, mais expansion technique triviale depuis cette base (chat + MCP tools déjà en place).

**Scénarios à 3-6 mois (analyse PM 06-08)** :
- Scénario A (30%) — reste ops-front, F&B safe
- Scénario B (50%) — F&B "lite" (résumé historique covers, info menu) → Aetherix toujours différencié sur predictive + reasoning + memory
- Scénario C (20%) — F&B forecasting/staffing predictive natif → niche fermée sur PMS bedrock, pivot urgent requis

**Trigger d'escalade vers Scénario C** : embauches Apaleo "operations AI" mentionnant F&B / forecasting / data science · partnership annoncé avec Meuze.ai-like · release notes Copilot avec `forecast_covers` / `predict_staffing`.

**Profil rapide** : Apaleo confirmé first PMS MCP à ITB Berlin 2026. Risque historique : Copilot étend vers F&B forecasting/staffing → fermerait la niche Aetherix sur le PMS bedrock (Décisions #1, #7, #21).
**Évidence base** : `docs/competitive/apaleo-mcp-mapping.md` (HOS-197) · **Audit fonctionnel** : à créer via session SM 06-08 → `docs/competitive/apaleo-copilot-functional-audit.md`

**Triggers à monitorer (cadence ↑ : bi-hebdo au lieu de mensuel jusqu'à clarification scénario)** :
- Release notes Apaleo Copilot — nouveaux tools chaque sprint Apaleo
- Embauches Apaleo "operations AI" / "F&B product" / "data science F&B"
- Modifications Marketplace (modules F&B natifs ou third-party endorsed)
- Communications product Apaleo mentionnant "covers" / "staffing prediction" / "F&B forecasting"

**Mitigation pré-cadrée (activée 06-08)** :
- ✅ Audit fonctionnel Copilot via session SM Linear story prioritaire (✓ flaggé 06-08)
- Shipper pilote HOS-176 Phase 3 avant Q4 2026 (déjà roadmap)
- Outreach Apaleo Marketplace pour position de complément (pas concurrent) — Marketplace activation à reconfirmer
- Accélérer Aetherix MCP v1 (`get_operational_predictions` primitive prédictive F&B absente des 235 tools Apaleo natifs — différenciateur défensif identifié HOS-197)

### W10 — OtelAI (concurrent F&B direct UK/Ireland) — ajouté 2026-06-08

**Profil rapide** : UK/Ireland · Founder Paul Ryan (ex-Accor CTO advisor) · 6 départements incl. F&B explicite · ISO 27001 + GDPR · O'Callaghan Collection case study (+8.6% RevPAR) · PMS stack enterprise (Opera/Guestline/IDeaS/Duetto, **pas Apaleo/Mews mentionné**).
**Analyse complète** : `docs/competitive/otelai-analysis.md`
**Risque** : extension F&B vers predictive forecasting/staffing native OU buyer UK/IE achète "tout-en-un" et refuse Aetherix add-on.

**Triggers à monitorer chaque lundi** :
- Annonces produit *"F&B forecasting"*, *"covers prediction"*, *"staffing recommendations"* (= extension scope vers le nôtre)
- Embauches LinkedIn : "ML engineer", "data scientist", "forecast", "F&B product"
- Partenariats PMS publics : Apaleo Marketplace, Mews Marketplace (= expansion modern ecosystem)
- Funding rounds (Series A+ = signal agressivité GTM)
- Customer wins enterprise (Marriott/Hilton/IHG flag = enterprise capture)

**Mitigation** : positioning snippet H-8 *"specialist beats generalist"* + Apaleo Marketplace listing rapide + outreach Paul Ryan post-Phase 3 pilote.

### W11 — TH1.ai / Theone Inc (concurrent F&B stealthy multi-property) — ajouté 2026-06-08

**Profil rapide** : Stealth team (founders anonymes) · 16 mois R&D European boutique hotels · 5-50 properties target · F&B ops + restaurant bookings + multi-property workflows · 100+ heures économisées/property/year claim · custom enterprise pricing.
**Analyse complète** : `docs/competitive/th1-ai-analysis.md`
**Risque** : lifting stealth = visibility marché soudaine · expansion vers F&B predictive natif · enterprise customer capture flag.

**Triggers à monitorer chaque lundi** :
- Lifting stealth : founders disclosure, funding round visible, customer reference flag
- Annonces *"F&B forecasting"*, *"covers prediction"*, *"staffing prediction"*
- Embauches LinkedIn ML engineering F&B
- Partenariats PMS publics
- Pricing publication (passage stealth → mid-market)

**Mitigation** : positioning snippet H-8 partagé avec OtelAI + Apaleo Marketplace listing + Phase 3 pilot delivery rapide.

**À vérifier prochaine session** : confirmer URL canonique TH1.ai (ambiguïté th1.ai vs thine.com vs theone.inc dans les sources veille 06-08).

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

### W12 — Venli (Apaleo Marketplace concurrent adjacent) — ajouté 2026-06-08

**Profil rapide** : Danish startup <10 employees · "Agent Management System for Hospitality" · 5-tools replacement (messaging + housekeeping + sales + reporting + analytics) · Apaleo-native + 100+ intégrations · €99-299/mois transparent · 14-day free trial.
**Pas de F&B forecasting predictive** dans scope actuel.
**Pertinence** : (a) concurrent Apaleo Marketplace direct sur audience hôtelière mid-market · (b) **template référence format listing Apaleo Marketplace** pour Aetherix · (c) pricing anchor pour HOS-179 (€99-299 mid-market multi-modules).

**Triggers** :
- Ajout module F&B forecasting / staffing predictive (pivot vers notre scope)
- Funding round visible (signal agressivité)
- Partnership Mews (extension écosystème)
- Customer wins Marriott/Hilton/IHG flag

**Mitigation** : shipper Apaleo Marketplace listing Aetherix avant Venli pivot F&B · différenciation F&B vertical specialist (vs Venli generalist 5-tools replacement).

### W13 — Cloudbeds Ask Signals AI (PMS verticalization continue) — ajouté 2026-06-08

**Profil rapide** : Spring Release 2026 — Cloudbeds ajoute Ask Signals (AI conversational beta) + Groups & Events + Spaces + Accounting + Insights. PMS verticalization pattern post-Mews OS Unfold 2026. **Pas de F&B encore**.

**Triggers** :
- Ajout F&B au scope Ask Signals (forecasting / staffing / covers)
- Partnership Meuze-like ou F&B predictive specialist
- Marketplace Cloudbeds avec apps F&B endorsed
- Communication Cloudbeds mentionnant "covers" / "staffing prediction"

**Mitigation** : monitor quarterly (cycle PMS release plus lent que startups) · Aetherix reste API-first Apaleo+Mews focused.

### W5 — Jengu.ai (front-of-house adjacent)

**Profil rapide** : agents IA custom hospitality, focus comm guest + pricing + voice bots. Pas mention F&B ops.
**Risque** : extension vers ops F&B (convergence probable 12-18 mois).

**Triggers** :
- Funding round publique
- Features F&B / staffing dans roadmap
- PMS specific integrations annoncées

**Mitigation** : speed Phase 3 pilote pour capture mindshare "AI for hospitality F&B" avant convergence.

## Tech compatibility watch (infrastructure dependencies)

> Items techniques externes dont l'évolution peut débloquer ou changer une décision architecturale Aetherix.
> Différent des items W1-W9 (concurrents) — ici c'est de la veille techno passive sur des fournisseurs / extensions / standards.

### WT1 — Apache AGE support sur Supabase managed

**Profil rapide** : Apache AGE = extension Postgres graphe (OpenCypher partial). Non supportée par Supabase managed au 06/06/2026 (extension C non-trusted, pas dans pre-approved list — vérifié via GitHub Discussion supabase/#40285 + Supabase docs extensions).
**Impact si supporté** : ADR-0008 §13 Path A redevient option viable. Migration Path C (Postgres recursive CTE retenu Phase 4) → Path A (Apache AGE backend) faisable Phase 5+ — expressivité Cypher >> CTE sur queries 3-hop.
**Évidence baseline** : `docs/adr/0008-context-graph.md` §13.1.

**Triggers à monitorer (trimestriel)** :
- Supabase ajoute Apache AGE à la liste officielle des extensions ([docs](https://supabase.com/docs/guides/database/extensions))
- Mise à jour de la GitHub Discussion supabase/#40285 (statut officiel)
- Annonce Supabase blog / changelog mentionnant graph database / Cypher / AGE
- pg_tle support C extensions (déblocage indirect)

**Cadence automatisée** : scheduled task `check-supabase-apache-age-compatibility` (cron `0 9 1 */3 *` — 1er du mois trimestriel 9h). Output Markdown court, notification user si changement détecté.

**Mitigation si trigger déclenché** :
- Ouvrir session Architect pour amender ADR-0008 §13 (Path C → Path A migration plan)
- Évaluer effort migration CTE → AGE (export tables → MERGE Cypher, ~1-2 sprints estimés)
- Décision PM : migrer Phase 5 OU rester sur CTE si pas de bénéfice business démontré

### WT2 — Embedding strategy (pgvector vs Qdrant) — trigger Phase 4 multi-tenant scale

**Profil rapide** : Décision #3 = `pgvector > Qdrant > Pinecone` **actée** (Phase 0-3 confirmé suffisant < 50K patterns / < 50 hôtels, latence MCP < 500ms préservée). Cette entrée **n'est pas une décision ouverte** mais un trigger to revisit Phase 4 si scale multi-tenant l'impose.
**Évidence baseline** : CLAUDE.md §Décisions architecturales #3 + `docs/context/memory-architecture.md`.

**Triggers à monitorer (Phase 4 onwards)** :
- Nombre de patterns `operational_memory` cross-tenants > 50K
- Nombre de tenants actifs > 50 (cohérent seuil Phase 0-1 documenté)
- p95 latence `MemoryRecallService.recall()` > 400ms (approche SLO 500ms)
- HNSW index size > 80% capacité Supabase tier actuel
- Qdrant Cloud annonce drops latency / coût significatifs vs pgvector + Supabase

**Mitigation si trigger déclenché** :
- Ouvrir Décision ouverte §Actives + session Architect pour ADR migration vector DB
- Évaluer Qdrant managed (rejeté Phase 0 — *"504 timeouts documentés"*) vs Pinecone vs alternative Phase 4 (2026 marché peut avoir évolué)
- Tester migration shadow read (dual-write `operational_memory` Supabase + Qdrant, compare results) avant cutover

**Cadence** : passive — déclenche review **uniquement** sur trigger. Pas de cron récurrent (gaspillage si pas atteint).

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
