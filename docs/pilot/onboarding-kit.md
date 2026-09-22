# Aetherix — Design Partner Onboarding Kit

> **Audience** : F&B Manager / GM d'un hôtel indépendant 4★ sous Apaleo, 100-150 chambres, restaurant ouvert le soir, EU.
> **Statut** : kit interne — la §1 (Value prop) est exportable en PDF Notion pour envoi prospect. §2-4 = matériel commercial interne.
> **Story** : HOS-175 (Phase 3, P3-1). Bloque HOS-176 (real-pilot deploy).

---

## §1 — Value Proposition (1-pager prospect)

### Aetherix — F&B intelligence for your Apaleo hotel
**15-min setup. Daily forecasts by WhatsApp. No new dashboard to learn.**

#### Le problème

Vos couverts dîner varient de ±30% d'un soir à l'autre selon la météo, les événements locaux, et l'occupation de l'hôtel. Votre F&B Manager planifie les équipes chaque semaine à partir d'un mélange d'expérience et de tableurs. Une sous-estimation = clients qui attendent et NPS qui chute. Une surestimation = ~10% de coût labour gaspillé. Apaleo gère vos chambres parfaitement, mais ne prédit ni vos couverts, ni votre staffing F&B.

#### La solution

- **Forecast J+1 par WhatsApp chaque matin** : nombre de couverts dîner attendus, météo, événements locaux, recommandation staffing.
- **Apprentissage continu** : chaque retour ("on a fait 75, pas 60") améliore le modèle.
- **Read-only sur votre PMS Apaleo** : aucune écriture, aucun risque opérationnel.

#### La preuve — et ses limites, dites franchement

| KPI | Valeur | Nature | Source |
|-----|--------|--------|--------|
| Écart vs baseline naïve, MAPE moyen (30 restaurants réels) | **−6,15 pts** (49,71 % vs 55,86 %) | **données réelles** | benchmark Recruit, [`mape-benchmark.md`](../context/mape-benchmark.md) |
| Écart vs baseline naïve, **jour médian** | **−0,56 pt** — jeu égal ; à J+1, Prophet est même légèrement derrière | **données réelles** | idem |
| Économies labour estimées (ICP) | ~€16K/an | **modèle, non mesuré** | calcul ROI §2 ci-dessous |

**Ce que ces chiffres veulent dire.** Sur un restaurant typique un jour typique, notre forecast fait aujourd'hui
jeu égal avec « la moyenne des 4 derniers mêmes jours de semaine ». Son avantage se manifeste sur les jours
atypiques — c'est réel, mais ce n'est pas encore un différenciateur prouvé. Le pilote sert précisément à
mesurer l'écart sur **votre** établissement, où l'occupancy hôtelière (absente du dataset public) devrait jouer
en notre faveur. Le seuil de réussite est fixé à l'avance et publié :
[`protocole-de-preuve.md`](../planning/protocole-de-preuve.md) §4.1.

> Un chiffre interne de **15,09 % de MAPE** a circulé début 2026. Il est **circulaire** — les données de test
> étaient fabriquées à partir des mêmes variables que le modèle consomme. Nous ne le présentons plus comme une
> preuve ; il ne subsiste que comme garde-fou interne de non-régression.

#### Pourquoi Apaleo first

> *"Aetherix runs on one of the two PMS tiers the Anthropic playbook recommends for AI hotel owners — Apaleo (API-first) and Mews. You're on the right infrastructure."*

Apaleo expose 235 outils MCP natifs. Aucun ne prédit les couverts, ne calcule le capture-rate, ni ne recommande le staffing F&B. Ce sont exactement les primitives qu'Aetherix expose — nous sommes **complémentaires, pas en concurrence**. Source : [docs/competitive/apaleo-mcp-mapping.md](../competitive/apaleo-mcp-mapping.md).

#### Comment ça marche

1. **Connexion** (15 min) : vous générez un client OAuth2 read-only dans votre Apaleo Developer Portal, vous nous le transmettez par canal sécurisé.
2. **Historique** : on charge 90 jours d'historique réservations + occupancy depuis votre Apaleo.
3. **Apprentissage** (3-5 jours) : le modèle se cale sur votre property (saisonnalité, jours de la semaine, événements).
4. **Run** : chaque matin à 8h, vous recevez un message WhatsApp avec le forecast J+1 et la recommandation staff. Vous répondez en 1 mot ("ok", "non on a fait 75") — la boucle de feedback se ferme automatiquement.

#### Ce que l'agent fait / ne fait pas

