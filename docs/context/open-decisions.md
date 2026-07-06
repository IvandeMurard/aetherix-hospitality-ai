# Décisions ouvertes & archive

> **Périmètre :** décisions cross-cutting en débat (§Actives) + archive des décisions tranchées (§Resolved).
> **Convention CLAUDE.md :** 1 ligne d'index dans `CLAUDE.md` §Décisions ouvertes (statut + 1-ligne summary). Détail complet (rationale, alternatives, échéance, dépendances) ici.
> **Archive policy :** garder indéfiniment. Historique = asset (sales, investors, onboarding équipe).

---

## Actives

### Pricing model (HOS-179 P3-5)

**Statut :** Open
**Trigger :** Décision après 90j data pilote design partner
**Tracking Linear :** HOS-179
**Anchors documentés :**
- Anthropic playbook *"AI for Hotel Owners"* L2-L3 = $500-$2,500/property/mois multi-modules
- SafouAI €200-400/mois (mono-purpose revenue pricing)

**Reco interne :** $500-$2,500/property/mois selon scope modules activés.

### Apaleo Copilot scope F&B (canari à surveiller) — 🚨 FIRED 06-08

**Statut :** Open — **canari FIRED** (veille hebdo 06-08-2026). Monitor cadence ↑ : bi-hebdo au lieu de mensuel jusqu'à clarification scénario.

**Date documentation :** 01/06/2026 · **Trigger fired :** 08/06/2026

**Status update 06-08 :** Apaleo a officiellement lancé son AI Copilot (Hospitality Net mai 2026). Scope actuel = chat interface embedded + check arrivals + extend stays + plan housekeeping + resolve overbookings + assign rooms. **F&B explicite pas encore**, mais expansion technique triviale depuis cette base.

**Scénarios à 3-6 mois (analyse PM 06-08) :**
- **(A) 30%** — reste ops-front, F&B safe pour Aetherix
- **(B) 50%** — F&B "lite" (résumé historique, info menu, pas predictive) → Aetherix différencié sur predictive + reasoning + memory
- **(C) 20%** — F&B forecasting / staffing predictive natif → niche fermée sur PMS bedrock, pivot urgent requis

**Trigger d'escalade vers Scénario C :**
- Embauches Apaleo "operations AI" mentionnant F&B / forecasting / data science
- Partnership annoncé avec Meuze.ai-like ou similaire predictive F&B
- Release notes Copilot avec `forecast_covers`, `predict_staffing`, ou tools équivalents

