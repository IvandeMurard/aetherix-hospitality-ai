# Guide de Dépannage - Aetherix

Ce guide aide à résoudre les problèmes courants rencontrés avec Aetherix, notamment les erreurs 403 et les problèmes de connexion API.

## Erreur 403 - Forbidden

### Symptômes

- Les prédictions ne se chargent pas
- Message d'erreur : "Prediction API returned status 403"
- Les KPI cards affichent "—" (aucune donnée)

### Causes possibles

1. **HuggingFace Spaces en mode "sleep"**
   - Après une période d'inactivité, HF Spaces peut mettre l'espace en veille
   - Le backend n'est pas accessible jusqu'au redémarrage

2. **Backend non démarré ou crashé**
   - Variables d'environnement manquantes
   - Erreur au démarrage du backend
   - Port incorrect ou non exposé

3. **Problème CORS**
   - Configuration CORS incorrecte
   - Headers manquants dans les requêtes

4. **Variables d'environnement manquantes**
   - ANTHROPIC_API_KEY
   - QDRANT_URL / QDRANT_API_KEY
   - MISTRAL_API_KEY
   - SUPABASE_URL / SUPABASE_KEY

### Solutions

#### Solution 1 : Redémarrer l'espace HuggingFace (Quick Fix)

1. Aller sur https://huggingface.co/spaces/IvandeMurard/fb-agent-api
2. Cliquer sur le bouton **"Restart"** ou **"Reboot"** (en haut à droite)
3. Attendre 2-3 minutes pour le redémarrage complet
4. Rafraîchir le dashboard

#### Solution 2 : Vérifier l'accessibilité de l'API

Tester directement l'API avec curl :

```bash
# Test health endpoint
curl https://ivandemurard-fb-agent-api.hf.space/health

# Test diagnostic endpoint
curl https://ivandemurard-fb-agent-api.hf.space/diagnostic

# Test predict endpoint
curl -X POST "https://ivandemurard-fb-agent-api.hf.space/predict" \
  -H "Content-Type: application/json" \
  -d '{"restaurant_id": "hotel_main", "service_date": "2026-02-09", "service_type": "dinner"}'
```

**Interprétation des résultats :**
- ✅ `200 OK` → API fonctionne, problème côté frontend
- ❌ `403 Forbidden` → Problème backend/HF Spaces
- ❌ `Timeout` → Backend non démarré ou en sleep
- ❌ `Connection refused` → Backend non accessible

#### Solution 3 : Vérifier les logs HuggingFace Spaces

Utiliser les scripts de diagnostic :

```bash
# Vérifier les logs
python scripts/check_space_logs.py

# Ou récupérer les logs récents
python scripts/fetch_space_logs.py
```

**Vérifier dans les logs :**
- Messages de démarrage : `[STARTUP]`, `[CORS] Configured`
- Erreurs de variables manquantes
- Erreurs CORS
- Erreurs de connexion à Qdrant/Claude

#### Solution 4 : Vérifier les variables d'environnement

```bash
# Vérifier les secrets configurés
python scripts/verify_hf_secrets.py
```

**Variables requises :**
- `ANTHROPIC_API_KEY` - Clé API Anthropic (Claude)
- `QDRANT_URL` - URL du cluster Qdrant
- `QDRANT_API_KEY` - Clé API Qdrant
- `MISTRAL_API_KEY` - Clé API Mistral (embeddings)
- `SUPABASE_URL` - URL du projet Supabase
- `SUPABASE_KEY` - Clé service_role Supabase

**Si des variables manquent :**
1. Aller sur https://huggingface.co/spaces/IvandeMurard/fb-agent-api/settings
2. Section "Variables and Secrets"
3. Ajouter les variables manquantes
4. Redémarrer l'espace

#### Solution 5 : Utiliser l'endpoint de diagnostic

L'endpoint `/diagnostic` fournit des informations détaillées :

```bash
curl https://ivandemurard-fb-agent-api.hf.space/diagnostic
```

**Réponse attendue :**
```json
{
  "status": "running",
  "cors_configured": true,
  "missing_env_vars": [],
  "env_vars_count": 6,
  "backend_status": "ok"
}
```

**Si `missing_env_vars` n'est pas vide :** Ajouter les variables manquantes sur HF Spaces.

#### Solution 6 : Utiliser l'API locale pour développement

Si vous développez localement et que l'API HF ne fonctionne pas :

1. Démarrer le backend localement :
   ```bash
   cd backend
   uvicorn main:app --reload --port 8000
   ```

2. Configurer le frontend pour utiliser l'API locale :
   ```bash
   # Dans Streamlit Cloud secrets ou .env local
   USE_LOCAL_API=true
   ```

   Ou explicitement :
   ```bash
   AETHERIX_API_BASE=http://localhost:8000
   ```

## Erreurs de connexion

### Symptômes

- "Unable to connect to backend API"
- Timeout sur les requêtes
- Erreurs de réseau

### Solutions

1. **Vérifier que le backend est démarré**
   - Test `/health` endpoint
   - Vérifier les logs

2. **Vérifier l'URL de l'API**
   - Dashboard affiche l'URL utilisée dans les logs
   - Vérifier `AETHERIX_API_BASE` dans les secrets Streamlit Cloud

3. **Vérifier le firewall/réseau**
   - Certains réseaux peuvent bloquer les requêtes vers HF Spaces
   - Essayer depuis un autre réseau

## Problèmes de performance

### Prédictions lentes

- **Première prédiction** : Peut prendre 60-90 secondes (cold start + embeddings + LLM)
- **Prédictions suivantes** : Devraient être plus rapides (cache)

### Solutions

1. Attendre la première prédiction (normal)
2. Utiliser le cache pour les dates déjà chargées
3. Vérifier les logs pour identifier les goulots d'étranglement

## Problèmes de données

### Prédictions incorrectes

- Vérifier que les patterns sont chargés dans Qdrant
- Vérifier que les variables d'environnement sont correctes
- Vérifier les logs pour voir quels patterns sont utilisés

### Données manquantes

- Vérifier que Supabase est configuré correctement
- Vérifier les connexions aux APIs externes (Qdrant, Mistral, Anthropic)

## Support supplémentaire

### Ressources

- **Logs HuggingFace Spaces** : https://huggingface.co/spaces/IvandeMurard/fb-agent-api/logs
- **Documentation API** : https://ivandemurard-fb-agent-api.hf.space/docs
- **Health Check** : https://ivandemurard-fb-agent-api.hf.space/health
- **Diagnostic** : https://ivandemurard-fb-agent-api.hf.space/diagnostic

### Commandes utiles

```bash
# Vérifier les secrets HF Spaces
python scripts/verify_hf_secrets.py

# Récupérer les logs
python scripts/fetch_space_logs.py

# Configurer les secrets (si manquants)
python scripts/setup_hf_secrets.py
```

## Checklist de dépannage rapide

- [ ] Redémarrer l'espace HuggingFace
- [ ] Tester `/health` endpoint avec curl
- [ ] Tester `/diagnostic` endpoint
- [ ] Vérifier les logs HF Spaces
- [ ] Vérifier les variables d'environnement
- [ ] Vérifier que le backend démarre correctement
- [ ] Vérifier la configuration CORS dans les logs
- [ ] Essayer depuis un autre réseau/navigateur
