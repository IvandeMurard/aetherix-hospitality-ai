# Moat — ce qui est défendable, testé contre la menace plateforme (Story 16.13 AC2)

> Acté 09/07/2026. **Réordonné le 10/08/2026** après confrontation au framework Mandal & Sinha
> (Stanford Law, juin 2026, « Defensible Moats for Vertical AI Application Companies ») et à la
> veille du 10/08 (`Veille/Veille_Tech_Stack.md` §AUG 10). Complète `positionnement-wedge.md` :
> le wedge dit *comment on entre*, ce doc dit *pourquoi on reste*.
> À relire après le pilote (HOS-176) et les interviews (HOS-309).

## Le moat n'est pas le modèle

Le benchmark Recruit (HOS-307) l'a établi noir sur blanc : Prophet égale la baseline naïve sur le
jour médian. **Le modèle de forecast n'est pas défendable** — un concurrent le réentraîne en une
semaine, un PMS le bundle gratuitement demain. Toute thèse de moat qui repose sur « notre IA
prédit mieux » est morte à l'arrivée.

Constat du 10/08 : un app listé sur l'Apaleo Store (Ovimore) vend désormais du « forecasting »
dont le mécanisme *est* la comparaison N-1 — la baseline elle-même expédiée comme produit.
La commoditisation n'est plus une hypothèse, elle est observable.

## Ce qui est défendable, du plus solide au moins solide

Ordre revu le 10/08. L'ordre précédent menait avec la mémoire ; il est renversé parce que la
mémoire est la couche la plus facilement égalable des quatre (voir §Ce qui a cessé d'être un
différenciateur).

1. **La boucle act-and-measure, et surtout la capture des overrides manager** (Décision #26-D5).
   Seul acteur qui *agit* (recommande) + *capture* (l'outcome réel) + *attribue* (l'écart, nommé)
   + *recalibre*. Qui n'a pas les quatre n'apprend pas — il prédit dans le vide.
   **C'est le sommet du moat, pas la mémoire.** Enregistrer qui override quoi, quand, et qui avait
   raison, c'est observer les décisions des meilleurs praticiens du métier — le mécanisme que
   Mandal & Sinha classent au niveau le plus élevé de leur hiérarchie, celui qui compose avec
   l'usage. Spécifié en D4/HOS-246 (triple `context-features, action, propensity, outcome`),
   **pas encore instrumenté** : c'est la couche à protéger et à livrer en priorité.
2. **La conformité câblée dans le produit.** Guardrails runtime avec raison typée (NFR2,
   Décision #27), eval-gate bloquant en CI (Décision #29), audit différentiel clos (Décision #30),
   DPIA et ses 13 mesures (Décision #20), gate honnêteté métriques et sa taxonomie (Décision #33),
   lignes rouges AI Act nommées. **Ce corpus a toujours été traité en interne comme un coût — gel,
   NO-GO, dette — jamais comme un actif.** C'est une erreur de lecture : Mandal & Sinha classent
   la conformité intégrée au-dessus de la mémoire d'agent, avec le tier « strict liability »
   (RGPD, catégories interdites/haut risque de l'AI Act) comme le plus profond, précisément parce
   qu'une fois la conformité câblée dans la supervision et l'archivage, changer de fournisseur
   oblige à tout revalider. Signal de marché convergent : sur l'Apaleo Store de juillet, un
   produit de conformité pure (Delta ID) est vendu comme produit.
3. **La mémoire opérationnelle par propriété.** Ce que *ce* restaurant fait quand il pleut pendant
   un salon. Elle se compose dans le temps : 8 mois d'outcomes capturés ne se copient pas, ils se
   vivent. **Précision indispensable depuis le 10/08 : le moat n'est pas la capacité de mémoire,
   c'est le corpus.** La capacité est devenue une brique d'infrastructure gratuite (Mem0, Zep,
   Letta, Oracle). Ce qui n'est pas copiable, c'est *de quoi* la mémoire est faite — des outcomes
   d'un métier capturés au point de décision — et le temps qu'il faut pour l'accumuler.
4. **L'agnosticisme PMS** (schéma canonique, Décision #28). La mémoire vit *au-dessus* d'Apaleo ET
   de Mews, pas dedans. Un groupe multi-PMS a une seule mémoire ; un PMS natif ne verra jamais que
   ses propres propriétés. **Couche moyenne, et à ne plus adosser à l'argument MCP-native**
   (voir ci-dessous).
5. **L'effet réseau multi-propriété** (Hive prior, Phase 4 — *pas encore shippé*). Un nouvel hôtel
   démarre avec les priors de propriétés similaires. Cette couche est une promesse, pas une preuve :
   ne pas la vendre comme acquise.

## Ce qui a cessé d'être un différenciateur (constaté le 10/08)

Trois arguments portés par le récit externe se sont banalisés le même jour, indépendamment.
Ils restent vrais et nécessaires — ils ne séparent plus.

| Argument | Ce qui l'a banalisé | Statut |
|---|---|---|
| « Système de mémoire opérationnelle » | Mem0, Zep, Letta, Oracle — catégorie d'infrastructure financée, plusieurs implémentations de niveau production dont des gratuites | **Prérequis.** À qualifier systématiquement : ce qui compte est le corpus, pas la capacité |
| « MCP-native, appelable par leur écosystème » (Décision #21) | Le serveur MCP Apaleo est passé en disponibilité générale, public et documenté, en juillet 2026 | **Prérequis.** Ne plus le présenter comme un avantage : c'est le ticket d'entrée |
| Human-in-the-loop explicite (Décision #6) | Trois occurrences indépendantes en trois semaines : FinSuite AI (20/07), Zaplar et BE-A (10/08), toutes avec approbation avant action | **Norme de catégorie.** À garder comme prérequis correctement implémenté, pas comme séparateur |

**Conséquence de discipline** : ne jamais ouvrir un pitch, un case study ou un entretien sur l'un
de ces trois. Ils se mentionnent en second rideau, comme hygiène acquise.

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
- **Ne jamais mener non plus avec la mémoire, le MCP-native ou le human-in-the-loop** — les trois
  sont devenus des prérequis (§Ce qui a cessé d'être un différenciateur). Mener avec la boucle
  et la conformité.
- Garder la boucle *fermée* : un forecast sans capture d'outcome nous ramène au rang de wrapper.
- **Livrer la capture des overrides manager** (D4/HOS-246). C'est la couche 1 et elle n'est pas
  encore instrumentée : le moat le plus haut est aujourd'hui revendiqué sur du spécifié, pas du
  livré. Tant que c'est le cas, le dire tel quel.
- Rester PMS-agnostic : le jour où on devient dépendant d'un seul PMS, on perd la couche 4.
- Livrer la profondeur verticale qu'une plateforme ne fera pas (droit du travail, capture rates,
  rituel de confiance) — c'est le fossé qui reste quand la commodité tombe à zéro.

Voir aussi : [`positionnement-wedge.md`](positionnement-wedge.md) · [`concurrence.md`](../competitive/concurrence.md) (analyse frontale) · Décisions #26, #28, #21.
