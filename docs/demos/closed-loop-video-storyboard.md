# Storyboard — vidéo démo 3 min « closed loop » (HOS-310 AC3) — v2, trois écrans

> Objectif : montrer **l'anticipation et la réaction de l'agent**, pas un terminal qui défile.
> Layout : **terminal à gauche · schéma de la boucle au centre · fil WhatsApp à droite**.
> Annoncer « données sandbox, mécanique réelle » à voix haute dès la scène 1.

## Préparation

- **Gauche (terminal)** : `backend/.venv/Scripts/python scripts/ops/closed_loop_demo.py` (police ≥ 16pt).
- **Centre (architecture)** : le diagramme de la boucle (forecast → reco → feedback → réel → G-3 → recalibration) en slide — surligner l'étape active à chaque scène (un simple slide avec 5 variantes surlignées suffit ; pas besoin d'app interactive).
- **Droite (WhatsApp)** : `docs/demos/whatsapp_transcript.md` généré par le script — rendu dans un viewer markdown étroit (~380 px) pour l'effet fil de discussion. Scroller au jour affiché à gauche.
- Optionnel scène 6 : onglet Logfire (si token posé) — sinon la scène 6 se fait sur le centre.

## Comment l'anticipation et la réaction sont montrées

| Capacité | Où ça se voit (écran de droite) | Jour |
|---|---|---|
| **Anticipation** | Le receipt de la veille cite ses *drivers* : « 📍 Signal : événement local demain — impact +X % intégré » · « 🏨 Hôtel à 92 % d'occupation » — l'agent explique pourquoi demain ≠ la semaine dernière | J18, J23… |
| **Auto-évaluation** | Chaque matin l'agent verbalise son écart : « Réel constaté : 92 (prévu 82, écart +11 %) » — il ne cache pas ses erreurs | tous les jours |
| **Réaction : données corrompues** | « ⚠️ La donnée POS d'hier (900 couverts) est implausible — écartée, elle n'alimentera pas l'apprentissage. Pouvez-vous vérifier l'export caisse ? » | **J10** |
| **Réaction : détection de dérive** | « 📈 Troisième sous-estimation consécutive — un changement de régime semble en cours. La recalibration l'intégrera » — l'agent *nomme* le pattern avant d'être corrigé | **J17** |
| **Apprentissage** | « 🔁 Modèle recalibré sur les 7 derniers services » puis les écarts semaine 4-5 redescendent (visible à gauche : MAPE 15,9 → 12,3 %) | J21, J28 |

## Séquencier (3 min)

| # | Durée | Gauche | Centre | Droite | À dire |
|---|---|---|---|---|---|
| 1 | 0:00–0:20 | — | Boucle complète affichée | Premier receipt | « Aetherix apprend de chaque service. Données sandbox, mécanique réelle — voici la boucle, en entier. » |
| 2 | 0:20–0:50 | Lancer, J1-J9 défilent | Surligner *forecast → reco* | Receipts + « OK 👍 » | « Chaque soir : prévision, staffing, un message. Le manager répond d'un mot — c'est tout le rituel. » |
| 3 | 0:50–1:20 | **J10 ⛔ rejeté G-3** | Surligner *G-3 bounds* | Message ⚠️ export caisse | « Export POS bugué : 900 couverts pour 120 places. Le guardrail rejette, prévient le manager, et la donnée n'empoisonne pas l'apprentissage. » |
| 4 | 1:20–1:50 | **J15 ⚡ choc**, APE montent | Surligner *réel vs prévu* | J17 : « troisième sous-estimation… » | « Nouveau contrat banquets, +25 %. Trois services plus tard, l'agent nomme lui-même la dérive — il ne subit pas en silence. » |
| 5 | 1:50–2:20 | ↻ recalibrations, APE redescendent | Surligner *recalibration* | « 🔁 Modèle recalibré » + receipts justes | « Recalibration hebdomadaire sur les couverts réels : l'erreur post-choc passe de 16 à 12 %. La boucle absorbe le changement. » |
| 6 | 2:20–2:45 | Rapport final | Logfire (trace + event guardrail) *ou* zoom NFR2 sur le schéma | J18 : anticipation événement | « Et tout est observable : chaque étape tracée, chaque trip typé. L'agent anticipe les signaux connus — événements, occupation — au lieu de répéter la semaine passée. » |
| 7 | 2:45–3:00 | — | Boucle + lien méta-repo | — | « Déterministe, rejouable, public. Il ne manque que votre propriété. » |

**Chiffres à incruster** : acceptation 76,7 % · 1 rejet G-3 · 5 recalibrations · MAPE post-choc 15,9 → 12,3 %.

**Anti-piège** : la crédibilité repose sur la séparation nette démo-mécanique (ici) vs accuracy réelle (benchmark Recruit, HOS-307) — le dire, et pointer le benchmark dans la description de la vidéo.
