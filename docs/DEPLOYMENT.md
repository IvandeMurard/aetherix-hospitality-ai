# Recommandations de déploiement – Aetherix / F&B Agent

Ce document résume les options de déploiement actuelles et les recommandations selon le cas d’usage.

---

## État actuel

| Composant   | Techno    | Déjà déployé              | Fichiers concernés                    |
|------------|-----------|----------------------------|----------------------------------------|
| **API**    | FastAPI   | Oui (HuggingFace Spaces)   | `Dockerfile`, `backend/Procfile`, `backend/render.yaml` |
| **Dashboard** | Streamlit | Non (local uniquement)  | `frontend/` – pas d’image Docker dédiée |

---

## 1. Déployer l’API (backend)

### Option A : HuggingFace Spaces (actuel, recommandé pour démo)

- **Avantages** : Gratuit, démo publique, intégration Git.
- **Config** : Variables dans Settings → Variables and Secrets (voir `docs/HUGGINGFACE_ENV_SETUP.md`).
- **Port** : 7860 (défini dans le `Dockerfile`).
- **Commande** : Le `Dockerfile` à la racine lance `uvicorn backend.main:app --host 0.0.0.0 --port 7860`.

À la racine du repo, le build doit pouvoir résoudre `backend.main:app`. Si le contexte de build HF est la racine du repo, le `Dockerfile` actuel suppose que le `WORKDIR` est `/app` et que `backend/` est copié ; il faut donc lancer uvicorn avec le module complet : `backend.main:app` (déjà le cas dans le Dockerfile).

### Option B : Render

- **Fichier** : `backend/render.yaml`.
- **Important** : Sur Render, définir la **root directory** du service sur `backend` (pas la racine du repo). Ainsi `uvicorn main:app` et `pip install -r requirements.txt` s’exécutent dans `backend/`.
- **Variables** : À renseigner dans le dashboard Render (ANTHROPIC_API_KEY, QDRANT_*, MISTRAL_*, SUPABASE_*, etc.).
- **Health check** : `/health` est déjà configuré.

### Option C : Autre PaaS (Railway, Fly.io, etc.)

- Utiliser la même commande que le Procfile :  
  `uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}`  
  avec la **root** du service = `backend/`.
- Exposer le port fourni par la plateforme et définir toutes les variables d’environnement nécessaires.

---

## 2. Déployer le dashboard (Streamlit)

Le frontend appelle l’API via `AETHERIX_API_BASE` (défaut : `http://localhost:8000`). En production, il doit pointer vers l’URL publique de l’API.

### Option A : Streamlit Community Cloud (recommandé pour MVP)

**📖 Guide détaillé** : Voir [docs/STREAMLIT_CLOUD_SETUP.md](STREAMLIT_CLOUD_SETUP.md)

