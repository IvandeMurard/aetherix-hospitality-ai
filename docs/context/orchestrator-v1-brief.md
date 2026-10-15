# Orchestrateur v1 — brief de reprise

> **Statut : Design** (taxonomie [`status-taxonomy.md`](status-taxonomy.md), Décision #33). Brief de reprise pour une session Claude Code : ni spécification, ni décision. Date : 15/10/2026.
> **Ce que ce brief fait** : poser l'intention, le cadre, ce qui existe réellement dans le code et ce qui manque, les chantiers et les questions qui restent à Ivan. **Ce qu'il ne fait pas** : définir le périmètre de « construit » — c'est §6, à trancher par Ivan.
> **Emplacement du dépôt** : `C:\Users\ivand\aetherix-hospitality-ai`. L'ancien dossier OneDrive de même nom n'est plus le dépôt ; une session qui n'y trouve pas ce brief y est rattachée à tort.
> **Brief jumeau** : [`anima-v1-brief.md`](anima-v1-brief.md) (Anima v1). L'Orchestrateur est le consommateur d'Anima : ne pas dupliquer, se référer à l'autre brief.

---

## 1. Intention

Ivan veut **construire enfin l'Orchestrateur** (15/10/2026), en parallèle d'Anima v1. Le contexte — objectif portfolio, gel Epic 16 levé pour le développement, données synthétiques — est dans la **Décision #36**. La livraison sera étiquetée **Design / Synthetic PoC**, jamais « Built » (voir §2, dernier point).

## 2. Cadre non négociable

| Règle | Source |
|---|---|
| L'Orchestrateur est le **seul** composant avec logique de décision et boucle de feedback ; les nœuds (Aetherix, Anima, Tacet) informent ou exécutent, ne routent pas | Décision #19, [`ADR-0004`](../adr/0004-orchestrator-separation.md) D1, D7 |
| Interface **MCP uniquement** entre l'Orchestrateur et les nœuds ; zéro import `app.*` dans `orchestrator/` (test AST en CI) | ADR-0004 D4 |
| Pas d'auto-actions ; l'autonomie d'un agent hôte est un seam « Proposed » (ADR-0013), rien n'est activé ; les actions dérivées d'Anima sont « Never autonome » | Décision #6, [`ADR-0013`](../adr/0013-decision-autonomy-policy.md) |
| Garde-fous runtime : toute décision d'un guardrail est loguée avec une raison typée ; dégrader plutôt que bloquer | [`ADR-0009`](../adr/0009-runtime-guardrails.md), Décision #27 |
| Données **synthétiques uniquement** ; gate DPIA non levé ; marché EU | Décisions #36, #20 ; `open-decisions.md` §Resolved |
| Étiquetage honnête (Design / Synthetic PoC), jamais « Built » sans preuve | Décision #33 |
| Portabilité de modèle : les services demandent un **tiers** (`reasoning` / `fast`), jamais un identifiant de modèle | Décision #35, Décision #9 |

⚠️ **Piège de nomenclature — « Built » n'a pas la même définition partout.** `llms.txt` du méta-repo : « deployed and exercised end-to-end on the target environment » ; `public-status.yml` d'Aetherix (Décision #42) : « MERGED on main and covered by tests… does NOT mean deployed ». Tant que ce n'est pas réconcilié, ne pas employer « Built » pour l'Orchestrateur.

## 3. Ce qui existe — et ce qui n'existe pas

**Existe (vérifié dans le code le 15/10/2026)**
- `backend/orchestrator/agent.py` — `OrchestratorAgent` : services **injectés** (forecaster, RAG, reasoner, staffer, memory, chargeur de profil) ; `get_forecast` enchaîne prévision → RAG → rappel mémoire avec boucle bornée → constitution d'agent → raisonnement → staffing. `AetherixEngine` (`backend/app/services/aetherix_engine.py`) y délègue.
- `backend/orchestrator/rules.py` — règles **pures et déterministes** de la boucle de rappel : plancher de similarité 0,7, `k` 5 → 10, **2 tentatives maximum**, une `RecallOutcome` typée sur chaque sortie. Le commentaire du module renvoie à HOS-335 (règles figées : ne pas rendre ces seuils modifiables par une boucle d'apprentissage) et HOS-331 (déposer l'objet « run » dans le ledger) — **tickets non vérifiés dans Linear**.
- Tests : `backend/tests/orchestrator/test_agent.py` (dont l'interdiction d'importer `app.*`) et `test_rules.py`.
- À proximité, ajoutés par d'autres sessions depuis le 24/09 : `decision_policy.py` (le seam d'autonomie, politique par défaut), `decision_provenance.py`, `manager_decision.py`, `inbound_decision.py`, `learning_loop.py`, `risk_assessment.py`, `task_classes.py` (tous sous `backend/app/services/`). **À relire avant de rien dupliquer** (Décisions #38 à #41, ADR-0007 §16 à §19).
- **Référence de fonctionnement** : `C:\Users\ivand\OneDrive\Documents\anima-poc\coordinator.py` (hors dépôt, synthétique) — un orchestrateur qui consulte Anima par un pont d'outils ; il a confirmé le partage « Anima informe, l'Orchestrateur décide ».

**N'existe pas** (ADR-0004 §5 et §4)
- **Aucun client MCP** dans `orchestrator/` : « Wire MCP client … **Not started** — Phase 4 ». Les services sont encore injectés par le constructeur.
- Aucune planification par LLM (« Phase 3 partial (stub) »), aucun routage dynamique entre nœuds, aucune prise d'événements, aucun magasin de règles métier par hôtel.
- Aucun appel à **Tacet** ni à **Anima** : le D8 d'ADR-0004 prévoit `get_room_risk_score` (Tacet MCP) puis `query_guest_profile` (Anima MCP) comme endpoints de l'Orchestrateur ; aucun fichier de `backend/app` ne mentionne Tacet (grep, 15/10/2026). L'Orchestrateur **public** est classé « Design — proto-stub only ».
- **Emplacement du code** : le D2 place le module dans ce dépôt pour la Phase 3 ; le D3 prévoit un **dépôt séparé en Phase 4**. Non tranché pour la v1 — voir §6.

## 4. Pourquoi Tacet entre dans ce brief

Le lien Aetherix ↔ Tacet **passe par l'Orchestrateur** (ADR-0004 D8), pas par Aetherix. Le `llms.txt` de Tacet affirme pourtant que « Aetherix … consumes Tacet over MCP » : tant que l'Orchestrateur ne l'appelle pas, c'est **une affirmation sans preuve dans le code**. Construire le client MCP de l'Orchestrateur et lui faire appeler Tacet sur données synthétiques serait donc la plus petite tranche qui rende cette phrase vraie — et qui sorte Tacet de l'état « paused ». Ce n'est **pas** automatique : relancer Tacet n'est qu'une conséquence si cette tranche est retenue (§6).

## 5. Les quatre chantiers

| Chantier | Déjà documenté | À produire |
|---|---|---|
| **Interopérabilité** | ADR-0004 D4 et D8, contrat MCP (`mesh-architecture.md`), Signal Contract (ADR-0012, privé) | un **client MCP** et un registre d'endpoints (Aetherix `/mcp/v1/`, Tacet, Anima synthétique) ; un nœud indisponible **dégrade**, il ne fait pas échouer |
| **Boucle agentique et règles** | `rules.py` (boucle de rappel bornée), ADR-0004 D7, ADR-0009 | planification et choix d'outils bornés (budget d'appels, raisons typées), objet « run » tracé ; règles métier **hors** de tout apprentissage tant que HOS-335 n'est pas levé |
| **Évaluation** | eval-by-design (Décision #22), ADR-0007 §13 à §19, calibrage du juge (Décision #32) | scénarios propres à l'Orchestrateur : choix de nœud, arrêt de boucle, nœud indisponible, abstention ; décision tracée de bout en bout (provenance, ADR-0007 §17) |
| **Bornage** | Décision #6, ADR-0013 (Proposed), ADR-0009 | échelle d'autonomie **L0 partout** pour la v1 ; lignes rouges du DPIA ; aucune action dérivée d'Anima sans humain |

## 6. À trancher par Ivan — rien n'est décidé ici

1. **Définition de « construit »** : (a) démonstration bout en bout sur données synthétiques — un événement entre, l'Orchestrateur appelle deux nœuds par MCP, produit une recommandation avec une trace typée, un humain valide ; (b) en plus, des scénarios d'évaluation ; (c) en plus, l'amendement d'ADR-0004 et un statut publié.
2. **Première tranche** : Aetherix seul par MCP (le plus petit pas) ; Aetherix + Tacet ; Aetherix + Tacet + Anima synthétique. Le choix détermine si Tacet est relancé (§4).
3. **Emplacement du code** (ADR-0004 D2 / D3) : ce dépôt, module séparé, ou dépôt dédié.
4. **Source des données de Tacet en développement** : serveur MCP de `tacet-app` en local, ou serveur simulé.
5. **Statut à afficher pour Tacet** : « Built · paused » aujourd'hui dans son `llms.txt` ; à reformuler selon (2).
6. **Modèle et tiers** : quels tiers (`reasoning` / `fast`) pour la planification (Décision #35).

## 7. À lire, dans cet ordre

1. [`ADR-0004`](../adr/0004-orchestrator-separation.md) (surtout D4, D7, D8, §4, §5) · [`mesh-architecture.md`](../mesh-architecture.md) (§Orchestrateur)
2. `backend/orchestrator/agent.py` · `backend/orchestrator/rules.py` · `backend/tests/orchestrator/`
3. [`ADR-0013`](../adr/0013-decision-autonomy-policy.md) · [`ADR-0009`](../adr/0009-runtime-guardrails.md) · [`ADR-0007`](../adr/0007-evaluation-by-design.md) §13, §16 à §19
4. [`status-taxonomy.md`](status-taxonomy.md) · [`anima-v1-brief.md`](anima-v1-brief.md) · [`learning-loop.md`](learning-loop.md) · [`decision-ledger.md`](decision-ledger.md)
5. `decisions-architecturales.md` — Décisions #6, #9, #19, #22, #27, #33, #35, #36, #42
6. Tacet : `C:\Users\ivand\dev\tacet-app\ARCHITECTURE_MANIFEST.md` et `llms.txt` · PoC : `C:\Users\ivand\OneDrive\Documents\anima-poc\coordinator.py`

## 8. Pour démarrer une session

Produire d'abord un **plan, pas du code** : lister ce qui n'est pas documenté et les hypothèses à trancher, poser à Ivan les questions de §6, puis planifier les quatre chantiers de §5. D'autres sessions travaillent sur ce dépôt : vérifier `git log` et les PR ouvertes. Ne pas écrire dans `CLAUDE.md` sans demander.
