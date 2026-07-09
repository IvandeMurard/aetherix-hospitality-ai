# Memory tour — ce que le système sait après 30 jours (HOS-310)

> Étage 2 du « memory tour » (levier de visibilisation n°2, wedge note). Données
> sandbox ; le format des réflexions est celui persisté en production par
> `receipts.persist_actual_covers` → `operational_memory`.

## Le régime appris
- Demande moyenne avant le choc (J1-J14) : 70 couverts/service
- Demande moyenne après le choc (J15+) : 82 couverts/service (+18 %)
- Le modèle recalibré intègre ce nouveau régime : erreur 15.9 % la semaine du choc → 12.3 % ensuite

## Réflexions mémorisées (les 5 écarts les plus instructifs)
- `actual covers 71 vs predicted 89 on 2026-01-09` — APE 25.4 %
- `actual covers 64 vs predicted 48 on 2026-01-20` — APE 25.0 % · post-choc
- `actual covers 84 vs predicted 66 on 2026-01-15` — APE 21.4 % · post-choc
- `actual covers 70 vs predicted 57 on 2026-01-21` — APE 18.6 % · post-choc
- `actual covers 71 vs predicted 58 on 2026-01-27` — APE 18.3 % · post-choc

## Événements systèmes mémorisés
- J10 : outcome quarantainé (export POS à 900 couverts, raison typée `implausible_feedback`) — jamais entré en training
- J17 : dérive auto-détectée (3 sous-estimations consécutives ≥ 10 %) et annoncée au manager
- 5 recalibrations, 29 outcomes capturés

## Ce que le manager a appris au système
- 7 contre-propositions du manager enregistrées (signal d'apprentissage futur : qui a raison, l'agent ou le manager ?)

*C'est cet actif-là — la mémoire par propriété — qui se compose dans le temps. Un concurrent copie le modèle en une semaine ; pas 30 jours d'outcomes capturés.*