**Résumé rapide** :
1. Pousser le code sur GitHub.
2. Aller sur [share.streamlit.io](https://share.streamlit.io), connecter le repo.
3. **Main file path** : `frontend/app.py` ⚠️ (pas `streamlit_app.py` !)
4. **Python version** : `3.11` (dans Advanced Settings)
5. **Secrets** (format TOML dans Advanced Settings) :
   ```toml
   AETHERIX_API_BASE = "https://ivandemurard-fb-agent-api.hf.space"
   ```
   *(Pas de slash final)*
6. Streamlit Cloud build et déploie automatiquement ; le dashboard appelle ton API HuggingFace Spaces.

### Option B : Render (ou autre) en second service

- Créer un second “Web Service” pour le frontend.
- **Root** : `frontend/`.
- **Build** : `pip install -r requirements.txt`.
- **Start** : `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`.
- **Variable** : `AETHERIX_API_BASE` = URL du service API (ex. `https://fb-agent-api.onrender.com`).

### Option C : Docker + docker-compose (self‑hosted / VPS)

- Une image pour l’API (ex. le `Dockerfile` actuel).
- Une image pour Streamlit (voir exemple `docker-compose` ci‑dessous).
- En production, mettre un reverse proxy (Traefik, Caddy, nginx) devant, avec HTTPS.

---

## 3. Variables d’environnement à prévoir

### API (backend)

| Variable           | Obligatoire | Description |
|--------------------|-------------|-------------|
| ANTHROPIC_API_KEY  | Oui         | Claude (raisonnement) |
| QDRANT_URL         | Oui         | Cluster Qdrant |
| QDRANT_API_KEY     | Oui         | Auth Qdrant |
| MISTRAL_API_KEY    | Oui         | Embeddings |
| SUPABASE_URL       | Recommandé  | PostgreSQL / profils |
| SUPABASE_KEY       | Recommandé  | Clé service_role |
| DISABLE_FILE_LOGGING | Optionnel | `true` en prod pour limiter les écritures disque |

### Dashboard (frontend)

| Variable           | Obligatoire en prod | Description |
|--------------------|----------------------|-------------|
| AETHERIX_API_BASE  | Oui (si API déployée) | URL de base de l’API (sans slash final) |

---

## 4. Recommandations synthétiques

1. **Garder l’API sur HuggingFace Spaces** pour la démo et la stabilité actuelle ; documenter l’URL dans le README (ex. “Dashboard: à déployer sur Streamlit Cloud en pointant vers cette API”).
2. **Déployer le dashboard sur Streamlit Community Cloud** en premier : peu de config, une seule variable `AETHERIX_API_BASE` vers l’API HF (ou Render).
3. **Render (ou équivalent)** : utiliser pour une API de “staging” ou si tu préfères tout héberger au même endroit ; bien définir la root du service sur `backend/` pour `render.yaml`.
4. **Accès réseau local** : pour tester depuis un autre appareil sur le même réseau, lancer Streamlit avec `--server.address 0.0.0.0` et le backend avec `host="0.0.0.0"` (voir section “Accès local” dans le README principal si tu l’ajoutes).
5. **Sécurité** : ne jamais commiter de clés ; utiliser les secrets des plateformes (HF, Render, Streamlit Cloud). En production, mettre l’API et le dashboard derrière HTTPS (fourni par les plateformes ou par un reverse proxy en self‑hosted).

---

## 5. Diagnostic HuggingFace Spaces

### Vérifier que l'API fonctionne

```bash
# Health check
curl https://ivandemurard-fb-agent-api.hf.space/health

# Diagnostic complet
curl https://ivandemurard-fb-agent-api.hf.space/diagnostic
```

### Vérifier les logs

```bash
# Utiliser les scripts de diagnostic
python scripts/check_space_logs.py
python scripts/fetch_space_logs.py
```

Ou consulter directement : https://huggingface.co/spaces/IvandeMurard/fb-agent-api/logs

### Vérifier les variables d'environnement

```bash
python scripts/verify_hf_secrets.py
```

### Problèmes courants

**Erreur 403 :**
- L'espace HF peut être en "sleep" → Redémarrer l'espace
- Variables d'environnement manquantes → Vérifier avec `verify_hf_secrets.py`
- Backend crashé → Vérifier les logs

**Timeout :**
- Backend non démarré → Vérifier les logs de démarrage
- Cold start HuggingFace (~30s) → Attendre le démarrage complet

**CORS errors :**
- Vérifier que CORS est configuré dans `backend/main.py`
- Vérifier les logs pour "[CORS] Configured"

Voir [docs/TROUBLESHOOTING.md](TROUBLESHOOTING.md) pour plus de détails.

## 6. Résumé des commandes utiles

```bash
# Backend en local (écoute local uniquement)
cd backend && uvicorn main:app --reload --port 8000

# Backend en local, accessible sur le réseau (autre machine / même WiFi)
cd backend && uvicorn main:app --host 0.0.0.0 --port 8000

# Dashboard en local
cd frontend && streamlit run app.py

# Dashboard en local, accessible sur le réseau
cd frontend && streamlit run app.py --server.address 0.0.0.0
```

### Stack complète avec Docker Compose (local ou VPS)

À la racine du repo :

```bash
# Créer un .env à la racine avec les clés API (ANTHROPIC, QDRANT_*, MISTRAL_*, SUPABASE_*)
docker compose up --build
```

- **API** : http://localhost:8000  
- **Dashboard** : http://localhost:8501  

Le dashboard utilise `AETHERIX_API_BASE=http://backend:7860` pour appeler l’API depuis le réseau Docker. Sur un VPS, placer un reverse proxy (Caddy, nginx) devant avec HTTPS.
