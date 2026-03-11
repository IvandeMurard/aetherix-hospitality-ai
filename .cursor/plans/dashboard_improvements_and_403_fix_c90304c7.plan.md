---
name: Dashboard improvements and 403 fix
overview: Résoudre l'erreur 403 des prédictions et améliorer le dashboard avec les inspirations Perplexity, Mixpanel, Hex et Deel, tout en gardant Streamlit pour le MVP.
todos:
  - id: fix_403_headers
    content: "Améliorer fetch_prediction() dans forecast_view.py : ajouter headers explicites (Content-Type), timeout augmenté, retry logic pour gérer les erreurs 403"
    status: completed
  - id: fix_403_batch
    content: "Améliorer get_week_predictions() et get_month_predictions() dans timeline_chart.py : meilleure gestion erreurs, retry pour batch requests"
    status: completed
  - id: verify_cors
    content: "Vérifier configuration CORS dans backend/main.py : s'assurer que allow_origins=['*'] et allow_credentials=False sont corrects, ajouter logging pour diagnostiquer"
    status: completed
  - id: improve_kpi_cards
    content: "Améliorer _render_kpi_cards_*() dans forecast_view.py : style Perplexity (bordures subtiles, ombres, typographie claire, couleurs sémantiques)"
    status: completed
  - id: improve_bar_charts
    content: "Améliorer render_week_chart() et render_month_chart_from_data() dans timeline_chart.py : style Mixpanel (couleurs cohérentes, légendes claires, tooltips informatifs)"
    status: completed
  - id: reorganize_hierarchy
    content: "Réorganiser hiérarchie visuelle dans render_forecast_view() : ordre titre → KPIs → graphiques → factors → feedback (style Perplexity)"
    status: completed
isProject: false
---

# Plan : Résolution 403 et Améliorations Dashboard

## Analyse des Inspirations

### Priorités recommandées

**1. Perplexity (Haute priorité - MVP)**

- ✅ **Agencement titre → chiffres → graphiques** : Structure claire déjà présente, à améliorer
- ✅ **Équilibre visuel** : Cards KPI uniformes, espacement généreux
- ✅ **Action** : Améliorer la hiérarchie visuelle des KPI cards et graphiques

**2. Mixpanel (Haute priorité - MVP)**

- ✅ **Sidebar** : Déjà bien structurée, correspond à Aetherix
- ✅ **Chiffres clés** : Présentation actuelle correcte, à renforcer visuellement
- ✅ **Bar charts** : Déjà utilisés (Plotly), style à aligner avec Mixpanel
- ⚠️ **Vue calendrier** : À considérer pour Phase 4 (History view améliorée)

**3. Hex Context Studio (Moyenne priorité - Phase 4)**

- 📋 **Semantic layer** : Concept intéressant mais hors scope MVP
- 📋 **Conversational BI** : Mix charts + texte - déjà présent via Factors panel
- 📋 **Context curation** : Observabilité des interactions - Phase 4+

**4. Deel (Basse priorité - Later)**

- 📋 **Coût staff vs habituel** : Intéressant mais pas critique MVP
- 📋 **Action** : À considérer pour Phase 4 quand feedback loop sera actif

## Problème 403 - Diagnostic et Solution

### Causes probables

1. **CORS HuggingFace Spaces** : Même avec `allow_origins=["*"]`, HF peut bloquer certaines requêtes
2. **Headers manquants** : Streamlit peut ne pas envoyer les bons headers
3. **Timeout/rate limiting** : HF Spaces peut limiter les requêtes longues

### Solutions à implémenter

**Solution 1 : Headers explicites dans requests**

- Ajouter `Content-Type: application/json` explicitement
- Ajouter timeout plus long pour batch predictions
- Gestion d'erreur améliorée avec retry logic

**Solution 2 : Vérifier configuration CORS backend**

- S'assurer que `allow_credentials=False` avec `allow_origins=["*"]` est correct
- Ajouter logging pour diagnostiquer les requêtes bloquées

**Solution 3 : Fallback et error handling**

