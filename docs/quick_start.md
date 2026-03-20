# 🚀 DÉMO RAPIDE - GUIDE DE LANCEMENT

## ⚡ Commandes à exécuter (dans l'ordre)

### 1. Seed Qdrant local (une seule fois)
```bash
python seed_data.py
```

### 2. Lancer l'API (Terminal 1)
```bash
uvicorn api:app --reload --port 8000
```

### 3. Lancer Streamlit (Terminal 2)
```bash
streamlit run demo_app.py
```

### 4. Ouvrir dans le navigateur
http://localhost:8501

## ✅ Vérification rapide

Test API direct :
```bash
python test_final.py
```

## 📋 Fichiers créés/modifiés

- ✅ `agents/pattern_search.py` - Qdrant local
- ✅ `seed_data.py` - Qdrant local + création collection
- ✅ `demo_app.py` - Interface Streamlit
- ✅ `test_final.py` - Test API
- ✅ `PITCH.md` - Script de pitch
- ✅ `README.md` - Section démo ajoutée

## 🎯 Résultat attendu

- API répond en <2s avec prédictions
- Interface Streamlit fonctionnelle
- 3 outils partenaires intégrés (Mistral + Qdrant + ElevenLabs)
- Démo prête pour le pitch

