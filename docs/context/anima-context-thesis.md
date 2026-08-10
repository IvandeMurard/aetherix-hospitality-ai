# Anima — thèse de contexte opérationnel

> **Statut : Research.** Cadre conceptuel issu de l'échange « Contexte de réservation Anima »
> (03/08/2026). Ce document fixe un langage et une intention produit ; il ne crée ni backlog,
> ni promesse externe, ni exigence d'implémentation. Le gel Epic 16 et le gate DPIA Anima
> (Décision #20) restent inchangés.

---

## La question fondatrice

> **How can an organization understand a human situation and act accordingly?**

L'hospitalité est un terrain particulièrement lisible pour explorer cette question, mais n'en est
pas la limite conceptuelle. Une réservation n'est qu'un signal transactionnel : elle dit qu'un
client vient, à un moment donné. Elle n'explique pas nécessairement ce qui compte dans cette visite.

La formulation courte est :

> **Booking is becoming a commodity. Context isn't.**

## Rôle d'Anima

Anima n'est pas un système de réservation ni un simple *guest profile*. Sa fonction conceptuelle
est de construire une compréhension utile de la situation présente :

> **What should the organization understand about this guest and this moment before acting?**

Un profil est principalement statique (préférences, historique, statut). Le contexte est
dynamique : il relie, pour un moment précis, les informations explicitement disponibles, leurs
contraintes et leur pertinence opérationnelle. L'objectif n'est pas d'accumuler des données, mais
de rendre visible ce qu'une équipe doit comprendre afin de servir justement.

Les exemples souvent cités — une occasion particulière, une contrainte alimentaire communiquée,
un besoin de mobilité, un horaire contraint — illustrent la différence entre une table réservée et
une situation comprise. Ils ne constituent pas un schéma de données ni une autorisation d'inférer
des attributs personnels.

## Complémentarité avec Aetherix

| Nœud | Question principale | Fonction |
|---|---|---|
| **Anima** | Qui ? Pourquoi ? Que faut-il comprendre maintenant ? | Construire un contexte humain pertinent et borné |
| **Aetherix** | Quoi ? Combien ? Comment ? | Transformer les signaux autorisés en décisions et exécution opérationnelles |

La frontière est importante : Anima produit de la compréhension ; il ne décide ni n'agit seul.
Aetherix reste le nœud d'exécution F&B et l'orchestrateur reste séparé conformément à l'ADR-0004.

```text
Signals → Context → Understanding → Decision → Action → Outcome → Memory
              Anima              orchestration / Aetherix
```

Cette boucle décrit une ambition de cognition organisationnelle : passer de données et de mémoire
à une compréhension située, puis à une action évaluable. Elle complète le wedge Aetherix —
mémoire opérationnelle et apprentissage à partir de chaque service — sans présenter Anima comme
une capacité déjà livrée.

## Discipline de cadrage

- Ne pas confondre contexte et surveillance : seules les données nécessaires, pertinentes et
  légalement fondées peuvent alimenter une compréhension opérationnelle.
- Ne pas confondre compréhension et automatisation : toute action reste soumise aux frontières
  d'orchestration et de human-in-the-loop applicables.
- Ne pas présenter une inférence comme un fait sur une personne ; la contestabilité, la
  rectification et l'opposition sont des prérequis explicitement non levés.
- Ne pas employer cette thèse comme claim de produit : **Anima est Research**, pas un produit
  disponible.

Les conséquences RGPD/AI Act, notamment pour les données de santé, les inférences sensibles et le
profilage, sont détaillées dans la DPIA ; elles priment sur toute extension de cette vision.

## Références internes

- [`positionnement-wedge.md`](positionnement-wedge.md) — « Aetherix est la preuve, Anima est la
  promesse » et discipline de statut.
- [`mesh-architecture.md`](../mesh-architecture.md) — source de vérité inter-nœuds.
- [`dpia-anima-2026-08.md`](dpia-anima-2026-08.md) — gate de conformité Anima, non levé.
- [`ADR-0004`](../adr/0004-orchestrator-separation.md) — séparation orchestrateur / nœud
  d'exécution.

## Note de mise à jour

- 2026-08-03 — Création à partir de la conversation « Contexte de réservation Anima » : clarification
  de la distinction Anima (compréhension) / Aetherix (exécution) et de la thèse
  « context, not just transactions ».
