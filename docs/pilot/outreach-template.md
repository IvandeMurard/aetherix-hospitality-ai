# Outreach Template — Design Partner Recruitment

> **Audience** : Ivan, pour identifier 3 prospects et envoyer le premier message.
> **Story** : HOS-175 AC4 (manuel Ivan — Dev livre les templates).
> **Critère minimum AC4 Done** : 1 message envoyé à 1 prospect qualifié (Apaleo confirmé + restaurant ouvert le soir).
>
> ⚠️ **Surface prospect — Décision #33 (gate honnêteté métriques) s'applique.** Aucun chiffre
> d'accuracy ne sort d'ici sans provenance nommée. Le 15 % MAPE historique est **retiré** : il vient
> du générateur synthétique et il est **circulaire** (`docs/context/mape-benchmark.md`). Le seul
> benchmark citable est **Recruit** (données publiques réelles) ; il n'y a **aucune** mesure sur
> couverts hôteliers réels tant que HOS-308 n'est pas fait. Le ~€16K/an est un **modèle, non mesuré**
> (`docs/pilot/onboarding-kit.md` §2, HOS-312 Todo) — il ne se présente jamais comme un résultat.

---

## 1. Critères ICP (rappel)

À utiliser pour qualifier un prospect avant outreach. **Tout prospect ciblé doit cocher ≥ 5/7.**

- [ ] **Taille** : 100-150 chambres (indépendant ou petit groupe 2-5 properties).
- [ ] **Catégorie** : 4★ ou boutique tech-forward.
- [ ] **PMS** : Apaleo client (vérifiable via Apaleo Marketplace customer logos ou LinkedIn).
- [ ] **Restaurant** : ouvert le soir (pas seulement breakfast). **Non négociable** — covers dîner = le forecast le plus valuable.
- [ ] **Localisation** : Paris / EU majeure (modèle weather+events validé sur cette géographie).
- [ ] **Équipe** : pas de data analyst dédié (F&B Manager fait la planification manuellement).
- [ ] **Revenue F&B** : > €500K/an estimé (signal : restaurant ouvert au public, pas juste pension).

---

## 2. Sources de prospection

