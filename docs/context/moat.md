# Moat — ce qui est défendable, testé contre la menace plateforme (Story 16.13 AC2)

> Acté 09/07/2026. Complète `positionnement-wedge.md` : le wedge dit *comment on entre*, ce doc
> dit *pourquoi on reste*. À relire après le pilote (HOS-176) et les interviews (HOS-309).

## Le moat n'est pas le modèle

Le benchmark Recruit (HOS-307) l'a établi noir sur blanc : Prophet égale la baseline naïve sur le
jour médian. **Le modèle de forecast n'est pas défendable** — un concurrent le réentraîne en une
semaine, un PMS le bundle gratuitement demain. Toute thèse de moat qui repose sur « notre IA
prédit mieux » est morte à l'arrivée.

Ce qui est défendable se situe autour de la prédiction, en quatre couches qui se renforcent :

1. **La mémoire opérationnelle par propriété.** Ce que *ce* restaurant fait quand il pleut pendant
   un salon, quel manager override quelles recommandations et qui a raison. Elle se compose dans le
   temps : 8 mois d'outcomes capturés ne se copient pas, ils se vivent. C'est un actif cumulatif,
   pas une feature.
2. **La position dans la boucle act-and-measure** (Décision #26-D5). Seul acteur qui *agit*
   (recommande) + *capture* (l'outcome réel) + *attribue* (l'écart, nommé) + *recalibre*. Qui n'a
   pas les quatre n'apprend pas — il prédit dans le vide.
   > **État au 11/08/2026** — `Built`, 0 utilisateur réel (taxonomie `status-taxonomy.md`). Le
   > Decision Ledger (HOS-317, Done 01/08) relie contexte → reco → réponse manager → outcome mesuré
   > → abstention typée. Manque le leg **trace d'émission** (`policy_id` + entrées de sélection +
   > confiance/tier), seul leg non reconstructible après coup : HOS-326, S3, précondition dure du
   > go-live (`docs/planning/phase-3-sprint-plan.md` §Amendement 11/08). Le corpus lui-même ne
   > commence qu'au premier override d'un manager réel, c'est-à-dire à HOS-176.
3. **L'agnosticisme PMS** (schéma canonique, Décision #28). La mémoire vit *au-dessus* d'Apaleo ET
   de Mews, pas dedans. Un groupe multi-PMS a une seule mémoire ; un PMS natif ne verra jamais que
   ses propres propriétés.
4. **L'effet réseau multi-propriété** (Hive prior, Phase 4 — *pas encore shippé*). Un nouvel hôtel
   démarre avec les priors de propriétés similaires. Cette couche est une promesse, pas une preuve :
   ne pas la vendre comme acquise.

## Stress test : « et si Apaleo ou Mews shippent un forecast F&B natif ? »

C'est la question qui tue, posée en entretien comme en due diligence. Réponse honnête, en trois temps.

**Ce qu'ils ont, et qu'on n'a pas.** La donnée (réservations, occupancy) à la source. La
distribution (ils sont déjà installés). La confiance (le contrat PMS existe). S'ils décident de
faire du forecast F&B « good enough » gratuit, **la couche commodité s'érode — et c'est très bien,
parce qu'on ne mène pas avec elle.**

**Pourquoi ce n'est pas leur jeu.** Le F&B est une part mince du revenu d'un PMS (l'hébergement
domine) ; un forecast est une *feature* d'un module, pas un produit avec une boucle d'apprentissage
instrumentée. Un PMS est horizontal par construction — **c'est l'hypothèse la plus porteuse de ce
document, et elle est falsifiable** (voir encadré) : il ne descendra pas dans la profondeur
opérationnelle F&B (staffing calibré au droit du travail français, capture rates spécifiques,
recalibration hebdomadaire sur outcomes, guardrails typés anti-empoisonnement). Ce sont des
acteurs de plateforme ; la profondeur verticale est précisément ce qu'ils délèguent à leur
marketplace.

> **Ce qui rendrait ce paragraphe faux** — c'est une hypothèse concurrentielle, pas un fait acquis,
> et elle est la plus porteuse du document. Trois signaux la réfuteraient : (1) Apaleo Copilot
> étend son scope au F&B opérationnel (staffing, capture rate) plutôt qu'au reporting — c'est
> exactement la décision ouverte sous surveillance mensuelle, `open-decisions.md` §Apaleo Copilot ;
> (2) un PMS ship une boucle outcome-capture instrumentée, pas seulement une prédiction ;
> (3) un acteur de marketplace F&B lève et intègre verticalement vers le PMS. Le canari existe et
> tourne : ce paragraphe se relit à chaque revue de watchlist, il ne se cite pas comme établi.

**Notre réponse structurelle : être la couche d'intelligence, pas un PMS concurrent.** MCP-native
signifie qu'on est *appelable* par leur écosystème (Décision #21, convention native Apaleo). « Glue,
not replacement » : on ne remplace pas le PMS, on branche une mémoire opérationnelle par-dessus,
cross-PMS. Le scénario où Apaleo ship un forecast natif n'est pas un scénario de mort — c'est un
scénario de *partenariat* : ils fournissent la donnée et la commodité, on fournit la boucle et la
mémoire qu'ils ne construiront pas.

## Le risque résiduel, nommé

Si un PMS bundle un forecast F&B *plus* une capture d'outcomes *plus* une mémoire par propriété
*plus* la profondeur staffing — c'est-à-dire s'il décide de construire exactement notre boucle —
le moat des couches 1-2 s'érode aussi. C'est improbable (ce n'est ni leur focus ni leur culture
produit) mais pas impossible. La parade n'est pas technique, elle est temporelle : **arriver au
pilote et accumuler de la mémoire réelle avant qu'ils n'y pensent.** Le moat se construit en
étant déployé, pas en étant architecturé. D'où la priorité absolue du plan 90j : la preuve
terrain, pas plus d'architecture.

## Ce qui doit rester vrai

- Ne jamais mener le récit avec l'accuracy du forecast (couche commodité).
- Garder la boucle *fermée* : un forecast sans capture d'outcome nous ramène au rang de wrapper.
- Rester PMS-agnostic : le jour où on devient dépendant d'un seul PMS, on perd la couche 3.
- Livrer la profondeur verticale qu'une plateforme ne fera pas (droit du travail, capture rates,
  rituel de confiance) — c'est le fossé qui reste quand la commodité tombe à zéro.

Voir aussi : [`positionnement-wedge.md`](positionnement-wedge.md) · [`concurrence.md`](../competitive/concurrence.md) (analyse frontale) · Décisions #26, #28, #21.
