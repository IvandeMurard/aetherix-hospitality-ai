# Guide de déploiement Streamlit Cloud - Dashboard Aetherix

Ce guide te permet de déployer le dashboard Streamlit sur [Streamlit Community Cloud](https://share.streamlit.io).

---

## 📋 Prérequis

1. **Repository GitHub** : Ton code doit être poussé sur GitHub
   - Repo actuel : `IvandeMurard/Hospitality-Operations-Agentic-AI-B2B` (ou le repo où se trouve `frontend/app.py`)
2. **Compte Streamlit Cloud** : Connecte-toi avec ton compte GitHub sur [share.streamlit.io](https://share.streamlit.io)

---

## 🚀 Configuration dans Streamlit Cloud

### Étape 1 : Nouvelle App

1. Va sur [share.streamlit.io](https://share.streamlit.io)
2. Clique sur **"New app"** ou **"Deploy an app"**

### Étape 2 : Configuration de base

Remplis les champs suivants :

| Champ | Valeur |
|------|--------|
| **Repository** | `IvandeMurard/Hospitality-Operations-Agentic-AI-B2B` (ou ton repo GitHub) |
| **Branch** | **`master`** ou **`main`** (une GitHub Action synchronise `main` → `master` à chaque push ; les deux branches sont identiques) |
| **Main file path** | **`frontend/app.py`** ⚠️ (pas `streamlit_app.py` !) |
| **App URL (optional)** | `aetherix` (donnera `aetherix.streamlit.app`) |

### Étape 3 : Advanced Settings

Clique sur **"Advanced settings"** et configure :

#### Python version
```
3.11
```
*(Correspond à la version du backend)*

#### Secrets (Variables d'environnement) ⚠️ OBLIGATOIRE

Dans la section **"Secrets"**, ajoute en format TOML :

```toml
AETHERIX_API_BASE = "https://ivandemurard-fb-agent-api.hf.space"
```

**⚠️ IMPORTANT** : 
- **Ce secret est OBLIGATOIRE** pour que les prédictions fonctionnent sur Streamlit Cloud
- Sans ce secret, le dashboard essaiera de se connecter à `http://localhost:8000` qui n'existe pas sur Streamlit Cloud
- Pas de slash final (`/`) à la fin de l'URL
- L'URL doit être accessible publiquement (ton API HuggingFace Spaces)
- Le code détecte automatiquement Streamlit Cloud et utilise l'API HuggingFace par défaut, mais **il est fortement recommandé de configurer ce secret explicitement** pour éviter tout problème

**Comment vérifier que le secret est bien configuré :**
1. Va dans **Settings** → **Secrets** de ton app Streamlit Cloud
2. Vérifie que `AETHERIX_API_BASE` est présent avec la valeur `https://ivandemurard-fb-agent-api.hf.space`
3. Après avoir ajouté/modifié un secret, **redémarre l'app** (clique sur "Reboot app" dans Settings)
4. Les logs de l'app afficheront `[API_DETECT] Using explicit AETHERIX_API_BASE: https://ivandemurard-fb-agent-api.hf.space` si le secret est bien lu

---

## ✅ Vérification

Après le déploiement :

1. **URL de l'app** : `https://aetherix.streamlit.app` (ou l'URL que tu as choisie)
2. **Test** : 
   - Ouvre le dashboard
   - Va sur la page "Forecast"
   - Sélectionne une date et clique sur "Get Prediction"
   - Vérifie que les données s'affichent (appel à l'API HuggingFace)

---

## 🔧 Dépannage

### Erreur "This file does not exist"
- **Cause** : Le chemin du fichier principal est incorrect
- **Solution** : Vérifie que `Main file path` = `frontend/app.py` (avec le préfixe `frontend/`)

### Erreur de connexion à l'API / Prédictions ne fonctionnent pas
- **Cause** : `AETHERIX_API_BASE` non configuré, mal configuré ou API HuggingFace non accessible
- **Solution** : 
  1. **Vérifie que le secret `AETHERIX_API_BASE` est bien configuré** dans Advanced Settings → Secrets
     - Format TOML : `AETHERIX_API_BASE = "https://ivandemurard-fb-agent-api.hf.space"` (sans slash final)
  2. Vérifie que l'API répond : `curl https://ivandemurard-fb-agent-api.hf.space/health`
  3. Redémarre l'app après avoir ajouté/modifié le secret (clique sur "Reboot app")
  4. Vérifie les logs Streamlit Cloud pour voir les erreurs exactes
  5. Si le problème persiste, vérifie que l'API HuggingFace Space est bien déployée et accessible

### Erreur d'import Python
- **Cause** : Dépendances manquantes ou chemin d'import incorrect
- **Solution** : 
  - Vérifie que `frontend/requirements.txt` contient toutes les dépendances
  - Streamlit Cloud installe automatiquement depuis `requirements.txt` à la racine du repo OU dans le même dossier que `app.py`
  - Si `requirements.txt` est dans `frontend/`, il sera trouvé automatiquement

### Python version incompatible
- **Cause** : Version Python différente de celle du backend
- **Solution** : Utilise Python **3.11** dans Advanced Settings pour correspondre au backend

---

## 📝 Structure attendue dans le repo

Streamlit Cloud cherche :
- Le fichier principal : `frontend/app.py` (selon ton `Main file path`)
- Les dépendances : `frontend/requirements.txt` (automatiquement détecté)

Si ton repo a cette structure :
```
repo/
├── frontend/
│   ├── app.py          ← Fichier principal
│   ├── requirements.txt
│   ├── config.py
│   ├── components/
│   └── views/
└── backend/
```

Alors `Main file path` = `frontend/app.py` ✅

---

## 🔄 Mise à jour après déploiement

Streamlit Cloud redéploie automatiquement à chaque push sur la branche configurée. Une **GitHub Action** synchronise `main` → `master` à chaque push sur `main`, donc **`main`** et **`master`** restent identiques : tu peux utiliser l’une ou l’autre (par ex. `master` si l’app est déjà configurée ainsi, sans rien changer).

**Si l’app n’est pas à jour :**
1. Va sur [share.streamlit.io](https://share.streamlit.io), ouvre ton app **aetherix**
2. **Settings** (ou "Manage app") → vérifie que **Branch** = **`master`** ou **`main`**
3. Clique sur **"Reboot app"** (ou "Redeploy") pour forcer un nouveau build

---

## 🎯 Résumé des valeurs à utiliser

| Paramètre | Valeur |
|-----------|--------|
| Repository | `IvandeMurard/Hospitality-Operations-Agentic-AI-B2B` |
| Branch | **`master`** ou **`main`** (synchronisées par l’action GitHub) |
| Main file path | **`frontend/app.py`** |
| App URL | `aetherix` |
| Python version | `3.11` |
| Secret `AETHERIX_API_BASE` | `https://ivandemurard-fb-agent-api.hf.space` |

---

Une fois déployé, ton dashboard sera accessible publiquement et appellera automatiquement ton API HuggingFace Spaces ! 🎉
