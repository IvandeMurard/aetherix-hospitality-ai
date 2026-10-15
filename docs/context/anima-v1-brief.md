# Anima v1 — brief de reprise

> **Statut : Design** (taxonomie [`status-taxonomy.md`](status-taxonomy.md), Décision #33). Brief de reprise pour une session Claude Code : ce n'est ni une spécification, ni une décision. Date : 15/10/2026.
> **Ce que ce brief fait** : poser l'intention, le cadre, ce qui existe et ce qui manque, les données disponibles sur le partage volontaire (avec leurs réserves), et les questions qui restent à Ivan. **Ce qu'il ne fait pas** : définir le périmètre de « livré » — c'est §6, à trancher par Ivan.
> **⚠️ Emplacement du dépôt (15/10/2026)** : le dépôt vit dans `C:\Users\ivand\aetherix-hospitality-ai`. L'ancien dossier `C:\Users\ivand\OneDrive\Documents\aetherix-hospitality-ai` **n'est plus le dépôt** : il ne contient qu'une note orpheline (`docs/context/session-memory-anima-cognition.md`). Une session qui ne trouve pas ce brief ou `docs/context/` complet est rattachée à l'ancien dossier : la rattacher au nouveau (ou la lancer depuis celui-ci).

---

## 1. Intention

Ivan veut **livrer une première version d'Anima intégrée à Aetherix et à l'agent orchestrateur** (`backend/orchestrator/`). Le contexte — objectif portfolio, gel Epic 16 levé pour le développement — est dans la **Décision #36** (`decisions-architecturales.md`). La livraison sera étiquetée **Synthetic PoC / Design**, jamais « Built ».

## 2. Cadre non négociable

| Règle | Source |
|---|---|
| Données **synthétiques uniquement** ; aucune donnée guest réelle | Décisions #36, #11 ; gate DPIA |
| Étiquetage honnête (Design / Synthetic PoC) sur toute surface | Décision #33 |
| Gate DPIA **non levé** — mesures M-1 à M-16 conçues avant tout traitement réel | Décision #20, [`dpia-anima-2026-08.md`](dpia-anima-2026-08.md) |
| Marché **EU**, ICP unifié EU/Apaleo | `open-decisions.md` §Resolved (25/09/2026) |
| Pas d'auto-actions ; Anima **informe**, l'Orchestrateur **décide** | Décision #6, ADR-0004, ADR-0011 D1 |
| Autonomie d'un agent hôte = **ADR-0013, statut Proposed, rien d'activé** ; les actions dérivées d'Anima y sont classées « Never autonome » | [`ADR-0013`](../adr/0013-decision-autonomy-policy.md) |
| Lignes rouges : aucune inférence émotionnelle sur le personnel, aucune entrée biométrique/voix sans nouvelle DPIA | DPIA M-10 |

## 3. Ce qui existe — et ce qui n'existe pas

- **Repo Aetherix** : **aucun module Anima** (vérifié le 15/10/2026 : seuls `backend/README.md` et `backend/app/core/demo_events.py` mentionnent le mot). L'orchestrateur existe en proto : `backend/orchestrator/` (`agent.py`, `rules.py`, ADR-0004). Des services de décision ont été ajoutés par d'autres sessions depuis le 24/09 (provenance de décision — ADR-0007 §17, Décision #39 ; learning loop — Décision #40 ; politique de décision `decision_policy.py`) : **à relire avant de dupliquer quoi que ce soit**.
- **PoC Anima, hors repo** : `C:\Users\ivand\OneDrive\Documents\anima-poc` — hackathon, **synthétique** (12 guests fictifs), 4 couches mémoire, `coordinator.py`, dossier `eval/`. ⚠️ **Piège** : son README décrit la couche Semantic en « TTL ∞ », ce que le DPIA a remplacé par **36 mois glissants** (§6, §10.1). Ne pas reprendre cette valeur en portant le PoC.
- **Contrat d'interface spécifié** : `query_guest_profile(guest_id, context_query, scope)` et `get_emotional_risk(...)` dans [`mesh-architecture.md`](../mesh-architecture.md) §2 ; namespace `guest.*` de l'ADR-0012.
- **Emplacement du code** : la Décision #19 prévoyait Anima / Guest Context Node en **Phase 4**, avec un repo séparé pour l'orchestrateur. L'emplacement de l'Anima v1 (dans ce repo, module séparé, autre repo) n'est **pas tranché** — voir §6.

## 4. Hypothèse de départ — première tranche en claims *déclarées*

Source : DPIA §14 (statut Design, aucune décision prise). Distinguer l'**origine** d'une claim Semantic : `declared` (fournie par le guest) ou `inferred` (déduite d'observations).

- **Ce que ça évite en tranche 1** : l'inférence émotionnelle par LLM, donc le gros du risque R4 (inférence erronée durable), la fragilité de la base légale « intérêt légitime » (§4) et l'absence de provenance (§13, M-16 devient trivial : la source est le guest).
- **Ce que ça ne supprime pas** : le consentement par finalité et découplé de la réservation (M-4, W3), la rétention bornée (M-1), le scope-gating (M-2), l'art. 9 si la claim est une préférence alimentaire (§5.2), le fait que l'hôtel reste responsable de traitement.
- **Règle de précédence à tester** : une claim `inferred` ne peut pas écraser une claim `declared` sans confirmation.
- **Testable sur données synthétiques** : un générateur de déclarations suffit.

## 5. Les quatre chantiers

| Chantier | Déjà documenté | À produire |
|---|---|---|
| **Interopérabilité** | contrat MCP (`mesh-architecture.md` §2), ADR-0012, ADR-0004, pattern Provider (Décisions #9, #28) | un **adapter d'entrée des claims déclarées, indépendant de la source** (même logique que `POSProvider`) |
| **Parcours de la donnée** | DPIA §3 (flux), §4 (bases légales), §6 (durées), §7 (droits), §13 (provenance), §14 | la **carte du parcours déclaré** : qui déclare, par quel canal, consentement, stockage, usage par l'Orchestrateur, effacement |
| **Évaluation** | eval-by-design (Décision #22), calibrage du juge (Décision #32), `eval/` du PoC | des **scénarios d'évaluation Anima** : précédence déclarée > inférée, abstention à faible confiance, scope-gating |
| **Bornage** | ADR-0009 (guardrails runtime), Décision #6, ADR-0013 (Proposed) | une décision d'Ivan sur ADR-0013 ; lecture explicite des lignes rouges M-10 |

## 6. À trancher par Ivan — rien n'est décidé ici

1. **Définition de « livré »** (options, non exclusives) : (a) démonstration bout en bout sur données synthétiques — déclaration → claim → recommandation de l'Orchestrateur → action F&B validée par un humain ; (b) en plus, un jeu de scénarios d'évaluation ; (c) en plus, un amendement d'ADR-0011 D2 (champ `origin`).
2. **Type de claim de la tranche 1** (heure d'arrivée, préférence de service, préférence alimentaire — cette dernière est potentiellement art. 9).
3. **Statut d'ADR-0013** (Proposed) : à trancher ou à laisser en l'état pour la v1.
4. **Emplacement du code** de l'Anima v1 (§3).
5. **Source des claims déclarées en développement** : générateur synthétique, réutilisation des 12 guests du PoC, autre.

## 7. Ce que disent — et ne disent pas — les données sur le partage volontaire

Question posée : la tendance à la déclaration volontaire est-elle en hausse ? **Réponse : aucune source trouvée ne le montre.** Toutes mesurent une **volonté déclarée à un instant**, pas une évolution.

| Source | Chiffre | Réserves |
|---|---|---|
| **Mews, 2025** (enquête d'un éditeur de PMS) | 93 % des voyageurs prêts à partager des données si cela améliore leur séjour ; 60 % pour les heures d'arrivée/départ, 48 % pour les préférences F&B, 46 % pour les équipements/activités | éditeur ; étude primaire non relue ; mesure une intention |
| **Priceline « Where to Next? 2027 »**, 14/10/2026 | 45 % des Américains partageraient personnalité, valeurs, « love languages », extraits de journal de rêves pour un itinéraire personnalisé ; 61 % Gen Z, 62 % millennials | **éditeur** (Priceline, groupe Booking Holdings, même groupe que Vayo) ; **aucun institut ni taille d'échantillon nommés** ; États-Unis implicite ; le destinataire est un **planificateur IA, pas un hôtel** ; données **psychographiques**, pas opérationnelles |
| **Amadeus, Travel Dreams 2026** | 74 % souhaitent un voyage personnalisé | mesure le désir de personnalisation, **pas le partage de données** |
| **Deloitte** (ancien, cité par un éditeur) | 22 % prêts à partager des données avec des marques | source primaire non relue ; formulation « marques » |
| **IAB, janvier 2025** | cohabitation de l'attente de personnalisation et de la crainte pour la vie privée (UK, Allemagne) | seuls des extraits ont été lus ; pas de ventilation par pays |

**Ce qu'on peut en dire, honnêtement** :
- La volonté déclarée dépend de **ce qu'on demande et de ce qu'on rend en échange** (22 % contre 93 % selon la formulation). Les chiffres ne sont **pas comparables** entre enquêtes.
- Il existe un « paradoxe personnalisation-vie privée » : intention déclarée ≠ comportement observé. Aucune des sources ci-dessus ne compare les deux.
- **L'Europe est peu documentée.**
- **Aucune mesure** de la volonté de laisser *son agent transmettre* ses préférences à l'hôtel réservé : c'est pourtant la question qui compte pour Anima.
- À **ne pas citer** (pitch, portfolio) comme preuve d'adoption. Au mieux : un indice de plausibilité.

## 8. Contexte écosystème — des agents côté voyageur

Quatre agents côté demande en environ quatre semaines (DirectBooker, Odessia, Vayo — projet de Booking Holdings —, skill open source de Fliggy/Alibaba) ; détail et réserves dans le vault Obsidian : `Veille/Veille_Distribution_Discovery.md` §OCT 15, 2026.

- **Lecture** : deux côtés d'un séjour — la cognition côté hôtel (Aetherix, Anima) et l'agent qui connaît le voyageur. Ils se rencontrent au moment de la **remise**. **Aucun protocole de remise n'est connu** ; aucun de ces produits n'est tourné vers l'hôtel.
- **Hypothèse d'Ivan (non vérifiée)** : si une grande chaîne (Accor, Louvre Hotels) ouvrait cette remise, l'effet serait soudain. **Rien ne le démontre** : ALL Concierge (Accor) est l'assistant de la marque, et l'annonce ne mentionne aucune ouverture à des agents tiers.
- **Conséquence de conception** : pas de pari sur un partenaire. Un **adapter d'entrée indépendant de la source** couvre tous les cas.
- **Vigilance** : la mémoire détenue par l'agent du voyageur vivrait chez un OTA ou une startup, pas chez l'hôtel — un point de passage qu'il ne contrôle pas.
- **À surveiller** : (a) un agent voyageur annonçant une API ou un point MCP/A2A **tourné vers les hôtels** ; (b) un PMS (Apaleo, Mews) recevant des préférences déclarées ; (c) un OTA exigeant des données F&B structurées ; (d) Booking Holdings étendant Vayo côté hôtel.

## 9. À lire, dans cet ordre

1. [`mesh-architecture.md`](../mesh-architecture.md) §2 · [`anima-context-thesis.md`](anima-context-thesis.md)
2. [`ADR-0011`](../adr/0011-learning-engine-hive-v2.md) · [`ADR-0004`](../adr/0004-orchestrator-separation.md) · [`ADR-0012`](../adr/0012-mesh-signal-contract.md) · [`ADR-0013`](../adr/0013-decision-autonomy-policy.md)
3. [`dpia-anima-2026-08.md`](dpia-anima-2026-08.md) — surtout §4, §6, §7, §13, §14
4. [`status-taxonomy.md`](status-taxonomy.md) · [`learning-loop.md`](learning-loop.md) · [`decision-ledger.md`](decision-ledger.md)
5. `decisions-architecturales.md` — Décisions #6, #19, #20, #22, #26, #33, #36
6. PoC hors repo : `C:\Users\ivand\OneDrive\Documents\anima-poc`

## 10. Pour démarrer une session

Cette session doit d'abord **produire un plan, pas du code** : lister ce qui n'est pas documenté et les hypothèses à trancher, poser à Ivan les questions de §6, puis planifier les quatre chantiers de §5. D'autres sessions travaillent sur ce repo : vérifier `git log` et les PR ouvertes avant de commencer. Ne pas écrire dans `CLAUDE.md` sans demander.
