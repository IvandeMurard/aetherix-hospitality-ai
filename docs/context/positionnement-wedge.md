# Positionnement — le wedge Aetherix (Story 16.13 AC1)

> Acté 08-09/07/2026 (échange fondateur + audit critique). Ce document est la référence
> pour tout support externe : case study, méta-repo, article, LinkedIn, pitch.
> **Amendé le 10/08/2026** : deux formulations corrigées après veille (`Veille/Veille_Tech_Stack.md`
> §AUG 10). Révision attendue après les interviews F&B (HOS-309) et le shadow mode (HOS-308).

## La thèse en une phrase

**Aetherix n'est pas un outil de forecasting : c'est un système de mémoire opérationnelle
qui apprend de chaque service.** Le forecast est un organe, pas le produit.

> ⚠️ **Amendement du 10/08 — désambiguïser la phrase de tête.** « Mémoire opérationnelle » est
> devenu, courant 2026, le nom d'une catégorie d'infrastructure (Mem0, Zep, Letta, Oracle AI Agent
> Memory) : plusieurs implémentations de niveau production, dont des gratuites. Prononcée seule
> devant un lecteur technique — recruteur, investisseur, CTO hôtelier — la phrase s'entend
> désormais « wrapper sur mem0 ».
>
> **La phrase reste juste, mais ne se dit plus jamais sans son complément** : ce qui distingue
> n'est pas *d'avoir* de la mémoire, c'est **de quoi elle est faite** — des outcomes d'un métier
> capturés au point de décision, pas des préférences utilisateur extraites d'un fil de chat.
> Formulation courte utilisable telle quelle : *« une mémoire des décisions d'un métier, pas une
> mémoire de conversation »*.

## Pourquoi ce renversement (et pourquoi maintenant)

Le benchmark données réelles (HOS-307, Recruit) a montré que **Prophet fait jeu égal avec la
baseline naïve sur le jour typique** (MdAPE 27,0 vs 27,6 %). La couche prédictive est
commoditisée : n'importe quel maître d'hôtel expérimenté — ou n'importe quel concurrent avec
LightGBM — atteint la même zone. Mener le récit avec "F&B forecasting" revient à se positionner
sur la couche la moins défendable du système.

Ce qui n'est pas commoditisé, dans l'ordre de ce que la closed-loop demo (HOS-310) rend visible :

1. **La capture d'outcomes** — **dans l'hôtellerie**, personne ne sait ce que ses prévisions
   valaient il y a trois semaines. Aetherix le sait, le persiste, et le dit au manager.

   > ⚠️ **Amendement du 10/08 — la restriction de périmètre est obligatoire, pas cosmétique.**
   > La claim est vraie en hôtellerie et **fausse si on la laisse porter sur le restaurant tech** :
   > 7shifts expédie déjà de la variance analytics planifié-vs-réel sur les heures et coûts de
   > main d'œuvre, et ClearCOGS revendique une recalibration sur les ventes réelles (revendication
   > marketing, non étayée par sa source primaire — mais un interlocuteur ne le saura pas).
   > Énoncée sans périmètre devant quelqu'un venu du restaurant tech, elle se casse en une réplique
   > et emporte la crédibilité du reste. **Toujours dire « dans l'hôtellerie » ou « en F&B
   > hôtelier ».** Ce qui reste vrai sans restriction : la boucle *complète* — capture **plus**
   > attribution d'écart nommée **plus** recalibration — n'a été trouvée chez personne.
2. **La mémoire opérationnelle par propriété** — patterns, réflexions "actual vs predicted",
   feedback manager : les recommandations citent leurs souvenirs (memory hits dans les receipts).
3. **Les bornes de confiance** — le gate G-3 refuse les données implausibles (l'agent protège
   sa propre mémoire de l'empoisonnement) ; tout trip porte une raison typée (NFR2).
4. **La recalibration** — le système absorbe les changements de régime au lieu de les subir
   (démo : erreur post-choc 15,9 % → 12,3 %).
5. **Le rituel de confiance** — le Daily Receipt WhatsApp : l'agent anticipe (cite ses signaux),
   s'auto-évalue chaque matin, nomme ses dérives. La transparence *est* l'interface.

## Hiérarchie produit (Décisions liées : #26-D5, audit 07/07)

- **Surface produit** : le Daily Receipt (le rituel quotidien que le manager achète).
- **Moteur** : la boucle mémoire → forecast → recommandation → feedback → outcome → recalibration.
- **Moat** : la position dans la boucle act-and-measure (seul acteur qui agit + capture +
  attribue + apprend, par propriété, PMS-agnostic) — pas la taille du corpus ni le modèle.
- **North-star metrics** : `recommendation_acceptance_rate` + `weekly_operational_usage`.
  Le MAPE devient une exigence interne de qualité, plus un argument de vente.

## Discipline de langage (à respecter partout)

| Dire | Ne plus dire |
|---|---|
| "système de mémoire opérationnelle qui apprend de chaque service" | "outil de prévision F&B" |
| "une mémoire des décisions d'un métier, pas une mémoire de conversation" | "mémoire opérationnelle" seul, sans complément (collision catégorie infra, 10/08) |
| "dans l'hôtellerie, personne ne sait ce que ses prévisions valaient" | la même phrase sans restriction de périmètre (10/08) |
| "le forecast est un organe" | "notre IA prédit avec X % de précision" |
| "l'agent anticipe, se trompe, le dit, et apprend" | promesses de MAPE non mesurées |
| "Aetherix est la preuve, Anima est la promesse" | présenter Anima comme existante |
| mener avec la boucle et la conformité câblée | mener avec la mémoire, le MCP-native ou le human-in-the-loop — devenus des prérequis (`moat.md` §Ce qui a cessé d'être un différenciateur) |

Statut des chiffres : voir `docs/demos/demo-kit.md` §4 (mesuré / démo mécanique / cible).

## Applications (état au 09/07/2026)

- Méta-repo public : récit renversé (lead = operational memory) — fait
- Contenu marketing (case study prompt, article, kit LinkedIn, posts) → Obsidian vault `Aetherix - Marketing` (hors repo depuis le 09/07)
- Anima : thèse publiée au méta-repo ("Cognition, not just prediction"), sans schémas (Décision #31)
