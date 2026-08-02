# Story 16.17: Gate honnêteté métriques — audit MAPE synthétique + taxonomie de statut

Status: ready-for-dev

> **Linear**: [HOS-318](https://linear.app/hospitalityagent/issue/HOS-318) · **Epic**: 16 ([HOS-300](https://linear.app/hospitalityagent/issue/HOS-300)) · **Priorité**: 🟠 High · **Estimate**: **non estimée** (≈2 pts proposés) · **Sprint**: S1 (03/08 → 09/08)
> **Type**: audit documentaire + convention transverse — **PR `eval-exempt`**
> **Source**: adversarial review externe GPT (20/07/2026) — Critical C6 + Finding F13 + High Value H8. Corpus : `C:\Users\ivand\OneDrive\Documents\aetherix-gpt-review-corpus\`
> **Plan de sprint** : [`docs/planning/phase-3-sprint-plan.md`](../../../docs/planning/phase-3-sprint-plan.md) §S1

## Story

As **Ivan présentant Aetherix à un recruteur, un hôtelier ou un investisseur**,
I want **qu'aucune capacité ni aucun chiffre ne puisse être lu comme plus mûr qu'il ne l'est**,
so that **la crédibilité tienne à l'examen — un seul chiffre non qualifié suffit à faire douter de tout le reste**.

## Contexte

Le MAPE **15,09 %** est circulaire : `generate_demo_data.py` fabrique les couverts à partir des mêmes régresseurs que Prophet consomme — le modèle retrouve sa propre formule génératrice. C'est établi en interne depuis le 08/07 (`analyse-critique-2026-07.md`) et **confirmé indépendamment** par la review adversariale externe du 20/07.

Rien ne garantit aujourd'hui que ce chiffre n'apparaisse plus, seul et sans contexte, sur une surface publique. La review recommande en complément une **taxonomie de statut explicite** partout où une capacité est présentée.

**Timing favorable** : [HOS-307](https://linear.app/hospitalityagent/issue/HOS-307) (benchmark Recruit) est **Done depuis le 30/07** — le chiffre réel de remplacement existe enfin. Cette story n'a plus à choisir entre « retirer » et « remplacer ».

## Acceptance Criteria

1. **AC1** — Grep systématique de `15.09` / `15,09` / `MAPE` sur toutes les **surfaces publiques** (méta-repo `hospitality-agentic-mesh`, case study [ivandemurard.com/aetherix](https://ivandemurard.com/aetherix), pitch deck, posts LinkedIn existants) — chaque occurrence porte soit le contexte « synthétique, non-produit », soit est remplacée par le chiffre réel ([HOS-307](https://linear.app/hospitalityagent/issue/HOS-307)/[HOS-308](https://linear.app/hospitalityagent/issue/HOS-308)).
2. **AC2** — Taxonomie (**Built / Shadow-mode / Synthetic PoC / Design / Research**) définie une fois dans un doc de référence et appliquée a minima à : Daily Receipt (Built) · forecast Prophet (Shadow-mode) · Anima (Synthetic PoC, jamais en production) · Context Graph (Design, ADR-0008 Path C non démarré) · HiveMemory/Learning Engine (Research) · Signal Contract/ADR-0012 (Design, gated).
3. **AC3** — Coordonné avec [HOS-313](https://linear.app/hospitalityagent/issue/HOS-313) et [HOS-314](https://linear.app/hospitalityagent/issue/HOS-314) pour que tout nouveau contenu public respecte la taxonomie dès publication.

## Tasks / Subtasks

- [ ] **T1 — Trancher la métrique de référence** (pré-requis AC1) — voir §Le vrai arbitrage
  - [ ] Décider quel chiffre devient le chiffre public : MAPE all-leads, MdAPE, ou les deux avec leur écart.
  - [ ] Statuer sur la clause de pivot de la DoD Epic 16 : déclenchée ou non, et pourquoi. **Décision à écrire, pas à sous-entendre.**
- [ ] **T2 — Audit des surfaces publiques** (AC1)
  - [ ] Méta-repo `hospitality-agentic-mesh` ([HOS-305](https://linear.app/hospitalityagent/issue/HOS-305), Done) · case study · pitch deck · posts LinkedIn publiés.
  - [ ] Pour chaque occurrence : qualifier ou remplacer. Consigner la liste traitée dans le livrable.
- [ ] **T3 — Passe interne (hors AC, recommandée)**
  - [ ] 12 fichiers du repo privé contiennent `15.09` / `15,09` : `README.md`, `CLAUDE.md`, `AGENTS.md`, `docs/INDEX.md`, `docs/adr/0007-evaluation-by-design.md`, `docs/context/analyse-critique-2026-07.md`, `docs/context/mape-benchmark.md`, `docs/pilot/onboarding-kit.md`, `docs/planning/evaluation-by-design.md`, 3 veilles.
  - [ ] ⚠️ **`docs/pilot/onboarding-kit.md` est prioritaire** — c'est un document destiné au partenaire pilote. Un chiffre circulaire y est de facto public.
  - [ ] `mape-benchmark.md` porte déjà l'avertissement du 08/07 — le prendre comme modèle de qualification.
- [ ] **T4 — Taxonomie** (AC2)
  - [ ] Doc de référence court + tableau des briques. Emplacement proposé : `docs/context/status-taxonomy.md`, référencé depuis `docs/INDEX.md`.
  - [ ] Définitions non ambiguës : *Built* = en production et utilisé · *Shadow-mode* = tourne sur données réelles sans décision livrée · *Synthetic PoC* = validé sur données fabriquées uniquement · *Design* = spécifié, non implémenté · *Research* = exploration sans engagement.
- [ ] **T5 — Rendre la taxonomie exécutoire** (AC3)
  - [ ] Étendre l'**agent d'hygiène architecturale** ([HOS-320](https://linear.app/hospitalityagent/issue/HOS-320), Done 29/07) d'une règle de drift : toute occurrence de `15.09` hors contexte qualifié, ou toute brique présentée sans étiquette de statut, = drift détecté. **Sans cela, la gate se dégrade dès le prochain contenu publié.**
  - [ ] Noter la convention dans `CLAUDE.md` pour que HOS-313 et HOS-314 l'appliquent par défaut.

## Dev Notes

### Le vrai arbitrage (à traiter en premier)

Le benchmark Recruit ([HOS-307](https://linear.app/hospitalityagent/issue/HOS-307), `docs/context/mape-benchmark.md`) donne :

| Modèle | MAPE all-leads | MdAPE all-leads |
|---|---|---|
| Baseline naïve | 55,86 % | 27,57 % |
| **Prophet (config Aetherix)** | **49,71 %** | **27,01 %** |
| **Écart** | **+6,15 pts** | **+0,56 pt** |

La **DoD d'Epic 16** stipule : *« Prophet bat la baseline naïve de ≥ 5 pts sur données réelles, **sinon décision pivot modèle documentée** »*.

**En MAPE, la barre est franchie. En MdAPE, elle ne l'est pas — d'un facteur dix.** Le MAPE est gonflé par les jours à faible fréquentation (erreur relative explosive sur petits dénominateurs) ; le MdAPE est plus robuste et raconte une histoire nettement moins flatteuse : sur la médiane, Prophet **égale** la baseline naïve.

`docs/context/moat.md` a déjà acté cette lecture — *« Prophet égale la baseline naïve »* — et en a tiré la conclusion stratégique que le moat n'est pas le modèle. **Cette story doit rendre cette lecture explicite sur les surfaces publiques**, pas seulement dans un doc interne.

Publier « +6,15 pts vs baseline » sans mentionner le MdAPE serait **exactement le travers** que cette story existe pour corriger — un chiffre vrai, choisi pour flatter. La recommandation par défaut : **publier les deux, avec l'écart, et la lecture qui va avec.**

### Ancrages (anti-réinvention)

- **Chiffres de référence** : `docs/context/mape-benchmark.md` §« Benchmark données réelles — Recruit (08/07/2026) ». Protocole déterministe, 2 runs bit-identiques (Décision #29), 30 restaurants (dataset de 829) réels, 1 193 points scorés. Script : `scripts/ops/benchmark_recruit.py` · Résultats : `eval/benchmarks/recruit_results.json`.
- **Modèle de qualification déjà écrit** : l'encart d'avertissement en tête de `mape-benchmark.md` (08/07). Réutiliser sa formulation plutôt qu'en inventer une.
- **Lecture stratégique déjà actée** : `docs/context/moat.md` (HOS-313 AC2) — cohérence à préserver, pas à recréer.
- **Mécanisme d'application** : `HOS-320` a livré un agent d'hygiène qui détecte les drifts docs/code/eval en PR-only, zéro surface runtime. C'est le véhicule naturel de T5.
- **Constat d'origine** : `docs/context/analyse-critique-2026-07.md` (audit 07/07) — la circularité y est démontrée.

### Pièges

- **⚠ La story n'est pas estimée dans Linear.** ≈2 pts proposés (audit + doc court + 1 règle d'hygiène). À confirmer avant de l'ouvrir — c'est le seul item non pointé de S1.
- **AC1 dit « surfaces publiques »**, mais `docs/pilot/onboarding-kit.md` est remis au partenaire pilote : traité en T3, à ne pas oublier sous prétexte qu'il vit dans un repo privé.
- **Ne pas supprimer le 15,09 % de `mape-benchmark.md`.** Il reste un gate interne de non-régression légitime (Décision #14), correctement encadré depuis le 08/07. La cible, ce sont les usages **non qualifiés**, pas le chiffre lui-même.
- **Une taxonomie non outillée se périme en trois semaines.** T5 n'est pas cosmétique : sans règle d'hygiène, la convention ne survivra pas à HOS-314 (contenu & distribution, S3).
- **Cohérence avec HOS-313** : `positionnement-wedge.md` pose déjà *« MAPE = exigence interne, pas argument de vente »*. La taxonomie doit s'y aligner, pas la contredire.

### Test Plan

- [ ] Aucun test automatisé (sauf si T5 ajoute une règle à l'agent d'hygiène → tester la détection sur un cas positif et un cas négatif).
- [ ] Contrôle : un grep `15.09|15,09` sur les surfaces publiques ne renvoie que des occurrences qualifiées.
- [ ] Contrôle : les 6 briques listées en AC2 portent une étiquette de statut dans le doc de référence.

### References

- [Source: Linear HOS-318] · [Source: docs/context/mape-benchmark.md#Benchmark données réelles] · [Source: docs/context/analyse-critique-2026-07.md] · [Source: docs/context/moat.md] · [Source: docs/context/positionnement-wedge.md] · [Source: Linear HOS-300 DoD] · [Source: Linear HOS-320] · [Source: eval/benchmarks/recruit_results.json]

## Dev Agent Record

### Agent Model Used

_(à remplir par l'agent d'implémentation)_

### Debug Log References

### Completion Notes List

### File List