**Risque historique (reformulation) :** Apaleo confirmé first PMS MCP à ITB Berlin 2026 + démos booking apps ChatGPT natives. Si Copilot étend vers F&B forecasting / staffing → ferme la niche Aetherix sur le PMS bedrock (Décisions #1, #7, #21).

**Triggers monitoring (cadence ↑ bi-hebdo, vs mensuel pré-fire) :**
- Release notes Apaleo Copilot — nouveaux tools chaque sprint Apaleo
- Embauches Apaleo "operations AI" / "F&B product" / "data science F&B"
- Modifications Marketplace (modules F&B natifs ou third-party endorsed)
- Communications product Apaleo mentionnant "covers" / "staffing prediction" / "F&B forecasting"

**Mitigation activée 06-08 :**
- ✅ Audit fonctionnel Copilot via session SM Linear story flaggée (livrable `docs/competitive/apaleo-copilot-functional-audit.md` + reco scope MCP v1 différenciateur)
- (a) Shipper pilote HOS-176 Phase 3 avant Q4 2026 — déjà roadmap
- (b) Outreach Apaleo Marketplace pour position de complément (pas concurrent) — à confirmer
- (c) Accélérer Aetherix MCP v1 (`get_operational_predictions` = primitive prédictive F&B absente des 235 tools Apaleo natifs, différenciateur défensif identifié HOS-197)

**État actuel mapping :** ✅ Mapping livré (HOS-197, 2026-06-03) → [`docs/competitive/apaleo-mcp-mapping.md`](../competitive/apaleo-mcp-mapping.md) — 235 tools classés (5 consommés / 44 border-zone F&B / 186 inutilisés), leading indicators LI-1 → LI-5, reco MCP v1 = accélérer HOS-71 v1 (`get_operational_predictions`).

**Aussi présent dans :** `docs/context/monitoring-watchlist.md` W2 (status FIRED 06-08, cadence bi-hebdo).

### Food waste tracking

**Statut :** Open
**Trigger :** Décision Phase 4 vs Phase 5 — à trancher avec PM
**Rationale :** ~25% gaspillage moyen en hôtellerie FR (ADEME/Accor), ~115g/couvert. La plupart des hôtels ne mesurent pas précisément → notre modèle crée cette donnée comme sous-produit du forecasting.
**Option A — Phase 4 :** feature ROI (€ gaspillés évités) calculé sur predicted prep vs actual covers post-service.
**Option B — Phase 5 :** intégrer POS data pour mesure précise vs juste predicted.

### Graphe de contexte Q1 backend — amendment 06/06/2026 (sous-décision ADR-0008)

**Statut :** Open — sous-décision résiduelle ADR-0008 (§13). Architecture §2 D2-D7 **tranchée Accepted**, seul le **backend hosting Apache AGE** reste à arbitrer.

**Trigger :** Vérification R6 ADR-0008 post-rédaction (06/06/2026) — Apache AGE **non supporté** Supabase managed (vérifié via GitHub Discussion supabase/#40285 + Supabase docs extensions, jun 2026 = pas dans la liste pre-approved, extension C non-trusted, pas de roadmap).

**Paths forward (PM decision required avant SM Linear kickoff) :**

- **Path A — Fly Postgres dédié + `postgres_fdw`** *(reco Architect §13.4)* — +$15-30/mois, cohérent Décision #17 Fly.io, +2j effort, single network hop intra-region cdg.
- **Path B — Neo4j Aura** — +$65/mois, viole Décision #3 frame stricte Postgres-native, +3-5j effort transport layer refactor.
- **Path C — Postgres recursive CTE fallback §R6** — $0, +1 sprint refactor, perd Cypher + expressivité limitée queries 3-hop.
- ~~Path D — Attendre Supabase AGE support~~ — bloque Phase 4 calendar, rejeté.

**Reco Architect :** Path A.

**Échéance :** avant SM Linear kickoff Phase 4 (TODO checklist ADR-0008 §14).

**Référence :** `docs/adr/0008-context-graph.md` §13 amendment complet.

### Politique d'exploration éthique (Anima / Learning Engine) (17/06/2026)

**Statut :** Open — Phase 5 (pas urgent Phase 4)
**Origine :** ADR-0011 D4 — décision explicitement déférée
**Trigger :** Kickoff Learning Engine Phase 5

**Tension centrale :** un Learning Engine qui apprend "quelle action → quel résultat" a besoin d'*explorer* — parfois délibérément ne pas donner l'action optimale connue pour tester une alternative. En hôtellerie, cela signifie expérimenter sur l'expérience d'un guest réel.

**Conflict avec :**
- "Every guest deserves the best" — la culture hospitalité s'oppose à l'idée d'offrir délibérément un moindre geste
- Décision #6 (no auto-actions) — les actions restent human-in-the-loop, donc "explorer" requiert que le manager accepte consciemment une recommandation sous-optimale
- DPIA gate (Décision #20) — exploration automatisée sur des données individuelles sensibles

**Options à trancher Phase 5 :**
- **(A)** Exploration uniquement sur des cohortes / off-policy (jamais d'exploration dirigée sur un guest identifié) — plus lent à apprendre, DPIA-safe
- **(B)** Exploration opt-in property (l'hôtel accepte explicitement un budget d'exploration en échange d'apprentissage accéléré) — contractuel, transparent
- **(C)** Exploration purement via variation naturelle (log propensity des décisions existantes, pas d'exploration forcée) — IPW / doubly-robust suffit si propensity est loggée depuis Phase 4

**Reco préliminaire :** Option C est la moins risquée et couvre le cas Phase 5 sans violation DPIA. Options A/B à reconsidérer si volume insuffisant après 12 mois.

**Dépendances :** ADR-0011 D4 (propensity logging) · Décision #6 · DPIA gate Décision #20

---

### Définition multi-objectif du reward (Learning Engine) (17/06/2026)

**Statut :** Open — Phase 5 (pas urgent Phase 4)
**Origine :** ADR-0011 — décision explicitement déférée
**Trigger :** Design Learning Engine Phase 5

**Tension centrale :** "ce qui fonctionne" n'est pas une seule métrique. Les trois objectifs naturels sont en conflit partiel :

| Objectif | Signal proxy | Tension |
|----------|-------------|---------|
| Guest satisfaction | CSAT · NPS · complaint absence | Maximiser CSAT peut coûter de la marge (geste commercial inutile) |
| Marge opérationnelle | RevPAR · F&B margin | Optimiser marge peut nuire au guest (sous-geste) |
| Fidélisation | Repeat booking · segment upgrade | Long-terme (mois) vs signal immédiat (heure) |

**Options à trancher Phase 5 :**
- **(A)** Scalarisation pondérée (α × CSAT + β × marge + γ × fidélisation) — simple, opaque, poids à calibrer par property
- **(B)** Pareto front (multi-objectif non-scalaire) — correct conceptuellement, difficile à expliquer au manager
- **(C)** Contrainte : maximiser CSAT sous contrainte de marge minimale par catégorie de geste — lisible par un opérateur hôtelier

**Reco préliminaire :** Option C — naturel pour un hôtelier ("on peut offrir un snack si marge restante > X%"), auditables par le manager.

**Dépendances :** KPI framework CLAUDE.md §KPI · pricing model (open decision HOS-179) · résultats pilote Phase 3

---

### Méthode off-policy evaluation (Learning Engine) (17/06/2026)

**Statut :** Open — Phase 5 (mais propensity logging = Phase 4, cf. HOS-247)
**Origine :** ADR-0011 D4 — décision explicitement déférée
**Trigger :** Design Learning Engine Phase 5

**Contexte :** "snack → NPS +12" n'est estimable causalement que si l'on corrige le biais de sélection (le staff offrait des snacks aux guests qui semblaient déjà satisfaits). La propensity loggée dès Phase 4 (HOS-247) permet d'appliquer des estimateurs off-policy.

**Candidats :**
- **IPW (Inverse Propensity Weighting)** — simple, instable si propensity proche de 0 ou 1
- **Doubly Robust (DR)** — combine model-based + IPW, plus stable, plus complexe
- **DR-Learner (Causal Forest)** — hétérogénéité conditionnelle de l'effet (quel geste pour *quel* profil de guest), le plus expressif mais data-hungry

**Critère de choix :** volume de triples par cellule (context × action). Avec < 500 triples par cellule : IPW. > 2000 : DR. > 10K et hétérogénéité hypothétisée : DR-Learner.

**Dépendances :** volume de données pilote Phase 3-4 · propensity logging HOS-247 (Phase 4 gate) · définition reward (open decision ci-dessus)

**Veille (20/06/2026) :** Sapiaverse (simulation à 8.14Md d'agents IA, backé Sequoia Scout/a16z Scout/NVIDIA) valide marché-niveau l'idée de "tester une politique sur une population simulée avant déploiement réel" — catégorie désormais financée sérieusement. Pas une méthode adoptable telle quelle (simulation de population générique, pas estimateur causal sur cohortes guest), mais référence utile au design Phase 5 : un méta-test "simuler le Learning Engine sur cohortes synthétiques avant d'explorer sur de vrais guests" serait cohérent avec Option (A) ci-dessus (exploration off-policy cohortes) et réduirait le risque DPIA pendant la phase d'apprentissage du choix d'estimateur.

---

### Floor k-anonymat couche Segment (17/06/2026)

**Statut :** Open — à trancher avant build Segment Phase 4
**Origine :** ADR-0011 D3 — décision explicitement déférée
**Trigger :** Build couche Segment production (Epic 4, HOS-231)

**Enjeu :** la couche Segment produit des agrégats de cohortes anonymisés. Si une cohorte est trop petite, les agrégats peuvent être suffisamment distinctifs pour ré-identifier un guest individuel (ex : "business traveler, late arrival, suite, anniversaire demain" = 1 seule personne sur la période).

**DPIA link :** ce floor est à la fois un contrôle privacy et le mécanisme qui rend la Hive prior RGPD-safe (Décision #20 + ADR-0011 D3).

**Options :**
- **(A)** Floor k=5 — minimum usuel de k-anonymat, très restrictif pour petits hôtels
- **(B)** Floor k=10 — pratique courante en analytics santé / RH — conservateur
- **(C)** Floor adaptatif selon taille property : k=5 (> 200 chambres) / k=10 (< 200 chambres) — proportionnel au risque de ré-identification
- **(D)** Différentielle privacy (DP-noise) à la place du floor — plus rigoureux, significativement plus complexe, standard ML fédéré

**Reco préliminaire :** Option C pour Phase 4 local. Option D à évaluer si la Hive prior fédérée Phase 5 nécessite des garanties formelles pour les régulateurs.

**Dépendances :** DPIA gate Décision #20 · Epic 2 compliance gate (HOS-229) · Hive prior Phase 5 design

---

### Interaction model — event-driven Phase 4-5 (04/06/2026)

**Statut :** Open — pas urgent
**Trigger :** Brief ADR-0009 futur
**Origine :** Challenge Mira Murati (Thinking Machines, *"tandem bike"* + *"time-based interaction"*) → Aetherix actuel = fondamentalement turn-based (cron daily + reply WhatsApp batch).
**Reframing PM Ivan 04/06 :** Pour notre cas (PMS-data anticipation, pas conversation continue) **event-driven > time-based**.

**Architecture cible Phase 4-5 :**
- **(a)** PMS webhook ingestion (Apaleo push booking / cancellation events)
- **(b)** External signals subscription (weather alerts, event calendars)
- **(c)** Threshold-based interim alerts — e.g. cancellation wave à 14h → push reco interim, pas attendre 06h00 lendemain
- **(d)** Manager context channel bidirectionnel — manager peut pousser tacit context en cours de journée *("banquet privé off-system ce soir, ignorer surge")*

**Trade-off :** reactivity ↑ vs alerting fatigue + complexité state / events Redis.

**Décisions liées :** #15 *"luxury feel + daily cadence"* à re-évaluer dans ce frame. #6 *"no auto-actions"* reste compatible.

**Adopté immédiatement :** marketing snippet *"tandem bike"* (`docs/marketing/positioning-snippets.md` H-6, sections Tandem bike framing).

---

### Seuils de calibration SignalComposite (ADR-0012)

**Statut :** Open — pas urgent, ne bloque pas Phase 3
**Trigger :** données pilote Phase 3 réelles
**Origine :** ADR-0012 (Décision #31), D-calibration — le modèle à 3 niveaux (prior cohorte Hive / apprentissage local / override manager) est tranché, mais les **valeurs numériques** des seuils de `significance_score` par type de `SignalComposite` ne le sont pas.

**Ce qui reste à faire :** une fois le pilote Phase 3 en cours et les premiers `recommendation_accepted`/rejected + outcomes disponibles, calibrer empiriquement à partir de quel `significance_score` un composite justifie une `RecommendationCandidate`, par domaine (`environmental.*`, `guest.*`, `fnb.*`, `operational.*`).

**Dépendances :** implémentation d'ADR-0012 elle-même gated par le tranchage de "Interaction model event-driven Phase 4-5" (ci-dessus) — ce point ne peut être calibré qu'une fois les deux construits.

---

## Resolved (archive)

### [x] Multi-repo strategy + governance — RÉSOLU 16/06/2026 → ADR-0010 (Décision #25)

**Décision :** méta-repo public `hospitality-agentic-mesh` (MIT, vitrine vision Mesh) + execution nodes privés (Aetherix, Tacet, Orchestrator, Anima). Aetherix scindé en stub public archivé (`aetherix-hospitality-ai`, redirect) + repo privé actif (`aetherix`) — résout la contradiction brief Q1 (IP privée) ↔ Q5 (redirect public). BMad par URL (pas submodule par défaut, push-back Architect sur convention PM #5). Reusable workflows CI exposés par le méta-repo public (schema-drift #16, eval-gate #22). `mesh-architecture.md` migré vers méta-repo. Conventions PM #1-7 (06-15) + Q1-Q9 tranchées.

**Phasing :** Étape 1 = status quo (rien ne bouge maintenant) · **Étape 1.5** = refonte README vision-first (exception sanctionnée, additive, faite 16/06) · **Étape 2** = sprint migration 3-5j déclenché au trigger (pilote Phase 3 livré + design partner NDA, OU pré-approche investisseurs Phase 4).

**Date :** 16/06/2026 (Architect-finalisé, PM sign-off). **Document canonique :** `docs/adr/0010-multi-repo-strategy.md`.

**Application downstream :** CLAUDE.md §Décisions architecturales #25 · `docs/context/decisions-architecturales.md` H3 §25 · README refondu (Étape 1.5) · Linear epic Étape 2 (migration sprint) à créer · numérotation : « Eval rollout discipline » spéculé → #26 si formalisé.

### [x] Graphe de contexte Postgres recursive CTE — RÉSOLU 06/06/2026 → ADR-0008 (Path C accepted)

**Décision :** Phase 4 confirmé · **Tech retenue = Postgres recursive CTE sur Supabase managed** (Path C, PM sign-off 06/06/2026 pour raison financière) · Apache AGE rejeté car non supporté Supabase managed jun 2026 (vérifié GitHub Discussion supabase/#40285 + Supabase docs extensions) · Reco Architect initiale = Path A (Fly Postgres dédié + AGE + FDW, +$15-30/mois) non-suivie pour cash discipline pre-pilote · Schema = 8 node tables + 9 edge tables `aetherix_graph.*` + RLS Postgres natives 17 policies · Coexistence permanente pgvector + CTE (pas de cutover — pgvector reste source recall sémantique flou, CTE source recall relationnel/path via single-transaction `WITH RECURSIVE` + UNION ALL avec pgvector cosine) · `MemoryRecallService.recall()` étendu backward-compat param `recall_strategy: Literal["cosine_only","path_find","hybrid","cohort_traversal"]` default `"cosine_only"` zéro régression callers Phase 0-3 · Cohort matching v3 multi-dim path traversal (γ × cos_pms + δ × cos_pos + ε × path_match_score) extension ADR-0006 D4 · Forward-compat schema Anima Phase 4 (`Guest`/`Stay`/`Sentiment` réservés non créés, DPIA gate reste blocker Anima) · MCP tool atomique `query_context_graph(query_type, depth)` scope `graph:read` whitelist 6 query types Phase 4 (templates SQL CTE, pas Cypher) · Tenant isolation RLS Postgres natives (simplifié vs Path A `_inject_tenant_filter`) + canary eval `graph-tenant-isolation-001` blocking + `GRAPH_BACKEND=disabled` kill-switch · SLO latence p95 amendé < 1200ms (vs 800ms Path A — verbosité CTE acceptable cash-driven trade-off).

**Réversibilité Phase 5+** : si Supabase ajoute support Apache AGE (monitor `docs/context/monitoring-watchlist.md` WT1 trimestriel + cron `check-supabase-apache-age-compatibility`), Path A redevient option viable. Migration CTE schema → AGE Cypher MERGE documentée ADR-0008 §16, effort estimé 1-2 sprints.

**Date :** 06/06/2026 (session Architect Opus dédiée, brief PM 04/06 — formalisation + résolution + amendment Path C même session, pré-requis ADR-0006 POS tranché 06/06 même journée).

**Rationale :** (a) Convergence thèse *"knowledge extraction = the real bottleneck"* (Mira Murati Thinking Machines + Hyperspell + GBrain + projet personnel Lore — `memory/market_signals_2026Q2.md` 04/06) ; (b) Cohort matching v2 ADR-0006 = late-fusion **scalar** insuffisant pour traverser *"event A causé outcome B chez hôtel co-cohorte 18 mois plus tôt"* — graphe = relations explicites traversables ; (c) Foundation Anima Phase 4 Guest Context Node (Décision #20 4 couches) nécessite relations explicites guest × stay × event × intervention ; (d) Aetherix Voice Phase 5+ (Lore-inspired tacit knowledge capture, `docs/context/vision-future.md`) pré-requis knowledge graph relationnel.

**Story breakdown Phase 4 (Path C amendé)** : 6 stories, **26 points**, ~6-7 sprint-weeks single-dev. P4-GRAPH-1 → P4-GRAPH-6 (vs 5 stories / 21 pts Path A initial — +1 story / +5 pts surcoût refactor CTE accepté PM). Sequencing Phase 4 = POS d'abord (semaines 1-4 via ADR-0006), GRAPH ensuite (semaines 5-11).

**Application downstream :**
- CLAUDE.md §Décisions architecturales ligne d'index #24 (libellé *"Postgres recursive CTE"*)
- `docs/context/decisions-architecturales.md` H3 §24 détail complet amendé Path C (Q1-Q7 + DDL 17 tables `aetherix_graph.*` + cohort v3 + Anima forward-compat + 6 query types CTE templates + eval gate `context_graph_query`)
- `docs/adr/0008-context-graph.md` document canonique (Accepted Path C, 9 risques + amendment §13 PM sign-off + §16 patterns CTE override D1/D2/D4/D6)
- `docs/context/memory-architecture.md` section ajoutée "Couche graphe Phase 4 (ADR-0008)" amendée Path C
- `docs/context/monitoring-watchlist.md` WT1 — réouvrir Path A si Supabase ajoute AGE Phase 5+
- Cron `check-supabase-apache-age-compatibility` (1er trim 9h) — notification user si statut change
- Débloque Anima Phase 4 (forward-compat schema réservé `Guest`/`Stay`/`Sentiment`) · Aetherix Voice Phase 5+ (expressivité CTE inférieure à Cypher reconnue, à reconsidérer si AGE disponible Phase 5+)

**Variables env nouvelles (Path C)** : `GRAPH_BACKEND` (default `postgres_cte` Phase 4 | `apache_age` Phase 5+ option si WT1 trigger | `disabled` kill-switch). Pas de `GRAPH_DATABASE_URL` ni `GRAPH_FDW_ENABLED` (Path C = même DB Supabase).

**Trade-off PM documenté** : raison financière (Path A +$15-30/mois × multi-tenant Phase 5+ vs Path C $0). Effort dev +1 sprint refactor accepté. Expressivité Cypher manquante = limitation connue, mitigée via WT1 watchlist trimestrielle pour réouvrir Path A si Supabase débloque AGE.

### [x] POS integration scope + adapter pattern — RÉSOLU 06/06/2026 → ADR-0006

**Décision :** Phase 4 confirmé · Tier 1 vendors = Lightspeed K-Series (pick #1) + Oracle Micros Simphony (pick #2 conditionnel) · Pattern = `POSProvider` Protocol dans `backend/app/providers/pos/` + adapter par vendor (cohérent Décision #9 `LLMProvider` jurisprudence) · Read-only Phase 4 via `POS_READONLY=true` default + `POSWriteBlockedError` (cohérent Décision #7) · Impact ADR-0005 = table sœur `hotel_cohort_features_pos` avec 3 features POS-driven (item-mix Dirichlet 9-dim, ticket-size quantiles per service, time-of-day 168 buckets) + late-fusion blending.

**Date :** 06/06/2026 (formalisation + résolution même session — pas de passage §Actives intermédiaire car brief PM 04/06 a tranché directement la session Architect Opus dédiée)

**Rationale :** (a) Meuze.ai *"POS-only restaurants"* confirmé 01/06 — défense narrative *"PMS+POS-aware cross-property intelligence"* (snippet H-6) requiert ship Phase 4 ; (b) ADR-0008 graphe de contexte bloqué tant que schema POS non tranché ; (c) ADR-0005 cohort v1 PMS-only insuffisant pour discriminer boutique BER 80 chambres breakfast-heavy vs même profil PMS dinner-heavy.

**Story breakdown Phase 4 :** 6 stories, 24 points, ~6 sprint-weeks single-dev (P4-POS-1 → P4-POS-6).

**Application downstream :**
- CLAUDE.md §Décisions architecturales ligne d'index #23
- `docs/context/decisions-architecturales.md` H3 §23 détail complet (Q1-Q4 + DDL + Protocol + story breakdown + eval gate `pos_anomaly`)
- `docs/adr/0006-pos-integration.md` document canonique (Accepted, 8 risques + DoD opérationnel)
- Débloque open decision *"Graphe de contexte — Phase 4 priority"* (cf. §Actives — pré-requis POS marked DÉBLOQUÉ)
- Étend open decision *"Food waste tracking"* Option B (mesure précise via POS items vs forecast — débloquée Phase 4 si pilote ship POS)

**Variables env nouvelles :** `POS_BACKEND` (default `mock`), `POS_READONLY` (default `true`), `LIGHTSPEED_CLIENT_ID/SECRET`, `MICROS_TENANT_ID/CLIENT_ID/CLIENT_SECRET` (conditionnel Phase 4.4).

### [x] Federated Hive timing — RÉSOLU 04/06/2026

**Décision :** **OUI** — avancer la narrative communication à *"announced Phase 3 + shipped Phase 4"*.
**Date :** 04/06/2026 (correction post-confusion initiale "Non" → "OUI")
**Rationale :** Meuze.ai revendique federated learning live en production. Pour ne pas paraître en retard dans les sales conversations contre Meuze (et tout futur concurrent), communiquer Federated Hive comme roadmap publique dès Phase 3 (design doc public + LOO validation visible) tout en shippant prod en Phase 4. Coût annonce ~0, retire le talking point différenciant à Meuze.
**Application downstream :**
- README §Roadmap Phase 4 highlights : *"Federated HiveMemory ship (announced Phase 3)"*
- `docs/marketing/positioning-snippets.md` H-7 snippet (cohort intelligence + raw data sovereignty + Day-1 unlock)
- `docs/context/vision-future.md` Phase 4 narrative

### [x] Hive Memory scope Phase 3 — RÉSOLU 28/05/2026 → ADR-0005

Swap *"LLM persona generation"* → **cold-start meta-learner** ACCEPTÉ dans HOS-174 Track B. Architecture validée :
- Cohort matching hybride (hard rules + embedding cosine)
- Prior Prophet via `add_seasonality` + hyperparams calibrés
- Blending Bayesian model averaging (`n_eff_prior=30`, hard cutoff J+90)
- Gate runtime auto-disable si Day-7 MAPE > 25%

Nouvelle table `hotel_cohort_features` (coefficients agrégés, opt-in tenant). MCP tool `query_cohort_prior` ajouté. Validation pré-pilote : LOO sur 5 sandbox properties. LLM persona déplacé Phase 4. Détail → `docs/adr/0005-cold-start-meta-learner.md`. Action SM : amender HOS-174 (P3-7 amend + P3-7b/7c new, +8 pts).

### [x] PMS priorité live — RÉSOLU 17/05/2026

Apaleo prod Phase 3 (1 design partner, HOS-176). Mews déplacé Phase 4 + form partner à soumettre Day 1 Phase 3 (latence approval).

### [x] MCP server — RÉSOLU 19/04/2026

FastAPI endpoint dédié retenu — `/mcp/v0` mounted sur l'app principale (lifespan partagé, ADR D2). Shippé via PR #73. Sidecar process rejeté (coût ops, pas de bénéfice latence observé).

### [x] Apaleo MCP direct — RÉSOLU 31/03/2026

URL confirmée `https://mcp.apaleo.com/mcp/`, transport HTTP Streamable (SSE déprécié — notre `streamablehttp_client` est correct). Scope MCP activé sur le compte (code IIQJ). Auth OAuth2 bearer identique à la raw API. Activer via `POST /pms/sync?use_mcp=true` + `APALEO_MCP_SERVER_URL=https://mcp.apaleo.com/mcp/` dans `.env`.

### [x] ROI dashboard vs WhatsApp — RÉSOLU implicitement post-Phase 1

WhatsApp primary retenu (cf. Décision #15 OQ1 — Receipts channel = WhatsApp + email opt-in). Dashboard différé Phase 3+ si adoption le justifie.

---

## KPIs à instrumenter (référence — voir aussi CLAUDE.md §KPI framework)

- `tool_success_rate` > 99.5%
- `p95_latency` < 500ms
- `schema_stability` = 0 breaking changes par sprint
- `agent_retry_rate` < 1%
- `MAPE` couverts < 15%
- `recommendation_acceptance_rate` (alerte si < 30%)
- `labor_cost_variance` cible –3% à –8%

---

## Notes de maintenance

- **Update protocol** : décision tranchée → déplacer de §Actives à §Resolved avec date + rationale. **Ne pas supprimer.**
- **Index CLAUDE.md** : pour chaque décision active = 1 ligne dans `CLAUDE.md` §Décisions ouvertes (statut + 1-ligne summary). Le détail (alternatives, échéance, dépendances, sources) vit ici.
- **Cross-références** : ADR (`docs/adr/`) pour décisions techniques validées. Watchlist (`docs/context/monitoring-watchlist.md`) pour monitors récurrents perpétuels (Conduit.ai, Apaleo Copilot, etc.).
