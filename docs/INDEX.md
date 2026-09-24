# 📚 Index de la documentation — Aetherix

> Catalogue de la documentation **vivante** de `docs/`, classée par sous-catégorie. Chargé sur demande (pas automatiquement).
> **Convention :** facts de session → `CLAUDE.md` ; contexte narratif & détaillé → ici et dans les fichiers ci-dessous.
> **Élagage 08/07/2026 (Story 16.2 / HOS-302)** : 292 → ~51 fichiers vivants. Docs de phases terminées, stratégies périmées et vieux rapports → [`docs/_archive/`](_archive/) (rien n'est supprimé). Framework BMad → `tools/bmad/` (outillage, pas de la doc projet).
> ⚡ Priorité inter-nœuds : `mesh-architecture.md` (vérité cross-repos).

---

## ⚖️ Dette CLAUDE.md — dépassement du plafond

`CLAUDE.md` se donne un **plafond dur de 170 lignes** (facts + INDEX uniquement), relevé de 150 le 31/07 et contrôlé en CI. Il était à **196 lignes** quand la règle en disait 150 : dépassement structurel — les sections INDEX grossissent à mesure que les décisions s'accumulent — et surtout **non détecté, faute de contrôle**. C'est ce trou qui a motivé le détecteur D5.

### Refactoring du 30/07 — fait

| Section | Avant | Après | Destination |
|---------|------:|------:|-------------|
| `## Variables d'environnement` | 23 | 3 | ✅ [`ops/environment-variables.md`](ops/environment-variables.md) |
| `## Dev Agent — Definition of Done` | 16 | 3 | ✅ [`context/dev-agent-dod.md`](context/dev-agent-dod.md) |

**Résultat : 195 → 166 lignes.** (L'estimation initiale de ~158 était optimiste — les lignes de pointeur comptent aussi.)

### Ce qui reste, et pourquoi ça ne bougera pas facilement

| Section | Lignes | Diagnostic révisé |
|---------|-------:|-------------------|
| `## Décisions architecturales — INDEX` | 41 | **C'est la raison d'être du fichier.** Compressible en `#N — titre court` sans le résumé, mais on perd la lisibilité en session. |
| `## Décisions ouvertes — INDEX` | 20 | ~~Idem.~~ **Diagnostic révisé le 11/08 — sorti du fichier**, voir §Refactoring du 11/08. |
| `## Fichiers clés` | 17 | **Diagnostic initial erroné** — j'avais écrit « recoupe ce catalogue ». Faux : c'est une carte du **code** (`backend/app/*`, `scripts/*`), ce catalogue liste la **documentation**. À conserver. |

> ⚖️ **Plafond relevé à 170 le 31/07/2026 (arbitrage Ivan).** Il restait 16 lignes à trouver et le seul gisement était constitué des deux index de décisions — soit le contenu principal du fichier. Un plafond qui oblige à supprimer ce pour quoi le fichier existe est mal calibré : l'index a grandi depuis que 150 a été posé. Le plafond est désormais **contrôlé en CI par le détecteur D5**, qui le lit dans la ligne de règle de `CLAUDE.md` — il n'est donc pas dupliqué dans le script.

> ⚠️ **Drift de comptage — résolu le 31/07.** Trois chiffres différents circulaient pour le même ensemble : deux docs et le fichier source lui-même annonçaient des totaux qui ne correspondaient ni entre eux, ni au décompte réel. Le détecteur **D6** les a tous les trois trouvés dès son premier run — y compris celui que la note précédente de cette section avait elle-même introduit. **Correctif appliqué : les comptes codés en dur ont été retirés, pas corrigés.** Un nombre dupliqué dérive au premier ajout ; le décompte se lit désormais en comptant les sections de la source.

**Traité le 31/07** : plafond relevé à 170, refactoring appliqué, et les deux règles (plafond + comptes) sont désormais contrôlées en CI — elles ne peuvent plus dériver en silence.

### Refactoring du 11/08 — index des décisions ouvertes sorti

Le fichier est remonté à **169/170** en ouvrant une décision de plus. Le diagnostic de juillet — « c'est la raison d'être du fichier, ça ne bougera pas » — tenait pour les décisions **architecturales**, pas pour les **ouvertes** : une décision tranchée est stable et mérite sa ligne permanente ; une décision ouverte bouge, se reformule, s'archive, et son index doit être maintenu à deux endroits à chaque mouvement. C'est un coût récurrent pour une information périssable.

`## Décisions ouvertes — INDEX` (20 lignes) est donc devenu `## Décisions ouvertes — POINTEUR` (4 lignes). **Résultat : 169 → 154 lignes**, soit 16 de marge sous le plafond. Source de vérité unique : [`context/open-decisions.md`](context/open-decisions.md).

Ce qui reste indexé dans `CLAUDE.md` : les décisions architecturales seules. Le prochain gisement, si le besoin revient, est la compression de cet index en `#N — titre court` — au prix de la lisibilité en session, donc à ne faire que contraint.

---

## 🔒 Convention « local-only » (élagage du 30/07/2026)

Le dépôt ne porte plus que **le code et la documentation vivante**. Trois ensembles restent **sur disque mais hors versionnement** — ils sont toujours présents dans l'historique Git, seulement plus dans les commits à venir :

| Chemin | Contenu | Pourquoi hors dépôt |
|--------|---------|---------------------|
| `docs/veille/` | Veilles hebdomadaires | Source de vérité = vault Obsidian `Agentic AI Hospitality/Veille/` (acté 10/07, CLAUDE.md §Obsidian) |
| `docs/_archive/` | 47 fichiers : anciennes veilles, **`monitoring-watchlist.md`**, MVP_SCOPE, Problem_Statement, ROADMAP, presentation, `internal/`, `handoff/` | Archive de phases closes |
| `tools/bmad/_bmad/` | Install BMAD vendorée (233 fichiers) | Outillage tiers réinstallable. **`tools/bmad/_bmad-output/` reste versionné** — il porte les stories. |

> ✅ **Migration de la veille achevée le 30/07.** La watchlist, restée trois semaines dans le repo malgré la consolidation du 10/07, est portée dans le vault Obsidian : `Veille/Veille_Watchlist.md` (hub) + trois sous-notes (W2 Apaleo, concurrents, tech & Mesh). Le canari W2 a de nouveau un foyer dans la source de vérité déclarée.

**⚠️ Lecture des références.** Plusieurs docs en ligne — `CLAUDE.md`, `AGENTS.md`, `context/open-decisions.md`, `context/decisions-architecturales.md`, `adr/0006`, `adr/0008`, `marketing/positioning-snippets.md`, `Cost_Model.md` — citent encore `monitoring-watchlist.md`, `docs/veille/` ou `docs/_archive/`. **Ces liens sont valides en local et ne sont pas des drifts** : ils pointent vers des fichiers présents sur la machine, absents du dépôt distant. Un clone frais ne les résoudra pas.

> ✅ **Exclusion implémentée le 31/07** — `LOCAL_ONLY_PREFIXES` dans `scripts/ops/hygiene_architecturale.py`. Sans elle, le détecteur D2 remontait **7 faux positifs** dès le premier run en CI. Un contrôle qui crie au loup est désactivé en quinze jours.

**Le canari concurrentiel W2 (Apaleo Copilot scope F&B) vit désormais hors dépôt.** Sa re-vérification trimestrielle est fixée au **30/10/2026** (voir `context/apaleo-a2a-spike-decision.md` §Conditions de bascule, qui reste en ligne). Ne pas compter sur le dépôt pour la rappeler.

---

## 🏛️ Architecture
- `ARCHITECTURE.md` — pointeur architecture (v0.3.0, 07/07/2026) : où trouver quoi + résumé 10 lignes. La vérité vit dans CLAUDE.md / mesh-architecture.md / ADRs
- `mesh-architecture.md` — **SOURCE DE VÉRITÉ CROSS-REPOS** (Mesh : Aetherix + Tacet + Orchestrateur + Anima)
- `adr/` — Architecture Decision Records :
  - `0001-aetherix-mcp-server-v0` · `0002-memory-instrumentation` · `0003-agent-observability-and-metering` · `0004-orchestrator-separation`
  - `0006-pos-integration` · `0007-evaluation-by-design` · `0008-context-graph` · `0009-runtime-guardrails`
  - `0010-multi-repo-strategy` · `0011-learning-engine-hive-v2` · `0012-mesh-signal-contract` (**privé à jamais**, Décision #31)
  - `0013-decision-autonomy-policy` (**Proposed** 24/09/2026 — autonomie des agents hôtes, amenderait Décision #6 ; rien d'activé)

## 🧭 Context (détail par domaine)
- `context/decisions-architecturales.md` — détail des décisions architecturales (index 1-ligne dans CLAUDE.md ; compte non figé, cf. détecteur D6)
- `context/open-decisions.md` — décisions ouvertes + archive des résolues
- `context/analyse-critique-2026-07.md` — **audit critique complet Aetherix+Tacet (07/07/2026)** : chaîne de valeur 5 maillons, circularité MAPE synthétique, différenciation, wedge/moat, risques crédibilité
- `context/positionnement-wedge.md` — **le wedge acté (09/07)** : "mémoire opérationnelle, le forecast est un organe" — référence pour tout support externe (case study, méta-repo, article, LinkedIn) + discipline de langage
- `context/anima-context-thesis.md` — **thèse Anima (03/08)** : contexte humain pertinent avant action, frontière Anima (compréhension) / Aetherix (exécution) ; **Research**, sans nouveau scope ni promesse produit
- `context/moat.md` — **ce qui est défendable, testé contre la menace plateforme** (09/07) : 4 couches de moat + stress test "et si Apaleo/Mews shippent un forecast natif ?" + risque résiduel nommé
- `context/data-conventions.md` — convention tenant_id/property_id/hotel_id + table des drifts (HOS-163)
- `context/memory-architecture.md` — Private + Hive Memory (Décision #2)
- `context/decision-ledger.md` — **Decision Ledger (01/08, HOS-317)** : audit des 5 tables + l'unique arête manquante (`operational_memory.recommendation_id`, aucune table nouvelle) · schéma contexte→reco→réponse manager→outcome · requête bout-en-bout (service + vue `decision_ledger`) · §5 ce qui reste non fermé · vocabulaire *outcome-tracked* et non *self-improving*
- `context/vision-future.md` — vision long terme (Phase 5, Mesh, Aetherix Voice)
- `context/demo-apaleo.md` — Demo PRD Apaleo + résultats probe sandbox (HOS-190 AC1)
- `context/mape-benchmark.md` (+ `mape-benchmark-holdout.json`) — **benchmark données réelles Recruit (08/07, HOS-307)** : naïve vs Prophet vs LightGBM, MAPE+MdAPE J+1→J+7 · verdict AC4 arbitré 01/08 = **PASS formel + clause pivot déclenchée volontairement** (Décision #33) · l'ancien 15.09 % synthétique = circulaire, gate interne uniquement
- `context/status-taxonomy.md` — **taxonomie de statut (HOS-318, Décision #33)** : Built / Shadow-mode / Synthetic PoC / Design / Research · doc de référence unique, applicable à toute surface · état des 10 briques · appliqué par le détecteur D7
- `context/audit-surfaces-publiques-2026-08.md` — **audit des surfaces publiques (01/08, HOS-318 AC1)** : état par surface + correctifs prêts à coller pour le case study et le méta-repo
- `context/perimetre-et-conformite-prospect.md` — **fiche prospect (01/08, HOS-313 AC4+AC5)** : périmètre honnête (built vs north-star, bus factor solo nommé comme risque) + one-pager conformité (rôles processor/controller + DPA, RGPD WhatsApp Q2-03 corrigé, posture sandbox/non-PII) — posture + feuille de route, pas un certificat
- `context/dpia-anima-2026-08.md` — **DPIA Anima — analyse RGPD/CNIL (01/08, HOS-229)** : gate Décision #20 **non levé** · obligation art. 35 établie (6/9 critères WP248) · durées de conservation par couche (Working/Episodic/Semantic/Segment) · droits des personnes · profilage émotionnel + frontière AI Act (biométrique = ligne rouge) · 13 mesures bloquantes + 9 conditions de levée · §10 = 4 conclusions qui remettent en cause l'archi 4 couches, signalées non appliquées
- `context/runbook-pre-pilot.md` — checklist pré-pilote
- `context/llm-provider-strategy-review-2026-06.md` — revue stratégie reasoning Sonnet/fallback/Haiku + HITL
- `context/linear-conventions.md` — protocole Epic/Story Linear
- `context/security-review-2026-05-01.md` — audit sécurité mai (clôturé, Epic 12)
- `context/security-review-2026-Q2.md` — audit différentiel pré-pilote Q2 (CLOSED, Décision #30)

## 🗺️ Planning
- `planning/plan-90j-proof-visibility.md` — **plan actif (Epic 16, HOS-300)** : preuve empirique + visibilité, juil.→oct. 2026, phases A→E + draft ticket GitHub Support
- `planning/protocole-de-preuve.md` — **protocole de preuve pré-enregistré (HOS-316)** : baseline, horizon de décision, métriques, seuils d'arrêt — GELÉ, s'applique à HOS-308/309/312 (HOS-307 hors garantie, §0)
- `planning/phase-3-pilot-validation.md` · `planning/phase-3-sprint-plan.md` — Phase 3 pilote
- `planning/pilot-readiness-test-plan.md` — test plan readiness pilote (Epic Pilot-Readiness)
- `planning/evaluation-by-design.md` — plan d'implémentation eval-by-design (Décision #22, ADR-0007)
- `planning/hos-190-manual-runbook.md` — runbook manuel HOS-190
- Phases 0-2 terminées → `_archive/planning/`

## 🚀 Pilot & Ops
- `pilot/onboarding-kit.md` · `pilot/outreach-template.md` · `pilot/credentials-sop.md`
- `pilot/journal-prospection.md` — **journal de prospection design-partner (01/08)** : modèle d'entrée 6 champs (objection en verbatim), tableau de bord, synthèse des objections à partir de 10 conversations (4 familles : valeur / preuve / risque / coût de changement), et la grille des **5 maillons de la chaîne de valeur** — c'est le critère de sortie n°5 du plan 90 j, s'il est tenu
- `ops/latency-slo.md` — SLO latence · `ops/llm-fallback-runbook.md` — runbook fallback LLM
- `SECURITY/secrets_handling.md` · `SECURITY/secrets_rotation_playbook.md`

## 🧪 Testing & MCP
- `testing/e2e-apaleo-sandbox.md` (+ `testing/evidence/`) — E2E sandbox Apaleo
- `mcp/getting-started.md` — consommer le MCP server Aetherix
- `demos/README.md` — démos disponibles + closed-loop (`scripts/ops/closed_loop_demo.py`, sortie gitignorée `eval/reports/`)

> **📣 Marketing/contenu = hors repo (09/07/2026).** Case study prompt, article, kit LinkedIn, posts LinkedIn/X, storyboard démo, transcript, memory tour, fiches : tout vit dans l'Obsidian vault `Aetherix - Marketing`. Le repo garde l'analyse stratégique (`context/positionnement-wedge.md`, `context/moat.md`) et `marketing/positioning-snippets.md` (exception : cité comme provenance de décisions par ADR-0006 / open-decisions).
>
> **📡 Veille/Competitive = hors repo (10/07/2026).** Élargissement de la décision ci-dessus : toute la veille (hebdo + watchlist + analyses concurrentielles dédiées, y compris `competitive/concurrence.md`) vit désormais dans l'Obsidian vault, dossier `Veille/` (`Veille_Competitors_Market.md`, `Veille_Index.md`). Les anciens `docs/veille/`, `docs/_archive/context/monitoring-watchlist.md`, `docs/competitive/*` sont archivés → `_archive/veille/`, `_archive/context/monitoring-watchlist.md`, `_archive/competitive/` (historique git préservé, citations ADR/decisions-architecturales restent valides vers ces chemins archivés). **Non résolu à date** : le cron `.github/workflows/veille-hebdomadaire.yml` (lundi 07h30 UTC, `scripts/ops/veille_proactive.py`) continue de générer/committer `docs/veille/draft-*.md` — tourne sur runners GitHub cloud, sans accès au vault local. Décision à prendre : désactiver ou garder comme générateur brut à recopier manuellement.

## 🗄️ Hors docs/
- `tools/bmad/` — framework BMad (agents SM/Dev/PM/QA…) — outillage, référencé par CLAUDE.md §BMad
- `docs/_archive/` — tout ce qui précède les jalons actuels : phases 0-2, stratégies pré-Mesh (Problem_Statement, MVP_SCOPE, ROADMAP_NOW_NEXT_LATER, MARKET_INTELLIGENCE, AI_CONTEXT_LAYER, DEPLOYMENT/TROUBLESHOOTING pré-Fly), audits internes mai, veille mars/avril + juin/juillet (`_archive/veille/`), watchlist (`_archive/context/monitoring-watchlist.md`), analyses concurrentielles (`_archive/competitive/`)
- `docs/metrics/` · `docs/linear/` — artefacts JSON historiques (backtest avril, import Linear)
