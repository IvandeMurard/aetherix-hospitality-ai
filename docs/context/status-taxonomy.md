# Taxonomie de statut — ce qui est prouvé, et jusqu'où

> **Story 16.17 / HOS-318** (AC2) · Origine : adversarial review externe GPT du 20/07/2026 (C6 / F13 / H8).
> Doc de référence **unique**. Toute brique présentée — README, case study, deck, post, doc interne — porte
> une des cinq étiquettes ci-dessous. Une brique sans étiquette est un drift, pas un oubli.
>
> Voisin : [`docs/planning/protocole-de-preuve.md`](../planning/protocole-de-preuve.md) — cette taxonomie
> qualifie **ce qui est prouvé** ; le protocole définit **ce que prouver veut dire**.

---

## Les cinq étiquettes

| Étiquette | Définition | Question qui tranche |
|---|---|---|
| **Built** | Code livré, déployé, exercé de bout en bout sur l'environnement cible. | *Est-ce que ça tourne, aujourd'hui, sans intervention de ma part ?* |
| **Shadow-mode** | Tourne sur des données réelles, mais aucune décision n'est livrée à un humain sur cette base. | *Est-ce que quelqu'un agit sur cette sortie ?* Si non → Shadow-mode, pas Built. |
| **Synthetic PoC** | Validé sur données fabriquées uniquement. Jamais confronté au réel. | *Les données d'entrée ont-elles été générées par moi ?* Si oui → Synthetic PoC, quel que soit le soin du code. |
| **Design** | Spécifié (ADR, schéma, contrat), non implémenté. | *Existe-t-il du code qui exécute ça ?* Si non → Design, même si la spec est complète et acceptée. |
| **Research** | Exploration sans engagement de livraison. Question ouverte, pas backlog. | *Y a-t-il une date, un scope et une DoD ?* Si non → Research. |

**Deux pièges nommés explicitement**, parce que ce sont les deux qui ont produit les défauts corrigés par cette story :

1. **`Built` ne veut pas dire adopté.** Une capacité peut être Built et n'avoir aucun utilisateur. C'est le
   cas de tout Aetherix aujourd'hui. L'étiquette dit que le code tourne, pas que quelqu'un s'en sert — d'où
   la colonne **Preuve** obligatoire ci-dessous, qui nomme les données et le nombre d'utilisateurs réels.
2. **`Built (PoC)` n'existe pas.** C'est une formulation qui emprunte la crédibilité de *Built* à une chose
   qui est *Synthetic PoC*. Interdite.

## Règle d'emploi

- Toute brique citée sur une surface publique porte son étiquette **à côté de son nom**, pas en note de bas de page.
- Le présent de l'indicatif est réservé à **Built** et **Shadow-mode**. Une brique *Design* ou *Research* se
  décrit au conditionnel ou au futur (« partagerait des priors anonymisés »), jamais par « the system employs ».
- Tout chiffre publié porte la **nature de ses données** (réelles / synthétiques) et, si c'est une métrique de
  décision, le renvoi au seuil pré-enregistré du protocole de preuve.

---

## État des briques (01/08/2026)

| Brique | Statut | Preuve — données, utilisateurs |
|---|---|---|
| **Daily Receipt** (P2-1→P2-7) | **Built** | Déployé staging Fly.io, smoke E2E 5/5. Données sandbox + synthétiques. **0 utilisateur réel.** |
| **Forecast Prophet** | **Shadow-mode** | Benchmarké sur données réelles publiques (Recruit, 30 restaurants JP tirés d'un dataset de 829, 1 193 points — [`mape-benchmark.md`](mape-benchmark.md)). Aucune décision livrée à un manager sur cette base. Shadow-mode sur données hôtelières réelles = HOS-308, non démarré. |
| **MCP Server v0** | **Built** | Live Fly.io, 3 tools atomiques, multi-tenant, token binding. 0 consommateur externe. |
| **Mémoire opérationnelle** (pgvector) | **Built** | Instrumentée (ADR-0002/0003). Corpus synthétique — la mémoire n'a jamais mémorisé un vrai service. |
| **Guardrails runtime** (Epic 12, G-1→G-5) | **Built** | 11 raisons typées, tests + eval layer `guardrail` (HOS-321). Éprouvés en CI, pas en incident réel. |
| **Anima** | **Synthetic PoC** | 4 couches temporelles, cohorte synthétique, hackathon Anthropic juin 2026. Jamais en production. Production = DPIA-gated. |
| **Context Graph** (ADR-0008 Path C) | **Design** | Spécifié, non démarré. Différé Phase 4 en entier (PM sign-off 31/07/2026, Décision #24). |
| **Signal Contract** (ADR-0012) | **Design** | Contrat accepté et gelé terminologiquement, aucune implémentation. Reste privé (Décision #31). |
| **HiveMemory fédérée / Learning Engine** | **Research** | Aucun socle : `hotel_cohort_features` v1 n'existe pas, socle Hive gelé (Décision #23 §D4). Ce qui tourne aujourd'hui sous le nom « cold-start » = patterns génériques, pas un prior fédéré. |
| **Orchestrateur** | **Design** | Proto-stub Phase 3 (`backend/orchestrator/`, AetherixEngine migré). Le moteur de décision événementiel est spécifié, pas construit. |

---

## Le cas du 15,09 %

Le MAPE J+1 **15,09 %** est **circulaire** : `scripts/ops/generate_demo_data.py` fabrique les couverts à partir
de `weather_score` / `event_impact` / `occupancy`, et Prophet reçoit exactement ces trois régresseurs — le modèle
retrouve sa propre formule génératrice ([`analyse-critique-2026-07.md`](analyse-critique-2026-07.md), 07/07/2026 ;
confirmé indépendamment par la review externe du 20/07).

**Le chiffre n'est pas supprimé** : il reste un gate interne de non-régression légitime (Décision #14). Ce qui est
interdit, c'est son usage **non qualifié**. Toute occurrence porte, dans la même phrase :

> synthétique et circulaire — gate interne de non-régression, sans valeur prédictive sur données réelles

Le chiffre de référence sur données réelles est celui du benchmark Recruit ([`mape-benchmark.md`](mape-benchmark.md)
§Benchmark données réelles), et il se cite **avec son écart MdAPE**, jamais le MAPE seul.

---

## Application

- **Contrôle automatique** : détecteur **D7** de [`scripts/ops/hygiene_architecturale.py`](../../scripts/ops/hygiene_architecturale.py)
  — toute citation du MAPE synthétique sans qualificatif à ±2 lignes est un drift. D7 alimente le rapport
  d'hygiène hebdomadaire ; seul **D1** bloque une PR (cf. `.github/workflows/ci.yml`). Le contrôle est donc
  *détectif*, pas préventif — à savoir avant de s'y fier.
- **Contrôle humain** : HOS-313 (docs stratégiques) et HOS-314 (contenu & distribution) appliquent cette
  taxonomie dès la rédaction, pas en relecture.
- **Surfaces externes** : l'état d'audit et les correctifs prêts à appliquer sont consignés dans
  [`docs/context/audit-surfaces-publiques-2026-08.md`](audit-surfaces-publiques-2026-08.md).
