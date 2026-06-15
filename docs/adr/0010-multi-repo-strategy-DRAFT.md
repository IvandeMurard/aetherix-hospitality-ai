# ADR 0010 — Multi-repo Strategy (Méta-repo public + Execution nodes séparés) — DRAFT

**Status:** DRAFT — handoff vers session Architect (mode BMad Architect)
**Date proposée:** Phase 4 kickoff OR pré-fundraise (whichever sooner)
**Décide:** Architect (Ivan, mode BMad)
**Implémente:** Sprint dédié 3-5 jours cumulés (migration + tooling + redirects)

> ⚠️ Ce fichier est un **brief d'entrée + decisions structure validées PM**, pas un ADR finalisé. La session Architect produit la version finale en supprimant `-DRAFT`, complétant les spec techniques (Git submodules, shared workflows GitHub, redirects), et créant le plan d'exécution séquencé.

---

## Contexte

Suite session PM 06-15, décision de séparer la vitrine publique (vision, architecture agentique, roadmap macro) de l'execution node F&B (Aetherix backend). Cohérent avec :

- **Décision #18** Tacet MCP wrapping = repo séparé hors Linear Aetherix
- **Décision #19** Orchestrateur = `backend/orchestrator/` Phase 3 → repo séparé Phase 4
- **Décision #20** Anima = repo séparé Phase 4 (PoC hackathon `anima-poc` déjà standalone juin 2026)
- **Mesh philosophy** : chaque nœud = bounded context strict, communicate via MCP

État actuel (pre-migration) :
- **Aetherix** (`github.com/IvandeMurard/aetherix-hospitality-ai`) = PUBLIC, contient code F&B + docs/ + ADRs cross-cutting + `mesh-architecture.md` (SOURCE OF TRUTH cross-repos per CLAUDE.md)
- **Anima** (`C:\Users\ivand\OneDrive\Documents\anima-poc`) = repo séparé (probablement privé / local) — PoC hackathon juin 2026
- **Tacet** = repo séparé annoncé hors Linear
- **Orchestrateur** = module Phase 3 dans Aetherix, repo séparé Phase 4

**Sources à charger en début de session Architect :**

- `docs/context/decisions-architecturales.md` Décisions #18, #19, #20 (séparation repo déjà actée par node)
- `docs/mesh-architecture.md` (cross-repo source of truth actuelle — sera migrée méta-repo)
- `CLAUDE.md` §Fichiers clés (architecture courante repo Aetherix)
- `README.md` (vitrine actuelle de facto)
- `docs/INDEX.md` (catalog documentation à éventuellement migrer méta-repo)
- `docs/bmad/_bmad/` (BMad agents files — décision : central méta + submodule)
- `.github/workflows/` (CI/CD existante — base pour shared workflows)
- `memory/market_signals_2026Q2.md` §veille 06-15 (contexte PM décision)

---

## Macro-structure validée PM 06-15

```
github.com/IvandeMurard/
├── hospitality-agentic-mesh    [PUBLIC, MIT]  ← NOUVEAU méta-repo vitrine
│   ├── README.md                — vision, architecture diagram, roadmap macro
│   ├── docs/
│   │   ├── mesh-architecture.md — SOURCE OF TRUTH cross-repos (migré depuis Aetherix)
│   │   ├── adr/                  — ADRs cross-cutting (multi-node, philosophy, governance)
│   │   ├── INDEX.md              — catalog public docs
│   │   └── bmad/                 — BMad agent files (central, submodulés depuis chaque node)
│   ├── .github/workflows/        — Reusable workflows partagés (eval-gate, schema-drift, lint)
│   └── REPOS.md                  — liste agents + status + liens (publics ou "private — contact")
│
├── aetherix                    [PRIVATE, propriétaire]  ← Aetherix execution node (migré)
│   ├── backend/                  — code F&B (forecast, staffing, memory, receipts)
│   ├── docs/                     — ADRs agent-specific (0001..0008), planning, context
│   └── .github/workflows/        — référence reusable workflows méta via uses:
│
├── anima                       [PRIVATE, propriétaire]  ← Anima Guest Context Node
│   └── (déjà séparé sous anima-poc — formalize as repo)
│
├── tacet                       [PRIVATE, propriétaire]  ← Tacet Sensory Node
│   └── (déjà annoncé séparé — formalize as repo)
│
└── orchestrator                [PRIVATE, propriétaire]  ← Orchestrateur supervisory agent (Phase 4)
    └── (issue de backend/orchestrator/ Aetherix par extract Phase 4)
```

