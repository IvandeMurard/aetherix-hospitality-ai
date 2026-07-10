# Concurrence frontale F&B forecasting & staffing — pourquoi le segment hôtel reste ouvert (Story 16.13 AC3)

> Acté 09/07/2026. Analyse de positionnement, pas de dénigrement : ces acteurs sont réels, financés,
> avec de vrais clients. La question n'est pas « sont-ils mauvais ? » mais « pourquoi le F&B *hôtelier*
> reste-t-il un espace ouvert ? ». Chiffres de financement/clients à confirmer via la veille
> (`context/monitoring-watchlist.md`) — ne pas citer sans vérification à jour.

## Les concurrents directs (forecast + staffing restauration)

| Acteur | Cœur de cible | Ce qu'ils font bien | Angle |
|---|---|---|---|
| **Nory** | Groupes de restauration & hospitality (UK/IE), chaînes | Forecast demande + labor scheduling + inventory, produit mûr, vrais déploiements | Le plus proche de nous, mais orienté *chaînes de restaurants*, pas F&B intégré à l'hôtel |
| **Tenzo** (gotenzo.com) | Restaurants, pubs & **hôtels explicitement ciblés** (page "Solutions Hotels" dédiée) — mais confirmé sans occupancy/PMS (07-10) | Analytics + forecast + intégrations POS multiples, dashboards, agrégation multi-outlets (room service/events/restaurant/bar/minibar) | BI-first (on regarde des tableaux de bord), pas push-first agentique — cible commercialement l'hôtel, mais reste sans le signal occupancy qui définit raison n°1 |
| **5-Out** | Restaurants indépendants & petits groupes | Forecast ventes/labor, prédiction quasi temps réel, intégrations POS | Forecast-led, restaurant standalone, pas de contexte hôtelier |
| **Avero** | F&B hôtelier & restauration | Analytics F&B établies, ancrage hôtelier réel, base installée | Le plus proche côté *hôtel*, mais analytics/reporting rétrospectif, pas agent prédictif à boucle fermée |

## Pourquoi le F&B hôtelier reste un espace ouvert

Quatre raisons structurelles, pas conjoncturelles :

1. **Ils sont construits pour le restaurant, pas pour l'hôtel.** Nory, Tenzo, 5-Out partent du POS
   du restaurant. Le F&B hôtelier a un signal qu'ils ne modélisent pas : **l'occupancy et le capture
   rate** (quelle part des clients de l'hôtel dînent sur place). C'est le régresseur le plus prédictif
   du couvert hôtelier, et il vit dans le PMS, pas dans le POS. Aetherix part de là (Décision #11,
   adapter PMS #28). Avero a l'ancrage hôtelier mais reste sur l'analytics rétrospectif.

2. **BI-first vs agent push-first.** La plupart livrent un dashboard. Le pari d'Aetherix (et la
   thèse anti-fatigue, ADR-0009 G-4) est qu'un manager F&B hôtelier n'ouvrira pas un tableau de bord
   de plus : la valeur arrive dans WhatsApp, là où il est déjà, et l'agent ne sollicite que quand ça
   compte. C'est une différence de *surface produit*, pas de modèle.

3. **Forecast-led vs memory-led.** Ils vendent la prédiction (couche commodité, cf. `moat.md`).
   Aucun, à notre connaissance, ne construit la boucle *fermée* instrumentée — capture d'outcome,
   auto-report de l'écart, recalibration, guardrails typés — comme cœur de produit. C'est le
   différenciateur défendable.

4. **Ni MCP-native, ni pensés pour le mesh.** Aucun ne s'expose comme outils appelables par un
   orchestrateur agentique cross-domaine (F&B + environnement + guest). C'est un pari sur la
   direction de l'écosystème (agents + MCP), pas une supériorité acquise aujourd'hui.

## Où ils sont devant — à dire honnêtement

- **Ils ont de vrais clients et du vrai revenu.** Aetherix a zéro propriété en production. C'est
  l'asymétrie n°1, et aucun argument d'architecture ne la compense : elle se comble par le pilote
  (HOS-176), pas par un doc.
- **Produit mûr, intégrations POS multiples, équipes.** Nory en particulier a une profondeur
  produit et une base que ce projet solo n'a pas.
- **Ils ont validé que le marché paie** pour du forecast + labor. C'est une bonne nouvelle (le
  besoin est prouvé), mais ça veut dire que la commodité a déjà des acheteurs établis.

## Ce qui ferait tomber l'analyse (à surveiller)

- Un des acteurs ci-dessus **shippe une intégration PMS profonde + capture rate hôtelier** → notre
  raison n°1 s'érode. À monitorer (watchlist). **Tenzo vérifié 07-10 : cible bien l'hôtel commercialement
  mais son offre `/solutions-hotels/` reste de l'agrégation multi-outlets sans occupancy ni PMS — le
  trigger n'est pas déclenché.** Cf. `nory-tenzo-5out-analysis.md` et watchlist W15.
- Un acteur passe **push-first agentique + boucle fermée instrumentée** → la raison n°2-3 s'érode.
- Un PMS (Apaleo/Mews) internalise le F&B → scénario traité dans [`../context/moat.md`](../context/moat.md).

## Verdict

Le segment F&B *hôtelier* reste ouvert parce que les acteurs forts sont *restaurant-first* et
*BI-first*, et parce que personne ne semble construire la mémoire opérationnelle à boucle fermée
comme produit. Mais « ouvert » n'est pas « gagné » : la seule chose qui transforme cette analyse
en avantage est une propriété réelle en pilote, avec de la mémoire qui se compose. Sans ça, c'est
une thèse, pas une position.

Voir aussi : [`../context/moat.md`](../context/moat.md) · [`../context/positionnement-wedge.md`](../context/positionnement-wedge.md) · veille `../context/monitoring-watchlist.md`.
