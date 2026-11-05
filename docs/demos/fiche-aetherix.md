# Aetherix — fiche produit (1 page)

**Une recommandation d'effectif par jour pour le restaurant d'un hôtel indépendant, dans WhatsApp ; la
réponse du manager et le résultat réel enregistrés à côté.** Projet solo, construit avec Claude Code.
Statut : *Built* (fusionné et testé), **0 utilisateur réel**, staging arrêté. Données de démo fictives.

## Cas métier
Mardi 14 h, Claire, responsable F&B d'un hôtel de 118 chambres (restaurant de 78 couverts), doit décider
avant l'heure limite du planning si elle ajoute un extra pour le dîner de mercredi : séminaire en
résidence, match à 2 km, pluie annoncée. Aujourd'hui : moyenne des 4 derniers mercredis, de tête.

## Problème de départ
Ce qu'un hôtel sait de son service vit dans la tête de son manager. Résultat : sur- ou sous-effectif
récurrent, gaspillage, décisions réactives. Le goulot n'est pas la donnée, c'est la synthèse
(occupation + historique + météo + événements → une décision, pour cette propriété, à temps).

## Parties prenantes
| Qui | Rôle | Ce qu'il attend |
|---|---|---|
| Responsable F&B | utilise, décide | une phrase actionnable avant l'heure limite, zéro outil à apprendre |
| Direction de l'hôtel | paie | coût de personnel maîtrisé, service tenu |
| PMS (Apaleo) | distribue, fournit la donnée (lecture seule) | une intégration listée sur sa marketplace |
| Agent de l'hôtel (MCP) | relaie | des outils atomiques, isolés par hôtel, avec provenance |

## Distribution
Dans les outils que l'hôtel utilise déjà, pas de dashboard : WhatsApp (ou e-mail / SMS selon l'hôtel),
l'agent de l'hôtel via MCP, plus tard le planning et le PMS. Canal d'acquisition visé : marketplace du PMS.
Plateformes d'agents des éditeurs (Apaleo A2A) : attentisme tant qu'aucune interface n'existe.

## Indicateurs et critères de succès (gelés avant toute mesure)
| Niveau | Indicateur | Critère |
|---|---|---|
| Vérité produit | Δ MdAPE vs baseline naïve, à l'horizon de décision | ≥ 5 pp = PASS · 2–5 pp = zone grise, décision écrite · < 2 pp = pivot |
| Adoption | taux d'acceptation des recommandations (décisions humaines) | ≥ 30 % |
| Impact | écart de coût de personnel, incidents de sous-effectif, gaspillage par couvert | mesurés seulement avec des réels indépendants (POS) |
| Fiabilité | décisions écrites sans confirmation sous 0,85 de confiance | 0 (invariant testé) |

Source : `docs/planning/protocole-de-preuve.md` (horodatage git = preuve du pré-enregistrement).

## Ce qui est prouvé, et sur quoi
- Boucle de décision : tests + scripts de démo sur les services de production (données fictives).
- Prévision : Kaggle Recruit (restaurants réels) — meilleure que la naïve en moyenne, **à égalité en médiane, derrière à J+1**.
- Rien n'est mesuré sur un hôtel réel.
