# Configuration des Variables d'Environnement sur HuggingFace Spaces

## Méthode 1 : Interface Web (Recommandée)

### Étape 1 : Accéder aux Settings
1. Allez sur votre espace : https://huggingface.co/spaces/IvandeMurard/fb-agent-api
2. **En haut à droite**, cherchez l'icône d'engrenage ⚙️ ou le bouton **"Settings"**
3. Si vous ne voyez pas Settings, essayez cette URL directe :
   ```
   https://huggingface.co/spaces/IvandeMurard/fb-agent-api/settings
   ```

### Étape 2 : Trouver "Variables and Secrets"
Dans la page Settings, cherchez la section **"Variables and Secrets"** ou **"Repository secrets"**.

**Emplacements possibles :**
- Section dans le menu de gauche
- Section principale au milieu de la page
- Onglet séparé dans Settings

### Étape 3 : Ajouter les secrets
Pour chaque variable, cliquez sur **"New secret"** ou **"Add secret"** :

1. **QDRANT_URL**
   - Name: `QDRANT_URL`
   - Value: `https://f9ade3b3-7d26-4502-9ab7-ca8abf3004f7.europe-west3-0.gcp.cloud.qdrant.io:6333`

2. **QDRANT_API_KEY**
   - Name: `QDRANT_API_KEY`
   - Value: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.kHtDSrbNb8aKYQbg5F5FEm-eExVXyiSmbo6oL5UOntM`

3. **MISTRAL_API_KEY**
   - Name: `MISTRAL_API_KEY`
   - Value: `8NizwlIAUPZr8w2o2POWrYdQULFYgOIM`

4. **ANTHROPIC_API_KEY**
   - Name: `ANTHROPIC_API_KEY`
   - Value: (votre clé Anthropic depuis .env)

5. **SUPABASE_URL**
   - Name: `SUPABASE_URL`
   - Value: URL de votre projet Supabase (ex. `https://xxxxx.supabase.co`)
   - Où la trouver : Supabase Dashboard → Project Settings → API

6. **SUPABASE_KEY**
   - Name: `SUPABASE_KEY`
   - Value: Clé **service_role** du projet (feedback loop, stockage des prédictions)
   - Où la trouver : Supabase Dashboard → Project Settings → API → service_role

### Étape 4 : Redémarrer l'espace
Après avoir ajouté toutes les variables :
1. Allez dans l'onglet **"App"**
2. Cliquez sur **"Restart"** ou **"Reboot"**

---

## Méthode 2 : API Python (Alternative)

Si vous ne trouvez pas le menu dans l'interface web, utilisez l'API Python :

### Installation
```bash
pip install huggingface_hub
```

### Obtenir votre token HuggingFace
1. Allez sur : https://huggingface.co/settings/tokens
2. Créez un nouveau token avec les permissions "Write"
3. Copiez le token

### Exécuter le script
```bash
# Ajouter le token à votre .env
echo "HF_TOKEN=votre_token_ici" >> .env

# Exécuter le script
python scripts/setup_hf_secrets.py
```

Le script va automatiquement :
- Lire les variables depuis votre `.env`
- Les ajouter comme secrets sur HuggingFace Spaces
- Vous indiquer quand redémarrer l'espace

---

## Vérification

Après configuration, testez l'endpoint :
```bash
curl -X POST "https://ivandemurard-fb-agent-api.hf.space/predict" \
  -H "Content-Type: application/json" \
  -d '{"restaurant_id": "test", "service_date": "2025-01-18", "service_type": "dinner"}'
```

Vérifiez que les patterns ont `"source": "qdrant"` au lieu de `"source": "mock"`.

---

## Dépannage

**Si vous ne voyez pas "Settings" :**
- Vérifiez que vous êtes connecté avec le compte `IvandeMurard`
- Vérifiez que vous avez les permissions Owner/Admin sur l'espace
- Essayez l'URL directe : `/settings` à la fin de l'URL de l'espace

**Si "Variables and Secrets" n'apparaît pas :**
- Certains espaces Docker peuvent avoir une interface différente
- Utilisez la Méthode 2 (API Python) à la place
