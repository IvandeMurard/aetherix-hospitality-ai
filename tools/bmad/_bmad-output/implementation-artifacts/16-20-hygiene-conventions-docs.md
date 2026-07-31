# Story 16.20: Agent d'hygiène — contrôles de conventions documentaires

Status: review

> **Linear**: *(à créer — proposition ci-dessous)* · **Epic**: 16 ([HOS-300](https://linear.app/hospitalityagent/issue/HOS-300)) · **Priorité**: 🟡 Medium · **Estimate**: 2 pts proposés · **Sprint**: non planifié
> **Type**: extension de l'agent d'hygiène existant — PR-only, zéro surface runtime. **PR `eval-exempt`**
> **Étend** : [HOS-320](https://linear.app/hospitalityagent/issue/HOS-320) (Story 16.18, agent d'hygiène architecturale, Done 29/07)

## Story

As **le mainteneur solo d'un dépôt dont les conventions sont écrites mais pas contrôlées**,
I want **que l'agent d'hygiène vérifie mécaniquement les conventions documentaires vérifiables**,
so that **une règle cesse de dériver silencieusement entre le moment où on l'écrit et celui où on s'en aperçoit**.

## Contexte — trois dérives constatées le même jour

Le 30/07/2026, une session SM a relevé trois conventions écrites mais non tenues. Aucune n'était détectable autrement qu'en tombant dessus par hasard :

1. **Plafond `CLAUDE.md` dépassé de 30 %.** Le fichier déclare en tête *« facts + INDEX uniquement, cible ≤ 150 lignes »*. Il était à **196 lignes**. Personne ne l'avait vu, et la session a commencé par y ajouter un pavé narratif de 586 caractères — aggravant la violation dans le fichier qui porte la règle.
2. **Compte de décisions divergent.** `CLAUDE.md` annonçait *« 24 décisions architecturales »*, `docs/INDEX.md` en comptait **31**. Un nombre codé en dur dans deux fichiers dérive à chaque ajout.
3. **Fichier fantôme.** `docs/context/monitoring-watchlist.md` et `open-decisions.md` annonçaient un `apaleo-copilot-functional-audit.md` **jamais écrit**. Celui-là, HOS-320 l'a bien détecté (drift D2) — preuve que le mécanisme fonctionne quand la règle est exprimable.

**La différence entre les trois** : le cas 3 était déjà couvert. Les cas 1 et 2 sont tout aussi mécaniques, mais personne ne les avait formulés comme des contrôles.

> Le point n'est pas que ces trois erreurs soient graves. C'est qu'elles sont **toutes vérifiables par une machine**, et qu'aucune ne l'était.

## Acceptance Criteria

1. **AC1 — Plafond de lignes `CLAUDE.md`.** L'agent échoue la PR si `CLAUDE.md` dépasse son plafond. Le plafond est **lu depuis le fichier lui-même** (la ligne « plafond dur N lignes » en tête), pas codé en dur — sinon on recrée la dérive qu'on corrige.
2. **AC2 — Cohérence du compte de décisions.** Le nombre de décisions annoncé dans un doc doit correspondre au nombre réellement présent dans `docs/context/decisions-architecturales.md`. Détecte le cas 2. **Généraliser** : tout « N décisions » / « N stories » / « N tools » codé en dur et vérifiable.
3. **AC3 — Exclusions local-only.** Les chemins sortis du dépôt le 30/07 (`docs/veille/`, `docs/_archive/`, `tools/bmad/_bmad/`) **ne doivent pas être signalés** comme références cassées : ils existent en local. Règle d'exclusion documentée dans `docs/INDEX.md` §Convention local-only.
4. **AC4 — Sortie actionnable.** Chaque violation nomme le fichier, la ligne, la règle violée et l'écart chiffré. Pas de « drift détecté » sans le delta.

## Tasks / Subtasks

- [ ] **T1 — Lire l'implémentation existante** (pré-requis)
  - [ ] HOS-320 a livré l'agent (`aeb68a3` et commits liés, PR-only, zéro surface runtime). **Étendre, ne pas réécrire.**
  - [ ] Identifier où s'ajoutent les règles et sous quel format elles sont déclarées.
- [ ] **T2 — Contrôle de plafond** (AC1)
  - [ ] Parser la ligne de règle en tête de `CLAUDE.md` pour extraire N.
  - [ ] Comparer au `wc -l` réel. Échec si dépassement.
  - [ ] ⚠️ **Le plafond est aujourd'hui dépassé (166 / 150)** — voir §Piège d'amorçage.
- [ ] **T3 — Contrôle de comptes** (AC2)
  - [ ] Regex sur les « N décisions » / « N stories » etc. dans les docs suivis.
  - [ ] Compter la source de vérité correspondante, comparer.
  - [ ] Commencer par le seul cas connu (décisions architecturales) ; généraliser ensuite si d'autres apparaissent.
- [ ] **T4 — Exclusions** (AC3)
  - [ ] Ajouter `docs/veille/`, `docs/_archive/`, `tools/bmad/_bmad/` à la liste d'exclusion des vérifications de liens.
- [ ] **T5 — Format de sortie** (AC4)
  - [ ] Aligner sur le format des drifts D1/D2/D3 existants.

## Dev Notes

### ⚠️ Piège d'amorçage — à trancher avant T2

**Le plafond est violé au moment où on écrit le contrôle** : `CLAUDE.md` est à 166 lignes pour un plafond de 150, après le refactoring du 30/07 (extraction de `Variables d'environnement` → `ops/environment-variables.md` et `Dev Agent — DoD` → `context/dev-agent-dod.md`, 195 → 166).

Activer AC1 tel quel **casse toutes les PR immédiatement**. Trois issues, à choisir explicitement :

| Option | Effet |
|--------|-------|
| **Relever le plafond à ~170** | Assume la croissance de l'index de décisions (24 → 31 depuis que 150 a été posé). Le contrôle devient vert tout de suite. |
| **Compresser l'index de décisions** | Titres courts sans résumé — gagne les 16 lignes, mais oblige à ouvrir `decisions-architecturales.md` plus souvent en session. |
| **Livrer en WARN puis flipper en blocking** | Pattern déjà éprouvé sur l'eval gate ([HOS-216](https://linear.app/hospitalityagent/issue/HOS-216) → [HOS-274](https://linear.app/hospitalityagent/issue/HOS-274)). Laisse le temps de dégraisser. |

L'arbitrage est documenté et **non tranché** dans `docs/INDEX.md` §Dette CLAUDE.md. **Ne pas le trancher dans le code sans décision PM.**

### Ancrages (anti-réinvention)

- **L'agent existe** : livré par HOS-320 (Story 16.18) le 29/07 — détection de drift docs/code/eval, PR-only, zéro surface runtime. C'est le véhicule.
- **Le drift D2 est le précédent qui marche** : le fichier fantôme `apaleo-copilot-functional-audit.md` a été détecté par ce même agent, et la correction est visible dans `context/open-decisions.md`. Même forme de règle.
- **Les conventions à contrôler sont déjà écrites** : règle anti-surcharge en tête de `CLAUDE.md` · `docs/INDEX.md` §Dette CLAUDE.md (diagnostic par section) · `docs/INDEX.md` §Convention local-only (exclusions).
- **Pattern WARN → blocking** : `scripts/ci/check_eval_coverage.py` + workflow eval-gate, flippé après N PR vertes (Décision #22, HOS-274).

### Pièges

- **Ne pas coder le plafond en dur.** Le lire depuis `CLAUDE.md`. Un seuil dupliqué dans le script et dans le doc, c'est exactement le cas 2 qu'on essaie de détecter.
- **AC3 n'est pas cosmétique.** Sans les exclusions, l'agent signalera au prochain run les ~13 docs en ligne qui citent `monitoring-watchlist.md` — tous faux positifs. Un contrôle qui crie au loup est désactivé en deux semaines.
- **Rester dans le vérifiable.** « Le fichier fait plus de N lignes » et « le compte annoncé ≠ le compte réel » sont mécaniques. « La doc est à jour » ne l'est pas — ne pas essayer.
- **Portée : conventions documentaires uniquement.** Ni style, ni orthographe, ni qualité rédactionnelle.

### Impact sur le plan de sprint

**Aucun — non planifié.** Epic 16 se clôt à S2 et cette story n'est pas requise par ses critères de sortie J+90. C'est de la dette outillage, à placer après la reprise de Phase 3 ou dans une fenêtre creuse. Ne pas la laisser repousser HOS-176.

### Test Plan

- [ ] AC1 : `CLAUDE.md` volontairement gonflé au-dessus du plafond → détecté ; sous le plafond → vert.
- [ ] AC2 : compte volontairement faussé dans un doc → détecté avec l'écart chiffré.
- [ ] AC3 : une référence à `docs/_archive/` → **non signalée** ; une référence à un fichier réellement inexistant → signalée.
- [ ] Non-régression : les drifts D1/D2/D3 existants sont toujours détectés.

### References

- [Source: Linear HOS-320] · [Source: docs/INDEX.md#Dette CLAUDE.md] · [Source: docs/INDEX.md#Convention local-only] · [Source: CLAUDE.md règle anti-surcharge] · [Source: docs/context/decisions-architecturales.md] · [Source: scripts/ci/check_eval_coverage.py]

## Proposition de ticket Linear (non créé)

**Non créé délibérément** — la convention de cette session est que les mouvements dans Linear passent par Ivan.

- **Titre** : `Story 16.20: Agent d'hygiène — contrôles de conventions documentaires (plafond CLAUDE.md + comptes)`
- **Parent** : HOS-300 (Epic 16)
- **Priorité** : Medium · **Estimate** : 2 pts · **Labels** : `Story`
- **Description** : reprendre le §Contexte et les 4 AC ci-dessus.

## Dev Agent Record

### Agent Model Used

Bob (Scrum Master) executant dev-story - claude-opus-5 - 2026-07-31

### Debug Log References

- `pytest backend/tests/scripts/test_hygiene_architecturale.py` : **34 passed** (25 avant, +9).
- Gate CI simule (`--detectors D1,D5,D6`) : **exit 0**.
- Rapport complet : 0 drift, 7 info -> `docs/testing/evidence/hygiene/report-2026-07-31-conventions.md`.

### Completion Notes List

- **AC1 (D5) OK** - plafond lu dans le fichier via `plafond dur (\d+) lignes`, jamais code en dur. Un test verifie explicitement qu'elever le plafond declare suffit a lever le finding.
- **AC2 (D6) OK** - **3 drifts reels trouves au premier run** : `AGENTS.md` et le fichier source lui-meme annoncaient 24, `docs/INDEX.md` annoncait 31, la realite etait 29. Correctif : les comptes codes en dur ont ete **retires**, pas corriges.
- **AC3 OK** - `LOCAL_ONLY_PREFIXES` : sans elle, D2 remontait **7 faux positifs** des le premier run.
- **AC4 OK** - chaque finding porte l'ecart chiffre.
- **Piege d'amorcage resolu par l'arbitrage Ivan** : plafond releve de 150 a 170. D5 et D6 partent donc directement en **blocking**, sans passer par une phase WARN.
- **Deux regressions de mon propre refactoring du 30/07, trouvees par l'agent lui-meme** : D1 cassait (AGENTS.md non resynchronise) et D3 lisait une section vide (`Variables d'environnement` extraite sans repointer le detecteur). D3 a ete repointe, son regex accepte les deux formats, et un garde-fou a ete ajoute : zero variable lue = drift, pas silence.
- **Portee elargie en CI** : le job passe de `--detectors D1` a `D1,D5,D6`, renomme `conventions-docs`. D2/D3/D4 restent report-only - ils produisent legitimement des `info` qui ne doivent pas casser une PR.
- **Entree PLANNED_PATHS periemee retiree** (`apaleo-copilot-functional-audit.md`) : le fichier fantome a ete supprime des docs le 30/07, l'entree ne couvrait plus rien.

### File List

- `scripts/ops/hygiene_architecturale.py` *(D5 + D6 + LOCAL_ONLY_PREFIXES + D3 repointe)*
- `backend/tests/scripts/test_hygiene_architecturale.py` *(+9 tests)*
- `.github/workflows/ci.yml` *(gate elargi a D1,D5,D6)*
- `CLAUDE.md` + `AGENTS.md` *(plafond 170, resynchronises)*
- `docs/INDEX.md`, `docs/context/decisions-architecturales.md` *(comptes retires)*
- `docs/testing/evidence/hygiene/report-2026-07-31-conventions.md` *(preuve)*
