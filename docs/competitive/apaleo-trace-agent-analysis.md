# Apaleo Trace Agent (THE FLAG) — audit de couverture fonctionnelle vs pipeline F&B Aetherix

> **Story:** [HOS-285](https://linear.app/hospitalityagent/issue/HOS-285) (Story 10.14) — Audit Trace Agent vs pipeline F&B Aetherix
> **Type:** Competitive / defensive analysis — no code
> **Date d'observation:** 2026-07-30 (sources publiques re-scannées à cette date)
> **Parent decision:** `docs/context/open-decisions.md` → *« Apaleo Copilot scope F&B — canari à surveiller »* · Watchlist §W2
> **Related:** [HOS-197](https://linear.app/hospitalityagent/issue/HOS-197) (`apaleo-mcp-mapping.md`, base d'évidence) · [HOS-278](https://linear.app/hospitalityagent/issue/HOS-278) (spike A2A — protocole, question distincte) · [HOS-180](https://linear.app/hospitalityagent/issue/HOS-180) (Agent Hub listing)

---

## TL;DR

- **AC2 — réponse binaire : NON.** Trace Agent ne couvre ni le F&B, ni les couverts, ni le staffing, ni aucune forme de prévision. Aucune source publique consultée le 30/07/2026 ne mentionne ces domaines.
- Trace Agent est un agent **réactif d'extraction** : il lit les *reservation comments* et crée des tâches opérationnelles (housekeeping). Aetherix est un pipeline **prédictif** (forecast → reco → Receipt). Les deux patterns ne se recouvrent pas.
- Périmètre réel des tâches : *« amenities, room setup, dietary requirements, celebrations »* — dont *« baby cots, extra beds, birthdays »*. La seule mention alimentaire (*dietary requirements*) est une **préférence guest routée**, pas de la gestion d'exploitation F&B.
- Résultats revendiqués : **~30 tâches/jour**, **3,5 h/semaine** économisées à THE FLAG Zürich (101 chambres). Destination des tâches : **Sweeply**, ou *« any housekeeping tool that exposes their APIs »*.
- ⚠️ **Le vecteur de menace a changé de nature.** Le risque n'est plus « Apaleo construit du F&B » mais « **Apaleo outille un tiers pour le construire vite** » : l'Agent Factory a produit Trace Agent en **prototype à 1 mois, production à 2,5 mois**. C'est le vrai signal de cet audit.
- Conséquence : le listing Agent Hub ([HOS-180](https://linear.app/hospitalityagent/issue/HOS-180)) gagne en valeur défensive — occuper la catégorie F&B avant qu'un tiers ne la prenne.

---

## AC1 — Inventaire des tâches générées

| Élément | Valeur observée | Source |
|---------|-----------------|--------|
| Catégories de tâches | *« amenities, room setup, dietary requirements, celebrations, etc. »* | Apaleo Store |
| Exemples nommés | *« baby cots, extra beds, birthdays and other special requests from guest comments »* | Customer story THE FLAG |
| Données lues | *« booking comments, guest profiles, rate codes, and special dates (like birthdays or anniversaries) »* | Apaleo Store |
| Destination des tâches | Sweeply · *« any housekeeping tool that exposes their APIs to create tasks »* | Apaleo Store |
| Volume | *« around 30 tasks per day without manual input »* | Customer story |
| Gain revendiqué | *« 3.5 hours per week in direct task creation time »* | Customer story |
| Propriété pilote | THE FLAG Zürich — 101 chambres, property d'expérimentation du groupe | Customer story |
| Mode de construction | **Agent Factory** + Sweeply — endpoints API dédiés créés par Sweeply ; prototype < 1 mois ; production ≈ 2,5 mois | Customer story |

**Nature du système** : boucle réactive mono-direction — *lecture de texte non structuré → classification LLM → création de tâche dans un outil tiers*. Aucune inférence sur des données historiques, aucune projection temporelle.

**Roadmap annoncée** (à surveiller) : *« Future enhancements are expected to let agents book services directly in connected systems, notify guests automatically once requests are confirmed, and support room allocation based on guest preferences. »* — extension de la **surface d'exécution**, toujours déclenchée par une demande guest. Pas de bascule vers le prédictif annoncée.

---

## AC2 — Couverture F&B / covers / staffing : **NON**

Vérification menée sur quatre sources publiques le 30/07/2026 :

| Source | Mention F&B / covers / staffing / forecasting |
|--------|-----------------------------------------------|
| Apaleo Store — fiche Trace Agent | **Aucune.** Seule occurrence alimentaire : *« dietary requirements »* |
| Customer story Apaleo × THE FLAG | **Aucune** |
| `apaleo.dev` — AI integrations overview | **Aucune** (agent non listé ; seuls Claude Plugin + MCP Server documentés) |
| Annonce Agent Hub | **Aucune.** Les 4 agents cités sont Email Booking, Corporate Sales, Digital Twin, CRM & Guest Experience |

**Sur `dietary requirements`** — c'est le seul terme qui pourrait prêter à confusion. Il désigne la remontée d'une **contrainte alimentaire individuelle d'un client** vers l'équipe, au même titre qu'un lit bébé. Il ne s'agit ni de prévision de couverts, ni de dimensionnement d'équipe, ni de pilotage de service. Aucun agrégat, aucune projection, aucune notion de capacité.

**Confirmation croisée par la base d'évidence existante** : `apaleo-mcp-mapping.md` (03/06/2026) établit que sur les **235 tools MCP Apaleo natifs**, aucun n'expose de primitive de forecast covers, de capture-rate ou de staffing. Trace Agent est bâti sur ces mêmes APIs ouvertes — il ne peut donc pas exposer une capacité que le socle n'a pas. **Ce constat reste valide.**

---

## AC3 — Benchmark vs pipeline Aetherix

Pipeline de référence Aetherix : `forecast (Prophet + regressors) → recommandation staffing → push WhatsApp Receipt → feedback manager → mémoire`.

### Axe 1 — Profondeur prédictive

| | Trace Agent | Aetherix |
|---|---|---|
| Déclencheur | Un commentaire de réservation déjà écrit | Un horizon temporel (J+1 … J+7) |
| Nature | **Réactif** — extraction d'une intention explicite | **Prédictif** — inférence sur données historiques + régresseurs météo/événements |
| Sortie | Une tâche | Un nombre de couverts + un dimensionnement d'équipe |
| Incertitude | Non modélisée | MAPE mesurée, abstention explicite, gate CI bloquant |

**Écart structurel.** Trace Agent transforme de l'information **déjà présente** ; Aetherix produit de l'information **qui n'existe pas encore**. Ce n'est pas une différence de maturité, c'est une différence de classe de problème.

### Axe 2 — Reasoning / explicabilité

Trace Agent : aucune explicabilité exposée dans les sources publiques. La sortie est une tâche ; le raisonnement LLM qui l'a produite n'est pas présenté à l'opérateur. Le contrôle qualité repose sur la lisibilité de la tâche elle-même.

Aetherix : le **Daily Receipt** est le produit — la recommandation est livrée avec sa justification, et la boucle de feedback (`submit_feedback_to_memory`) capte l'accord ou le désaccord du manager. L'explicabilité n'est pas un ajout, c'est la surface produit (positionnement wedge, `docs/context/positionnement-wedge.md`).

### Axe 3 — Mémoire cross-séjour

Trace Agent : lit `guest profiles` et `special dates` **par réservation**. C'est du contexte au moment du séjour, sans accumulation. Rien n'indique un apprentissage d'une réservation à l'autre, ni d'une propriété à l'autre.

Aetherix : `operational_memory` (pgvector), capture-rate appris par propriété, et prior de cohorte cross-propriété (Hive) — la valeur croît avec l'usage.

### Verdict

**Aucun chevauchement fonctionnel au 30/07/2026.** Le pattern commun de surface — *« une demande devient une action »* — masque deux architectures opposées : Trace Agent **route de l'intention explicite**, Aetherix **anticipe une demande non exprimée**.

---

## AC4 — Impact sur le scénario W2

### Ce qui est confirmé

Les scénarios A (30 %) / B (50 %) / C (20 %) portaient sur *« Apaleo étend-il son Copilot vers le F&B ? »*. Sur cette question précise, l'audit **conforte le scénario A** : douze mois après le lancement du Copilot et deux mois après Trace Agent, aucun signal F&B, y compris dans la roadmap annoncée.

### Ce qui change — reformulation du vecteur

L'audit fait apparaître un vecteur que la formulation A/B/C ne capturait pas. **Apaleo ne construit pas les agents : il fournit les rails.**

- **Agent Hub** = marketplace, *« vendor-neutral »*, *« direct path to market »* pour les développeurs, avec monétisation.
- **Agent Factory** = cadre de co-construction, *« co-funding and co-creating AI agent use cases in collaboration with hoteliers and partners »*.
- **Vitesse démontrée** : prototype en 1 mois, production en 2,5 mois, sur un cas réel avec un partenaire tiers (Sweeply).

La menace pertinente n'est donc plus *« Apaleo absorbe le F&B »* (peu probable, hors de son modèle) mais **« un tiers publie un agent F&B sur Agent Hub en un trimestre »**. Le socle technique est ouvert, le canal de distribution existe, et Apaleo co-finance.

### Nouveau trigger à ajouter à W2

> **Publication sur Agent Hub d'un agent tiers touchant covers / F&B forecasting / staffing / labour planning** → escalade immédiate, indépendamment du scope du Copilot Apaleo lui-même.

### Conséquence de séquencement

Le listing Agent Hub ([HOS-180](https://linear.app/hospitalityagent/issue/HOS-180), S7) change de statut : d'opportunité de visibilité, il devient un **acte défensif d'occupation de catégorie**. Aucun des quatre agents cités en exemple par Apaleo ne couvre le F&B — la catégorie est vacante au 30/07/2026.

---

## AC5 — Note de différenciation F&B

Formulation défendable devant un hôtelier Apaleo, adossée aux preuves ci-dessus :

> *Trace Agent lit ce qu'un client a déjà écrit et le transforme en tâche. Aetherix prévoit ce que personne n'a encore demandé — combien de couverts demain, et combien de personnes pour les servir. Le premier supprime une ressaisie ; le second prend une décision d'exploitation. Les deux sont complémentaires sur le même PMS : rien dans le Trace Agent ne produit une prévision, et rien dans les 235 tools Apaleo natifs n'expose de primitive de forecast, de capture-rate ou de staffing.*

Cette formulation est **vérifiable** : chaque affirmation est sourcée dans ce document ou dans `apaleo-mcp-mapping.md`. Elle est à reprendre dans le listing Agent Hub (HOS-180 AC1) et dans le deck pilote.

---

## Limites de cet audit

- **Sources publiques uniquement.** Trace Agent n'a pas été testé en sandbox Apaleo — la fiche Store ne documente pas d'accès d'évaluation, et le déploiement observé est spécifique à THE FLAG × Sweeply.
- **Le comptage des 235 tools n'a pas été rejoué** (`scripts/list_apaleo_tools.py` requiert des credentials OAuth2 Apaleo). La conclusion « aucune primitive de forecast » repose sur le relevé du 03/06/2026. **À rejouer avant le go-live** — c'est une vérification à 5 minutes qui invaliderait ou confirmerait le cœur de l'argument de différenciation.
- **Pas de signal de veille depuis le 20/06** sur Trace Agent (vérifié sur les veilles du 02, 06, 13, 20 et 27 juillet). L'état décrit ici est celui du 30/07/2026.

---

## Sources

- [Apaleo Store — Trace Agent](https://store.apaleo.com/apps/trace-agent)
- [Apaleo × THE FLAG — customer story](https://apaleo.com/customer-stories/hotel-groups-chains/apaleo-and-THE-FLAG-bring-agentic-AI-into-live-hotel-operations)
- [Hospitality Net — Apaleo and THE FLAG bring agentic AI into live hotel operations](https://www.hospitalitynet.org/news/4131029/apaleo-and-the-flag-bring-agentic-ai-into-live-hotel-operations-with-autonomous-task-creation)
- [apaleo.dev — AI integrations overview](https://apaleo.dev/guides/ai/overview.html)
- [Apaleo — Agent Hub announcement](https://apaleo.com/blog/apaleo-news/apaleo-unveils-agent-hub)
- Base d'évidence interne : `docs/competitive/apaleo-mcp-mapping.md` (HOS-197, 03/06/2026)
