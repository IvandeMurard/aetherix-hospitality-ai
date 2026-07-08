# Session Veille — Instructions & Thématiques

> Chargé en mode Veille uniquement.
> **Mettre à jour :** si de nouveaux acteurs émergent dans §Acteurs à surveiller, ou si le protocole de scoring change.

---

## Mode Réactif (à la demande)

Quand l'utilisateur partage un lien, un document, ou du contenu :

1. Analyser le contenu en profondeur
2. Confronter avec le contexte projet (stack, roadmap, positionnement)
3. **Scorer la pertinence (0-10)** selon les critères ci-dessous
4. **Ne pousser vers Linear et Obsidian QUE si score ≥ 7/10**
5. Si score < 7 : livrer l'analyse uniquement, sans créer d'artefact

**Critères de pertinence :**
- Impacte directement la roadmap ou les décisions techniques (+3)
- Révèle un concurrent direct ou une opportunité de marché (+3)
- Apporte une information actionnable (justifie une nouvelle story) (+2)
- Contenu récent (< 7 jours) (+1)
- Source fiable (hospitalitynet.org, YC, Apaleo/Mews official, etc.) (+1)

**Format de sortie si score ≥ 7/10 :**
```
## [Titre]
**Score de pertinence : X/10**
**Pourquoi c'est important :** ...
**Lien avec le projet :** ...
**Action recommandée :** [story Linear proposée]
**Tags :** #hotel-tech #agentique #concurrent etc.
```

---

## Mode Proactif (automatique, lundi 8h30)

Rapport hebdomadaire généré par GitHub Actions via `scripts/veille_proactive.py`.
Résultat : ticket Linear "Veille Hebdomadaire" + note Obsidian dans `AI Reports/Intelligence/`.

---

## Thématiques

1. **Hotel tech & agentique IA** — nouvelles solutions, startups, acquisitions
2. **IA dans l'hôtellerie** — cas d'usage F&B, forecasting, automatisation ops
3. **Apaleo** — nouveautés API, partenaires, blog officiel — ⚠️ surveiller l'expansion du Copilot vers le F&B
4. **Mews** — features, positionnement, acquisitions
5. **Y Combinator** — nouvelles références liées à l'hospitality/F&B/forecasting
6. **hospitalitynet.org** — articles pertinents publiés dans les 7 derniers jours
7. **Agent-first / MCP ecosystem** — outils, frameworks, distribution patterns

**Acteurs à surveiller :**
- **DialogShift** (Olga Heuser) — 95%+ automation hôtels, auteure du WP Agentic AI, avance sur MCP
- **Lighthouse / Connect AI** — premier booking direct dans ChatGPT via MCP
- **IDeaS / Duetto** — RMS enterprise, hors segment PME Aetherix
- **Canary Technologies** — guest management, adjacent mais pas F&B ops

---

## Roadmap synthétique (pour évaluer la pertinence)

- **Phase 0 (en cours)** : Architecture FastAPI, modèles DB, Apaleo, WhatsApp
- **Phase 0.5** : MCP Server — capabilities agent-callable
- **Phase 1** : Forecasting F&B, alertes WhatsApp, Agent SEO
- **Phase 2** : Agent conversationnel "Receipts"
- **Phase 3** : Multi-hotel, Mews, analytics avancés
