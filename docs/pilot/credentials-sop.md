# Credentials Management SOP — Apaleo Design Partner

> **Scope** : comment Aetherix reçoit, stocke, fait tourner et révoque les credentials Apaleo (`APALEO_CLIENT_ID` / `APALEO_CLIENT_SECRET`) d'un design partner réel pendant le pilot Phase 3.
> **Story** : HOS-175 AC3.
> **Statut** : SOP obligatoire avant tout onboarding HOS-176.
> **Owner** : Ivan de Murard (Aetherix).

---

## 1. Principes non-négociables

- **Read-only PMS** durant tout le pilot (CLAUDE.md Décision #7). Le client OAuth2 du partner DOIT être créé avec scopes read-only (`reservations.read`, `availability.read`, `properties.read`).
- **Jamais en session IA** : aucun secret n'entre dans une conversation Claude, ChatGPT, ou un prompt LLM. Si un partner envoie un secret en clair dans un canal IA, on **invalide immédiatement** et on demande une rotation.
- **Jamais par email non chiffré** : email = canal non sécurisé. Utiliser 1Password share, Bitwarden Send, ou Signal.
- **Stockage exclusif** : Fly.io secrets (`flyctl secrets set`) — CLAUDE.md Décision #17. Pas de `.env` local, pas de fichier sur le disque dev.
- **Audit trail** : chaque rotation, révocation, ou incident est logué dans `docs/pilot/credentials-log.md` (à créer au premier onboarding, gitignored si contenu sensible).

---

## 2. Étapes — Onboarding d'un nouveau design partner

### Étape 1 — Partner génère les credentials

Côté partner (instructions à inclure dans le mail post-discovery call) :

1. Se connecter à [Apaleo Developer Portal](https://apaleo.dev/).
2. Aller dans **Apps → New App → "Aetherix F&B Pilot"**.
3. **Scopes requis (read-only uniquement)** :
   - `reservations.read`
   - `availability.read`
   - `properties.read`
4. Cocher la property cible du pilot (1 seule property — pas tout le portfolio).
5. Générer `client_id` + `client_secret`. **Le secret n'est affiché qu'une fois** — copier immédiatement.
6. Envoyer les credentials à Ivan via **1Password share** (lien expirant 24h) ou **Bitwarden Send**. Pas d'email, pas de Slack public, pas de message IA.

> **⚠️ À mettre à jour — Apaleo Fine-Grained API (FGA)** (annonce du forum développeurs Apaleo reçue le 15/10/2026 ; guide `apaleo.dev/guides/api/scopes.html`). Un nouveau modèle d'accès s'applique aux **nouvelles apps** : type choisi **une seule fois à l'enregistrement, définitif** ; permissions au format `service.resource.action` (ex. `core.reservations.read`) à la place des scopes `resource.action` ; propriétés autorisées par l'hôtel **à la connexion** (modifiables ensuite, effet immédiat) ; rôle de l'utilisateur qui a connecté l'app vérifié à chaque appel. Les apps existantes restent en scopes. Apaleo recommande FGA.
>
> **Non appliqué ici tant qu'Apaleo n'a pas répondu** : les étapes 3 et 4 ci-dessus décrivent le modèle par scopes (property cochée à la création de l'app). Avant d'envoyer ces instructions à un partner : (1) enregistrer l'app en FGA d'emblée — le type ne peut pas être changé après coup ; (2) lever les inconnues — comment un client `client_credentials` FGA est restreint par propriété ; si la règle « rôle de l'utilisateur qui a connecté l'app » s'applique à ce flux (risque de coupure silencieuse de l'agent quotidien si ce rôle change — à traiter par un guardrail typé 403/400 + alerte, Epic 12) ; quelle granularité sur les données guest (la doc est muette sur la PII). Aucun changement de principe : la **Décision #7 (read-only)** et la règle « une seule property » restent.
>
> **Point de code à lever avant HOS-176** : `ApaleoPMSAdapter` (chemin `apaleo_raw` de `/pms/sync`, utilisé quand ni mock ni MCP) demande en dur le scope `offline_access openid profile read:occupancy read:revenue write:schedules` (`backend/app/services/apaleo_adapter.py:66`). Il contient un scope `write:` alors que cette SOP exige du read-only (le garde-fou `APALEO_READONLY` n'agit que côté code, pas sur le jeton), et ces noms ne suivent pas le format documenté par Apaleo (`ressource.action`). `ApaleoMCPAdapter` n'envoie aucun scope au token endpoint. **Non testé contre l'API** : comportement face à un client read-only inconnu.

### Étape 2 — Ivan reçoit et stocke (hors Claude, hors session IA)

```powershell
# Terminal local Ivan — JAMAIS dans une session Claude/IA
flyctl secrets set `
  APALEO_PARTNER_CLIENT_ID="<copié depuis 1Password share>" `
  APALEO_PARTNER_CLIENT_SECRET="<copié depuis 1Password share>" `
  APALEO_PARTNER_PROPERTY_ID="<id property pilot>" `
  --app aetherix-backend
```

Le `flyctl secrets set` :
- chiffre les valeurs at-rest dans Fly.io,
- ne les ré-affiche jamais (`flyctl secrets list` ne montre que les noms),
- déclenche un rolling restart de l'instance Paris (`cdg`).

**Immédiatement après** : supprimer le 1Password share (révoquer le lien), vider l'historique terminal de la session (`Clear-History` PowerShell), ne pas committer.

### Étape 3 — Validation hors-prod

Sur la machine dev d'Ivan, créer un fichier `.env.partner-validation` **gitignored** (vérifier `.gitignore` avant) avec les mêmes valeurs, **temporairement**, pour exécuter :

```powershell
$env:APALEO_CLIENT_ID = "<client_id>"
$env:APALEO_CLIENT_SECRET = "<client_secret>"
$env:APALEO_MCP_SERVER_URL = "https://mcp.apaleo.com/mcp/"
python scripts/ops/validate_apaleo_sandbox.py --property-id <property_id>
```

Critère de succès :
- Probe MCP OAuth2 → 200.
- `ListProperties` → property attendue présente.
- `ListReservations` → ≥ 60 jours d'historique disponible.

En cas d'échec → ne pas pousser sur Fly.io, retour au partner pour vérifier les scopes.

Une fois validé : **supprimer `.env.partner-validation` immédiatement** (`Remove-Item .env.partner-validation`). Vider l'historique shell.

### Étape 4 — Déploiement et premier run

- `flyctl deploy` (si pas déjà déclenché par `secrets set`).
- Vérifier `GET https://aetherix-backend.fly.dev/pms/mcp/probe` retourne 200 et la property du partner.
- Lancer le job d'historique : `POST /api/v1/predictions/train` (CLAUDE.md Décision #13).
- Marquer dans `docs/pilot/credentials-log.md` : `<date> | onboarded | <property_name> | <ivan>`.

---

## 3. Rotation policy

**Cadence obligatoire** : tous les **90 jours**, ou plus tôt si :

- Suspicion de compromission (laptop perdu, fuite repo, employé partner qui quitte avec accès Developer Portal).
- Apaleo publie un avis de sécurité concernant l'OAuth2.
- Le partner change de gestionnaire de comptes côté hôtel.

**Procédure rotation** :

1. Partner régénère client_secret dans Apaleo Developer Portal (le `client_id` reste, seul le secret change).
2. Partner envoie le nouveau secret via 1Password share.
3. Ivan : `flyctl secrets set APALEO_PARTNER_CLIENT_SECRET="<new>" --app aetherix-backend` (rolling restart auto).
4. Vérifier probe MCP en post-rotation.
5. Logger dans `credentials-log.md` : `<date> | rotated | <property_name> | <ivan>`.

**Fenêtre de rotation acceptable** : ≤ 1h entre génération nouveau secret et déploiement. Pas de chevauchement avec l'ancien (Apaleo invalide l'ancien dès rotation).

---

## 4. Révocation (fin de pilot ou résiliation)

Trigger : fin des 4 semaines pilot, ou résiliation à l'initiative du partner / Aetherix.

1. **Partner** révoque l'app dans Apaleo Developer Portal (**Apps → "Aetherix F&B Pilot" → Revoke**). Cette action est la seule qui garantit la révocation côté Apaleo — Aetherix ne peut pas révoquer un secret partner.
2. **Ivan** supprime les secrets côté Fly.io :
   ```powershell
   flyctl secrets unset APALEO_PARTNER_CLIENT_ID APALEO_PARTNER_CLIENT_SECRET APALEO_PARTNER_PROPERTY_ID --app aetherix-backend
   ```
3. **Données de l'hôtel** (Décision #43, HOS-346) : d'abord l'export remis au partner, `GET /api/v1/hotels/<tenant_id>/data/export` ; puis la suppression, `GET …/data/deletion-plan` (plan + nombre de lignes, rien n'est touché) et `POST …/data/deletion` avec `{"confirm_tenant_id": "<tenant_id>", "dry_run": false}`. Le plan couvre toutes les tables de l'hôtel (inventaire testé dans `app/services/hotel_data.py`) ; les personnes (compte du manager) suivent la DSAR (`dsar.py`). Joindre au partner les limites du rapport (sauvegardes Supabase).
4. **Logger** dans `credentials-log.md` : `<date> | revoked | <property_name> | <ivan>` + raison.
5. **Confirmer au partner par email** : credentials révoqués, export remis, données supprimées (rapport de suppression joint), attestation RGPD article 17 (droit à l'effacement) si demandée.

---

## 5. Incident response — credential leak suspecté

Si fuite confirmée ou suspectée :

1. **Immédiat** (< 15 min) :
   - `flyctl secrets unset` sur le secret compromis (coupe l'accès Aetherix).
   - Notifier le partner par téléphone (pas d'email — peut être surveillé).
   - Partner révoque l'app dans Apaleo Developer Portal.
2. **< 4h** :
   - Audit logs Apaleo (le partner peut exporter les access logs OAuth2) pour identifier l'origine.
   - Audit `agent_action_log` (Aetherix observability ADR 0003) pour vérifier qu'aucune action non-attendue n'a été exécutée pendant la fenêtre de compromission.
3. **< 24h** :
   - Rapport incident dans `docs/pilot/credentials-log.md` : timeline, scope du leak, données potentiellement exposées.
   - Si données partner exposées : notification RGPD article 33 sous 72h à la CNIL (l'autorité française — vérifier juridiction du partner si non-FR).
4. **Post-mortem** sous 7 jours, documenté dans `docs/pilot/credentials-log.md`.

---

## 6. Checklist Go/No-Go onboarding

Avant d'exécuter `flyctl secrets set` pour un partner :

- [ ] Discovery call §3 onboarding-kit.md complété, 8/8 prereqs cochés.
- [ ] Partner a généré l'app Apaleo avec scopes **read-only uniquement** (vérifier dans le portal screenshot envoyé par le partner).
- [ ] Credentials reçus via canal chiffré (1Password share / Bitwarden Send / Signal). **Pas d'email.**
- [ ] `.gitignore` vérifié — `.env.partner-validation` exclu.
- [ ] Historique shell vide avant `flyctl secrets set`.
- [ ] Date de prochaine rotation notée dans `credentials-log.md` (J + 90).

---

## Références

- [Source: CLAUDE.md Décision #7] — Apaleo read-only Phase 0, loguer toutes actions agent
- [Source: CLAUDE.md Décision #17] — Fly.io secrets handling, region `cdg`
- [Source: docs/secrets_handling.md] — procédure générale secrets Fly.io
- [Source: HOS-111] — RLS Supabase 14/14 tables
- [Source: HOS-112] — webhook HMAC validation
- [Source: ADR 0003] — observability `agent_action_log`
- [Apaleo Developer Portal](https://apaleo.dev/)
- [Fly.io secrets docs](https://fly.io/docs/reference/secrets/)