- Afficher message d'erreur clair si 403
- Suggérer vérification des variables d'environnement HF
- Option de retry automatique

## Améliorations UI/UX (après résolution 403)

### Phase 1 : Améliorations immédiates (MVP)

**1. KPI Cards - Style Perplexity**

- Fichier : `frontend/views/forecast_view.py`
- Améliorer les cards avec :
  - Bordures subtiles, ombres légères
  - Typographie plus claire (taille, poids)
  - Icônes contextuelles (optionnel)
  - Couleurs sémantiques (vert = bon, orange = attention)

**2. Bar Charts - Style Mixpanel**

- Fichier : `frontend/components/timeline_chart.py`
- Améliorer `render_week_chart` et `render_month_chart_from_data` :
  - Couleurs cohérentes avec la palette Aetherix
  - Légendes claires et positionnées
  - Tooltips informatifs
  - Axes labels lisibles

**3. Hiérarchie visuelle - Perplexity**

- Fichier : `frontend/views/forecast_view.py`
- Réorganiser l'ordre d'affichage :
  1. Titre de la vue (date/week/month)
  2. KPI Cards (4 métriques clés)
  3. Graphique principal (bar chart ou hero card)
  4. Factors panel (expandable)
  5. Feedback panel (expandable)

**4. Sidebar - Améliorations mineures**

- Fichier : `frontend/components/sidebar.py`
- Garder la structure actuelle (déjà bonne)
- Améliorer la lisibilité des sections DATA et COMING SOON

### Phase 2 : Améliorations futures (Phase 4)

**1. Vue calendrier Mixpanel**

- Nouvelle vue dans `frontend/views/history_view.py`
- Calendrier mensuel avec prédictions
- Zoom jour/semaine
- Export CSV/Excel

**2. Présentation coût staff (Deel)**

- Nouveau composant `frontend/components/staff_cost_panel.py`
- Comparaison prédit vs habituel
- Indicateurs visuels (rouge = plus cher, vert = moins cher)

**3. Observabilité Hex-style**

- Logging des interactions utilisateur
- Dashboard d'observabilité (Phase 5)

## Fichiers à modifier

### Résolution 403

- `frontend/views/forecast_view.py` : Améliorer `fetch_prediction()` avec headers explicites et retry
- `frontend/components/timeline_chart.py` : Améliorer `get_week_predictions()` et `get_month_predictions()` avec meilleure gestion d'erreur
- `backend/main.py` : Vérifier/améliorer CORS middleware et logging

### Améliorations UI

- `frontend/views/forecast_view.py` : Améliorer `_render_kpi_cards_*()` avec style Perplexity
- `frontend/components/timeline_chart.py` : Améliorer les charts avec style Mixpanel
- `frontend/config.py` : Ajouter constantes de couleurs/styles pour cohérence

## Migration Vercel - Recommandation

**Recommandation : Garder Streamlit pour MVP**

**Raisons :**

1. Streamlit Cloud est gratuit et fonctionne bien pour MVP
2. Migration vers Vercel nécessiterait refactoring complet (Next.js déjà présent mais pas utilisé)
3. Le problème 403 n'est pas lié à Streamlit mais à HuggingFace Spaces
4. Focus MVP : résoudre 403 et améliorer UI, pas migration infrastructure

**Quand migrer vers Vercel :**

- Phase 4+ quand besoin de plus de contrôle
- Si Streamlit devient limitant pour les fonctionnalités avancées
- Si besoin de meilleures performances (SSR, optimisations)

## Ordre d'exécution

1. **Résoudre 403** (priorité absolue)
  - Améliorer headers et error handling dans `forecast_view.py`
  - Vérifier CORS backend
  - Tester avec HuggingFace Spaces
2. **Améliorer KPI Cards** (quick win)
  - Style Perplexity
  - Typographie et espacement
3. **Améliorer Bar Charts** (quick win)
  - Style Mixpanel
  - Couleurs et légendes
4. **Réorganiser hiérarchie visuelle** (quick win)
  - Ordre titre → KPIs → graphiques
5. **Vue calendrier et autres** (Phase 4)
  - Après MVP fonctionnel

