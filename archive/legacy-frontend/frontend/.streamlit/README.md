# Streamlit Configuration - Cache Troubleshooting

Ce dossier contient la configuration Streamlit pour le dashboard Aetherix.

## Problème de cache JavaScript

Si vous voyez le message "You need to enable JavaScript to run this app" après un déploiement, cela indique un problème de cache JavaScript.

### Solutions

#### 1. Vider le cache navigateur
- **Chrome/Edge** : `Ctrl+Shift+Delete` (Windows) ou `Cmd+Shift+Delete` (Mac)
- **Firefox** : `Ctrl+Shift+Delete` (Windows) ou `Cmd+Shift+Delete` (Mac)
- Sélectionner "Images et fichiers en cache" et vider

#### 2. Navigation privée
- Ouvrir le site en navigation privée/incognito pour tester sans cache
- Si ça fonctionne en navigation privée, c'est bien un problème de cache

#### 3. Hard refresh
- **Windows/Linux** : `Ctrl+F5` ou `Ctrl+Shift+R`
- **Mac** : `Cmd+Shift+R`

#### 4. Vérifier les assets JS dans DevTools
1. Ouvrir DevTools (F12)
2. Onglet Network
3. Recharger la page
4. Vérifier que les fichiers `index.*.js` se chargent correctement (status 200)
5. Si status 304 (Not Modified), le cache est actif - forcer un hard refresh

### Configuration actuelle

Le fichier `config.toml` contient :
- Configuration serveur pour désactiver le cache
- Paramètres de sécurité (XSRF protection)

### Après un déploiement

1. Attendre quelques secondes que Streamlit Cloud termine le déploiement
2. Vider le cache navigateur ou utiliser la navigation privée
3. Tester avec un bot/crawler (ex: Grok) pour vérifier la compatibilité

### Vérification des headers HTTP

Les headers suivants devraient être présents pour éviter le cache :
- `Cache-Control: no-cache, no-store, must-revalidate`
- `Pragma: no-cache`
- `Expires: 0`

Vérifier dans DevTools > Network > Headers de réponse.
