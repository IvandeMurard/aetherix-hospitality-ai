# Fiche prospect — périmètre honnête & conformité (Story 16.13 AC4+AC5)

> Acté 01/08/2026. Document remis à un prospect / design-partner en due diligence.
> Deux questions qu'un acheteur pose toujours, répondues sans enjoliver : **qu'est-ce qui
> existe vraiment aujourd'hui**, et **que faites-vous de mes données**.
>
> Convention de statut appliquée mot pour mot : [`status-taxonomy.md`](status-taxonomy.md)
> (Built / Shadow-mode / Synthetic PoC / Design / Research, Décision #33). Le présent de
> l'indicatif est réservé à *Built* et *Shadow-mode* ; tout le reste est au conditionnel.

---

## Partie A — Périmètre honnête (AC5)

### Ce qui tourne vs ce qui est promis

Le détail brique par brique — avec la colonne *Preuve* (données, nombre d'utilisateurs réels) —
vit dans [`status-taxonomy.md`](status-taxonomy.md) §État des briques. On ne le duplique pas ici ;
on en donne la lecture d'une phrase, celle qu'un prospect doit retenir :

- **Aetherix (nœud F&B) — Built, zéro utilisateur réel.** Le Daily Receipt, le MCP Server v0,
  la mémoire opérationnelle et les guardrails runtime sont déployés sur staging Fly.io et exercés
  de bout en bout. *Built* dit que le code tourne sans intervention — **pas** qu'un manager s'en
  sert : à ce jour, personne. La mesure commence avec le design-partner.
- **Forecast — Shadow-mode.** Benchmarké sur données réelles publiques (30 restaurants japonais
  tirés du dataset Kaggle *Recruit*, qui en compte 829), Prophet **fait jeu égal avec la baseline naïve sur le jour médian**
  (MdAPE 27,0 % vs 27,6 %) et est marginalement *moins bon* à J+1 ([`mape-benchmark.md`](mape-benchmark.md)).
  Aucune décision n'est encore livrée à un manager sur cette base. Le forecast n'est donc **pas**
  vendu comme le différenciateur tant que HOS-308 (shadow mode hôtelier réel) n'a pas tranché.
- **Le reste de la mesh est une north-star, pas un actif.** Anima = *Synthetic PoC*.
  Context Graph, Signal Contract, Orchestrateur = *Design*. HiveMemory fédérée / Learning
  Engine = *Research* (aucun socle : `hotel_cohort_features` v1 n'existe pas). Ces briques se
  décrivent au futur, jamais comme si elles tournaient.

La formule à tenir partout : **« Aetherix est la preuve, la mesh est la promesse. »**

### Le bus factor, nommé comme un risque et non comme un badge

Aetherix est construit **par une seule personne**. Le méta-repo public le dit déjà, mais comme une
*motivation* (« building this Mesh solo to master the full lifecycle »). Pour un acheteur, c'est
d'abord un **risque de continuité (bus factor = 1)** — dépendance à une personne clé — et il mérite
d'être posé franchement, pas enfoui :

- **Le risque, sans euphémisme.** Une seule personne connaît l'architecture, tient le déploiement et
  porte la roadmap. Indisponibilité prolongée = continuité non garantie contractuellement à ce stade.
- **Ce qui l'atténue déjà** (vérifiable, pas promis) : décisions d'architecture tracées (index dans
  `CLAUDE.md` + 12 ADR versionnés), harnais de reprise (`CLAUDE.md`/`AGENTS.md` synchronisés, gate D1),
  pipeline reproductible (benchmarks déterministes, bit-identiques sur 2 runs), infrastructure
  gérée (Fly.io + Supabase, pas de serveur artisanal). Le savoir est dans le repo, pas seulement
  dans une tête.
- **Ce qui reste ouvert** : aucune redondance humaine, pas d'engagement de service (SLA) ni de plan
  de réversibilité formalisé. À cadrer explicitement dans tout contrat pilote — c'est une raison de
  plus pour la posture sandbox / non-PII de la Partie B tant que le déploiement n'est pas durci.

### Intégration au méta-repo (dépend de la Décision #25 / Story 16.5)

La déclaration publique vit dans le README du méta-repo public
[`hospitality-agentic-mesh`](https://github.com/IvandeMurard/hospitality-agentic-mesh) (tableau
*What's built vs. what's vision*). Trois corrections pour l'aligner sur la taxonomie à cinq
étiquettes sont déjà spécifiées, prêtes à coller, dans
[`audit-surfaces-publiques-2026-08.md`](audit-surfaces-publiques-2026-08.md) §PR méta-repo
(`Built (PoC)` → **Synthetic PoC** ; `In Progress` → **Design**/**Research** ; « 0 real users »
sur la ligne Aetherix ; principes #4/#5 au conditionnel).

**Cette story ajoute une 4ᵉ correction à cette PR** : remplacer le cadrage « solo = motivation » par
la ligne bus-factor ci-dessus (risque de continuité nommé + atténuations + ce qui reste ouvert).
La PR est ouverte dans le dépôt méta (repo public distinct, hors de ce commit) :
[hospitality-agentic-mesh#2](https://github.com/IvandeMurard/hospitality-agentic-mesh/pull/2) — voir §Suites.

---

## Partie B — Conformité prospect (AC4)

> **Cadre d'honnêteté.** Ce n'est **pas** un certificat de conformité. La plupart de l'appareil RGPD
> est encore *Design* (inventaire de données, jobs de rétention, procédure DSAR, DPA signée). Ce
> qu'on décrit, c'est la **posture actuelle** — volontairement minimale et sûre — et la **feuille de
> route** pour passer aux données réelles. Un prospect qui lit « pleinement conforme » quelque part
> lit une erreur.

### Rôles sur la donnée (structure cible du DPA)

| Donnée | Rôle Aetherix | Base légale visée |
|---|---|---|
| Données clients / convives (via PMS) | **Sous-traitant** (processor) pour le compte de l'hôtel, responsable de traitement | Contrat hôtel |
| Coordonnées manager (téléphone WhatsApp, e-mail) | **Responsable de traitement** (controller) | Intérêt légitime / contrat |
| Données opérationnelles agrégées (couverts, occupancy) | Sous-traitant | Intérêt légitime |

Cette distinction **sous-traitant vs responsable** est le cœur de la **DPA (Data Processing
Agreement)** à signer avec chaque hôtel client. Statut : **Design** — la structure est arrêtée
(inventaire Story 7.5, `tools/bmad/_bmad-output/implementation-artifacts/7-5-gdpr-data-inventory.md`),
la DPA type reste à rédiger avant tout traitement de données réelles UE. Suivi : HOS-115.

### Posture actuelle (ce qui est vrai aujourd'hui)

- **Pilote = sandbox Apaleo + dataset non-PII.** C'est le périmètre du GO conditionnel de l'audit
  pré-pilote ([`security-review-2026-Q2.md`](security-review-2026-Q2.md), Décision #30) : un seul
  design-partner, données synthétiques ou de bac à sable, **pas de PII réelle**, supervision active.
  Cette contrainte est une **décision de conformité**, pas une limite technique subie — on ne
  traite pas de données personnelles réelles tant que le pipeline PII de bout en bout n'est pas
  construit et audité.
- **RGPD WhatsApp (finding Q2-03) — corrigé.** Le canal WhatsApp ne journalise plus le numéro de
  téléphone ni le corps des messages entrants ; les réponses Twilio sont réduites au `status_code`
  (PR #187, [HOS-289](https://linear.app/hospitalityagent/issue/HOS-289)). C'était le principal
  vecteur d'exposition RGPD au pilote ; il est fermé.
- **Autres correctifs de sécurité en place** (audit Q2, CLOSED) : secrets de production purgés de
  l'historique git + **rotation 11/11 clés** ; dépôt passé **privé** ; RLS sur 14 tables tenant ;
  vérification HMAC des webhooks. Détail : [`security-review-2026-Q2.md`](security-review-2026-Q2.md).

### Ce qui reste à construire avant les données réelles (Design)

Honnêtement listé pour qu'un prospect sache ce qui **n'existe pas encore** :

- **Inventaire de données RGPD** (`docs/GDPR-DATA-INVENTORY.md`) — spécifié (Story 7.5), non livré.
- **Contrôles PII techniques vérifiés** : test automatisé « payload PII synthétique → zéro PII en
  base », hachage SHA-256 des numéros manager. Conçus, non prouvés par un test.
- **Jobs de rétention** (PMS brut 90 j, recommandations/anomalies 2 ans, logs d'action 5 ans) — Design.
- **Procédure DSAR** (accès / effacement, cascade depuis `operational_memory`) — Design.
- **DPIA légère + inventaire des flux PII** avant l'ouverture du canal conversationnel aux données
  réelles — condition posée par l'audit Q2, reliée à HOS-115.
- **Modèle d'anonymisation Hive** (k-anonymat ≥ 5 propriétés, opt-out par hôtel) — *Research*, sans
  socle à ce jour (cf. Partie A).

### Contact

Responsable de traitement / point de contact données : **Ivan de Murard** — le `DPO_EMAIL`
dédié est à provisionner (Story 7.5, Task 6) avant tout traitement de données réelles.

---

## Suites (hors de ce commit)

- **PR méta-repo** `hospitality-agentic-mesh` : les 3 corrections d'`audit-surfaces` + la 4ᵉ (ligne
  bus-factor) sont dans [hospitality-agentic-mesh#2](https://github.com/IvandeMurard/hospitality-agentic-mesh/pull/2),
  **ouverte, en attente de merge** (dépôt public distinct).
- **DPA type + `docs/GDPR-DATA-INVENTORY.md`** : à produire (Story 7.5 / HOS-115) avant le passage
  aux données réelles. Ce document en est le cahier des charges honnête, pas le livrable.

Voir aussi : [`positionnement-wedge.md`](positionnement-wedge.md) · [`moat.md`](moat.md) ·
[`status-taxonomy.md`](status-taxonomy.md) · [`audit-surfaces-publiques-2026-08.md`](audit-surfaces-publiques-2026-08.md).
