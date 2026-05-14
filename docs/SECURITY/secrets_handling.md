**Secrets Handling — Guide court**

- **Objectif :** protéger les clés et secrets, réduire la surface d'exposition, et standardiser l'import CI → Fly.

- **Ne jamais** commit `.env` ou fichiers contenant des secrets. `.env` doit rester local et ignoré par Git (déjà en place).

- **Flux recommandé (CI / GitHub Actions)**
  - Stocker les secrets sensibles dans le store sécurisé du provider CI (GitHub Actions Secrets, GitLab CI variables, etc.).
  - Dans la pipeline CI, générer un fichier `.env.fly` filtré (ou composer directement `flyctl secrets import` via STDIN) sans écrire les secrets dans l'historique Git.
  - Exemple minimal (GitHub Actions) :

```yaml
name: Deploy secrets to Fly
on: workflow_dispatch
jobs:
  deploy-secrets:
    runs-on: ubuntu-latest
    steps:
      - name: Install flyctl
        run: curl -sL https://fly.io/install.sh | sh
      - name: Build env and import
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          AUTH_SECRET: ${{ secrets.AUTH_SECRET }}
          # ... autres secrets référencés ici
        run: |
          printf "DATABASE_URL=%s\nAUTH_SECRET=%s\n" "$DATABASE_URL" "$AUTH_SECRET" | $HOME/.fly/bin/flyctl secrets import --app aetherix-backend
```

- **Local → Fly (dev)**
  - Utiliser `scripts/generate_env_fly.ps1` pour produire `.env.fly` localement.
  - Importer via `scripts/clean_env_and_import_fly_secrets.ps1 -EnvFile .env.fly` (ou `type .env.fly | flyctl secrets import --app ...`) — évitez d'imprimer les valeurs.

- **Rotation & accès**
  - Activez MFA sur les comptes GitHub et Fly.
  - Limitez les scopes des clés (least privilege).
  - Alertez et rotatez immédiatement toute clé potentiellement exposée.

- **Audit Git**
  - Vérifiez que `.env` n'existe pas dans l'historique :
    - `git log --all -- .env`
  - Si une clé a été accidentellement committée, révoquez/rotatez la clé et nettoyez l'historique (BFG / git filter-branch) — puis informez l'équipe.

- **Bonnes pratiques**
  - Ne copiez/collez jamais le contenu d'un `.env` dans un chat ou service en ligne.
  - Limitez la durée de vie des secrets quand possible (tokens courts, rotation automatisée).

Fin du guide court.
