# Requête de faisabilité F&B — brief de conception

> **Statut : Design** (taxonomie [`status-taxonomy.md`](status-taxonomy.md), Décision #33). Brief de conception : ni spécification acceptée, ni décision. Date : 08/11/2026.
> **Origine** : veille du 08/11/2026 (le cadrage d'une jeune pousse sur « la capacité de l'hôtel à livrer » une préférence), vérifié contre le dépôt. La décision ouverte correspondante est dans [`open-decisions.md`](open-decisions.md) (« F&B feasibility query for the Orchestrator and host agents »).
> **Ce que ce brief fait** : poser la question, le calcul V1, un contrat d'entrée-sortie proposé, les critères d'une première tranche et ce qui reste à Ivan. **Ce qu'il ne fait pas** : amender ADR-0012, créer un outil MCP, ni promettre quoi que ce soit sur une surface publique.

---

## 1. La question

> *Le service F&B peut-il honorer une demande de cette classe, pour N couverts, à telle heure — et jusqu'à quand peut-on encore s'adapter ?*

Aujourd'hui, le Mesh sait dire qu'une **situation** existe (`fnb.late_service_capacity_pressure`, ADR-0012). Il ne sait pas répondre à une **demande précise**. Les 11 outils MCP annoncés par le manifeste v1 (`backend/app/mcp_core.py`) ne le font pas ; le brief Anima v1 définit « livré » comme *déclaration → claim → recommandation de l'Orchestrateur → action F&B validée par un humain* sans dire qui établit que l'action est faisable ; la première tranche de l'Orchestrateur (Aetherix + Tacet) ne l'exerce pas.

## 2. Cadre non négociable

| Règle | Source |
|---|---|
| Lecture seule, outil **atomique** ; aucune orchestration dans un outil MCP | ADR-0001, ADR-0004 D1 / D4 |
| Aetherix **informe**, l'Orchestrateur **décide** ; une réponse n'est pas un champ actionnable pour un autre nœud | ADR-0004 D5, ADR-0012 |
| Namespace `fnb.*`, propriété d'Aetherix | ADR-0012 D1 |
| **Une réponse n'est pas une promesse** : retenir une table ou une commande est une action, jamais autonome | Décision #6, ADR-0013 |
| PMS en lecture seule | Décision #7 |
| **Aucune identité de guest, aucune donnée de santé** dans la requête : un allergène rattaché à un guest est une donnée de santé | Décision #20, DPIA |
| Les règles sont celles **de l'hôtel** (ratios, équipe habituelle, décalages d'engagement) ; un défaut est étiqueté comme tel | Décisions #40, #43 |
| Livrer par les outils de l'hôtel, y compris son propre agent | Décision #44 |
| Dégrader plutôt que bloquer ; toute sortie d'un garde-fou porte une raison typée | ADR-0009, ADR-0007 D6 (`AgentAbstention`) |
| Étiquetage honnête : **Design** aujourd'hui, **Synthetic PoC** après une première tranche, jamais « Built » sans preuve | Décision #33 |

## 3. Ce qui existe — et ce qui manque

