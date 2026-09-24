# CLAUDE.md — Aetherix

> Source de vérité partagée. Chargé automatiquement à chaque session.
> **Règle — NE PAS SURCHARGER CE FICHIER.** Facts + INDEX uniquement, **plafond dur 170 lignes** (relevé de 150 le 31/07 : l'index de décisions a grandi, cf. `docs/INDEX.md` §Dette CLAUDE.md). Contrôlé en CI — détecteur D5.
> Une décision **architecturale tranchée** = une ligne d'index ici, détail en sous-section de `context/decisions-architecturales.md`. Une décision **ouverte** ne s'indexe plus ici depuis le 11/08 (pointeur seul) : elle vit entièrement dans `context/open-decisions.md`. Ni narratif, ni justification, ni historique ici : si ça ne tient pas en une ligne, ça va en sous-section et on met le lien.

---

## Projet

**Aetherix** — Plateforme IA agentique pour la gestion des opérations F&B hôtelières.
**Philosophie :** "Thin Frontend / Fat Backend" — logique métier et orchestration IA dans le backend.
**Paradigme :** Agentic-first (UX) + API-first (infra) + Human-in-the-loop (confiance).

---

## Stack

| Couche | Technologie | Notes |
|--------|------------|-------|
| Backend | FastAPI + Python 3.11 | Async, Pydantic v2 |
| Base de données | Supabase (PostgreSQL) | Auth, real-time |
| Vecteurs | pgvector (Supabase) | `fb_patterns` + `operational_memory`, Mistral 1024d, HNSW |
| Cache | Redis (Upstash) | Session state, TTL 1h |
| IA principale | Claude Sonnet | Reasoning + explainability. Multi-LLM via `LLMProvider` (Décision #9) |
| Forecast | Prophet (Meta) | Time-series covers + regressors (météo, events, occupancy) |
| Frontend | Next.js (App Router) + shadcn/ui | Thin — vérification uniquement |
| Alertes | WhatsApp via Twilio | Push-first, UI-less |
| PMS principal | Apaleo | OAuth2 + MCP Server officiel |
| PMS secondaire | Mews | Webhook, marketplace |

---

## Décisions architecturales — INDEX

> Détail complet : [`docs/context/decisions-architecturales.md`](docs/context/decisions-architecturales.md)
> Ne pas remettre en question sans raison documentée. Ajouter une nouvelle décision = ligne ici + détail dans le sous-fichier.

| # | Décision | Date |
|---|---|---|
| 1 | Claude Sonnet > Mistral/GPT | — |
| 2 | Architecture mémoire 2 couches (Private + Hive) | — |
| 3 | pgvector > Qdrant > Pinecone | — |
| 4 | Voice opt-in (pas voice-first) | — |
| 5 | Reasoning collapsible par défaut | — |
| 6 | Pas d'auto-actions (Phase MVP) | — |
| 7 | Apaleo read-only Phase 0 | — |
| 8 | Thin Frontend | — |
| 9 | Multi-LLM via `LLMProvider` abstrait | — |
| 10 | Provider singleton via `lifespan` FastAPI | — |
| 11 | Démo — stratégie données hybride (Apaleo sandbox + synthétique) | — |
| 12 | MCP Server Apaleo — probe suffisant pour candidature | — |
| 13 | Pipeline Prophet — gap training identifié | — |
| 14 | Phase 0 DoD amendée — MCP Server v0 inclus | 17/04/2026 |
| 15 | Phase 2 "Receipts" — scope locké | 19/04/2026 |
| 16 | Schema drift gate CI obligatoire | 14/05/2026 |
| 17 | Hébergement Fly.io | 14/05/2026 |
| 18 | Phase 3 cut serré + portfolio reinforcement | 17/05/2026 |
| 19 | Orchestrateur séparé — Aetherix = F&B execution node | 19/05/2026 |
| 20 | Anima — architecture mémoire 4 couches + DPIA gate — **analyse RGPD/CNIL livrée 01/08/2026 (HOS-229, `docs/context/dpia-anima-2026-08.md`) : gate NON levé**, 13 mesures bloquantes ; Semantic n'est plus « ∞ » (36 mois glissants) ; biométrique/voix + émotion sur le personnel = lignes rouges AI Act ; Hive prior fait d'Aetherix un responsable de traitement | 19/05/2026 |
| 21 | Apaleo MCP — convention nommage native + sales evidence Anthropic | 26/05/2026 |
| 22 | Eval-by-design = offline gate CI + runtime eval + outcome eval (Qonto + BMad ; portée élargie 3 bras, amendé 19/06 ADR-0007 §13) | 04/06/2026 |
| 23 | POS integration scope + adapter pattern (Phase 4) — **§D4 cohort v2 différé 31/07/2026** (ADR-0006 §10) : `hotel_cohort_features` v1 n'existe pas et son socle Hive est gelé ; la FK dans la migration P4-POS-2 bloquait tout le backlog POS. Ingestion POS reste livrable : 5 stories / 19 pts | 06/06/2026 |
| 24 | Graphe de contexte Postgres recursive CTE — Path C retenu cash-driven, AGE bloqué Supabase. 🛑 **DIFFÉRÉ Phase 4 en entier (PM sign-off 31/07/2026, ADR-0008 §17.6)** : moitié du graphe adossée à `hotel_cohort_features` inexistante + socle Hive gelé ; `Cohort` = frontière d'anonymisation donc query types cross-propriétés non dégradables ; ce qui reste double pgvector. Conception Path C intacte, arbitrage de calendrier. Reprise = précondition ADR-0006 §10.4. Effet transitif : ADR-0011 différé | 06/06/2026 |
| 25 | Multi-repo strategy + governance (méta-repo public + execution nodes privés) — **exécuté 07/07/2026** (déclencheur pré-candidatures) : méta-repo public [`Hospitality-Multi-agent-Architecture`](https://github.com/IvandeMurard/Hospitality-Multi-agent-Architecture) livré et vérifié (public, README propre, 0 fuite ADR-0012/Signal Contract), Aetherix reste privé, cross-link tacet-app. ADR-0012 jamais migré (Décision #31). **HOS-305 AC4 clos — vérifié 11/08/2026 : `ivandemurard.com/aetherix` pointe vers le méta-repo, zéro occurrence du repo privé** | 16/06/2026 |
| 26 | Anima = Guest Cognition Layer · confidence-weighted claims (schema, pas couche) · Segment double portée (local + Hive prior) · Learning Engine tier Mesh séparé · outcome-capture instrumentation Phase 4 | 17/06/2026 |
| 27 | Phase de mise en conformité (Epic 12 — runtime guardrails post-audit) **clôturée** : G-1→G-5 livrés (heartbeat/dead-man's switch, alerting error-rate/timeout, bornes feedback→training, circuit-breaker forecast tiered-confidence, bornes sanity outputs) + 6 findings QA-S4 ; G-6 prompt-injection **différé Phase 4**. Invariant : tout trip guardrail loggé avec raison typée (NFR2). Pattern = **ADR-0009** ; frontière runtime (Bras B) vs offline-eval (Bras A) = ADR-0007 §13 ; audit clôturé `docs/context/security-review-2026-05-01.md` | 20/06/2026 |
| 28 | PMS canonical schema — jurisprudence Provider (#9/#10) étendue aux adapters PMS, amendement **ADR-0006** | 23/06/2026 |
| 29 | Eval-gate EVAL-1 passé **WARN→blocking** (HOS-274) : exit 1/2 bloque le merge, exit 3 (WARN) reste non-bloquant. Précondition prouvée par canari CI (PR #185) — Prophet-in-CI **déterministe** : 3 runs, MAPE 25.40 % identique, 0 régression, variance 0.00pp vs baseline re-figée (PR #175). Frontière paths (doivent porter couverture vs runtime-guardrails Bras B légitimement exempts) = **ADR-0007 §D2.g**. Rollback = `EVAL_GATE_BLOCKING="false"` | 04/07/2026 |
| 30 | Audit différentiel pré-pilote 2026-Q2 (HOS-277) **CLOSED** : NO-GO levé → **GO conditionnel** (sandbox Apaleo + dataset non-PII). Q2-01 (fuite `.env.fly`) → repo PRIVATE + historique purgé (filter-repo) + rotation 11/11 clés ; **résidu `refs/pull/*` clos 22/07/2026** (HOS-304 : ticket GitHub Support, 32 PRs déréférencées, commit `7070837` non résolvable — 422 confirmé) ; Q2-02 AsyncSession (HOS-288) + Q2-03 PII WhatsApp (HOS-289) corrigés (PR #187). Doc = `docs/context/security-review-2026-Q2.md` (bannière CLOSED) | 04/07/2026 |
| 31 | Hospitality Agentic Mesh Signal Contract (**ADR-0012**) : `DomainSignal` namespaced par bounded context nœud (`environmental.*` Tacet, `guest.*` Anima, `fnb.*` Aetherix, `operational.*`/`orchestrator.*` Orchestrateur) · `SignalComposite` = perception cross-domaine, jamais de champ actionable (frontière décision protégée, ADR-0004 D5) · `CollectivePattern` = alias `fb_patterns`/Hive prior Anima · calibration à 3 niveaux (cohorte Hive / apprentissage local / override manager) · pas de `decay_rate` sur Signal (réservé ADR-0011 D2) · gel terminologique post-acceptation · **exception explicite Décision #25/ADR-0010 Q2 : reste privé, ne migre jamais vers le méta-repo public malgré le critère cross-cutting** | 06/07/2026 |
| 32 | Processus de calibration LLM-judge, pré-requis EVAL-6 (**ADR-0007 §14**) : rubrique binaire miroir `FAILURE_THRESHOLDS.md` · golden set dédié `eval/judge_calibration_set.jsonl` · juge d'une **autre famille** que les générateurs, via `LLMProvider` (amendé 24/09, ADR-0007 §14.5) · Cohen's kappa ≥ 0.8 avant scoring autonome · recalibration sur triggers explicites | 30/07/2026 |
| 33 | Gate honnêteté métriques (HOS-318) : taxonomie **Built / Shadow-mode / Synthetic PoC / Design / Research** obligatoire sur toute surface (`docs/context/status-taxonomy.md`, `Built` ≠ adopté, `Built (PoC)` interdit) · 15.09 % synthétique = circulaire, gate interne seul, usage non qualifié = drift D7 · verdict Recruit = **PASS formel MAPE + clause pivot déclenchée volontairement** (à J+1 Prophet est derrière la naïve en médiane) · amendement protocole §7 : WAPE reporté obligatoire, Δ MdAPE reste primaire | 01/08/2026 |
| 34 | Apaleo A2A **tranché : wait-and-see, Aetherix reste MCP standalone** (audit Trace Agent HOS-285 + spike A2A HOS-278) — A2A = cap annoncé, pas d'interface (aucune spec/auth/endpoint sur `apaleo.dev` au 30/07) · Décision #19 rend Aetherix déjà prêt sans dette à provisionner · risque branchement précoce = Daily Receipt disparaît derrière l'UI Copilot, commoditise l'exécution · vecteur de menace reformulé : Apaleo fournit les rails (Agent Hub/Agent Factory), pas les agents — risque = un tiers publie un agent F&B en 1 trimestre · 4 conditions de bascule B1-B4, re-vérification trimestrielle 30/10/2026 · canari W2 dé-escaladé (mensuel) mais reste ouvert | 30/07/2026 |
| 35 | Portabilité de modèle (règle de Mesh) : services → **tiers** `reasoning`/`fast`, jamais d'ID de modèle (livré) · sorties validées par schéma · gate matriciel provider×modèle = juge d'admissibilité (qualifier auto oui, promouvoir auto non) · `embedding_model` par vecteur · cycle de vie du golden dataset (noyau figé / zone datée / croissance). Dérogation au gel Epic 16 (renforce la preuve, pas le Mesh). Public : **Design** tant qu'aucun 2e fournisseur n'a passé le gate | 24/09/2026 |
| 36 | Gel Epic 16 **levé pour le développement** (Orchestrateur avancé, meta-learner ADR-0005, Anima) — objectif projet reformulé portfolio/recherche d'emploi, pas vente. Construction reprend sur données synthétiques/mock (Décision #11), étiquetage honnête obligatoire (Décision #33). **Gate DPIA (Décision #20) intégralement inchangé** — 13 mesures bloquantes, aucune donnée guest réelle sans elles. Les 2 audits (interne + GPT) restent valides pour un contexte commercial, à réappliquer si design-partner réel | 22/09/2026 |

---

## Roadmap

| Phase | Statut | Highlights |
|---|---|---|
| Phase 0 (validation harness) | 🔨 In Progress | Backtest pipeline + MCP v0 livrés. Benchmark réel Recruit : Prophet −6.15 pts MAPE vs naïve mais **jeu égal en médiane** (Décision #33). Le 15.09 % synthétique est circulaire — gate interne seul. |
| Phase 1 | ✅ Done (19/04/2026) | MCP Server v0 + ADR 0003 observability + memory instrumentation. PR #73 merged. |
| Phase 0 (deploy) | ✅ Done (15/05/2026) | Staging Fly.io live. Smoke E2E 5/5 PASS. RLS 14/14 + webhook HMAC. |
| Phase 2 | ✅ Done (17/05/2026) | Agent "Receipts" P2-1 → P2-7 mergées. Daily + WhatsApp + email + inbound parser + weekly digest. |
| Phase 3 | Kickoff 17/05/2026 | Pilot Validation + Portfolio Reinforcement. **Conformité pré-pilote close** : Epic 12 runtime guardrails (20/06) + **audit différentiel 2026-Q2 (HOS-277) CLOSED 04/07** (Q2-01 secrets/rotation + Q2-02/03 corrigés, Décision #30) → **NO-GO levé, GO conditionnel** sandbox+non-PII → gate pilote **HOS-176** débloqué. Détail → `docs/planning/phase-3-pilot-validation.md` + `docs/planning/phase-3-sprint-plan.md`. |
| Phase 4 | Scale & Distribution | Mews integration · POS ingestion · **Federated HiveMemory ship (announced Phase 3)** · cross-property dashboard · food waste KPI · multi-tenant. |
| Phase 5 | Vision long-terme | Agentic Hospitality Mesh — Revenue Orchestration Agent + MCP-native design pipeline + Aetherix Voice (Lore-inspired). Détail → `docs/context/vision-future.md`. |

---

## Décisions ouvertes — POINTEUR

> **Source de vérité unique : [`docs/context/open-decisions.md`](docs/context/open-decisions.md)** — §Actives + §Resolved (archive).
> L'index tabulaire vivait ici jusqu'au 11/08 ; il a été retiré au profit d'un pointeur (CLAUDE.md à 169/170 lignes, détecteur D5). Une décision ouverte ne se déclare plus dans ce fichier — elle s'ajoute en sous-section du fichier dédié, point. Les décisions **architecturales** (tranchées) gardent leur index ci-dessus : elles sont stables, les ouvertes ne le sont pas.

---

## KPI framework produit (référence)

Trois niveaux de mesure de la valeur. **Principe de stickiness :** publiés activement au manager (WhatsApp + dashboard) pour rendre la valeur visible sur le P&L.

**Niveau 1 — Product Truth (accuracy)** : `MAPE` couverts cible < 15% · `staffing_prediction_accuracy`
**Niveau 2 — Operational Impact (business value)** : `labor_cost_variance` (-3% à -8%) · `understaffing_incidents` · `food_waste_per_cover`
**Niveau 3 — Adoption (product health)** : `recommendation_acceptance_rate` (alerte si < 30%) · `weekly_operational_usage` · `planning_time_saved`

---

## Fichiers clés

```
backend/app/providers/    — abstraction LLM + Embedding (claude, mistral, gemini, fallback)
backend/app/services/     — exécution F&B (forecast, staffing, memory, receipts) — pas d'orchestration (ADR-0004)
backend/app/integrations/ — Obsidian, Linear, Apaleo, Twilio, SendGrid
backend/app/mcp_server.py — MCP Server v0 (HOS-71, PR #73) — tools atomiques uniquement
backend/orchestrator/     — proto-orchestrateur Phase 3 (AetherixEngine migré, ADR-0004)
backend/app/middleware/   — agent_tracking.py (Agent SEO + request_id, P1-5/HOS-72)
scripts/ci/               — gates CI (schema drift #16, eval-by-design #22, audit_id_types HOS-163)
scripts/ops/              — ops & monitoring (veille_proactive, sync_obsidian, validate_apaleo_sandbox, measure_mape_j1, generate_demo_data)
.github/workflows/        — CI (cron veille-hebdomadaire retiré le 30/07, veille → Obsidian)
```

> **📚 Documentation** : catalogue par sous-catégorie dans [`docs/INDEX.md`](docs/INDEX.md). À charger en priorité pour contexte inter-nœuds : `docs/mesh-architecture.md` (SOURCE DE VÉRITÉ CROSS-REPOS Aetherix + Tacet + Orchestrateur + Anima).

---

## Variables d'environnement

23 variables (LLM, Supabase, Apaleo, Redis, Logfire, outillage) → [`docs/ops/environment-variables.md`](docs/ops/environment-variables.md). Secrets en prod via `flyctl secrets set`, jamais committés.

---

## Linear · Obsidian · BMad

**Linear** — Workspace `Hospitalityagent`, team `2f6bb5e2-d735-4769-9377-11fe186aa0ad`. Conventions Epic/Story → `docs/context/linear-conventions.md`. Verify session : `list_teams` doit retourner "Hospitalityagent".

**Obsidian** — Vault `C:\Users\ivand\OneDrive\Documents\Agentic AI Hospitality`. MCP : Claude Desktop + Claude Code. Reports : `AI Reports/Intelligence/`. **Veille + watchlist = `Veille/` uniquement** (migration achevée 30/07/2026, plus rien dans le repo). Détail → `docs/INDEX.md` §Convention local-only.

**BMad modes** — Déclare en début de conversation. Veille · SM (Bob) · Dev (Amelia) · Architect (Winston) · PM · Analyst (Mary) · QA · Tech Writer. Files in `tools/bmad/_bmad/bmm/agents/`.

---

## Dev Agent — Definition of Done

8 étapes + eval gate (Décision #22) + gates merge/epic/pré-pilote + règle de contexte → [`docs/context/dev-agent-dod.md`](docs/context/dev-agent-dod.md).

---

## Points d'attention

1. Config env : source de vérité = `backend/.env.example` (le legacy `archive/` + son `.env.example` racine ont été retirés le 10/07/2026, snapshot récupérable via tag `legacy-backend-archive`).
2. Hébergement staging = Fly.io `cdg` (Décision #17). Dev local Windows pour scripts utilitaires.
3. Plan 90j Proof & Visibility (HOS-300, 07/07→10/2026) : hygiène/méta-repo/preuve empirique. **Gel développement levé 22/09/2026 (Décision #36)** — objectif reformulé portfolio recherche d'emploi. Détail `docs/planning/plan-90j-proof-visibility.md` + audit `docs/context/analyse-critique-2026-07.md`.
4. **Adversarial review externe (GPT, 20/07/2026)** — confirme indépendamment l'audit interne (gel Mesh/Anima/Context Graph/Hive tant que 5 conditions non prouvées : données PMS/POS réelles, horizon de décision réel, forecast > baseline naïve, adoption manager, unit economics). Ajoute 3 stories sous Epic 16 : HOS-316 (protocole de preuve pré-enregistré, à geler avant lecture des résultats HOS-307/308/309), HOS-317 (Decision Ledger — consolidation mémoire/feedback/outcome, pas de nouvelle brique), HOS-318 (gate honnêteté métriques + taxonomie Built/Shadow-mode/Synthetic PoC/Design/Research). Corpus complet + synthèse : `C:\Users\ivand\OneDrive\Documents\aetherix-gpt-review-corpus\` (`07_executive_action_plan.md`, `08_analysis_companion.md`). **Constat toujours valide pour un contexte commercial** — le gel de construction qu'il motivait est levé pour un objectif portfolio (Décision #36), le gate DPIA (Décision #20) reste inchangé.