| Fait | Ne fait pas |
|------|-------------|
| Forecast couverts par service (dîner, déjeuner, petit-déj) | Modifier les réservations Apaleo |
| Recommandation staffing F&B | Accéder aux données financières des guests |
| Rapport hebdo KPIs (covers vs predicted, capture-rate) | Envoyer des messages aux guests |
| Boucle de feedback WhatsApp | Auto-actions sans validation humaine |

**Read-only PMS** durant tout le pilot (CLAUDE.md Décision #7). **Human-in-the-loop** — vous validez chaque recommandation (Décision #6).

#### Ce qu'on vous demande

- **4 semaines** de pilot, **aucun coût** pendant cette période.
- **2 min/jour** : lire le Receipt WhatsApp et répondre par un mot.
- **30 min/mois** : un call de feedback pour caler le modèle.
- **Engagement RGPD** : données opérationnelles uniquement (covers, occupancy, staffing). Aucune PII guest exfiltrée.

#### Contact

Ivan de Murard — fondateur Aetherix — ivandemurard@gmail.com

---

## §2 — ROI Calculator (inline, paramètres éditables)

### Formule

```
Économies annuelles = covers_par_service × services_par_jour × 7 × 52
                    × taux_overstaffing × cost_serveur_par_heure × heures_par_shift
```

### Valeurs par défaut ICP

| Paramètre | Valeur | Note |
|-----------|--------|------|
| `covers_par_service` | 60 | dîner moyen ICP |
| `services_par_jour` | 3 | petit-déj + déjeuner + dîner |
| `jours_par_semaine` | 7 | restaurant ouvert 7/7 |
| `semaines_par_an` | 52 | annualisé |
| `taux_overstaffing` | 10% | benchmark hospitality (KPI framework Niveau 2 : labor_cost_variance) |
| `cost_serveur_par_heure` | €15 | brut chargé EU |
| `heures_par_shift` | 8 | shift standard |

### Résultat ICP par défaut

```
60 × 3 × 7 × 52 × 0.10 × 15 × 8 / (3 × 7) ≈ €15 600/an
```

(Cible CLAUDE.md KPI Niveau 2 : **−3% à −8% labor_cost_variance** = €15K-€25K/an pour un F&B €500K+)

### Personnalisation prospect

Lors du discovery call (§3 Q1 + Q7), récupérer les vraies valeurs et recalculer avant la proposition. Ne jamais envoyer la valeur par défaut sans contextualisation — le chiffre prend du poids quand il dérive **des données du prospect**.

---

## §3 — Discovery Call Script (45 min)

### 0-2 min — Opening

- Rappel : "Merci pour le temps. 45 min, j'aimerais comprendre votre setup F&B, vous montrer Aetherix en 15 min, et voir si un pilot 4 semaines a du sens."
- Confirmer enregistrement (si call interne — pas le prospect).
- Confirmer rôle : "Vous êtes F&B Manager ou GM ? Qui prendrait la décision sur un outil comme celui-ci ?"

### 2-17 min — Qualifying questions (8 obligatoires)

> **📌 TODO Phase 4 (non actionné — pilote reste Apaleo-only, Décision #11)** : ce script présume Apaleo (Q5, §4). À l'ouverture Phase 4 (Mews, multi-POS), ajouter en tête une question qualifiante "Quel PMS et quel POS utilisez-vous — natif ou tiers ?" et mapper la réponse contre la table vendors §D1 (`docs/adr/0006-pos-integration.md`, tiers T1/T2/T3) pour savoir immédiatement si l'adapter existe déjà ou doit être scopé avant de promettre une date de go-live. Réflexe déjà appliqué côté ingénierie dans ADR-0006 §11 (Mews POS natif) — "vérifier en premier si la donnée transite par l'écosystème PMS avant de présumer qu'un adapter tiers est nécessaire" ; même logique côté sales, pas de nouvel outil à construire.

1. **"Combien de couverts par service en moyenne au dîner ?"**
   → calibration modèle, sizing ROI.
2. **"Comment planifiez-vous vos effectifs F&B aujourd'hui — tableur, feeling, autre ?"**
   → pain validation. Si "outil existant qui marche bien", drapeau jaune.
3. **"Avez-vous déjà manqué de personnel un soir à forte demande ?"**
   → incident cost. Récupérer une anecdote concrète.
4. **"Avez-vous un restaurant le soir ou seulement le petit-déjeuner ?"**
   → scope check. Pas de dîner = pas notre ICP (Phase 3).
5. **"Êtes-vous sur Apaleo depuis combien de temps ?"**
   → historique disponible. < 3 mois = cold-start, on prévient.
6. **"Avez-vous un numéro WhatsApp Business pour la gestion opérationnelle ?"**
   → prereq technique (Twilio).
7. **"Combien de temps passez-vous à planifier les équipes F&B chaque semaine ?"**
   → ROI baseline (gain de temps en plus du gain labour).
8. **"Si on pouvait vous donner une prédiction de covers J+1 avec ±15% d'erreur par WhatsApp chaque matin, qu'est-ce que vous en feriez ?"**
   → test adoption intent. Si réponse vague, sonder davantage. Si "j'ajusterais mon staffing dîner" = green light.

### 17-32 min — Demo walkthrough (15 min)

Séquence en 4 temps :

1. **Probe Apaleo** (2 min) — montrer `GET /pms/mcp/probe` qui confirme la connexion MCP native. Talking point Décision #12.
2. **Forecast** (4 min) — montrer un forecast J+1 sur l'Apaleo sandbox (Hotel Kleber, [demo-apaleo.md](../context/demo-apaleo.md)). Montrer les regressors (météo, événements, occupancy).
3. **WhatsApp Receipt** (4 min) — montrer un Receipt réel sur le téléphone démo. Montrer la boucle feedback : "ok" / "non on a fait 75".
4. **Memory & learning** (5 min) — montrer comment le pattern écart est stocké dans `operational_memory` (pgvector) et impacte le prochain forecast. Talking point différenciateur : "le modèle apprend de **votre** property, pas d'un modèle générique".

### 32-42 min — Technical prereq check (§4)

Dérouler la checklist §4 ci-dessous, cocher en direct.

### 42-45 min — Next steps

- Si green light : poser la date d'onboarding (D+7 idéal), demander qui génère les credentials Apaleo.
- Si réserves : noter les blockers, proposer un call suivi à J+5.
- Envoyer la 1-pager §1 PDF + le credentials-sop.md par email dans les 24h.

---

## §4 — Technical Prereq Checklist

À cocher pendant le call (32-42 min). *Checklist Apaleo-only — TODO Phase 4 : gagner un item "PMS/POS confirmés = adapter existant (T1/T2) ou à scoper (T3/inconnu)" dès qu'un design partner hors Apaleo entre en pipeline (cf. note §3).*

- [ ] **Apaleo account** avec API access activé (vérifier le tier — l'OAuth2 client doit être créable dans le Developer Portal du prospect).
- [ ] **Numéro WhatsApp Business** configuré et joignable (le prospect doit savoir qui contrôle ce numéro côté hôtel).
- [ ] **F&B Manager nommé** disponible 2 min/jour pour lire le Receipt et répondre.
- [ ] **Accord RGPD opérationnel** — données covers/occupancy/staffing uniquement. Pas de PII guest. Stockage EU (Supabase Stockholm, Fly.io Paris).
- [ ] **Engagement écrit** : ≥ 4 semaines, feedback call mensuel 30 min, droit de résiliation à tout moment sans pénalité.
- [ ] **Restaurant ouvert le soir** confirmé (pas seulement petit-déj — sinon scope hors ICP Phase 3).
- [ ] **Historique Apaleo ≥ 60 jours** sur la property (sinon cold-start meta-learner ADR 0005, à signaler).
- [ ] **Décideur unique identifié** côté hôtel (GM ou propriétaire) — éviter le pilot enlisé en validation interne.

**Critère de Go pilot :** 8/8 cochés ou plan explicite pour combler les manques dans les 7 jours.

---

## Références

- [Source: CLAUDE.md Décision #6] — Human-in-the-loop, pas d'auto-actions Phase MVP
- [Source: CLAUDE.md Décision #7] — Read-only PMS Phase 0
- [Source: CLAUDE.md Décision #14] — MCP Server v0 shipped (HOS-71)
- [Source: CLAUDE.md Décision #17] — Fly.io hosting (cdg/Paris)
- [Source: CLAUDE.md Décision #21] — Anthropic playbook talking point
- [Source: docs/competitive/apaleo-mcp-mapping.md] — 235 tools Apaleo, 0 F&B primitives
- [Source: docs/context/demo-apaleo.md] — Hotel Kleber scenario, ICP details, Q&A
- [Source: docs/context/mape-benchmark.md] — benchmark Recruit sur données réelles (MAPE + MdAPE vs naïve)
- [Source: docs/context/mape-benchmark-holdout.json] — MAPE 15.09% synthétique et circulaire, gate interne de non-régression uniquement (run 2026-05-21)
- [Source: docs/context/status-taxonomy.md] — taxonomie Built / Shadow-mode / Synthetic PoC / Design / Research
- [Source: CLAUDE.md §KPI framework Niveau 2] — labor_cost_variance −3% à −8%
