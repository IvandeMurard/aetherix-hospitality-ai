# 🔧 Guide de Correction du fichier .env

## Problèmes identifiés

Votre fichier `.env` a quelques problèmes :

1. ❌ **PREDICTHQ_API_KEY** : Manquante
2. ❌ **OPENWEATHER_API_KEY** : Manquante  
3. ⚠️ **MISTRAL_API_kEY** : Typo (k minuscule au lieu de K majuscule)

## Solution

Ajoutez/modifiez ces lignes dans votre fichier `.env` :

```env
# Corriger la typo Mistral (optionnel, mais recommandé)
MISTRAL_API_KEY="6lYu70sA4D9Ri3nV9ucm4wbcyAjEyiEx"

# Ajouter PredictHQ (OBLIGATOIRE pour events_fetcher)
PREDICTHQ_API_KEY="votre_clé_predictHQ_ici"

# Ajouter OpenWeatherMap (OBLIGATOIRE pour weather_fetcher)
OPENWEATHER_API_KEY="votre_clé_openweather_ici"
```

## Où obtenir les clés API

### PredictHQ
1. Créez un compte sur https://predicthq.com/
2. Allez dans "API Tools" → "API Tokens"
3. Créez un nouveau token
4. Copiez-le dans `.env` comme `PREDICTHQ_API_KEY="votre_token"`

### OpenWeatherMap
1. Créez un compte sur https://openweathermap.org/api
2. Allez dans "API keys"
3. Générez une nouvelle clé (gratuite)
4. Copiez-la dans `.env` comme `OPENWEATHER_API_KEY="votre_clé"`

## Vérification

Après avoir ajouté les clés, testez avec :

```bash
python test_env.py
```

Vous devriez voir :
```
✅ PREDICTHQ_API_KEY         (PredictHQ           ) = ...
✅ OPENWEATHER_API_KEY       (OpenWeatherMap      ) = ...
```

## Format du fichier .env

Assurez-vous que votre `.env` ressemble à ceci :

```env
QDRANT_URL="https://f9..."
QDRANT_API_KEY="JhbGci..."
MISTRAL_API_KEY="6lYu70sA4D..."
ELEVENLABS_API_KEY="sk_5a0e24a..."
PREDICTHQ_API_KEY="votre_clé_ici"
OPENWEATHER_API_KEY="votre_clé_ici"
```

**Important :**
- Pas d'espaces autour du `=`
- Les noms de variables sont en MAJUSCULES
- Utilisez des guillemets si la valeur contient des caractères spéciaux

