# Closed-loop demo — rapport (HOS-310)

> Données **sandbox synthétiques** — cette démo prouve la mécanique de la boucle
> (forecast → reco → feedback → réel → recalibration), pas l'accuracy (cf. HOS-307).
> Services réels exercés : PredictionEngine, StaffingService, feedback_guard (G-3).

- **Scénario** : 30 jours · choc de régime +25 % au J15 (nouveau contrat banquets) · export POS corrompu au J10 (900 couverts)
- **MAPE par semaine** : semaine 1 8.4% · semaine 2 7.9% · semaine 3 15.9% · semaine 4 12.5% · semaine 5 11.6%
- **Adaptation au choc** : 15.9 % la semaine du choc → **12.3 %** après recalibration
- **Acceptation manager simulé** : 76.7 %
- **Gate G-3** : 1 outcome rejeté (donnée corrompue jamais entrée en training)
- **Recalibrations** : 5 · **Outcomes capturés** : 29

Détail jour par jour : `closed_loop_demo.json` (ledger). Reproduction : `python scripts/ops/closed_loop_demo.py` (déterministe, seed 42).
