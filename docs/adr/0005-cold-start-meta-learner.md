# ADR 0005 — Cold-start meta-learner : cohort prior Prophet pour propriété sans historique

> **Status**: Accepted (décision) · **Date de décision**: 2026-05-28 · **Date de rédaction**: 2026-07-27
> **Phase**: 3 (Pilot Validation) — HOS-174 Track B
> **Implémente**: Décision architecturale #2 (mémoire 2 couches, Hive)
> **Étend**: ADR 0002 (memory instrumentation)
> **Étendu par**: ADR 0006 §D4 (features cohort v2 enrichies POS) · ADR 0009 (runtime guardrails — généralisation du principe de dégradation)
> **Rédaction rétroactive** : cet ADR consigne une décision prise le 28/05/2026 et archivée dans `docs/context/open-decisions.md` §Resolved. Il n'introduit aucune décision nouvelle. Le numéro 0005 était réservé mais le fichier n'avait jamais été écrit, alors que `backend/app/core/config.py` et `backend/app/services/forecast_guardrail.py` le citent comme référence normative pour du code livré — gap détecté par l'agent d'hygiène architecturale (HOS-320, détecteur D2). L'écriture d'un ADR consignant l'existant ne relève pas du gel NFR2 de l'Epic 16, qui vise les décisions **nouvelles**.

---

## 0. Statut d'implémentation (taxonomie HOS-318)

Distinction indispensable : **la décision est actée, l'essentiel de son implémentation ne l'est pas.**

| Élément | Statut | Preuve |
|---|---|---|
| Principe « dégrader, ne pas éteindre » | **Built** | `backend/app/services/forecast_guardrail.py`, `backend/app/core/config.py` (`FORECAST_CONFIDENCE_WARN`, `FORECAST_MAPE_CATASTROPHE`) |
| Raison typée `cold_start_meta_learner_drift` | **Built** | `forecast_guardrail.py` (`REASON_TIER2`), couverte par le golden dataset |
| Gate auto-disable Day-7 MAPE > 25 % | **Built** (généralisé) | Epic 12 G-4 / HOS-251 — plafond porté à 35 % au dispatch |
| Table `hotel_cohort_features` | **Design** — non implémentée | aucune migration, aucune référence en code |
| MCP tool `query_cohort_prior` | **Design** — non implémenté | aucune référence en code |
| Cohort matching hybride + blending BMA | **Design** — non implémenté | — |
| Validation LOO sur 5 propriétés sandbox | **Non réalisée** | — |

⚠️ `docs/adr/0006-pos-integration.md` §1.2 énonce que « ADR-0005 repose sur `hotel_cohort_features` » au présent. La table n'existe pas : ADR-0006 §D4 construit sur un socle **conçu mais non bâti**. À relire avant tout démarrage Phase 4 POS.

---

## 1. Contexte

### 1.1 Le problème

Prophet a besoin d'historique. Une propriété nouvellement onboardée n'en a pas : les premières semaines, le forecast est soit impossible, soit si peu fiable qu'il détruirait la confiance du manager au moment précis où elle se construit.

C'est le moment le plus fragile du cycle de vie produit. Un chiffre absurde en semaine 1 coûte durablement plus cher qu'une absence de chiffre.

### 1.2 L'arbitrage d'origine

HOS-174 Track B portait initialement *« LLM persona generation »* — générer un profil de propriété synthétique par LLM pour amorcer le modèle. Cette option a été **écartée** le 28/05/2026 au profit d'un **cold-start meta-learner** : dériver un prior depuis des propriétés réellement comparables déjà présentes dans la Hive, plutôt que depuis une fiction générée.

Rationale : un prior tiré de données réelles est auditable et se calibre ; un persona LLM ne l'est pas. Cohérent avec Décision #1 (explainability) et Décision #2 (Hive comme actif). LLM persona déplacé Phase 4, jamais repris.

---

## 2. Décision

**D1 — Cohort matching hybride.** Apparier la nouvelle propriété à une cohorte par règles dures (capacité, segment, marché) *puis* similarité cosinus sur embedding. Ni l'un ni l'autre seul : les règles dures seules produisent des cohortes trop larges, l'embedding seul apparie des propriétés incomparables sur des critères non métier.

**D2 — Prior injecté via Prophet, pas en post-traitement.** Le prior cohorte entre par `add_seasonality` + hyperparamètres calibrés, dans le modèle. Un ajustement après coup serait invisible aux intervalles de confiance et casserait l'explicabilité de la prédiction.

