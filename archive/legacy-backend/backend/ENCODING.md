# UTF-8 Encoding Configuration

Ce projet garantit que tous les fichiers Python utilisent l'encodage UTF-8 pour éviter les problèmes de caractères spéciaux sur Windows.

## Configuration Automatique

### 1. Fichier `utf8_config.py`
Ce fichier est importé en premier dans `main.py` et configure automatiquement :
- `PYTHONIOENCODING=utf-8` (variable d'environnement)
- `sys.stdout` en UTF-8
- `sys.stderr` en UTF-8

### 2. Déclarations d'encodage
Tous les fichiers Python principaux incluent la déclaration :
```python
# -*- coding: utf-8 -*-
```

Fichiers configurés :
- `main.py`
- `agents/reasoning_engine.py`
- `agents/demand_predictor.py`
- `utils/claude_client.py`
- `utils/qdrant_client.py`
- `models/schemas.py`
- `utf8_config.py`

## Vérification

Pour vérifier que l'encodage est correctement configuré, exécutez :
```bash
python backend/verify_encoding.py
```

Vous devriez voir tous les indicateurs ✅ OK.

## Configuration Windows

### PowerShell
Si vous rencontrez des problèmes d'encodage dans PowerShell, exécutez :
```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
```

### CMD
Dans CMD, définissez :
```cmd
chcp 65001
set PYTHONIOENCODING=utf-8
```

### Variables d'environnement système (optionnel)
Pour une configuration permanente :
1. Ouvrez "Variables d'environnement" dans Windows
2. Ajoutez `PYTHONIOENCODING` avec la valeur `utf-8`

## Caractères non-ASCII

Le projet évite les caractères non-ASCII dans le code source pour garantir la compatibilité Windows :
- `°C` → `C` (degré Celsius)
- Tous les autres caractères Unicode sont remplacés par des équivalents ASCII

## Dépannage

Si vous rencontrez des erreurs d'encodage :
1. Vérifiez que `utf8_config.py` est importé en premier dans `main.py`
2. Exécutez `python backend/verify_encoding.py`
3. Vérifiez que `PYTHONIOENCODING=utf-8` est défini
4. Redémarrez votre terminal/serveur

