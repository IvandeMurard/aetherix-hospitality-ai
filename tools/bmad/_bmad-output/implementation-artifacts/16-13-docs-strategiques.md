# Story 16.13: Docs stratégiques — wedge, moat, menace plateforme, concurrence, conformité, périmètre honnête

Status: ready-for-dev

> **Linear**: [HOS-313](https://linear.app/hospitalityagent/issue/HOS-313) · **Epic**: 16 ([HOS-300](https://linear.app/hospitalityagent/issue/HOS-300)) · **Priorité**: 🟠 High · **Estimate**: 3 pts · **Sprint**: S1 (03/08 → 09/08)
> **Statut Linear** : **In Progress depuis le 09/07** — **AC1, AC2 et AC3 sont déjà livrés.** Reste **AC4 + AC5**.
> **Type**: docs stratégiques — aucun code. **PR `eval-exempt`**
> **Plan de sprint** : [`docs/planning/phase-3-sprint-plan.md`](../../../docs/planning/phase-3-sprint-plan.md) §S1 — story marquée « à clore »

## ⚠️ Reste-à-faire réel

Trois des cinq AC sont **faits** (fichiers datés du 09/07, explicitement étiquetés par AC). **Ne pas les refaire.**

| AC | Livrable | État |
|----|----------|------|
| AC1 — note wedge | `docs/context/positionnement-wedge.md` (57 l.) | ✅ **Fait** 09/07 |
| AC2 — doc moat + menace plateforme | `docs/context/moat.md` (71 l.) | ✅ **Fait** 09/07 |
| AC3 — concurrence frontale | `docs/competitive/concurrence.md` (66 l.) | ✅ **Fait** 09/07 |
| **AC4 — one-pager conformité prospect** | *(à créer)* | ⬜ **À faire** |
| **AC5 — déclaration périmètre honnête (méta-repo)** | *(à créer)* | ⬜ **À faire** |

Le reste-à-faire est de l'ordre de **1 pt sur les 3 estimés**. Reporter le solde en capacité disponible pour S1 plutôt que de laisser la story consommer son estimation initiale.

## Story

As **Ivan face à un premier hôtelier sérieux et à un lecteur du méta-repo public**,
I want **une réponse écrite aux questions de conformité, et une déclaration franche de ce qui est construit contre ce qui est visé**,
so that **la conversation commerciale ne bute pas sur le RGPD, et que la crédibilité technique ne repose pas sur un flou entretenu**.

## Acceptance Criteria (reste-à-faire)

4. **AC4** — One-pager conformité prospect : **DPA**, **RGPD WhatsApp (Q2-03)**, posture **sandbox / non-PII**.
5. **AC5** — Déclaration de périmètre honnête (**construit vs north star**, **bus factor**) intégrée au méta-repo (dépend de [HOS-305](https://linear.app/hospitalityagent/issue/HOS-305) — **Done**, donc débloqué).

## Tasks / Subtasks

- [ ] **T1 — One-pager conformité** (AC4) — proposé : `docs/SECURITY/conformite-prospect.md`
  - [ ] **DPA** : quelles données sont traitées, à quel titre (sous-traitant), où elles résident (Supabase / Fly.io — préciser la région), durée de conservation, sous-traitants ultérieurs (Anthropic, Twilio, Upstash).
  - [ ] **RGPD WhatsApp (Q2-03)** : **bonne nouvelle à valoriser** — le finding « PII (téléphone + corps) en clair dans les logs » est **RÉSOLU** ([HOS-289](https://linear.app/hospitalityagent/issue/HOS-289), PR #187 : numéros masqués, corps non loggé). Le one-pager documente la posture *après* correction, en citant la revue de sécurité comme preuve.
  - [ ] **Posture sandbox / non-PII** : ce qui a été démontré ne l'a été que sur données agrégées ou sandbox — le dire.
  - [ ] Format : **une page**, lisible par un directeur d'hôtel, pas par un juriste. C'est un support de levée d'objection.
- [ ] **T2 — Déclaration de périmètre honnête** (AC5)
  - [ ] Cible : méta-repo public `hospitality-agentic-mesh` (présent en local à `../hospitality-agentic-mesh`).
  - [ ] Séparer explicitement **construit** / **shadow-mode** / **conçu non implémenté** / **vision**. ⚠️ **Utiliser la taxonomie de [HOS-318](https://linear.app/hospitalityagent/issue/HOS-318)** — même sprint. Si HOS-318 passe en premier, reprendre ses définitions telles quelles plutôt que d'en forger d'autres.
  - [ ] **Bus factor assumé** : un seul mainteneur. Le plan 90j le pose comme un **choix de crédibilité**, pas comme un aveu (`plan-90j-proof-visibility.md` §Phase B).
  - [ ] Ne rien y mettre qui relève du Signal Contract / ADR-0012 (Décision #31 : reste privé, ne migre jamais).

## Dev Notes

### Ancrages (anti-réinvention)

- **Les trois docs déjà livrés portent la doctrine** — les lire avant d'écrire quoi que ce soit, pour ne pas les contredire :
  - `docs/context/positionnement-wedge.md` — Receipt = surface produit, forecast = moteur ; north-star = acceptance + weekly usage ; **MAPE = exigence interne, pas argument de vente**.
  - `docs/context/moat.md` — le moat n'est pas le modèle (le benchmark Recruit l'a établi) ; c'est la mémoire cognitive par propriété + PMS-agnostic + Hive.
  - `docs/competitive/concurrence.md` — Nory / Tenzo / 5-Out / Avero. Contient un avertissement explicite : *« chiffres de financement/clients à confirmer via la veille — ne pas citer sans vérification à jour »*.
- **Preuve de conformité disponible** : `docs/context/security-review-2026-Q2.md` — Q2-03 **RÉSOLU** (HOS-289, PR #187). Deux findings restent ouverts dans ce même doc (logs JSON structurés 8.1, métriques Prometheus 8.2) — **ne pas les présenter comme clos** dans le one-pager.
- **Cadrage méta-repo** : `docs/planning/plan-90j-proof-visibility.md` §Phase B — *« périmètre construit vs vision explicitement séparés (bus factor assumé — crédibilité) »*.
- **Contraintes de publication** : Décision #31 (Signal Contract privé) · NFR1 d'Epic 16 (aucun secret ni donnée sensible dans le méta-repo).

### Pièges

- **⚠ Ne pas refaire AC1-AC3.** La story est ouverte depuis le 09/07 et son intitulé Linear liste les six angles — il est facile de croire que tout reste à faire. Trois fichiers existent déjà.
- **Dépendance croisée avec HOS-318, même sprint.** AC5 a besoin de la taxonomie de statut ; HOS-318 la produit. **Séquencer HOS-318 avant AC5**, ou accepter de reprendre la déclaration si les définitions divergent.
- **Le one-pager conformité n'est pas un DPA.** C'est un support d'avant-vente qui explique la posture. Le DPA contractuel lui-même dépasse ce périmètre et relève d'un conseil juridique — le dire dans le doc plutôt que de laisser croire qu'il tient lieu de contrat.
- **Ne pas surclamer la conformité.** Q2-03 est corrigé, mais aucune propriété réelle n'a encore tourné en production (HOS-176 est en S9 au mieux). La posture honnête est *« conçu pour, vérifié en revue, pas encore éprouvé en production »*.
- **Chiffres concurrents non vérifiés** : `concurrence.md` porte lui-même l'avertissement. Si le one-pager ou la déclaration s'appuient dessus, re-vérifier d'abord.

### Test Plan

- [ ] Aucun test automatisé.
- [ ] Contrôle AC4 : un lecteur non technique peut répondre « où sont mes données, qui y accède, combien de temps » après une seule lecture.
- [ ] Contrôle AC5 : aucune capacité listée comme construite ne l'est en réalité au statut Design ou Research (recoupement avec la taxonomie HOS-318).
- [ ] Contrôle NFR1 : aucun secret, aucune donnée client, aucune référence au Signal Contract dans le contenu poussé au méta-repo public.

### References

- [Source: Linear HOS-313] · [Source: docs/context/positionnement-wedge.md] · [Source: docs/context/moat.md] · [Source: docs/competitive/concurrence.md] · [Source: docs/context/security-review-2026-Q2.md] · [Source: Linear HOS-289] · [Source: docs/planning/plan-90j-proof-visibility.md#Phase B] · [Source: Linear HOS-318] · [Source: docs/planning/phase-3-sprint-plan.md#S1]

## Dev Agent Record

### Agent Model Used

_(à remplir par l'agent d'implémentation)_

### Debug Log References

### Completion Notes List

### File List
