# Déploiement Vercel — Aetherix Dashboard

## Option 1 : Via l'interface Vercel (recommandé)

### Étape 1 : Connexion GitHub

1. Aller sur [vercel.com](https://vercel.com) et se connecter avec GitHub
2. Cliquer sur **"Add New Project"** ou **"Import Project"**

### Étape 2 : Sélectionner le repo

1. Choisir le repo : `IvandeMurard/Hospitality-Operations-Agentic-AI-B2B`
2. Vercel détecte automatiquement Next.js

### Étape 3 : Configuration du projet

**Paramètres importants** (car le dashboard est dans un sous-dossier) :

| Paramètre | Valeur |
|-----------|--------|
| **Framework Preset** | Next.js |
| **Root Directory** | `aetherix-dashboard` ⚠️ **CRITIQUE** |
| **Build Command** | `npm run build` (ou laisser vide, Vercel détecte) |
| **Output Directory** | `.next` (par défaut) |
| **Install Command** | `npm install` (par défaut) |

### Étape 4 : Variables d'environnement

Ajouter dans **Environment Variables** :

| Variable | Valeur |
|----------|--------|
| `NEXT_PUBLIC_API_URL` | `https://ivandemurard-fb-agent-api.hf.space` |

⚠️ **Important** : Ne pas ajouter de slash final (`/`) à l'URL.

### Étape 5 : Déployer

1. Cliquer sur **"Deploy"**
2. Vercel va :
   - Installer les dépendances (`npm install` dans `aetherix-dashboard/`)
   - Builder (`npm run build`)
   - Déployer

### Étape 6 : URL de production

Après le déploiement, Vercel génère une URL comme :
- `https://aetherix-dashboard-xxx.vercel.app`

Tu peux aussi configurer un domaine personnalisé dans **Settings → Domains**.

---

## Option 2 : Via CLI Vercel

### Installation CLI

```bash
npm install -g vercel
```

### Connexion

```bash
vercel login
```

### Déploiement depuis le dashboard

```bash
cd aetherix-dashboard
vercel
```

**Première fois** :
- Vercel demande le projet (créer nouveau ou lier à existant)
- **Root Directory** : répondre `aetherix-dashboard` ou configurer dans `vercel.json`

### Variables d'environnement (CLI)

```bash
cd aetherix-dashboard
vercel env add NEXT_PUBLIC_API_URL
# Entrer: https://ivandemurard-fb-agent-api.hf.space
# Sélectionner: Production, Preview, Development
```

### Déploiement production

```bash
cd aetherix-dashboard
vercel --prod
```

---

## Configuration automatique : `vercel.json` (optionnel)

Si tu veux que Vercel détecte automatiquement le root directory, crée `vercel.json` à la **racine du repo** (`fb-agent-mvp/vercel.json`) :

```json
{
  "buildCommand": "cd aetherix-dashboard && npm run build",
  "outputDirectory": "aetherix-dashboard/.next",
  "installCommand": "cd aetherix-dashboard && npm install",
  "framework": "nextjs",
  "rootDirectory": "aetherix-dashboard"
}
```

**OU** créer `aetherix-dashboard/vercel.json` :

```json
{
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "outputDirectory": ".next"
}
```

Et dans l'interface Vercel, définir **Root Directory** = `aetherix-dashboard`.

---

## Vérification post-déploiement

1. **Health check** : Ouvrir l'URL Vercel → doit rediriger vers `/forecast`
2. **API** : Vérifier que les appels API fonctionnent (ouvrir DevTools → Network)
3. **Console** : Vérifier qu'il n'y a pas d'erreurs dans la console navigateur

---

## Problèmes courants

### Erreur : "Cannot find module"

**Cause** : Root Directory mal configuré  
**Solution** : Dans Vercel → Settings → General → Root Directory = `aetherix-dashboard`

### Erreur : "NEXT_PUBLIC_API_URL is not defined"

**Cause** : Variable d'environnement manquante  
**Solution** : Vercel → Settings → Environment Variables → Ajouter `NEXT_PUBLIC_API_URL`

### Build échoue : "npm install failed"

**Cause** : Root Directory incorrect, npm s'exécute à la racine  
**Solution** : Vérifier Root Directory = `aetherix-dashboard` dans Vercel

### CORS errors depuis l'API

**Cause** : L'API backend doit autoriser le domaine Vercel  
**Solution** : Vérifier la config CORS dans `backend/main.py` (ajouter le domaine Vercel si nécessaire)

---

## Mises à jour automatiques

Par défaut, Vercel déploie automatiquement à chaque push sur `master` (ou la branche configurée).

Pour désactiver : **Settings → Git → Production Branch** → Désactiver **"Automatically deploy"**.

---

## Liens utiles

- [Vercel Dashboard](https://vercel.com/dashboard)
- [Vercel Docs — Next.js](https://vercel.com/docs/frameworks/nextjs)
- [Vercel Docs — Monorepos](https://vercel.com/docs/monorepos)