---

## Conventions sub-décisions — VALIDÉES PM 06-15

7 conventions tranchées en session PM 06-15 :

| # | Question | Réponse validée |
|---|---|---|
| **1** | **Source of truth ADRs** | ADRs cross-cutting (multi-node, Mesh philosophy, governance) → **méta-repo** `docs/adr/`. ADRs agent-specific (Aetherix #0001-0008, future Anima `#01..`, etc.) → **repo de l'agent** `docs/adr/`. Renumérotation préfixée par agent post-migration (e.g. `aet-0001`, `ani-0001`) à confirmer. |
| **2** | **`mesh-architecture.md` location** | **Méta-repo** uniquement. Repos agents linkent vers méta-repo (URL absolue) plutôt que copy/paste. |
| **3** | **BMad files (`docs/bmad/`)** | **Central dans méta-repo** + intégré dans chaque agent repo via **Git submodule** (`docs/bmad → meta-repo:docs/bmad`). Évite duplication + maintien synchrone des agents BMad cross-repo. |
| **4** | **License** | **MIT** pour méta-repo (vitrine publique, contribution open) · **Propriétaire fermé** pour repos agents (Aetherix, Anima, Tacet, Orchestrateur) — IP commerciale Phase 4+. |
| **5** | **Cross-repo references** | **Git submodules**. Méta-repo = parent, agents = submodules (clonables individuellement pour qui a les droits). Permet `git clone --recursive meta-repo` pour développeurs full-access. |
| **6** | **CI/CD** | **Shared workflows** (GitHub Actions reusable workflows). Méta-repo expose `.github/workflows/reusable-*.yml` (eval-gate, schema-drift, lint, security-scan). Agents repos référencent via `uses: org/meta-repo/.github/workflows/reusable-eval-gate.yml@main`. Single source of truth CI/CD. |
| **7** | **Discoverability publique** | **Redirects** depuis Aetherix repo actuel vers méta-repo après migration. README minimal sur Aetherix repo public (post-migration) avec banner *"This repo has moved to private — public docs at github.com/IvandeMurard/hospitality-agentic-mesh"*. Aetherix repo public garde tags historiques + archive read-only. |

---

## Questions à finaliser en session Architect

### Q1 — Aetherix execution repo : private OR archived-public + new-private fork ?

**Option A** : Transformer `aetherix-hospitality-ai` repo public actuel → privé (GitHub UI : Settings → Change visibility → Make private).
- ✅ Préserve historique commits, PRs, issues, contributors
- ⚠️ Stars/forks GitHub conservés mais audience perd accès (signal recrutement perdu)
- ⚠️ Public docs/READMEs ne sont plus accessibles

**Option B** : Archive read-only le repo public + créer fork privé.
- ✅ Public garde accès historique (vitrine partielle)
- ✅ Nouveau privé démarre clean
- ⚠️ Effort dupliqué + risque divergence
- ⚠️ Stars/forks pas transférables

**Reco Architect à trancher** : Option A si Aetherix repo public est encore "early-stage" (peu de stars/forks externes) ; Option B si traction publique mesurable.

### Q2 — Méta-repo `hospitality-agentic-mesh` — content scope précis

À spec dans ADR :
- Quelles ADRs sont "cross-cutting" vs "agent-specific" ? *(Reco : tout ADR référencé par 2+ nodes = cross-cutting → méta)*
- `docs/competitive/` reste sur Aetherix (perspective F&B) OR migre méta (perspective Mesh) ?
- `memory/` (mémoire PM) reste local ou intègre méta-repo `memory/`? *(Reco : reste local — privé par nature)*
- `scripts/ci/` Aetherix-specific (schema_drift_ignore.json) reste Aetherix · `scripts/ci/check_*` génériques → méta

### Q3 — Submodule strategy précise

À spec :
- Méta-repo a-t-il les agents comme submodules (parent contient tout) OR agents ont méta comme submodule (agent contient BMad central) ?
- **Reco** : *agents ont méta-repo comme submodule pour BMad uniquement* (`/docs/bmad → meta-repo:docs/bmad`). Méta-repo n'a pas les agents comme submodules (sinon clonage méta = pull tout). Méta-repo référence agents via `REPOS.md` + URLs.
- Git submodule update workflow : automated via Dependabot or manual ?

### Q4 — Shared workflows migration plan

À spec :
- Quels workflows actuels Aetherix `.github/workflows/` sont génériques (réutilisables Mesh-wide) vs Aetherix-specific ?
  - **Génériques (→ méta)** : schema-drift gate, eval-gate, lint, security-scan, BMad-validate
  - **Aetherix-specific (→ stay Aetherix)** : Apaleo MCP smoke test, Prophet training, F&B golden dataset eval
- Plan migration progressive (1 workflow à la fois) vs big-bang ?
- **Reco** : migration progressive, ordre = schema-drift → eval-gate → lint → security-scan → BMad-validate.

### Q5 — Redirects mechanism Aetherix public → méta-repo

À spec :
- GitHub repo description + pinned issue annonçant migration ?
- README.md court avec banner CTA *"This repo moved → meta-repo URL"* ?
- Archive le repo (GitHub Settings → Archive) après période de transition (3-6 mois) ?
- **Reco** : phase de transition 3 mois avec README banner + pinned issue + archive après.

### Q6 — Phasing migration

À spec timeline précise. **Reco PM 2 étapes** :

- **Étape 1 — Maintenant (pre-pilote Phase 3 en cours)** : ne rien changer. Status quo Aetherix public, monorepo de facto.
- **Étape 2 — Trigger** : (a) pilote Phase 3 livré + design partner sous NDA, OU (b) avant approche investisseurs sérieuse Phase 4. Effort dédié 3-5 jours, sprint focused.

### Q7 — Migration des secrets, .env, deployments

À spec :
- Fly.io app `aetherix-backend` reste-t-elle pointée sur le repo public archivé OR repointée sur nouveau repo privé ?
- Secrets `flyctl secrets` migration ?
- Apaleo MCP credentials, Linear API key, Anthropic API key, etc. — repositoning des secrets per repo ?
- **Reco** : pas de migration secrets — ils sont dans Fly.io infra, indépendants du repo source.

### Q8 — Impact CLAUDE.md convention

À spec :
- CLAUDE.md actuel = INDEX décisions architecturales Aetherix-specific. Reste sur Aetherix repo.
- Faut-il créer `CLAUDE.md` dans méta-repo aussi (Mesh-wide INDEX) ?
- **Reco** : OUI méta-repo `CLAUDE.md` séparé, contenu = vision globale Mesh + INDEX décisions cross-cutting + lien vers chaque agent CLAUDE.md.

### Q9 — REPOS.md format précis

À spec dans méta-repo :

```markdown
# Hospitality Agentic Mesh — Agent Repos

| Agent | Status | Repo | Access |
|---|---|---|---|
| Aetherix | Phase 3 pilot | github.com/.../aetherix | Private — partnership contact |
| Anima | Phase 4 design + PoC | github.com/.../anima | Private — partnership contact |
| Tacet | Phase 3-4 design | github.com/.../tacet | Private — partnership contact |
| Orchestrator | Phase 4 design | github.com/.../orchestrator | Private — partnership contact |

Contact : [LinkedIn / email]
```

---

## Décisions à produire à la fin de la session Architect

- [ ] Réponses tranchées Q1-Q9 avec rationale
- [ ] Plan migration séquencé jour-par-jour (Sprint 1, 2, 3 dédiés)
- [ ] Spec Git submodules concrète (commandes, .gitmodules format)
- [ ] Spec shared workflows GitHub Actions concrète (template `reusable-*.yml`)
- [ ] Spec redirects mechanism (README banner copy, archive trigger)
- [ ] Plan communication migration (LinkedIn post / GitHub announcement / Apaleo Marketplace notif si listed)
- [ ] DoD final ADR + acceptation par PM

---

## Risques + mitigations

| Risque | Mitigation |
|---|---|
| Perte stars GitHub Aetherix public → signal recrutement diminué | Méta-repo public reprend signal (vision + roadmap = aspirational asset attractive) + transition banner pendant 3 mois |
| Divergence méta-repo vs agents (`mesh-architecture.md` outdated, BMad files désynchronisés) | Submodules + CI auto-update Dependabot · single source of truth méta-repo enforced |
| Effort migration trop lourd pre-pilote | Étape 2 trigger explicite (post-pilote OR pré-fundraise) — pas urgent maintenant |
| Apaleo Marketplace listing en cours rupture URLs | Coordonner migration timing avec Apaleo Agent Hub submission (story flaggée veille 06-15) — soit pre-listing, soit post-listing stable |
| Secrets Fly.io ou Linear cassés post-migration | Audit pre-migration · secrets dans infra Fly.io, indépendants du repo source · garder repo source url stable côté CI/CD si possible |
| Designers / collaborateurs externes (futurs) accès repos privés | Process invite GitHub bien documenté · REPOS.md mentionne "contact pour collaboration" |
| Loss of OSS narrative pre-fundraise | Méta-repo public reste open vitrine · technical write-ups (Phase 3 Track B REX article) publiables sur méta-repo |

---

## Décisions liées

- **CLAUDE.md Décision #18** Phase 3 cut + Tacet repo séparé
- **CLAUDE.md Décision #19** Orchestrateur séparation + repo Phase 4
- **CLAUDE.md Décision #20** Anima repo Phase 4 + PoC hackathon livré
- **CLAUDE.md Décision #21** Apaleo MCP convention nommage (cohérence cross-repo)
- **CLAUDE.md Décision #22** Eval-by-design gate CI (devient shared workflow méta)
- **CLAUDE.md Décision #16** Schema drift gate (devient shared workflow méta)
- **`docs/mesh-architecture.md`** SOURCE OF TRUTH cross-repos — migration target méta-repo

---

## Action post-ADR

1. Drop suffixe `-DRAFT` → `docs/adr/0010-multi-repo-strategy.md` (initially in Aetherix repo, then migrated to méta-repo `docs/adr/` lors du sprint exécution)
2. Update `CLAUDE.md` §Décisions architecturales — ajouter ligne d'index #25 (ou next available) "Multi-repo strategy + governance (méta-repo public + execution nodes privés)" + détail H3 dans `docs/context/decisions-architecturales.md`
3. Update `docs/context/open-decisions.md` — déplacer décision "Multi-repo strategy" (à créer si pas existante) de §Actives vers §Resolved
4. **Étape 2 — Migration sprint** : déclencher au trigger (post-pilote OR pré-fundraise). Sprint 3-5 jours cumulés.

---

## Modèle recommandé pour session Architect

**Opus 4.7** (ou plus récent Opus disponible) — décision architecturale durable cross-cutting + impact long-terme + multi-ADR alignment. Pattern aligné avec ADR-0006, ADR-0007, ADR-0008 (tous Opus).
