# Inventaire des données personnelles — Aetherix

> **Story 7.5 / [HOS-115](https://linear.app/hospitalityagent/issue/HOS-115)** · Établi le 01/08/2026.
> **Méthode :** audit du schéma réel (`backend/app/db/models.py`, 19 tables) et des chemins d'écriture,
> pas du schéma supposé. Chaque ligne ci-dessous a été vérifiée dans le code.
>
> **Cadre d'honnêteté.** Ce document est un **inventaire**, pas une attestation. Il dit ce qui est
> stocké, où, et sous quel régime — y compris là où la réponse est inconfortable. Trois écarts
> matériels entre ce qui est affirmé ailleurs et ce qui est en base sont nommés au §6. Les durées de
> conservation du §4 sont **spécifiées, non implémentées** : aucun job de purge n'existe à ce jour.

---

## 1. Rôles

| Donnée | Rôle Aetherix | Base légale visée |
|---|---|---|
| Données de convives via PMS | **Sous-traitant** pour l'hôtel | Contrat hôtel (DPA) |
| Identité et coordonnées manager | **Responsable de traitement** | Contrat / intérêt légitime |
| Messages entrants WhatsApp (expéditeur inconnu) | **Responsable de traitement** | ⚠️ **aucune** — voir §6.2 |
| Données opérationnelles agrégées | Sous-traitant | Intérêt légitime |
| Agrégats Hive cross-propriétés | **Responsable de traitement** | Intérêt légitime — cf. DPIA Anima §2 |

Point de contact données : Ivan de Murard. `DPO_EMAIL` **non provisionné** (Task 6, non faite).

---

## 2. Inventaire par table

Classification : **PII** (identifie directement) · **Pseudo-PII** (identifie indirectement ou via
recoupement) · **Non-PII** (aucune personne concernée).

### 2.1 Tables portant des données personnelles

| Table | Colonnes concernées | Classe | Traitement actuel |
|---|---|---|---|
| `users` | `full_name`, `email`, `hashed_password`, `department_role` | **PII** | Géré par `fastapi-users` ; mot de passe haché. Comptes internes uniquement à ce jour. |
| `restaurant_profiles` | `manager_name`, `phone_number`, `notification_email` | **PII** | ⚠️ **en clair** — voir §6.1 |
| `conversational_queries` | `from_number`, `body` | **PII** | ⚠️ **en clair, sans durée** — voir §6.2 |
| `operational_memory` | `manager_feedback`, `reflection`, `outcome`, `embedding` | **Pseudo-PII** | Texte libre saisi par un manager : peut contenir un nom, un incident nominatif. L'`embedding` en dérive et **reste une donnée personnelle** à ce titre. |
| `agent_action_log` | `payload` (JSON), `abstention_context` (JSONB) | **Pseudo-PII** | Champs libres non contraints par schéma — rien n'empêche une PII d'y transiter. |
| `pms_sync_logs` | `raw_payload_summary` (JSON), `error_message` | **Pseudo-PII** | Résumé de payload PMS. Le `PIIStripper` s'applique en amont (§3), mais le champ reste non contraint. |

### 2.2 Tables sans données personnelles

`captation_baselines` · `weather_forecasts` · `demand_anomalies` · `local_events` ·
`staffing_recommendations` · `recommendation_cache` · `fb_patterns` · `training_runs` ·
`kpi_daily` · `eval_baselines` · `scheduler_event` · `mcp_api_tokens` (jetons hachés, liés à un
hôtel et non à une personne).

Réserve sur `staffing_recommendations` : `message_text` et `triggering_factor` sont du texte libre
généré par le système. Non-PII **par construction du générateur**, pas par contrainte de schéma —
si un prompt venait à y recopier un feedback manager nominatif, la classification changerait. À
re-vérifier si le générateur évolue.

---

## 3. Contrôles techniques — état vérifié

### 3.1 PII convive à l'ingestion PMS — ✅ en place

`PIIStripper.strip_guest_data()` (`services/pms_sync.py`) retire `guest_name`, `guest_email`,
`guest_phone` et remplace `guest_id` par un SHA-256. Le pipeline F&B n'a jamais besoin de l'identité
d'un convive : il consomme des comptages.

**Deux réserves à écrire noir sur blanc :**

- ✅ **Le hachage de `guest_id` est désormais poivré** (HMAC-SHA256, `PII_HASH_PEPPER`). Il était
  auparavant un sha256 nu : un `guest_id` PMS a un espace de valeurs restreint, le digest était donc
  rejouable hors ligne par quiconque disposait de la liste des identifiants. Cela reste de la
  **pseudonymisation** (considérant 26), pas de l'anonymisation — rien en aval ne doit le traiter
  autrement. Le poivre n'a **pas de valeur par défaut** : vide, l'application lève
  `PepperNotConfigured` plutôt que de retomber silencieusement sur un hachage nu.
- ⛔ Le stripper agit sur le dictionnaire de réservation. Il **ne protège pas** les champs libres
  (`raw_payload_summary`, `error_message`) qui peuvent recevoir un extrait de payload amont.

### 3.2 Pseudonymisation dans les logs — ✅ complétée le 01/08/2026

Le correctif Q2-03 (PR #187, [HOS-289](https://linear.app/hospitalityagent/issue/HOS-289)) avait
fermé le logger WhatsApp entrant. **Trois points d'écriture y avaient survécu**, corrigés par cette
story via `app/core/pii.pseudonymise()` :

| Fichier | Ce qui était loggé |
|---|---|
| `services/action_logger.py` | numéro brut de l'expéditeur, sur le chemin « profil introuvable » |
| `services/query_parser.py` | idem |
| `workers/receipts_dispatcher.py` | e-mail du manager, à **chaque** envoi réussi |

Les deux premiers sont le **pire** cas, pas le plus bénin : ils ne se déclenchent que pour un
expéditeur *inconnu* — mauvais numéro, ancien manager, test. Il n'existe alors ni contrat ni intérêt
légitime, et le log était le seul endroit où la valeur atterrissait.

### 3.3 Numéro du manager en clair — ⛔ AC3 non satisfaite, et non satisfiable telle qu'écrite

L'AC3 de la story demande que le numéro manager soit « stocké en SHA-256 uniquement, la
correspondance brute ne vivant que dans le profil Supabase Auth chiffré ». **Ce n'est pas
implémentable sans re-plomber le chemin sortant**, et il faut le dire plutôt que de le cocher :

- **Entrant** — `twilio_inbound.py`, `action_logger.py`, `query_parser.py`, `whatsapp_service.py`
  résolvent le profil par `WHERE phone_number = ?`. Un hachage déterministe conviendrait : on hache
  le numéro entrant et on compare les digests.
- **Sortant** — `alert_dispatcher.py` et `receipts_dispatcher.py` passent `phone_number` et
  `notification_email` à Twilio et SendGrid. **On n'envoie pas un WhatsApp à un hachage.** La valeur
  en clair doit être récupérable au moment de l'envoi.

Satisfaire l'AC3 suppose donc de déplacer la valeur en clair vers un magasin chiffré interrogé au
moment de l'envoi. C'est un travail réel, non fait, à arbitrer. **Atténuation en place en
attendant :** la valeur ne transite plus dans les logs (§3.2), le dépôt est privé, RLS actif sur
14 tables, chiffrement au repos Supabase. Le risque résiduel est un accès en base, pas une fuite
par log.

---

## 4. Durées de conservation — spécifiées, non implémentées

> ⚠️ **Aucun job de purge n'existe.** `pg_cron` n'est pas configuré, aucune tâche APScheduler ne
> supprime quoi que ce soit. Tout ce qui suit est une **spécification** (AC5), pas un état.

| Donnée | Durée | Déclencheur | Justification |
|---|---|---|---|
| `pms_sync_logs` (payload brut) | **90 j** | `created_at` | Fenêtre de rejeu/diagnostic ; au-delà, seuls les agrégats servent |
| `demand_anomalies` | 2 ans | `detected_at` | Comparaison saisonnière année sur année |
| `staffing_recommendations` | 2 ans | `created_at` | Idem + mesure d'outcome |
| `agent_action_log` | 5 ans | `created_at` | Traçabilité des actions de l'agent (NFR2 / ADR-0009) |
| `conversational_queries` | **90 j** | `created_at` | Voir §6.2 — c'est la mesure la plus urgente du document |
| `operational_memory` | 36 mois | `created_at` | Aligné sur la couche Semantic d'Anima (DPIA §6) ; au-delà, une mémoire opérationnelle ne décrit plus la même équipe ni le même établissement |
| `restaurant_profiles` | Jusqu'à demande de suppression | — | Donnée de contrat |
| `users` | Jusqu'à demande de suppression | — | Donnée de compte |

**Les sauvegardes font partie de la durée.** Une ligne supprimée en base mais présente dans les
snapshots Supabase n'est pas supprimée. La politique de rétention des sauvegardes doit être bornée
et documentée dans la DPA — elle ne l'est pas.

---

## 5. Modèle d'anonymisation Hive (AC4)

**Statut : *Research*.** La Hive n'est pas construite — `hotel_cohort_features` v1 n'existe pas,
socle gelé (Décision #23 §D4). Ce qui suit est le modèle arrêté, pas un mécanisme en service.

- **Plancher hôtels** : ≥ **5 propriétés** avant qu'un pattern soit publié à la Hive. Protège les
  hôtels contre l'attribution d'un pattern à un établissement identifiable.
- **Plancher personnes** : ≥ **20 clients** par cohorte + **garde de concentration ~90 %**
  (un attribut homogène n'est pas servi). Arbitrage
  [HOS-323](https://linear.app/hospitalityagent/issue/HOS-323) du 01/08/2026.
- **Sous le seuil** : dégradation vers une cohorte plus grossière, jamais un plancher plus bas.
- **Opt-out par hôtel** : drapeau en base, à honorer **rétroactivement** — c'est-à-dire recalculer
  le prior à l'exclusion de l'hôtel sorti. Techniquement non trivial, à prévoir au design.
- **Aucun anonymat n'est revendiqué.** Les agrégats restent traités comme des données personnelles
  tant qu'aucune analyse de ré-identification n'a été produite ni relue. Motif : voir HOS-323.

Ces deux planchers ne protègent pas les mêmes personnes et ne se substituent pas l'un à l'autre.

---

## 6. Écarts matériels constatés

### 6.1 `manager_name`, `phone_number`, `notification_email` en clair

Trois colonnes PII dans `restaurant_profiles`, sans chiffrement applicatif. Voir §3.3 pour pourquoi
le simple hachage ne suffit pas et ce qu'il faudrait faire.

### 6.2 `conversational_queries` — ✅ **corrigé le 01/08/2026**

La [fiche prospect](context/perimetre-et-conformite-prospect.md) affirmait : *« Le canal WhatsApp ne
journalise plus le numéro de téléphone ni le corps des messages entrants »*. C'était **vrai et
incomplet** — le correctif Q2-03 portait sur les **logs**. La table, elle, persistait `from_number`
et `body` en clair, indéfiniment, **par conception** (mécanisme d'idempotence).

C'était le point le plus exposé du système, pour trois raisons cumulées : contenu en texte libre non
contraint (un manager peut y écrire une donnée de santé ou un incident nominatif), expéditeur pas
nécessairement client (un mauvais numéro crée sa ligne, sans base légale), et aucune durée.

**Ce qui a été fait :**

- `from_number` stocke désormais un **HMAC-SHA256 poivré** (`hmac256:…`). La seule chose qui lisait
  cette colonne était la fenêtre de dédup de 60 s — comparer des digests fonctionne exactement
  aussi bien : **l'idempotence n'a jamais eu besoin du clair.**
- **Purge quotidienne à 90 j** — `app/workers/retention_purge.py`, enregistrée sur le scheduler
  partagé. C'est le **premier job de rétention du système** : jusqu'ici les durées existaient dans
  la documentation et nulle part ailleurs, ce qui est la définition d'une durée non respectée.
- Migration `20260801210000_conversational_queries_retention.sql` : index de purge, suppression de
  l'arriéré > 90 j, et écrasement des numéros en clair restants par un marqueur. Le poivre étant un
  secret applicatif, la migration ne peut pas recalculer les digests des lignes existantes ; écraser
  vaut mieux que laisser un numéro en clair vivre 90 jours de plus.

**Ce qui reste en clair, et pourquoi :** `body`. Le service de réponse
(`explainability_service.py`) en a besoin pour répondre à la question posée. Il est purgé à 90 j et
ne doit jamais atteindre un log — c'est écrit dans le `COMMENT ON COLUMN`.

### 6.3 L'AC2 exige un test automatisé qui n'existe pas

« payload PII synthétique → zéro PII en base ». Le `PIIStripper` est présent et correct sur les
champs qu'il connaît ; rien ne le vérifie, et rien ne détecte une PII qui passerait par un champ
libre. Non fait.

---

## 7. Procédure d'exercice des droits (AC6)

> **Statut : *Design*.** Jamais exécutée, jamais testée. Une DSAR non tenue dans les délais est un
> manquement, pas un incident.

### Identification

Le sujet est identifié par : `users.email` (compte), `restaurant_profiles.phone_number` /
`notification_email` (manager), ou un `guest_hashed_id` (convive — nécessite que l'hôtel fournisse
le `guest_id` d'origine, Aetherix ne peut pas remonter le hachage).

### Cascade de suppression

Dans cet ordre, en une transaction :

1. `conversational_queries` — `WHERE from_number = ?`
2. `restaurant_profiles` — colonnes PII neutralisées, la ligne opérationnelle survit (`tenant_id`,
   paramètres de couverts) car elle n'identifie personne
3. `operational_memory` — **la ligne *et* le vecteur**. Un embedding dérivé d'une donnée
   personnelle reste une donnée personnelle : supprimer le texte en laissant le vecteur ne satisfait
   pas l'art. 17
4. `agent_action_log` — purge des champs libres `payload` / `abstention_context`, la ligne d'audit
   survit (traçabilité, art. 17(3)(b))
5. `pms_sync_logs` — `raw_payload_summary`
6. `users` — dernier, sinon les FK cassent
7. **Sauvegardes** — noter la demande dans un registre de suppressions différées, purgée à
   l'expiration de la fenêtre de snapshots

### Export (art. 15)

Même parcours en lecture, sortie JSON. Doit inclure la **logique** de toute décision automatisée qui
a concerné la personne (art. 15(1)(h)) — dans Aetherix, la recommandation et son `triggering_factor`.

### Délai

1 mois (art. 12(3)), prorogeable de 2 mois avec information motivée. **Rien n'est instrumenté pour
tenir ce délai** : la cascade ci-dessus est manuelle.

---

## 8. Ce qui reste à faire

| # | Action | AC | Statut |
|---|---|---|---|
| 1 | Purge 90 j + idempotence sur digest, `conversational_queries` | AC5 | ✅ **fait** (§6.2) |
| 2 | Poivrage des digests d'identifiants (`guest_id`, expéditeur) | AC3 | ✅ **fait** (§3.1) |
| 3 | Pseudonymisation des 4 fuites PII dans les logs | AC3 | ✅ **fait** (§3.2) |
| 4 | Tests des contrôles PII (18 cas) | AC2 | ✅ **fait** — sauf le test bout-en-bout « payload → base », qui exige une base de test |
| 5 | Jobs de rétention sur les **7 durées restantes** du §4 | AC5 | ⛔ non fait — le harnais existe désormais, chaque durée reste à câbler et à tester une par une |
| 6 | Magasin chiffré pour le numéro/e-mail manager, lu au moment de l'envoi | AC3 | ⛔ **à arbitrer** (§3.3) |
| 7 | DSAR exécutable et **testée** de bout en bout | AC6 | ⛔ non fait |
| 8 | `DPO_EMAIL` provisionné | Task 6 | ⛔ non fait |
| 9 | Politique de sauvegarde bornée et documentée | — | ⛔ non fait |
| 10 | DPA type (sous-traitance + volet Hive responsable) | — | ⛔ HOS-115 |

**Ce que cette story a livré :** l'inventaire (AC1), le modèle Hive (AC4), la procédure DSAR sur le
papier (AC6), les tests des contrôles PII (AC2), la fermeture des 4 fuites de logs, le poivrage des
digests, et le **premier job de rétention du système**.

**Ce qu'elle n'a pas livré :** les 7 autres durées, le magasin chiffré, et une DSAR **exécutée**.
La différence entre ce document et la conformité, c'est le tableau ci-dessus — et le point 7 est
celui qui produit une preuve binaire, donc celui qui compte le plus.

---

Voir aussi : [`context/security-review-2026-Q2.md`](context/security-review-2026-Q2.md) ·
[`context/perimetre-et-conformite-prospect.md`](context/perimetre-et-conformite-prospect.md) ·
`context/dpia-anima-2026-08.md` (DPIA Anima — arrive avec la PR #231).
