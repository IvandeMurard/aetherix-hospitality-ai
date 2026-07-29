# Protocole de preuve pré-enregistré — Epic 16 (HOS-316, Story 16.15)

> **Statut :** GELÉ au commit de ce fichier. Toute modification postérieure passe par §7 (journal d'amendements).
> **Portée prospective :** [HOS-308](https://linear.app/hospitalityagent/issue/HOS-308) (shadow mode restaurant réel) · [HOS-309](https://linear.app/hospitalityagent/issue/HOS-309) (interviews F&B managers) · [HOS-312](https://linear.app/hospitalityagent/issue/HOS-312) (unit economics).
> **Hors garantie :** [HOS-307](https://linear.app/hospitalityagent/issue/HOS-307) — voir §0, la chronologie réelle est consignée telle quelle.
> **Origine :** adversarial review externe (GPT, 20/07/2026), Critical C4 + Finding F3. Amendement de séquençage PM du 21/07/2026.

---

## 0. Ce que ce document garantit — et ce qu'il ne garantit pas

Le risque traité est le **biais de confirmation** : choisir ou ajuster la métrique, la baseline ou le
seuil de succès *après* avoir vu le résultat. Le remède est banal et vérifiable — écrire les règles
avant, et laisser l'horodatage git le prouver.

**Garanti (prospectif).** Pour HOS-308, HOS-309 et HOS-312, ce document est commité **avant** le merge
de toute PR contenant leurs résultats. Le `git log` de ce fichier est la preuve : si le commit de ce
protocole est antérieur au commit des résultats, aucune métrique n'a pu être choisie en connaissance
de cause.

**Non garanti (HOS-307 — dit noir sur blanc).** Le benchmark Recruit a été mergé le **08/07/2026**
(PR #201, `docs/context/mape-benchmark.md`). La story HOS-316 a été créée le **21/07/2026**, soit
13 jours plus tard. Il n'y a **pas eu** de pré-enregistrement pour HOS-307, et ce document n'en
fabrique pas rétroactivement. Prétendre le contraire serait précisément le comportement que ce
protocole existe pour interdire.

Ce qui *peut* être dit de HOS-307, parce que c'est vérifiable dans le fichier de résultats : la
lecture livrée contient déjà son propre contre-argument — Prophet bat la naïve en MAPE moyen
(−6,15 pp) mais **fait jeu égal en médiane** (MdAPE 27,0 % vs 27,6 %), et LightGBM gagne en médiane.
Le résultat n'a pas été survendu malgré l'absence de protocole formel. C'est un point de fait, pas
une garantie procédurale, et il ne doit jamais être présenté comme telle.

---

## 1. Hiérarchie des métriques (AC4)

Une seule confusion à éliminer : **le MAPE n'est pas la métrique de décision produit.**

| Rang | Métrique | Rôle | Ce qu'elle décide |
|---|---|---|---|
| **Décision produit** | **Δ vs baseline naïve à l'horizon utile** | Le forecast apporte-t-il quelque chose qu'un maître d'hôtel expérimenté n'a pas déjà ? | Continuer / pivoter le moteur |
| **Décision produit** | **Taux d'acceptation des recommandations** | Le manager agit-il ? | Continuer / pivoter la surface |
| **Décision produit** | **Marge brute par propriété** | Le modèle économique tient-il ? | Pricing, viabilité |
| Qualité interne | MAPE / MdAPE absolus | Non-régression, santé du modèle | Rien, seul |

Justification (`docs/context/positionnement-wedge.md`, acté 08-09/07/2026) : la couche prédictive est
commoditisée. Un MAPE absolu excellent sur un dataset facile ne prouve rien ; un **écart** tenu face à
la baseline naïve sur l'horizon où une décision se prend, si.

**Corollaire :** aucune communication externe ne mène avec un MAPE absolu. Le MAPE est une exigence
interne de qualité (`CLAUDE.md` §KPI niveau 1), plus un argument de vente.

---

## 2. Baseline gelée

**Baseline de référence : moyenne des 4 derniers mêmes jours de semaine.**

C'est la baseline déjà employée en HOS-307, ce qui rend les résultats comparables d'une story à
l'autre. Elle est choisie parce qu'elle formalise ce que fait réellement un manager expérimenté
sans outil — « les 4 derniers mardis ». Battre une baseline plus faible (moyenne glissante 7 jours,
persistance J-1) ne prouverait rien d'intéressant.

**Comparateur secondaire obligatoire : LightGBM** (global, lags 7-28 + calendrier), configuration
HOS-307. Motif : LightGBM a gagné en médiane sur Recruit. L'omettre d'un benchmark ultérieur
transformerait une comparaison en argumentaire.

**Métrique de comparaison primaire : MdAPE (médiane)**, pas MAPE. Pré-engagement pris en connaissance
du mécanisme mis au jour par HOS-307 : le MAPE moyen est dominé par les jours à très faible
fréquentation (2 couverts réels → 400 % d'APE), ce qui flatte le modèle le plus robuste aux extrêmes
plutôt que le plus juste sur le service typique. Le MAPE reste **rapporté** comme lecture secondaire
de robustesse aux extrêmes, jamais seul.

---

## 3. Horizon de décision — déterminé, pas supposé

L'horizon utile est **ce que HOS-309 mesure**, pas J+1 par convention.

Tension à trancher : Prophet est évalué à J+1, mais les plannings F&B se figent typiquement à
J+7/J+14. Si aucune décision réelle ne bascule à J+1, un MAPE J+1 excellent est un progrès sans
destinataire — et le KPI `labor_cost_variance` repose sur une capacité d'ajustement non validée.

**Séquence imposée :**

1. HOS-309 (interviews) fixe l'horizon de décision **H** = l'horizon auquel le manager peut encore
   changer quelque chose (extras, coupures, commandes).
2. H est consigné en §7 avec sa date, **avant** que les métriques de HOS-308 soient lues à H.
3. Les seuils du §4 s'appliquent à H — pas à l'horizon qui donne le meilleur chiffre.

**Règle anti-cherry-picking :** le rapport de HOS-308 publie la grille **complète** des horizons
J+1 → J+7, quel que soit H. Sélectionner l'horizon après coup en fonction du résultat est exclu ; si
H n'est pas encore connu au moment du backtest, tous les horizons sont rapportés et la lecture
décisionnelle est différée jusqu'à HOS-309.

---

## 4. Seuils chiffrés et règles d'arrêt

Les seuils ci-dessous sont **pré-engagés**. Un résultat sous le seuil est un échec du maillon
concerné, pas une invitation à redéfinir le seuil.

### 4.1 Maillon modèle — HOS-308 (shadow mode restaurant réel)

Métrique de décision : **Δ MdAPE (baseline naïve − Aetherix) à l'horizon H**, sur données réelles.

| Résultat | Verdict | Suite |
|---|---|---|
| Δ ≥ **5,0 pp** | **PASS** | Le moteur forecast tient comme différenciateur ; publiable |
| **2,0 pp** ≤ Δ < 5,0 pp | **ZONE GRISE** | Décision écrite et datée requise avant toute communication ; pas de PASS implicite |
| Δ < **2,0 pp** | **ÉCHEC** | Le forecast n'est pas le produit — pivot obligatoire (§4.5) |

Validité de l'échantillon (à vérifier **avant** de lire le Δ, sinon le résultat est nul) :
- ≥ 12 mois d'historique continu, agrégats journaliers, non-PII (AC1 HOS-308) ;
- protocole de scoring **identique à HOS-307** : origines glissantes espacées de 5 jours (rotation
  des phases de semaine), horizon 7 jours, ≥ 300 points scorés ;
- run déterministe, reproductible via le harness `scripts/ops/benchmark_recruit.py` (discipline
  Décision #29).

Si la validité échoue, le résultat n'est ni PASS ni ÉCHEC : il est **non concluant**, et doit être
rapporté comme tel plutôt que converti en tendance encourageante.

### 4.2 Maillon décisionnel — HOS-309 (interviews ×5)

Métrique de décision : **nombre de managers sur 5 pour qui un forecast fiable à l'horizon H
changerait une décision qu'ils prennent réellement.**

| Résultat | Verdict | Suite |
|---|---|---|
| ≥ **3/5** | **PASS** | Maillon 3 validé, H retenu comme horizon cible produit |
| **2/5** | **ZONE GRISE** | Élargir à 3 interviews supplémentaires avant conclusion |
| ≤ **1/5** | **ÉCHEC** | Le forecast ne rencontre aucune décision — pivot wedge (§4.5) |

Sont également consignés, sans seuil (matière qualitative, entrée de HOS-179 et 16.13) : horizon de
figeage déclaré, leviers d'ajustement disponibles, réaction au Daily Receipt, fourchette de
consentement à payer.

**Contrainte de méthode :** les 5 interviews sont conduites et transcrites **avant** toute
agrégation. Arrêter la série dès que 3 réponses favorables sont obtenues serait un arrêt optionnel —
interdit.

### 4.3 Maillon adoption

Métrique : `recommendation_acceptance_rate`, seuil **≥ 30 %** (aligné sur `CLAUDE.md` §KPI niveau 3,
qui déclenche une alerte sous 30 %). Secondaire : `weekly_operational_usage`.

Mesurable seulement en pilote réel avec instrumentation outcome-capture ([HOS-275](https://linear.app/hospitalityagent/issue/HOS-275), Phase 4). Pré-enregistré
ici pour que le seuil ne soit pas fixé après avoir vu les premiers chiffres d'usage.

### 4.4 Maillon économique — HOS-312 (unit economics)

| Métrique | Seuil pré-engagé |
|---|---|
| Marge brute par propriété à l'échelle 10 propriétés | ≥ **70 %** |
| Coût complet / propriété / mois | ≤ **15 %** du point de prix envisagé |

Sous ces seuils : le modèle économique est le facteur limitant, et HOS-179 (pricing) doit être
tranché avant tout engagement pilote payant. Les trois scénarios de volume (1 / 10 / 50 propriétés)
sont publiés intégralement — y compris le scénario 1 propriété, structurellement défavorable.

> Les deux seuils du §4.4 sont les seuls du document à ne dériver d'aucune mesure ni décision
> antérieure : ils sont posés ici comme pré-engagement raisonnable pour un SaaS B2B early-stage. Ils
> peuvent être révisés — mais uniquement via §7, et **avant** que le calcul HOS-312 soit lu.

### 4.5 Règle de pivot

Un ÉCHEC en §4.1 **ou** §4.2 déclenche, dans les 5 jours ouvrés, une note de pivot écrite :

- §4.1 ÉCHEC → le forecast cesse d'être présenté comme le différenciateur. Options documentées :
  bascule moteur vers LightGBM global (piste déjà identifiée en HOS-307), ou repli assumé sur la
  mémoire opérationnelle + le rituel Daily Receipt comme produit (`positionnement-wedge.md` — c'est
  déjà la thèse ; §4.1 en teste la partie moteur).
- §4.2 ÉCHEC → le wedge lui-même est remis en cause, pas seulement le moteur. Aucune candidature ni
  communication externe ne s'appuie sur la valeur décisionnelle du forecast tant que la note n'est
  pas écrite.

Un ÉCHEC est un résultat livrable. Il se publie.

---

## 5. Règles anti-biais (s'appliquent aux trois stories)

1. **Gel.** Baseline, métrique primaire, seuils et règles d'arrêt sont figés à la date de commit de
   ce fichier. Un amendement postérieur n'est recevable que consigné en §7 **et** daté avant la
   lecture des résultats concernés.
2. **Pas de substitution post-hoc.** La métrique primaire est le Δ MdAPE. Rapporter le MAPE parce
   qu'il est plus flatteur, sans le Δ MdAPE à côté, est une violation du protocole.
3. **Reporting exhaustif.** Toutes les métriques pré-enregistrées sont publiées, y compris celles qui
   échouent, y compris les horizons non retenus.
4. **Passe d'analyse unique.** Un seul run de scoring fait foi. Tout re-run (correction de bug,
   changement de configuration) est consigné en §7 avec son motif — un re-run non consigné qui
   améliore le résultat est indistinguable d'un tuning sur le test set.
5. **Pas d'arrêt optionnel.** L'échantillon (5 interviews, N points scorés) est fixé à l'avance ; on
   n'arrête pas la collecte parce que le résultat courant est satisfaisant.
6. **Déviations déclarées.** Tout écart au protocole est écrit dans le rapport de la story, à côté du
   résultat, pas dans une note de bas de page.

---

## 6. Application par story

| Story | Statut au gel | Couverte par ce protocole | Métrique de décision |
|---|---|---|---|
| [HOS-307](https://linear.app/hospitalityagent/issue/HOS-307) Benchmark Recruit | Done, mergé 08/07/2026 | ❌ **Non** — antérieur (§0) | — (résultat déjà publié, lecture nuancée conservée) |
| [HOS-308](https://linear.app/hospitalityagent/issue/HOS-308) Shadow mode restaurant réel | Backlog | ✅ Oui | Δ MdAPE vs naïve à H (§4.1) |
| [HOS-309](https://linear.app/hospitalityagent/issue/HOS-309) Interviews F&B ×5 | Backlog | ✅ Oui | Managers /5 dont une décision bascule (§4.2) |
| [HOS-312](https://linear.app/hospitalityagent/issue/HOS-312) Unit economics | Backlog | ✅ Oui | Marge brute / propriété (§4.4) |

Articulation avec le reste du dispositif :
- `docs/planning/pilot-readiness-test-plan.md` — capacités agentiques (bras A/B/C, ADR-0007 §13). Ce
  protocole ne s'y substitue pas : il fixe les seuils **produit**, le test plan couvre les qualités
  **système**. Recouvrement assumé sur #6 (anticipation) et #8 (calibration HITL), tous deux Bras C.
- [HOS-318](https://linear.app/hospitalityagent/issue/HOS-318) (gate honnêteté métriques, taxonomie Built / Shadow-mode / Synthetic PoC / Design / Research) — consommateur
  direct de ce document : la taxonomie qualifie *ce qui est prouvé*, ce protocole définit *ce que
  prouver veut dire*.

---

## 7. Journal d'amendements

Toute modification du §2, §3 ou §4 s'inscrit ici avec sa date et son motif. Un amendement postérieur
à la lecture des résultats qu'il affecte est nul et doit être signalé comme tel.

| Date | Amendement | Motif | Antérieur à la lecture des résultats ? |
|---|---|---|---|
| 2026-07-29 | Création — gel initial (§1 à §6) | HOS-316 AC1/AC2/AC4 | ✅ HOS-308, 309, 312 non démarrées |
| — | **H (horizon de décision) = à renseigner** | Sortie de HOS-309 AC4 | À remplir avant lecture de HOS-308 à H |

---

## 8. Vérifier la garantie

```bash
# Date de gel du protocole
git log --follow --format='%aI %h %s' -- docs/planning/protocole-de-preuve.md | tail -1

# Date des résultats — doit être POSTÉRIEURE au gel pour HOS-308/309/312
git log --format='%aI %h %s' -- docs/context/interviews-fnb-2026.md docs/Cost_Model.md
```

Si un fichier de résultats couvert par ce protocole porte un horodatage antérieur au gel, la garantie
de pré-enregistrement ne s'applique pas à lui — et le rapport correspondant doit le dire.