**Existe (vérifié dans le code le 08/11/2026)**
- Places et rotations par service (profil restaurant), utilisées par `staffing_service` pour borner les couverts livrés.
- Ratios de l'hôtel par rôle (`covers_per_server`, `covers_per_host`, `covers_per_kitchen`…), équipe habituelle (`usual_*`), `max_extra_staff`, `max_staff_reduction`, décalages d'engagement par classe de tâche (`commit_offset_hours.*`, hôtel-réglables ; défauts 24 h ajout d'effectif, 72 h réduction, 4 h préparation, ADR-0007 §18.1).
- Prévision de couverts et probabilité de manque `P(D > capacité)` avec intervalle recalibré (ADR-0007 §18.2 et §18.4).
- Garde-fou à deux paliers et abstention typée (`forecast_guardrail.py`, `AgentAbstention`).

**Manque**
- Tout outil, schéma ou contrat qui réponde à une demande précise.
- **Une source d'historique de couverts réels.** `analyse-critique-2026-07.md` (maillon 1) : Apaleo ne fournit pas les couverts restaurant ; tout repose sur l'historique POS (Phase 4, non construit) ou sur un taux de captation « jamais validé ». *Le côté capacité n'a pas besoin du POS ; le côté demande, si.*
- Une source de **réservations de table** (décision ouverte distincte, couplée à celle-ci).
- Le niveau article, le stock et le débit de cuisine (POS, Epic 13 repris sous la Décision #45, données synthétiques).
- Une calibration **réalisée** : l'intervalle n'est recalibré que sur données synthétiques, et le prévisionniste qui pilote les recommandations émises n'a aucune calibration (ADR-0007 §18.6).

## 4. Le calcul V1

**Capacité effective à l'instant de la demande**
- `C_places` = places × rotations possibles du service.
- `C_équipe` = capacité de l'équipe en place : pour chaque rôle, `covers_per_rôle × effectif_rôle` ; **le rôle le plus contraignant borne** (souvent la cuisine ou la salle).
- `effectif_rôle` = équipe habituelle, **plus** les extras possibles (jusqu'à `max_extra_staff`) **seulement si** le délai restant avant le service dépasse le décalage d'engagement `staffing.add`. Après, seule l'équipe en place compte.
- `C_eff = min(C_places, C_équipe)`. La contrainte qui borne (`places`, `équipe`, `préparation`) est retournée.

**Demande attendue**
- On part de la prévision de couverts totale (distribution recalibrée si elle existe).
- **Marge** = `C_eff − (demande attendue + demande de la requête)`, lue à un quantile, pas sur la moyenne.

**La demande non réservée, et le « taux de captation »**
La demande qui n'est pas dans les réservations se décompose en : *réservations tardives attendues* (pickup) + *passages extérieurs* (walk-ins) + *clients de l'hôtel non réservés*. Ces derniers valent à peu près `chambres occupées × couverts par chambre et par service × (1 − part déjà réservée)`. Le « taux de captation » est donc l'un des facteurs, **pas la somme**, et l'occupation y entre par les chambres occupées.

⚠️ **Piège de nomenclature : « captation » a trois sens dans le dépôt.**
1. `CaptationBaseline` / `captation_service.py` : **revenu F&B par chambre vendue** (ratios par jour de semaine et par mois). Ce n'est pas une part de guests.
2. `DEFAULT_CAPTATION_RATE = 0.7` (`config.py`) : fraction de la **demande excédentaire** que l'établissement capte quand il est pleinement staffé (chemin des anomalies).
3. `capture_rate` de `manager_decision.py` : **décisions écrites ÷ réponses qui cherchent une décision**. Sans rapport avec la demande.

Pour la faisabilité il faut un quatrième objet, en **couverts par chambre occupée et par service**, qui n'existe pas ; le convertir depuis un revenu exigerait une dépense moyenne par couvert, aujourd'hui un placeholder (`DEFAULT_AVG_SPEND_PER_COVER`, cf. la décision ouverte « ROI gate »). Ce brief nomme cet objet `covers_per_occupied_room` ; **à rapprocher d'un glossaire** (§8).

**La décomposition n'est pas nécessaire au calcul de base** : comparer la capacité à un quantile de la demande **totale** suffit. Elle devient utile quand le service approche : la part réservée se connaît, l'incertitude ne porte plus que sur le reste. C'est le couplage avec la décision « réservations de table ».

**Verdicts** : `feasible | at_risk | not_feasible | indeterminate`. Les seuils (probabilité de manque tolérée) sont **fixés avant toute donnée** (esprit HOS-316), bornés, réglables par l'hôtel ; sans calibration réalisée, **aucune probabilité n'est affichée** : le verdict porte une étiquette de provenance.

## 5. Contrat proposé (à valider, pas une spec)

**Entrée** (liste fermée, aucun texte libre, tout champ inconnu est refusé)
```json
{
  "request_class": "group | preorder | early_service | late_service | special_prep | breakfast_extra",
  "service": "breakfast | lunch | dinner",
  "service_date": "2026-11-12",
  "service_time": "19:30",
  "party_size": 12,
  "restricted_prep": false
}
```

**Sortie**
```json
{
  "verdict": "feasible | at_risk | not_feasible | indeterminate",
  "binding_constraint": "seats | staff | prep_time | none",
  "adaptable_until": "2026-11-11T19:30:00Z",
  "headroom_covers": { "q50": 9, "q90": 3 },
  "uncertainty": { "status": "uncalibrated | synthetic-calibrated | realised-calibrated" },
  "assumptions": [{ "param": "covers_per_server", "value": 18, "set_by": "hotel | default" }],
  "reasons": ["typed_reason_code"],
  "as_of": "2026-11-10T08:00:00Z",
  "expires_at": "2026-11-10T12:00:00Z",
  "is_commitment": false
}
```
`headroom_covers` n'apparaît que si `uncertainty.status` ≠ `uncalibrated`. `restricted_prep` est un booléen **de classe** : jamais rattaché à une personne, jamais un type d'allergène. La charge utile de la requête n'est pas journalisée au-delà de la classe, de la taille et du créneau.

## 6. Ce que ce n'est pas

- **Pas un moteur de réservation.** Tables × créneaux contre des réservations déclarées restent l'autorité de l'outil de réservation ; l'outil le **consomme** quand il est connecté et dégrade sinon. *Non vérifié* : si Zenchef, CoverManager ou un autre font déjà du pacing selon la cuisine ou le staff.
- **Pas une promesse.** Retenir, réserver, confirmer : actions humaines (ADR-0013).
- **Pas une requête sur un guest.**

## 7. Première tranche proposée — **Synthetic PoC**, à valider

| # | Critère | Vérification |
|---|---|---|
| AC1 | Un outil MCP **en lecture seule**, atomique, scope à définir ; aucun chemin d'écriture | test de surface |
| AC2 | Sortie **déterministe** à entrées égales ; raison typée sur chaque verdict | tests purs |
| AC3 | La capacité n'utilise que des paramètres de l'hôtel ou des **défauts étiquetés** (`set_by`) ; jamais de défaut silencieux | test |
| AC4 | Le verdict **change de part et d'autre du décalage d'engagement** ; `adaptable_until` cohérent | scénario dédié |
| AC5 | Aucune probabilité sans provenance de calibration | test |
| AC6 | Tout champ d'identité ou de texte libre est **refusé** | test |
| AC7 | Prévision ou paramètres manquants : `indeterminate` + raison typée, pas une erreur | scénario de dégradation |
| AC8 | Données **synthétiques** déclarées dans le code et la sortie ; étiquette Synthetic PoC, jamais Built | vérification |

**Évaluation par conception** : bras A = au moins 10 scénarios construits (marge large ; places bornantes ; équipe bornante avec extras possibles avant l'engagement ; après l'engagement ; ratios par défaut ; prévision absente ; garde-fou palier 2 ; identité refusée ; non calibré ; déterminisme), seuils écrits avant ; bras B = raisons typées ; **bras C = résultat réel** (pour les demandes acceptées par un humain, le service a-t-il tenu, a-t-il fallu un extra ?) : **impossible avant des données réelles**, à dire.

**Formulation publique.** Autorisée : *« une requête de faisabilité en lecture seule est conçue pour l'Orchestrateur (Design) »*. Interdites : *« Aetherix dit si la cuisine peut dire oui »*, *« intégré aux outils de réservation »*, toute probabilité de faisabilité.

## 8. À trancher par Ivan

1. **V1 sans POS ?** Capacité depuis les paramètres de l'hôtel, demande depuis la prévision ; l'historique de couverts reste le maillon faible (§3).
2. **Premier consommateur** : l'Orchestrateur (actions issues d'Anima) ou l'agent propre de l'hôtel (Décision #44) ?
3. **Branchement à la première tranche de l'Orchestrateur** : son AC1 exige « un outil d'Aetherix » ; cet outil pourrait être celui-ci plutôt qu'une prévision générique. Non décidé : cela élargit la tranche.
4. **Réservations de table d'abord ?** (décision ouverte couplée).
5. **Glossaire « captation »** (§4) : trois sens, un quatrième à créer ; renommer ou documenter dans `data-conventions.md` ?
6. **Seuils** de probabilité de manque tolérée, à fixer avant toute donnée.

## 9. À lire

[`ADR-0012`](../adr/0012-mesh-signal-contract.md) · [`ADR-0004`](../adr/0004-orchestrator-separation.md) · [`ADR-0007`](../adr/0007-evaluation-by-design.md) §18 · [`ADR-0013`](../adr/0013-decision-autonomy-policy.md) · [`anima-v1-brief.md`](anima-v1-brief.md) · [`orchestrator-v1-brief.md`](orchestrator-v1-brief.md) · [`analyse-critique-2026-07.md`](analyse-critique-2026-07.md) · `backend/app/services/hotel_parameters.py` · `backend/app/services/staffing_service.py`
