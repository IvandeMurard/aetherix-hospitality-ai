# Secrets Rotation & History Purge Playbook

Objectif: révoquer/rotater les clés exposées (ou potentiellement exposées), purger l'historique Git des valeurs sensibles et documenter les actions à mener.

IMPORTANT: Ne jamais inclure de valeurs secrètes dans ce document. Toutes les commandes ci‑desses manipulent des noms ou des actions — les valeurs réelles doivent être gérées dans le vault/console du provider.

## 1) Liste rapide d'actions (ordre recommandé)
1. Identifier la(s) clé(s) exposée(s) et lister services affectés (ex: Anthropic, Twilio, Supabase, SendGrid, Mistral, etc.).
2. Pour chaque provider, révoquer / rotater la clé (via console provider). Documenter le nouveau secret dans le vault CI (ex: GitHub Secrets).
3. Mettre à jour les environnements (Fly, CI, etc.) avec les nouvelles valeurs via `flyctl secrets` ou équivalent.
4. Purger l'historique Git si la valeur a été committée (BFG/git-filter-repo), puis force-push et informer l'équipe.
5. Lancer une vérification post-rotation (tests d'intégration, smoke tests) et confirmer l'accès applicatif.

## 2) Rotation par provider (exemples)
- Anthropic (Claude):
  - Console Anthropic → rotate key → copy new key.
  - `gh secret set ANTHROPIC_API_KEY --body "$NEW"` (CI) ou ajouter dans Vault.
- Twilio:
  - Dashboard Twilio → Create new API Key (or regenerate auth token) → update `TWILIO_AUTH_TOKEN` in CI and Fly.
- Supabase:
  - Rotate `SUPABASE_KEY`/service roles in Supabase > Settings → Update in Fly/CI.
- SendGrid/GCP/Mistral/Other: follow provider console rotate steps and update CI/vault.

## 3) Purger l'historique Git (si valeurs committées)
Note: Ces opérations réécrivent l'historique — coordonnez avec l'équipe.

Option A — git-filter-repo (recommandé):
1. Installer `git-filter-repo` (pip install git-filter-repo).
2. Faire un backup: `git clone --mirror <repo> repo-mirror.git`
3. Exécuter (exemple pour supprimer `AUTH_SECRET`):
   ```bash
   cd repo-mirror.git
   git filter-repo --invert-paths --paths-glob ":" --replace-refs delete-no-add --commit-callback 'if b"AUTH_SECRET" in commit.message: commit.message=b"[redacted]"'
   ```
   (Remplacer par règles adaptées — ou utiliser `--replace-text` with a patterns file.)
4. Push force vers origin: `git push --force --all && git push --force --tags`.

Option B — BFG Repo-Cleaner (simpler):
1. `git clone --mirror git@github.com:owner/repo.git`
2. `java -jar bfg.jar --replace-text passwords.txt repo.git` where passwords.txt lists sensitive tokens.
3. `cd repo.git && git reflog expire --expire=now --all && git gc --prune=now --aggressive`
4. `git push --force`.

Après purge: Informez tous les contributeurs qu'ils doivent recloner (fresh clone) ou reset leurs branches locales.

## 4) PR / change template (suggestion)
- Title: `chore(secrets): rotate <provider> keys and purge history`
- Body should include:
  - Affected keys (names only)
  - Providers rotated
  - Commits purged (hashes) and reason
  - Post-rotation checks performed

## 5) Checklist de notification (interne)
- Alerter les responsables sécurité + CTO.
- Demander rotation des clés externes (3rd-party) si partagées.
- Demander à l'équipe CI de vérifier les secrets stockés (GitHub secrets, Vault).
- Plan de mitigation si rollback nécessaire.

## 6) Prévention (déployer maintenant)
- Ajoutez pre-commit hook (git-secrets or truffleHog pre-commit) pour empêcher commit de patterns courants.
- Ajoutez CI job qui grep les motifs `sk-`, `AIzaSy`, `SG\.`, `sb_publishable_`, `twilio` etc. et échoue le pipeline si trouvé.

## 7) Commandes rapides (exemples, sans valeurs)
- Rotate example provider key (manual step):
  - `# in provider console -> generate new key`
  - `flyctl secrets set AUTH_SECRET="<new>" --app aetherix-backend`
- Purge (BFG) example:
  - `git clone --mirror git@github.com:IvandeMurard/aetherix-hospitality-ai.git`
  - `java -jar bfg.jar --replace-text passwords.txt aetherix-hospitality-ai.git`
  - `cd aetherix-hospitality-ai.git && git reflog expire --expire=now --all && git gc --prune=now --aggressive`
  - `git push --force --all && git push --force --tags`

---
_Ce playbook est un point de départ — adaptez selon vos procédures ops et accord RH/Legal._
