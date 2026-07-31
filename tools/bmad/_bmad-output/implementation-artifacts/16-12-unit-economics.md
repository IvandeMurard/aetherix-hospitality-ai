# Story 16.12: Unit economics — coût complet par propriété/mois vs pricing

Status: review

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

Bob (Scrum Master) exécutant `dev-story` · claude-opus-5 · 2026-07-30

### Debug Log References

- Aucun test automatisé — analyse chiffrée, aucun code de production. PR à marquer `eval-exempt`.
- Aucun script d'extraction Logfire écrit : le trafic instrumenté depuis le 26/07 est du sandbox, pas de la production.

### Completion Notes List

- **AC1 ✅** — Coût complet chiffré. **≈ 0,75 $/propriété/mois de LLM**, calculé sur les tarifs Anthropic vérifiés (Sonnet 4.6 : 3/15 $ · Haiku 4.5 : 1/5 $ par MTok) × volumétrie dérivée du code (dispatchers APScheduler, `receipts.py`, `mcp_server.py`). Twilio ≈ 1,60 $ (facturation **par conversation**, pas par message). Infra Fly/Supabase/Upstash estimée depuis `fly.toml`.
- **AC2 ✅** — 3 scénarios : **8,05 $** @ 1 propriété · **5,42 $** @ 10 · **3,29 $** @ 50. Points de bascule identifiés : Supabase free→Pro (~25 $, entre 1 et 10 propriétés) et RAM Fly (Prophet `fit()` devient dimensionnant vers 30 propriétés).
- **AC3 ✅** — Marge brute **> 94 %** au prix le plus bas de la fourchette marché (Venli 99 €), dès 10 propriétés.
- **AC4 ✅** — `docs/Cost_Model.md` **réécrit** (v2.0). La v0.1.0 du 02/12/2025 modélisait un stack disparu (Qdrant, ElevenLabs, Vercel, Render) et un framing « restaurants à 49 $/mois » — c'était une réécriture, pas une mise à jour.
- **🎯 Conclusion structurante pour HOS-179 : le coût de service n'est pas la contrainte.** Le coût marginal d'une propriété (~2,35 $) est négligeable devant tout prix envisageable. Le pricing **ne peut donc pas se construire en cost-plus** — c'est un arbitrage valeur / disposition à payer. L'écart entre l'ancrage Venli (99-299 €) et la reco interne (500-2 500 $) est un **facteur 5 à 8 que ce modèle ne justifie pas** et qui devra se défendre sur la valeur mesurée au pilote.
- **Contre-intuitif** : le LLM n'est pas le poste dominant. Le socle fixe l'est — `min_machines_running = 1` + `auto_stop_machines = "off"` fait tourner la machine Fly 24/7 même sans trafic (contrainte des workers APScheduler).
- **Levier identifié, non retenu** : le prompt caching diviserait le poste input par ~10 (≈ 0,25 $/propriété). Gain absolu trop faible aujourd'hui — à reconsidérer au-delà de ~50 propriétés.
- **⚠ Limite assumée — T1 exécutée en mode estimé, pas mesuré.** Logfire est actif (HOS-311, Done 26/07) mais n'a accumulé que du trafic sandbox. L'extrapoler aurait présenté du synthétique comme du réel — exactement ce que [HOS-318](https://linear.app/hospitalityagent/issue/HOS-318) interdit. Chaque chiffre porte son statut **Calculé / Estimé** et le doc s'ouvre sur cet avertissement. **À re-mesurer après le go-live (HOS-176).**

### File List

- `docs/Cost_Model.md` *(réécrit — v2.0)*