**D3 — Blending par Bayesian model averaging.** Poids du prior décroissant à mesure que l'historique propre s'accumule : `n_eff_prior=30`, **coupure dure à J+90**. Passé ce seuil la propriété est autonome — le prior ne doit jamais devenir une béquille permanente qui masque un modèle local défaillant.

**D4 — Support de données : table `hotel_cohort_features`, opt-in tenant.** Coefficients Prophet agrégés et hyperparamètres calibrés uniquement. **Aucune donnée brute d'une propriété n'en traverse une autre** — c'est la frontière de souveraineté qui rend la Hive acceptable commercialement (Décision #2).

**D5 — Exposition via MCP : `query_cohort_prior`.** Tool atomique, cohérent avec ADR-0001 (le MCP Server n'expose que des tools atomiques, jamais d'orchestration).

**D6 — Gate runtime : auto-disable si Day-7 MAPE > 25 %.** Et surtout : **dégrader, ne pas éteindre.** Le forecast n'est jamais coupé — il retombe sur une baseline plus simple, explicitement étiquetée comme telle. Corollaire direct de Décision #6 (human-in-the-loop toujours) : un manager face à un écran vide n'a aucune information ; face à un chiffre étiqueté « baseline dégradée », il en a une.

**D7 — Validation pré-pilote : leave-one-out sur 5 propriétés sandbox.** Non réalisée à ce jour.

---

## 3. Portée réelle : ce que cette décision a produit

C'est **D6 qui a essaimé**, pas le meta-learner.

Le principe « dégrader, ne pas éteindre » a été généralisé par Epic 12 G-4 (HOS-251) à tout le chemin de dispatch, bien au-delà du cold-start :

* **Tier 1** — confiance < `FORECAST_CONFIDENCE_WARN` (0.6) : la recommandation part quand même, assortie d'une réserve de confiance.
* **Tier 2** — confiance < `FORECAST_CONFIDENCE_CATASTROPHE` (0.4) *ou* MAPE glissant > `FORECAST_MAPE_CATASTROPHE` (35 %) : repli sur baseline simple, étiquetée, recommandation toujours délivrée.

Le seuil de 35 % au dispatch est explicitement calibré « bien au-delà » du plafond cold-start de 25 % — les deux gates sont concentriques, pas concurrents.

La raison typée `cold_start_meta_learner_drift` (`REASON_TIER2` dans `forecast_guardrail.py`) est le vestige nominatif de cette filiation : le tier catastrophe réutilise la raison cold-start parce que c'est la même sémantique de dégradation.

**Autrement dit** : la partie de l'ADR-0005 réellement en production est son principe de sûreté, pas son mécanisme d'apprentissage.

---

## 4. Alternatives écartées

| Alternative | Raison du rejet |
|---|---|
| LLM persona generation | Non auditable, non calibrable — contradiction avec Décision #1. Déplacée Phase 4, jamais reprise. |
| Pas de forecast avant J+90 | Détruit la valeur perçue pendant la fenêtre d'onboarding, là où l'adoption se joue. |
| Prior en post-traitement | Invisible aux intervalles de confiance, casse l'explicabilité. |
| Partage de données brutes entre propriétés | Rédhibitoire commercialement et juridiquement. La frontière « coefficients agrégés uniquement » est non négociable. |

---

## 5. Conséquences

**Positives** — une propriété neuve reçoit un forecast dès J+1 ; la Hive gagne une valeur d'usage concrète au-delà du discours ; le principe de dégradation est devenu un invariant transverse (ADR-0009, NFR2).

**Négatives / dettes ouvertes**

1. **Le meta-learner n'est pas construit.** ADR-0006 §D4 planifie déjà une v2 POS-enrichie d'une table qui n'existe pas.
2. **La validation LOO n'a pas eu lieu.** La qualité du prior cohorte n'est étayée par aucune mesure.
3. **`n_eff_prior=30` et la coupure J+90 ne sont pas calibrés empiriquement** — valeurs de conception, jamais confrontées à des données réelles.
4. Le plancher de k-anonymat de la couche cohorte reste une décision ouverte (`open-decisions.md`).

---

## 6. Décision d'enregistrement

Les points 1 à 3 ci-dessus relèvent des conditions de sortie du gel Epic 16 : ils exigent des **données réelles** (HOS-307/308), pas un nouvel arbitrage d'architecture. Cet ADR ne les rouvre pas — il les nomme pour qu'ils cessent d'être invisibles.

**Ce document consigne, il ne décide pas.** Toute évolution du cold-start meta-learner passe par un ADR distinct, après le pilote.
