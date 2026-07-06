# ADR 0010 — Multi-repo Strategy (Méta-repo public + Execution nodes séparés)

**Status:** Accepted (Architect-finalisé — Q1-Q9 tranchées · conventions PM #1-7 validées 06-15) — *exécution déclenchée au trigger Étape 2 (cf. Q6)*
**Date:** 2026-06-16
**Décide:** Architect (Ivan, mode BMad) · conventions PM validées 06-15-2026
**Implémente:** Sprint dédié 3-5 jours cumulés au trigger Étape 2 (post-pilote OU pré-fundraise)
**Supersedes:** `0010-multi-repo-strategy-DRAFT.md` (brief d'entrée — à supprimer post-merge)

---

## Contexte

Suite session PM 06-15, décision de séparer la **vitrine publique** (vision, architecture agentique, roadmap macro) de l'**execution node F&B** (Aetherix backend). Cohérent avec les décisions de séparation déjà actées par nœud :

- **Décision #18** Tacet MCP wrapping = repo séparé hors Linear Aetherix
- **Décision #19** Orchestrateur = `backend/orchestrator/` Phase 3 → repo séparé Phase 4
- **Décision #20** Anima = repo séparé Phase 4 (PoC hackathon `anima-poc` déjà standalone juin 2026)
- **Mesh philosophy** (`mesh-architecture.md` §4) : chaque nœud = bounded context strict, communication via MCP, **zéro import Python cross-repos**

État actuel (pre-migration) :
- **Aetherix** (`github.com/IvandeMurard/aetherix-hospitality-ai`) = PUBLIC, contient code F&B + `docs/` + ADRs cross-cutting + `mesh-architecture.md` (SOURCE OF TRUTH cross-repos). **Porte deux casquettes contradictoires** : vitrine plateforme ET node d'exécution.
- **Anima** (`C:\Users\ivand\OneDrive\Documents\anima-poc`) = repo local séparé — PoC hackathon juin 2026 (synthétique, jetable)
- **Tacet** = repo séparé annoncé hors Linear
- **Orchestrateur** = module Phase 3 dans Aetherix, repo séparé Phase 4

**Problème central :** un visiteur ne peut pas distinguer « Aetherix = la plateforme » de « Aetherix = l'agent F&B ». La description LinkedIn (juin 2026) a tranché cette ambiguïté en prose ; la structure repo doit suivre.

---

## Macro-structure validée PM 06-15

```
github.com/IvandeMurard/
├── hospitality-agentic-mesh    [PUBLIC, MIT]  ← NOUVEAU méta-repo vitrine
│   ├── README.md                — vision, architecture diagram, roadmap macro
│   ├── CLAUDE.md                — INDEX Mesh-wide + décisions cross-cutting (Q8)
│   ├── REPOS.md                 — liste agents + status + liens (Q9)
│   ├── docs/
│   │   ├── mesh-architecture.md — SOURCE OF TRUTH cross-repos (migré depuis Aetherix)
│   │   ├── adr/                  — ADRs cross-cutting (multi-node, philosophy, governance)
│   │   ├── INDEX.md              — catalog public docs
│   │   └── bmad/                 — BMad agent files (central — cf. Q3)
│   └── .github/workflows/        — Reusable workflows partagés (eval-gate, schema-drift, lint, security-scan)
│
├── aetherix-hospitality-ai     [PUBLIC, ARCHIVED stub]  ← redirect → méta-repo (Q1+Q5)
│   └── README.md                — banner « moved » + tags historiques read-only
│
├── aetherix                    [PRIVATE, propriétaire]  ← Aetherix execution node (code F&B actif)
│   ├── backend/                  — forecast, staffing, memory, receipts
│   ├── CLAUDE.md                 — F&B-specific (reste)
│   ├── docs/                     — ADRs agent-specific (0001..0008), planning, context, competitive
│   └── .github/workflows/        — référence reusable workflows méta via uses:
│
├── anima                       [PRIVATE, propriétaire]  ← Guest Context Node (formalize anima-poc, Étape 2)
├── tacet                       [PRIVATE, propriétaire]  ← Sensory Node (formalize, Étape 2)
└── orchestrator                [PRIVATE, propriétaire]  ← Supervisory agent (extract backend/orchestrator/, Phase 4)
```

> **Changement clé vs brief :** Aetherix se scinde en **deux** entités GitHub — un *stub public archivé* (`aetherix-hospitality-ai`, conserve historique + stars + sert le redirect) et un *repo privé actif* (`aetherix`). Voir Q1+Q5 pour le rationale (réconciliation de la contradiction du brief).

---

## Conventions sub-décisions — VALIDÉES PM 06-15 (baseline, inchangées)

| # | Question | Réponse validée |
|---|---|---|
| **1** | Source of truth ADRs | Cross-cutting (multi-node / philosophy / governance) → **méta** · agent-specific → **repo agent**. Renumérotation préfixée agent (`aet-`, `ani-`) **rejetée** (cf. Q2 — coût > bénéfice). |
| **2** | `mesh-architecture.md` location | **Méta-repo** uniquement. Agents linkent via URL absolue. |
| **3** | BMad files | **Central méta-repo**. Mécanisme d'inclusion finalisé en Q3. |
| **4** | License | **MIT** méta-repo · **propriétaire fermé** repos agents. |
| **5** | Cross-repo references | Git submodules pour BMad — **affiné en Q3**. Agents listés via `REPOS.md`, pas en submodule du méta. |
| **6** | CI/CD | **Shared reusable workflows** exposés par le méta-repo. Spec en Q4. |
| **7** | Discoverability | **Redirect** depuis stub public archivé → méta-repo. Spec en Q5. |

---

## Décisions finalisées — Q1 à Q9

### Q1 — Devenir du repo Aetherix : **Option B affinée (stub public archivé + nouveau repo privé)**

**Décision :** Ne PAS faire un simple flip public→privé (Option A du brief). À la place :
1. Créer un **nouveau repo privé `aetherix`** ← y pousser le code F&B actif (avec historique via `git push --mirror` puis nettoyage des branches inutiles).
2. Convertir `aetherix-hospitality-ai` (public actuel) en **stub public archivé** : README réduit au banner de redirect (cf. Q5), repo passé en **Archived** (read-only) après la fenêtre de transition de 3 mois.

**Rationale :** Q5 (brief) exige un **redirect public** depuis le repo actuel. Or l'Option A (flip intégral en privé) rend le repo invisible publiquement → **aucun redirect possible** (404). Les deux exigences du brief sont donc incompatibles sous Option A. L'Option B affinée est la seule qui satisfait *à la fois* Q1 (IP F&B privée) et Q5 (surface publique de redirect).
- Le con « divergence » de l'Option B (brief) est **nul ici** : le stub est *archivé/read-only*, il ne reçoit jamais de commit → ne peut pas diverger.
- Le con « stars/forks non transférables » est sans objet : les stars **restent** sur le stub public, qui conserve donc le signal recrutement / build-in-public historique. Le signal *aspirationnel* futur migre vers le méta-repo public.

**Trade-off accepté :** +1 étape de setup (création repo privé + repointage remotes/CI) vs flip en un clic. Justifié par la cohérence Q1/Q5.

### Q2 — Scope de contenu du méta-repo

**ADRs cross-cutting → méta-repo** (`docs/adr/`) : **ADR-0004** (orchestrator separation = définit la frontière inter-nœuds), **ADR-0010** (gouvernance multi-repo). Critère retenu : *un ADR est cross-cutting s'il définit une interface/gouvernance s'étendant sur ≥ 2 nœuds.*

**ADRs agent-specific → repo `aetherix`** : 0001, 0002, 0003, 0005, 0006, 0007, 0008. Note : 0007 (eval-by-design) et le gate schema-drift (#16) **deviennent des shared workflows** (Q4), mais les ADRs qui les documentent restent côté Aetherix (leur origine). 0005/0008 sont forward-compat Anima mais nés Aetherix → restent Aetherix jusqu'à extraction Anima.

**Renumérotation préfixée (`aet-0001`…) : REJETÉE.** Coût (réécriture de tous les cross-liens internes + git history confusion) > bénéfice (cosmétique). Les ADRs gardent leur numéro ; la *localisation* (méta vs agent) porte la sémantique.

**Autres :**
- `docs/competitive/` → **reste `aetherix`** (lentille concurrentielle F&B, stratégique, privé). Le méta-repo public ne reçoit qu'une page *market positioning* dérivée de `positioning-snippets.md`.
- `memory/` (mémoire PM) → **reste local/privé**, jamais dans le méta-repo public.
- `scripts/ci/` : génériques (`check_eval_coverage.py`, `check_schema_drift.py`) → **méta** (base des reusable workflows) · spécifiques (`schema_drift_ignore.json`, smoke Apaleo, training Prophet) → **`aetherix`**.

**Amendement 06/07/2026 (Décision #31, ADR-0012) — exception explicite au critère cross-cutting :** `ADR-0012` (Mesh Signal Contract) définit une interface s'étendant sur ≥ 2 nœuds (Tacet, Anima, Aetherix, Orchestrateur) et satisferait donc mécaniquement le critère Q2. **Il reste néanmoins `aetherix`, PRIVÉ, et ne migre jamais vers le méta-repo public.** Motivation : contrairement à ADR-0004 (gouvernance/frontières de nœuds) ou ADR-0010 (governance repo), ADR-0012 documente l'IP différenciante du produit (le signal model — vocabulaire `DomainSignal`/`SignalComposite`/`RecommendationCandidate`/`CollectivePattern` + mécanismes de calibration à 3 niveaux). Le critère Q2 (*"cross-cutting = ≥2 nœuds"*) reste valide pour classer un ADR *architectural/gouvernance* ; il ne s'applique pas automatiquement à un ADR qui documente un avantage concurrentiel. Si une mention apparaît un jour dans le méta-repo public, elle se limite à une ligne générique sans vocabulaire ni mécanisme de calibration.

### Q3 — Stratégie BMad / submodules : **URL-reference par défaut, submodule uniquement si dépendance d'exécution**

**Décision (affine la convention #3/#5) :** BMad vit dans le méta-repo (`docs/bmad/`). Les repos agents le **référencent par URL** dans leur doc — **pas de submodule par défaut**.

**Rationale (push-back Architect documenté sur la convention PM #5) :** les Git submodules imposent un coût réel et permanent (clone `--recursive` obligatoire, HEAD détachés, checkout submodule en CI, friction contributeur) pour un bénéfice faible quand les fichiers BMad sont **lus** (par un humain ou Claude) et non **exécutés** par la tooling de l'agent. Churn BMad faible + founder solo = ROI submodule négatif.

**Exception :** si une tooling d'agent vient à *exécuter* des fichiers BMad depuis le repo (ex. un workflow CI qui les invoque), alors ajouter le submodule `docs/bmad → hospitality-agentic-mesh:docs/bmad` **pour ce repo uniquement**. Mise à jour manuelle (`git submodule update --remote`), pas Dependabot (mauvais support des SHAs de submodules internes).

**Invariant conservé :** le méta-repo **n'a pas** les agents comme submodules (sinon `git clone meta` tire tout). Les agents sont listés via `REPOS.md` + URLs (Q9).

### Q4 — Shared workflows : migration progressive

**Génériques → méta-repo** `.github/workflows/reusable-*.yml` : `reusable-schema-drift.yml`, `reusable-eval-gate.yml`, `reusable-lint.yml`, `reusable-security-scan.yml`, `reusable-bmad-validate.yml`.

**Aetherix-specific → restent `aetherix`** : smoke test Apaleo MCP, training Prophet, eval golden dataset F&B.

**Pattern de référence** (depuis un repo agent) :
```yaml
jobs:
  eval-gate:
    uses: IvandeMurard/hospitality-agentic-mesh/.github/workflows/reusable-eval-gate.yml@main
    secrets: inherit
```
> **Avantage de la License MIT/public du méta-repo (#4) :** les reusable workflows d'un repo **public** sont appelables par n'importe quel repo (y compris privé) **sans grant d'accès**. Un méta-repo privé aurait exigé Settings → Actions → access grant par repo appelant. Le choix public lève cette friction.

**Ordre de migration (1 workflow à la fois, pas big-bang) :** schema-drift → eval-gate → lint → security-scan → bmad-validate.

### Q5 — Mécanisme de redirect

Cohérent avec Q1 (stub public archivé). Sur `aetherix-hospitality-ai` :
1. **README réduit** au banner (copie ci-dessous).
2. **Pinned issue** « Repo migration notice » (lien méta-repo).
3. **GitHub description** mise à jour : `Moved → github.com/IvandeMurard/hospitality-agentic-mesh`.
4. **Archive** (Settings → Archive) après fenêtre de transition de **3 mois** (tags historiques préservés, read-only).

**Banner README (copie validée) :**
```markdown
# Aetherix — moved 🚚

The public home of the Hospitality Agentic Mesh (vision, architecture, roadmap)
is now **github.com/IvandeMurard/hospitality-agentic-mesh**.

Aetherix (the F&B execution node) is now developed privately.
Partnership / code access → [LinkedIn](…) · ivandemurard@gmail.com

_This repository is archived and kept read-only for historical reference._
```

### Q6 — Phasing (confirmé, + exception README sanctionnée)

- **Étape 1 — Maintenant (pré-pilote Phase 3) :** status quo structurel. **Aucune** migration repo.
- **Étape 1.5 — README vision pass (EXCEPTION SANCTIONNÉE) :** refonte du `README.md` Aetherix *vision-first + visuelle*, **additive et non destructive**, rédigée comme **brouillon de la future README du méta-repo**. Autorisée hors Étape 2 car (a) besoin immédiat de cohérence avec la description LinkedIn, (b) zéro travail jeté — ce contenu *est* la front-page du méta-repo (convention #2), (c) ne touche ni la visibilité, ni les remotes, ni la CI. Anima y figure en statut **PoC** sans lien repo (cf. README plan).
- **Étape 2 — Migration sprint (3-5 j cumulés).** **Trigger :** (a) pilote Phase 3 livré + design partner sous NDA, **OU** (b) avant approche investisseurs sérieuse Phase 4.

### Q7 — Secrets & deployments

**Pas de migration des secrets runtime.** Les secrets `flyctl secrets` vivent dans l'infra Fly.io, indépendants du repo source. L'app `aetherix-backend` et ses secrets runtime sont **intouchés**.

**Seule action réelle :** les **GitHub Actions secrets** (ex. `FLY_API_TOKEN`, clés CI) **ne se transfèrent pas** avec le code → les **recréer** dans le nouveau repo privé `aetherix` (Settings → Secrets and variables → Actions). Repointer la source du déploiement Fly (GitHub Action) vers le nouveau repo.

### Q8 — Impact CLAUDE.md

- `aetherix` (privé) **garde** son `CLAUDE.md` (F&B-specific).
- **Nouveau `CLAUDE.md` méta-repo** = vision globale Mesh + INDEX décisions **cross-cutting** + liens vers chaque `CLAUDE.md` agent.
- **Conséquence Étape 2 :** le `CLAUDE.md` actuel mélange décisions cross-cutting (#16, #18, #19, #20, #21, #22, #25) et Aetherix-specific (#1, #5, #6, #7, #9, #10, #11, #13, #15, #23, #24, …). À l'Étape 2, **scinder** l'index : cross-cutting → méta CLAUDE.md, F&B → aetherix CLAUDE.md. `decisions-architecturales.md` suit le même split.

### Q9 — Format REPOS.md (méta-repo)

```markdown
# Hospitality Agentic Mesh — Agent Repos

| Agent        | Role                 | Status                          | Access                        |
|--------------|----------------------|---------------------------------|-------------------------------|
| Aetherix     | F&B execution        | Phase 3 — pilot (live staging)  | Private — partnership contact |
| Tacet        | Sensory node         | Phase 3 — design                | Private — partnership contact |
| Orchestrator | Supervisory agent    | Phase 4 — design (stub Phase 3) | Private — partnership contact |
| Anima        | Guest context        | Phase 4 — PoC shipped (Jun 2026)| Private — partnership contact |

Contact : LinkedIn · ivandemurard@gmail.com
```

---

## Plan de migration séquencé (Étape 2 — au trigger)

**Sprint dédié ~3-5 j cumulés. Pré-requis : pilote livré + NDA, OU pré-fundraise.**

**Jour 1 — Méta-repo bootstrap**
- Créer `hospitality-agentic-mesh` (public, MIT).
- Migrer `mesh-architecture.md` + ADRs cross-cutting (0004, 0010) + `INDEX.md` public + `docs/bmad/`.
- Porter la README Étape 1.5 comme front-page méta-repo.
- Créer `CLAUDE.md` méta (Q8) + `REPOS.md` (Q9).
- Mettre à jour les pointeurs : `tacet-app/ARCHITECTURE_MANIFEST.md` + CLAUDE.md agents → URL méta.

**Jour 2 — Shared workflows (progressif, Q4)**
- Porter `reusable-schema-drift.yml` → tester depuis aetherix via `uses:` → puis eval-gate, lint, security-scan, bmad-validate.

**Jour 3 — Aetherix privé (Q1/Q7)**
- Créer repo privé `aetherix` ; `git push --mirror` ; nettoyer branches.
- Recréer GitHub Actions secrets ; repointer déploiement Fly ; smoke E2E.
- Scinder CLAUDE.md / decisions-architecturales.md (cross-cutting retirés, déjà au méta).

**Jour 4 — Stub + redirect (Q5)**
- Réduire `aetherix-hospitality-ai` au banner ; pinned issue ; description ; (archive à T+3 mois).

**Jour 5 — Buffer / comms**
- Coordonner avec submission Apaleo Agent Hub (URLs stables). Post LinkedIn / annonce.

---

## Specs concrètes

**`.gitmodules` (uniquement si exception Q3 déclenchée pour un agent) :**
```ini
[submodule "docs/bmad"]
    path = docs/bmad
    url = https://github.com/IvandeMurard/hospitality-agentic-mesh.git
    branch = main
```

**Template reusable workflow (méta-repo `.github/workflows/reusable-eval-gate.yml`) :**
```yaml
name: reusable-eval-gate
on:
  workflow_call:
    secrets:
      ANTHROPIC_API_KEY: { required: false }
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python scripts/ci/check_eval_coverage.py
```

---

## Numérotation Décision CLAUDE.md — caveat à résoudre

Le brief proposait `#25 "Multi-repo strategy"`. **Mais** `memory/market_signals_2026Q2.md` (06-15) a *spéculativement* réservé `#25` pour « Eval rollout discipline (engine/gate split…) » — non encore formalisé en ADR. **Aucun #25 n'existe dans `decisions-architecturales.md` (qui s'arrête à #24).**

**Décision :** cette ADR prend **#25 « Multi-repo strategy + governance »** (formalisée, datée, avec ADR). Si « Eval rollout discipline » est formalisé plus tard, il prendra **#26**. Ne pas créer deux #25.

---

## Risques + mitigations

| Risque | Mitigation |
|---|---|
| Perte signal recrutement (repo public devient privé) | Stub public conserve stars + historique ; méta-repo public porte le signal aspirationnel + REX Phase 3 Track B |
| Divergence méta vs agents (`mesh-architecture.md`, BMad désync) | Source unique au méta + référence URL (Q3) ; stub archivé ne diverge pas (Q1) |
| Effort migration trop lourd pré-pilote | Trigger Étape 2 explicite — rien ne bouge maintenant sauf README (Étape 1.5) |
| Rupture URLs pendant listing Apaleo Agent Hub | Coordonner timing migration ↔ submission (Jour 5) ; redirect 3 mois |
| GitHub Actions secrets cassés post-migration | Q7 — recréer secrets Actions dans repo privé ; secrets runtime Fly intouchés |
| Réutilisation reusable workflows bloquée | Méta-repo **public** → appelable sans grant (Q4) |

---

## Definition of Done (ADR finalisé)

- [x] Conventions PM #1-7 intégrées
- [x] Q1-Q9 tranchées avec rationale
- [x] Contradiction brief Q1↔Q5 résolue (stub public + privé actif)
- [x] Plan migration séquencé jour-par-jour
- [x] Specs submodule + reusable workflow + banner redirect
- [x] Caveat numérotation #25 résolu
- [ ] **PM sign-off final** (Ivan)
- [ ] Exécution Étape 2 au trigger

---

## Actions post-ADR (downstream)

1. Supprimer `0010-multi-repo-strategy-DRAFT.md` (ce fichier le remplace) — *présent sur origin/main, pas encore pull en local*.
2. `CLAUDE.md` §Décisions architecturales : ajouter ligne d'index **#25 « Multi-repo strategy + governance (méta-repo public + execution nodes privés) »** + détail H3 dans `docs/context/decisions-architecturales.md`.
3. `docs/context/open-decisions.md` : créer + déplacer « Multi-repo strategy » de §Actives → §Resolved (date 16/06/2026, trigger Étape 2 documenté).
4. **Étape 1.5 (immédiat) :** refonte README vision-first (deliverable suivant).
5. **Étape 2 (au trigger) :** exécuter le plan de migration séquencé.

---

## Décisions liées

#16 (schema drift → shared workflow) · #18 (Tacet repo) · #19 (Orchestrateur repo) · #20 (Anima repo + PoC) · #21 (Apaleo MCP cohérence cross-repo) · #22 (eval-by-design → shared workflow) · `mesh-architecture.md` (migration cible méta-repo).