| Source | Cible | Note |
|--------|-------|------|
| [Apaleo Marketplace](https://apaleo.com/marketplace/) — customer logos | Properties Apaleo confirmées | Filtrer par taille / EU |
| LinkedIn search : `"hotel manager" OR "F&B manager" AND "Apaleo"` | Décideurs sur les properties cibles | Filtrer par localisation Paris/EU |
| [Hotel Tech Report](https://hoteltechreport.com/) — communauté | Hôtels tech-forward | Chercher reviews Apaleo |
| HN hospitality / Slack communities | Founders/GMs early-adopters | Plus risqué (signal/bruit) |
| **Réseau direct Ivan** | Warm intros prioritaires | Toujours préférer warm intro à cold outreach |

---

## 3. Template de ciblage (à remplir)

| # | Property name | Location | Stars | Restaurant soir | Apaleo confirmé | Contact | Rôle | Canal | Statut | Notes |
|---|---------------|----------|-------|-----------------|------------------|---------|------|-------|--------|-------|
| 1 | _à remplir_ | | | ☐ | ☐ | | | LinkedIn / Email | Identified / Contacted / Replied / Call booked / Pilot signed / Declined | |
| 2 | _à remplir_ | | | ☐ | ☐ | | | | | |
| 3 | _à remplir_ | | | ☐ | ☐ | | | | | |

> **Statuts possibles** : `Identified` → `Contacted` → `Replied` → `Call booked` → `Pilot signed` / `Declined`.

---

## 4. Message LinkedIn — Français (≤ 300 mots)

> Personnaliser les `{{placeholders}}` avant envoi.

```
Bonjour {{prénom}},

Je suis Ivan, fondateur d'Aetherix. On construit un agent IA F&B pour les hôtels sous Apaleo — forecast couverts J+1 + recommandation staffing, livré chaque matin par WhatsApp.

Je vous écris parce que {{property_name}} coche tout ce qu'on cherche pour un pilot : 4★, Apaleo, restaurant ouvert le soir à {{ville}}. Je suis direct sur où on en est : le forecast est benchmarké sur des données publiques réelles (30 restaurants), pas encore sur des couverts d'hôtel. C'est exactement ce que ce pilot mesure — et vous verrez le chiffre en même temps que moi.

On lance 1 pilot de 4 semaines en juin/juillet, sans coût pour vous. Vous nous donnez un client Apaleo read-only (15 min de setup), votre F&B Manager lit un message WhatsApp 2 min/jour et nous renvoie un mot pour valider. C'est tout.

Ce qu'on demande en échange : 30 min de feedback par mois, et la permission de citer {{property_name}} comme design partner si le pilot marche.

20 minutes d'appel cette semaine pour creuser ? J'ai des créneaux {{créneaux}}.

Ivan
ivandemurard@gmail.com
```

---

## 5. Message LinkedIn — English (≤ 300 words)

> Personalise the `{{placeholders}}` before sending.

```
Hi {{first_name}},

I'm Ivan, founder of Aetherix. We're building an F&B AI agent for hotels running Apaleo — daily covers forecast + staffing recommendation, delivered by WhatsApp every morning.

I'm reaching out because {{property_name}} ticks every box for our pilot ICP: 4★, Apaleo, restaurant open in the evening in {{city}}. Straight about where we stand: the forecast is benchmarked on real public data (30 restaurants), not yet on hotel covers. That is precisely what this pilot measures — and you'll see the number the same day I do.

We're onboarding 1 pilot for 4 weeks in June/July, at no cost. You give us a read-only Apaleo OAuth2 client (15-min setup), your F&B Manager reads one WhatsApp message per day (2 min) and replies with a single word to validate. That's the whole loop.

In exchange: 30 min of monthly feedback, and permission to name {{property_name}} as a design partner if the pilot lands.

Open to a 20-min call this week to dig in? I have slots on {{slots}}.

Ivan
ivandemurard@gmail.com
```

---

## 6. Message email — Français (version longue, contexte Apaleo)

> Subject : `Pilot F&B sur Apaleo — 4 semaines, sans coût, pour {{property_name}}`

```
Bonjour {{prénom}},

Je vous écris depuis Aetherix, un outil que nous construisons pour les F&B Managers d'hôtels sous Apaleo.

Le constat : Apaleo gère vos chambres parfaitement, mais ne prédit ni vos couverts dîner, ni le staffing F&B associé. Sur 235 outils MCP exposés par Apaleo, aucun ne touche au F&B. C'est exactement le trou qu'on remplit — en complément, pas en concurrence.

Concrètement :
- Forecast couverts J+1 par WhatsApp chaque matin (benchmarké sur données publiques réelles — 30 restaurants ; jamais encore sur des couverts d'hôtel, c'est l'objet du pilot).
- Recommandation staffing. Cible modélisée, **pas encore mesurée** : −3% à −8% de labor cost variance, soit ~€16K/an pour une property de votre taille.
- Read-only sur votre Apaleo (aucune écriture, aucun risque opérationnel).
- Human-in-the-loop (vous validez chaque recommandation).

Ce qu'on cherche : 1 hôtel design partner pour un pilot 4 semaines, démarrage juin/juillet. Aucun coût. En échange, 30 min de feedback par mois et l'autorisation de citer {{property_name}} si le pilot fonctionne.

Pourquoi {{property_name}} : {{raison spécifique — taille, restaurant, localisation, intro par X}}.

Si ça résonne, 20 minutes d'appel cette semaine pour explorer ? Je vous propose {{créneau 1}}, {{créneau 2}}, ou un autre créneau qui vous convient mieux.

Merci pour votre temps,

Ivan de Murard
Fondateur, Aetherix
ivandemurard@gmail.com
```

---

## 7. Message email — English (long version, Apaleo context)

> Subject : `F&B pilot on Apaleo — 4 weeks, free, for {{property_name}}`

```
Hi {{first_name}},

I'm reaching out from Aetherix, a tool we're building for F&B managers at Apaleo-powered hotels.

The observation: Apaleo handles your rooms perfectly, but doesn't predict covers, capture rate, or F&B staffing. Out of 235 MCP tools Apaleo exposes, none touch F&B. That's exactly the gap we fill — complementary, not competitive.

Concretely:
- Next-day covers forecast delivered by WhatsApp every morning (benchmarked on real public data — 30 restaurants; never yet on hotel covers, which is what the pilot is for).
- Staffing recommendation. Modelled target, **not yet measured**: −3% to −8% labor cost variance, roughly €16K/year for a property your size.
- Read-only on your Apaleo (zero writes, zero operational risk).
- Human-in-the-loop (you validate every recommendation).

What we're looking for: 1 design partner hotel for a 4-week pilot, kicking off June/July. No cost. In exchange, 30 min of monthly feedback and permission to name {{property_name}} as a design partner if the pilot lands.

Why {{property_name}}: {{specific reason — size, restaurant profile, location, intro from X}}.

If this resonates, would you have 20 min this week to explore? I can suggest {{slot 1}}, {{slot 2}}, or any time that works better for you.

Thanks for your time,

Ivan de Murard
Founder, Aetherix
ivandemurard@gmail.com
```

---

## 8. Règles d'envoi

- **1 prospect = 1 canal à la fois.** LinkedIn OU email, pas les deux en même temps. Si pas de réponse à 5 jours, relance sur l'autre canal.
- **Toujours personnaliser** au moins le `{{property_name}}` et la `{{raison spécifique}}`. Un template envoyé sans personnalisation = quasi-zéro taux de réponse.
- **Pas de pièces jointes au premier message.** La 1-pager PDF est envoyée après la première réponse positive (sinon = filtre spam).
- **Pas plus de 2 relances.** Si silence après 2 follow-ups, marquer `Declined` et passer au suivant.
- **Tracker dans le tableau §3** chaque action (envoi, relance, réponse).

---

## 9. Evidence AC4

Pour marquer AC4 Done dans Linear HOS-175 :

- [ ] Tableau §3 rempli avec 3 prospects identifiés (statut min. `Identified`).
- [ ] ≥ 1 prospect en statut `Contacted` (= premier message envoyé).
- [ ] Screenshot du message envoyé archivé dans `docs/pilot/outreach-evidence/<date>-<property_slug>.png` (optionnel mais recommandé pour traçabilité).
- [ ] Commentaire Linear HOS-175 avec : noms des 3 prospects (initiales OK si confidentiel) + canal utilisé + statut.

---

## Références

- [Source: docs/pilot/onboarding-kit.md §1] — Value prop à reprendre dans les follow-ups
- [Source: docs/competitive/apaleo-mcp-mapping.md §TL;DR] — Talking point "235 tools, 0 F&B primitives"
- [Source: CLAUDE.md Décision #21] — Anthropic playbook talking point Apaleo
- [Source: docs/context/demo-apaleo.md] — ICP détaillé
