# Story 16.12: Unit economics — coût complet par propriété/mois vs pricing

Status: ready-for-dev

> **Linear**: [HOS-312](https://linear.app/hospitalityagent/issue/HOS-312) · **Epic**: 16 ([HOS-300](https://linear.app/hospitalityagent/issue/HOS-300)) · **Priorité**: 🟠 High · **Estimate**: 1 pt · **Sprint**: S1 (03/08 → 09/08)
> **Type**: analyse chiffrée — aucun code de production (script d'extraction toléré). **PR `eval-exempt`**
> **⛔ Débloque [HOS-179](https://linear.app/hospitalityagent/issue/HOS-179)** (pricing decision doc, S8)
> **Plan de sprint** : [`docs/planning/phase-3-sprint-plan.md`](../../../docs/planning/phase-3-sprint-plan.md) §S1

## Story

As **Ivan devant fixer un prix**,
I want **connaître le coût complet d'une propriété par mois et sa sensibilité au volume**,
so that **la décision pricing repose sur une marge calculée plutôt que sur une fourchette de marché**.

## Contexte

Maillon 5 de la chaîne de valeur — **jamais calculé**. C'est le dernier des cinq maillons du plan 90j à rester non instrumenté, et il conditionne directement [HOS-179](https://linear.app/hospitalityagent/issue/HOS-179).

**Timing favorable** : [HOS-311](https://linear.app/hospitalityagent/issue/HOS-311) (observabilité Logfire — traces FastAPI/Anthropic + spans forecast) est **Done depuis le 26/07**. L'AC1 prévoyait *« mesuré via 16.11 si dispo, sinon estimé »* : **c'est disponible**. La story bascule d'une estimation à une mesure — à condition qu'il y ait assez de trafic instrumenté pour être représentatif.

## Acceptance Criteria

1. **AC1** — Coût complet/propriété/mois chiffré : Claude API (par receipt/reco, mesuré via HOS-311) + Fly.io + Twilio WhatsApp + Upstash + Supabase.
2. **AC2** — 3 scénarios de volume (**1 / 10 / 50** propriétés) — mise en évidence coûts fixes vs variables.
3. **AC3** — Confrontation aux fourchettes pricing envisageables → **marge brute par propriété**.
4. **AC4** — Synthèse dans `docs/Cost_Model.md` (**mise à jour**, le fichier existe) + commentaire sur [HOS-179](https://linear.app/hospitalityagent/issue/HOS-179).

## Tasks / Subtasks

- [ ] **T1 — Extraire le coût LLM réel** (AC1)
  - [ ] Logfire `instrument_anthropic()` est actif (HOS-311) → extraire tokens in/out par appel, agrégés par type d'opération (receipt quotidien, reco, parsing inbound).
  - [ ] Convertir en €/mois pour une propriété au rythme nominal (1 Daily Receipt/jour + interactions inbound).
  - [ ] ⚠️ **Vérifier la représentativité** : si le trafic instrumenté depuis le 26/07 est trop faible ou uniquement synthétique, le dire et basculer sur une estimation modélisée — ne pas présenter un extrapolé comme un mesuré (cohérence [HOS-318](https://linear.app/hospitalityagent/issue/HOS-318), même sprint).
- [ ] **T2 — Coûts d'infrastructure** (AC1)
  - [ ] Fly.io (machines + volumes), Supabase (tier, stockage, pgvector), Upstash (Redis, requêtes), Twilio WhatsApp (**tarification par conversation, pas par message** — piège classique).
  - [ ] Séparer strictement **fixe** (socle partagé) et **variable** (par propriété).
- [ ] **T3 — Scénarios 1 / 10 / 50** (AC2)
  - [ ] Montrer le point de bascule : à 1 propriété, le coût fixe écrase tout ; l'intérêt du tableau est de dire **à partir de combien de propriétés le modèle tient**.
  - [ ] Identifier les paliers de tier (Supabase, Fly) qui créent des sauts de coût non linéaires.
- [ ] **T4 — Marge brute et confrontation pricing** (AC3)
  - [ ] Ancrage marché disponible : **Venli, 99-299 €/mois** (`monitoring-watchlist.md` §W12, explicitement noté comme *pricing anchor pour HOS-179*).
  - [ ] Reco interne déjà consignée dans `open-decisions.md` : **500-2 500 $/propriété/mois** selon modules. Confronter les deux et expliquer l'écart.
- [ ] **T5 — Livrable** (AC4)
  - [ ] Mettre à jour `docs/Cost_Model.md` (existant, ~15 Ko) — ne pas créer un doublon.
  - [ ] Commentaire de synthèse sur HOS-179 avec les 3 chiffres clés : coût/propriété, seuil de rentabilité, marge à 10 propriétés.

## Dev Notes

### Ancrages (anti-réinvention)

- **`docs/Cost_Model.md` existe déjà** (~15 Ko, 08/07) — l'AC4 dit « mise à jour ». Lire avant d'écrire : une partie de la structure de coûts y est probablement posée.
- **Observabilité livrée** : `HOS-311` (Done 26/07) — Logfire `instrument_fastapi` + `instrument_anthropic`, spans manuels sur le pipeline forecast. C'est la source de mesure de T1.
- **Ancrage pricing marché** : `docs/context/monitoring-watchlist.md` §W12 (Venli, 99-299 €/mois, Apaleo-native, mid-market) — déjà identifié comme anchor pour HOS-179.
- **Reco pricing interne** : `docs/context/open-decisions.md` §pricing — 500-2 500 $/propriété/mois.
- **Plan de référence** : `docs/planning/plan-90j-proof-visibility.md` §Phase C, dernier item — *« Unit economics : coût complet/propriété/mois vs fourchettes pricing. Nourrit HOS-179. ½ journée. »*

### Pièges

- **1 pt = ½ journée.** Le scope est volontairement serré : c'est un modèle de coûts, pas un business plan. Ne pas dériver vers de la projection de revenus, du CAC ou du churn.
- **Twilio WhatsApp facture à la conversation** (fenêtre 24 h), pas au message. Un Daily Receipt + 3 échanges de feedback = **1** conversation, pas 4. Se tromper ici fausse le coût variable d'un ordre de grandeur.
- **Le coût LLM n'est pas linéaire au nombre de propriétés** : le contexte RAG (pgvector) grossit avec la mémoire opérationnelle accumulée. Mentionner cette dérive même si elle n'est pas chiffrable aujourd'hui.
- **Cohérence avec la gate d'honnêteté** ([HOS-318](https://linear.app/hospitalityagent/issue/HOS-318), même sprint) : étiqueter clairement mesuré vs estimé vs extrapolé. Un coût « mesuré » sur trois jours de trafic synthétique n'est pas un coût mesuré.
- **Ne pas attendre HOS-176.** La tentation est de dire « on chiffrera avec le vrai pilote ». Le pilote est en S9 au mieux, et HOS-179 en a besoin en S8 — la modélisation doit tenir sans données de production.

### Test Plan

- [ ] Aucun test automatisé. Si un script d'extraction Logfire est écrit, le garder hors `backend/app/` (proposé : `scripts/ops/`).
- [ ] Contrôle de cohérence : la somme des postes du scénario « 1 propriété » correspond aux factures réelles du mois écoulé, à l'ordre de grandeur près.
- [ ] Contrôle : chaque chiffre porte son statut — mesuré / estimé / extrapolé.

### References

- [Source: Linear HOS-312] · [Source: docs/Cost_Model.md] · [Source: Linear HOS-311] · [Source: docs/context/monitoring-watchlist.md#W12] · [Source: docs/context/open-decisions.md#pricing] · [Source: docs/planning/plan-90j-proof-visibility.md#Phase C] · [Source: docs/planning/phase-3-sprint-plan.md#S1]

## Dev Agent Record

### Agent Model Used

_(à remplir par l'agent d'implémentation)_

### Debug Log References

### Completion Notes List

### File List
