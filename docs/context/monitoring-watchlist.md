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

**Status update 2026-06-20 — PAS de nouveau trigger.** Confirmation statut : ex-HostAI, $3.1M seed (PI Labs + YC, avril 2025), agents guest/ops multi-step text+voice. Aucun trigger F&B forecasting / embauche ML / partnership PMS Apaleo/Mews / nouvelle levée ce mois-ci. ⚠️ Collision de noms confirmée : ignorer "Conduit" proptech (€2.9M) et "Conduit" frontline scheduling ($375K) — pas le même acteur. Maintien cadence scan ciblé LinkedIn careers 2 semaines.

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

### W2 — Apaleo Copilot scope F&B (canari sur PMS bedrock) — 🚨 **FIRED 2026-06-08, RE-FIRED 2026-06-20**

**Status update 2026-06-20 — ESCALADE** : la couche agentique Apaleo s'étend sur 3 fronts nouveaux depuis le 08/06 :
1. **Apaleo Trace Agent** (partenariat THE FLAG) — premier agent Apaleo qui **exécute** des tâches opérationnelles (pas juste chat) à partir des reservation comments, via LLM + APIs ouvertes. Toujours pas de F&B explicite, mais le pattern "demande → tâche exécutée" est désormais prouvé en prod chez Apaleo.
2. **Copilot A2A + SOP upload** — le Copilot accepte l'upload de SOPs en texte brut ET ouvre un canal **agent-to-agent (A2A)** : des agents/apps tiers peuvent s'y connecter. Ceci change la nature du risque : pas seulement "Apaleo absorbe le F&B" mais "Apaleo devient la plateforme dans laquelle Aetherix doit choisir de se brancher (A2A) ou rester standalone (MCP)".
3. **Expansion France** (Nicolas Suissa, Country Lead) — marché direct, propriété PAR sandbox.
→ 2 items flaggés Linear ce 20/06 (spike A2A + audit Trace Agent) — voir `docs/veille/2026-06-20-veille.md` §Flaggés Linear.

