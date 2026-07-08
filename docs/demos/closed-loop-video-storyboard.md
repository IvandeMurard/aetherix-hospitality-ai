# Storyboard — vidéo démo 3 min « closed loop » (HOS-310 AC3)

> Objectif : montrer la boucle **forecast → reco → feedback → réel → recalibration** en conditions
> réelles de code (services réels, guardrails réels), en annonçant clairement « données sandbox,
> boucle réelle ». Destinations : case study ivandemurard.com/aetherix + méta-repo.

**Préparation** : terminal plein écran (police ≥ 16pt, thème sombre), dashboard Logfire ouvert dans
un onglet (LOGFIRE_TOKEN posé — HOS-311 AC5), commande prête :
`backend/.venv/Scripts/python scripts/ops/closed_loop_demo.py`

| # | Durée | Scène | À dire (FR, une phrase par scène) |
|---|---|---|---|
| 1 | 0:00–0:20 | Titre + case study ouvert sur le diagramme de la boucle | « Aetherix apprend de chaque service : voici la boucle complète, exécutée de bout en bout — données sandbox, mécanique réelle. » |
| 2 | 0:20–0:50 | Lancer le script ; défilement des 7 premiers jours (APE ~8 %) | « Chaque soir : forecast J-1 par Prophet, recommandation staffing, receipt WhatsApp. Le manager valide d'un mot — 77 % d'acceptation ici. » |
| 3 | 0:50–1:20 | **J10 : ⛔ rejeté G-3 (900 couverts)** — zoomer sur la ligne | « Jour 10 : l'export POS est bugué — 900 couverts pour 120 places. Le guardrail G-3 le rejette avec une raison typée : la donnée corrompue n'entre jamais dans l'entraînement. » |
| 4 | 1:20–1:50 | **J15 : ⚡ choc de régime** ; les APE montent (16 % la semaine du choc) | « Jour 15 : nouveau contrat banquets, +25 % de demande. Le modèle dérive — c'est exactement le scénario qui tue les forecasts statiques. » |
| 5 | 1:50–2:20 | Lignes « ↻ recalibration » puis semaine 4-5 (MAPE redescend à ~12 %) | « Recalibration hebdomadaire sur les couverts réels capturés : l'erreur post-choc passe de 16 à 12 % — la boucle absorbe le changement au lieu de le subir. » |
| 6 | 2:20–2:45 | Basculer sur Logfire : trace d'un jour (span closed_loop.day → prophet.predict), event guardrail | « Tout est observable : chaque étape est tracée, chaque trip de guardrail est un événement typé — l'invariant NFR2 en pixels. » |
| 7 | 2:45–3:00 | Rapport final à l'écran + lien méta-repo | « Script déterministe, rejouable à l'identique. Le code et le rapport sont publics — il ne manque que votre propriété. » |

**Chiffres-clés à l'écran (incruster si montage)** : acceptation 76,7 % · 1 rejet G-3 ·
5 recalibrations · MAPE post-choc 15,9 % → 12,3 %.

**Anti-piège** : dire « sandbox » à voix haute dès la scène 1 — la crédibilité du projet repose sur
la séparation nette démo-mécanique (ici) vs accuracy réelle (benchmark Recruit, HOS-307).