**Cross-référence 06-20 — Apaleo "The Agentic Hotel" (Hotel Yearbook 2026, pub. 15/06)** : article de positionnement Apaleo confirmant **THE FLAG Zürich** comme case study flagship agentic (même partenaire que Trace Agent). Thèse : infra ouverte API-first + design property-specific + ROI = friction reduction (pas headcount reduction) — citation exemple : demande baby cot devient automatiquement tâche housekeeping, "45 min de room assignment disparaissent/jour". **Toujours aucune mention F&B/staffing/MCP/A2A/Copilot/Trace Agent dans cet article** (article distinct du lancement Trace Agent, ton plus narratif/vision). Confirme philosophie "augmentation pas remplacement" — compatible avec narrative Aetherix (tandem bike, Décision #6). THE FLAG Zürich = property à surveiller/benchmarker en priorité pour l'audit Trace Agent flaggé Linear (même partenaire, accès facilité si outreach).

**Status update 2026-06-08 — VEILLE TRIGGER DÉCLENCHÉ** : Apaleo a officiellement lancé son AI Copilot (Hospitality Net mai 2026). Scope actuel = ops multi-domaine front + back office : chat interface · check arrivals · extend stays · plan housekeeping · resolve overbookings · assign rooms. **F&B explicite PAS ENCORE**, mais expansion technique triviale depuis cette base (chat + MCP tools déjà en place).

**Scénarios à 3-6 mois (analyse PM 06-08)** :
- Scénario A (30%) — reste ops-front, F&B safe
- Scénario B (50%) — F&B "lite" (résumé historique covers, info menu) → Aetherix toujours différencié sur predictive + reasoning + memory
- Scénario C (20%) — F&B forecasting/staffing predictive natif → niche fermée sur PMS bedrock, pivot urgent requis

**Trigger d'escalade vers Scénario C** : embauches Apaleo "operations AI" mentionnant F&B / forecasting / data science · partnership annoncé avec Meuze.ai-like · release notes Copilot avec `forecast_covers` / `predict_staffing`.

**Nouveau trigger 06-20 — canal A2A** : ouverture A2A = décision archi time-sensitive indépendante du scénario F&B (A/B/C) — même si Apaleo ne fait jamais de F&B natif, le choix "Aetherix branché en A2A dans le Copilot" vs "MCP standalone" doit être tranché avant le pilote M4 (juillet 2026). Spike flaggé Linear 06-20.

**Status update 2026-06-22 — Agent Hub lancé + A2A confirmé canal officiel** : Apaleo a officiellement lancé l'**Agent Hub**, premier marketplace d'agents IA hôteliers (developers/service providers publient leurs agents), en même temps que l'ouverture A2A du Copilot à des agents tiers. Les deux voies sont désormais actionnables concrètement, pas seulement anticipées : (1) lister Aetherix comme F&B agent sur Agent Hub — visibilité 1 500+ hôtels Apaleo ; (2) brancher Aetherix en A2A comme couche F&B native de Copilot (qui ne couvre toujours pas covers/staffing). Routé en Linear sans nouvelle issue orpheline : commentaire sur [HOS-180](https://linear.app/hospitalityagent/issue/HOS-180) (Story 10.6, listing Agent Hub déjà créée Phase 3 — passée actionnable) + nouvelle [HOS-278](https://linear.app/hospitalityagent/issue/HOS-278) (Story 10.7, spike A2A, sous le même Epic HOS-174).

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

### W14 — Grevon (Kore MCP + Ops staff intelligence) — ajouté 2026-06-22

**Profil rapide** : Lancé à HITEC 2026 (San Antonio). 200+ propriétés actives, 12 pays. Suite 3 produits : **Grevon Echo** (voice agent inbound 24/7), **Grevon Pulse** (booking agent, inquiry→reservation), **Grevon Ops** (operations intelligence — terme générique, pas de claim explicite covers/staffing forecasting dans le contenu public consulté 06-22). **Grevon Kore** = couche MCP centrale ("Built on MCP, AI-native from Day 1") qui traduit les données PMS en format AI-readable — intègre 7+ PMS (Mews, Cloudbeds, Oracle Hospitality, Apaleo, etc.). Positionnement business model = direct booking / élimination commissions OTA ("Book more. Answer less."), pas F&B execution.
**Risque** : "Ops" reste vague publiquement — si la roadmap couvre covers/labor forecasting, devient concurrent direct sur le core staffing Aetherix. Architecture MCP-native dès day 1 confirme la thèse de marché Décision #21 (MCP comme standard), mais élargit le champ concurrentiel MCP-natif (s'ajoute à Apaleo, SiteMinder, Simple Booking, TravelOS, Sabre, Aven).
**Mesh check (06-22)** : aucun signal Anima (pas de guest cognition/world model), Tacet (pas de données environnementales/capteurs) ni Orchestrateur (pas de pattern multi-agent routing — Kore est un hub de données, pas un orchestrateur décisionnel) au-delà de l'architecture MCP générique déjà couverte par W2/WT1.

**Triggers à monitorer (cadence mensuelle)** :
- Détail produit Grevon Ops révélant covers/labor forecasting explicite (= concurrent direct staffing)
- Customer wins enterprise / case studies F&B
- Funding round (signal agressivité GTM)
- Partenariat ou listing croisé avec Apaleo Agent Hub (W2) — chevauchement direct de marketplace

**Mitigation** : positioning H-8 "specialist beats generalist" (cf. W10/W11) si Ops s'avère être un forecasting généraliste plutôt que F&B-spécifique. Pas d'action immédiate — scan passif jusqu'à signal Ops plus concret.
**Doc dédié** : `docs/competitive/grevon-ops.md` (à créer si W14 escalade).

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

### W5 — Jengu.ai (front-of-house adjacent) — **scan escaladé 2026-06-20**

**Profil rapide** : agents IA custom hospitality, focus comm guest + pricing + voice bots. Pas mention F&B ops.
**Risque** : extension vers ops F&B (convergence probable 12-18 mois).

**Status update 2026-06-20** : article blog Jengu *"How AI is Transforming Hotel F&B Operations"* (menu design → revenue) repéré — premier contenu publié explicitement F&B par cet acteur. Forecasting covers / staffing prediction toujours absents du pitch, mais le sujet F&B entre dans leur narratif marketing. **Cadence passée de mensuel léger → ciblé ce mois-ci** (re-scan dans 2-4 semaines pour confirmer si c'est un one-off content ou un pivot produit).

**Triggers** :
- Funding round publique
- Features F&B / staffing dans roadmap (pas juste contenu marketing)
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

### WT3 — UCP (Universal Commerce Protocol) vs MCP — race de standards agentic commerce — ajouté 2026-06-20

**Profil rapide** : Amadeus a annoncé (insight Amadeus Hospitality, juin 2026) une expansion majeure de sa stratégie IA — AI Commerce Solution (booking agentique full-stack), Amadeus Max (couche assistant cross-produit), et surtout un **co-développement avec Google d'un nouveau standard : Universal Commerce Protocol (UCP) pour le lodging**. Citation : *"AI is reshaping how travelers discover, shop, book, and experience hotels"* (Francisco Pérez-Lozao Rüter, President Hospitality, Amadeus).
**Impact si UCP devient dominant côté distribution/booking** : ne menace pas directement MCP côté ops (Décision #21, Apaleo MCP nommage natif) — UCP cible la commerce/booking layer (GDS, CRS, advertising), MCP cible la couche opérationnelle/data (PMS, F&B, staffing). Mais si Google+Amadeus imposent UCP comme franchise standard sur tout le funnel agentic hospitality (incluant des extensions vers ops), cela pourrait fragmenter l'écosystème standards (UCP commerce vs MCP ops) ou, à l'inverse, créer une pression d'interopérabilité (UCP-to-MCP bridge) à anticiper.
**Évidence baseline** : https://www.amadeus-hospitality.com/insight/amadeus-unveils-major-expansion-of-ai-strategy-across-hospitality-sector/

**Triggers à monitorer (trimestriel)** :
- UCP spec publique ouverte (vs proprietary Amadeus+Google) — déterminant pour adoption large
- Extension UCP scope vers données opérationnelles (vs commerce/booking uniquement)
- Annonce interopérabilité UCP ↔ MCP (ou absence — silo confirmé)
- Adoption UCP par d'autres GDS/CRS majeurs (Sabre, Travelport) ou PMS (Mews, Cloudbeds)
- Mentions UCP dans contexte F&B / staffing / ops (hors scope actuel = commerce pur)

**Mitigation si trigger déclenché** : pas d'action immédiate requise — Aetherix opère côté ops (MCP), pas côté commerce/booking (UCP). Si convergence ops+commerce se dessine (ex. UCP veut absorber des signaux opérationnels pour personnaliser le booking), réévaluer position MCP-native vs interop bridge.

**Cadence** : trimestrielle — protocole nouveau-né (juin 2026), pas de cron automatisé pour l'instant.

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

## Mesh-wide monitoring — Anima · Tacet (scope élargi 2026-06-15)

Reminder PM 06-15 : la veille hebdo Cowork couvre tous les nodes du Mesh, pas seulement Aetherix. Anima (Guest Context Node) en particulier nécessite veille active sur architectures agentiques + guest context platforms (PoC hackathon livré juin 2026, cf. Décision #20). Tacet (Sensory Node) = light scope, proactif uniquement si contenu pertinent partagé.

### Anima (Guest Context Node) — surveillance priorité 1

**Scope** : architectures agentiques · multi-agent frameworks · world models hospitality · guest feedback platforms · DPIA/RGPD case studies guest data.

**Repo séparé** : `C:\Users\ivand\OneDrive\Documents\anima-poc` (PoC hackathon juin 2026, Managed Agents + Fable 5).

#### W-Anima-1 — Customer Alliance (partenaire potentiel Phase 4-5)

**Profil rapide** : guest feedback platform repositionnée "guest context at scale" (multilingual, structuré, continu). Per Nicholas Reid (juin 2026) : feedback = double-sided dans agentic stack (evaluation layer + steering signal).
**Status** : **partenaire potentiel, PAS concurrent**. Couvre côté guest-side context qu'Anima ne capture pas en interne. Boucle complète possible : Customer Alliance → Anima → Aetherix → exécution → Customer Alliance confirme.
**Référence** : `docs/mesh-architecture.md` §Anima Sources de données Phase 4.

**Triggers à monitorer (trimestriel)** :
- API / MCP server Customer Alliance disponible publiquement
- Partnerships PMS public (Apaleo / Mews integration)
- Funding rounds visibles
- Roadmap publique mentionning agent integration

**Action si trigger** : outreach exploratoire partnership Phase 4-5.

#### W-Anima-2 — Architectures agentiques + world models hospitality

**Profil rapide** : surveillance générale des publications, frameworks et papers sur agents IA, multi-agent orchestration, world models hospitality, agentic stacks.

**Sources prioritaires à scanner** :
- Anthropic Managed Agents updates (Anima PoC stack — Fable 5, claude-fable-5)
- Multi-agent framework releases (LangGraph evolutions, CrewAI, Microsoft Autogen, OpenAI Agents SDK)
- World model publications hospitality (Mews position paper *"hospitality doesn't have a software problem"* à trouver URL prochaine veille)
- Customer-context platforms agentic (HiJiffy AI agents, Duve, Akia, Canary expansion AI agents)
- Academic papers : agentic memory architectures, scope-gated retrieval, DPIA/AI-Act compliance

**Triggers à monitorer (chaque lundi)** :
- Nouveau framework agentic majeur release (impact Anima architecture)
- World model paper hospitality publié (alignement vocabulaire stratégique)
- DPIA/AI-Act case study guest data (impact Décision #20 gate)
- Partnership Anthropic × hospitality (signal écosystème)

**Mitigation pré-cadrée** : aligner narrative Anima sur consensus émergent (cf. snippet H-9 *"operator intelligence layer"* pour analogue) · monitor compatibilité PoC hackathon stack avec frameworks émergents.

### Tacet (Sensory Node) — surveillance priorité 3 (light, proactif)

**Scope** : environmental data agents · IoT hospitality · sensor data platforms · Paris Open Data MCP nodes.

**Repo séparé** : hors Linear Aetherix (Décision #18).

**Cadence** : **proactif uniquement** — pas de scan systématique chaque lundi. Activé si Ivan partage proactivement du contenu pertinent (papier, post, partnership) OU si signal majeur croise watchlist Aetherix (e.g. Apaleo expose sensor data API native).

**Triggers** :
- Paris Open Data nouveaux datasets utiles (events, météo détaillée)
- IoT hospitality platforms launching MCP servers
- Sensor data agentic frameworks (rare mais à monitorer trimestriel)

**Mitigation** : reste hors-scope opérationnel jusqu'à Phase 3 Track B livré (HOS-174 MCP node Paris Open Data).

### Cross-cutting (thèses marché)

**Knowledge extraction thesis** (5 voix consolidées 06/2026 : Murati · Hyperspell · Blomfield · Anthropic playbook · **Garry Tan YC president**) → Aetherix Private Memory + Hive + cold-start + Graphe CTE = aligned consensus marché.

**MCP industry consensus** (Aven · Booking · Expedia · Turkish · Amadeus · Sabre adopting per Skift) → MCP devient table stakes, plus différenciateur unique. À monitor pour signal F&B specific.

**PMS verticalization vs hub model** : 2 stratégies opposées identifiées
- Mews OS Unfold 2026 + Cloudbeds Ask Signals = verticalization walled garden
- Apaleo Agent Hub + RentalReady (philosophy Lavie juin 2026) = hub model intégrations
- Aetherix aligned avec hub model (MCP-native + Apaleo Marketplace strategy)

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
