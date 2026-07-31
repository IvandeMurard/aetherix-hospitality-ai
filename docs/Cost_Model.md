# Aetherix — Modèle de coûts (unit economics)

> **Story** : [HOS-312](https://linear.app/hospitalityagent/issue/HOS-312) (Story 16.12) — Unit economics, coût complet par propriété/mois
> **Version** : 2.0 · **Date** : 2026-07-30 · **Owner** : Ivan
> **Remplace** : version 0.1.0 du 02/12/2025 — modélisait un stack qui n'existe plus (Qdrant, ElevenLabs, Vercel, Render, framing « restaurants » à 49 $/mois). **Ne pas s'y référer.**
> **Alimente** : [HOS-179](https://linear.app/hospitalityagent/issue/HOS-179) (pricing decision doc, S8)

---

## Statut des chiffres (taxonomie HOS-318)

| Poste | Statut | Base |
|-------|--------|------|
| Coûts LLM | **Calculé** | Tarifs publics Anthropic × volumétrie dérivée du code (`mcp_server.py`, `receipts.py`, dispatchers APScheduler) |
| Fly.io · Supabase · Upstash · Twilio | **Estimé** | Configuration réelle (`fly.toml`) × grilles publiques — **à confronter aux factures réelles** |
| Volumétrie d'usage | **Estimé** | Rythme nominal modélisé, non observé — aucune propriété en production à ce jour |

⚠️ **Aucun chiffre de ce document n'est mesuré.** L'observabilité Logfire ([HOS-311](https://linear.app/hospitalityagent/issue/HOS-311)) est active depuis le 26/07, mais le trafic accumulé est du sandbox, pas de la production — l'extrapoler serait présenter du synthétique comme du réel, exactement ce que la gate d'honnêteté ([HOS-318](https://linear.app/hospitalityagent/issue/HOS-318)) interdit. **À re-mesurer après le go-live ([HOS-176](https://linear.app/hospitalityagent/issue/HOS-176)).**

---

## 1. Tarifs unitaires retenus

**LLM (Anthropic, vérifié 2026-07-30)** :

| Modèle | Rôle dans le pipeline | Input $/MTok | Output $/MTok |
|--------|----------------------|-------------:|--------------:|
| `claude-sonnet-4-6` | Modèle par défaut — raisonnement, Receipt, digest | 3,00 | 15,00 |
| `claude-haiku-4-5` | Classification inbound (routing HOS-283, `receipts.py:132`) | 1,00 | 5,00 |
| `gemini-2.0-flash` | Fallback (Décision LLM provider) | — | — |
| `mistral-embed` | Embeddings mémoire opérationnelle | négligeable | — |

**Infrastructure** — configuration réelle :

| Service | Configuration | Nature |
|---------|--------------|--------|
| Fly.io | 1× `shared-cpu-1x`, 1024 MB RAM, région `cdg`, `min_machines_running = 1`, `auto_stop_machines = "off"` | **Fixe** |
| Supabase | PostgreSQL + pgvector + RLS | **Fixe** (par palier) |
| Upstash | Redis — rate limiting, state | Fixe puis variable |
| Twilio | WhatsApp Business — **facturation par conversation (fenêtre 24 h)**, pas par message | **Variable** |

> ⚠️ `auto_stop_machines = "off"` + `min_machines_running = 1` : la machine Fly tourne **24/7 même sans trafic** — les workers APScheduler doivent rester vivants. C'est un coût fixe incompressible, pas un coût à l'usage.

---

## 2. Volumétrie modélisée (1 propriété, rythme nominal)

| Opération | Fréquence | Modèle | Input ~ | Output ~ |
|-----------|----------:|--------|--------:|---------:|
| Daily Receipt (forecast → reco → explication) | 30 / mois | Sonnet 4.6 | 3 500 | 400 |
| Parsing message manager entrant | 15 / mois | Haiku 4.5 | 800 | 50 |
| Réponse + écriture mémoire | 15 / mois | Sonnet 4.6 | 2 000 | 200 |
| Digest hebdomadaire | 4 / mois | Sonnet 4.6 | 5 000 | 600 |
| Forecast Prophet | 30 / mois | — | **aucun appel LLM** (calcul local) | — |

> Le forecast lui-même ne coûte pas de tokens : Prophet tourne sur la machine Fly. Le LLM n'intervient que pour l'explicabilité et la conversation.

### Coût LLM résultant

| Poste | Calcul | $/mois |
|-------|--------|-------:|
| Daily Receipt | 30 × [(3 500/1M × 3) + (400/1M × 15)] | **0,495** |
| Parsing inbound (Haiku) | 15 × [(800/1M × 1) + (50/1M × 5)] | **0,016** |
| Réponse + mémoire | 15 × [(2 000/1M × 3) + (200/1M × 15)] | **0,135** |
| Digest hebdo | 4 × [(5 000/1M × 3) + (600/1M × 15)] | **0,096** |
| Embeddings | — | ~0,01 |
| **Total LLM / propriété / mois** | | **≈ 0,75 $** |

**Le LLM n'est pas le poste dominant.** C'est le résultat le plus contre-intuitif de ce modèle : à 0,75 $/propriété/mois, le coût d'inférence est inférieur au coût WhatsApp et très inférieur au socle fixe.

> **Levier non exploité** : le prompt système est stable d'un appel à l'autre. Le prompt caching (~0,1× en lecture) diviserait le poste input par ~10, soit ≈ 0,25 $/propriété/mois. Gain absolu faible aujourd'hui — à considérer seulement au-delà de ~50 propriétés.

---

## 3. Coûts variables non-LLM

**Twilio WhatsApp — le piège de facturation.** La facturation est **par conversation** (fenêtre de 24 h), pas par message. Un Daily Receipt suivi de 3 échanges de feedback = **1 conversation**, pas 4. Se tromper ici fausse le coût variable d'un ordre de grandeur.

- 30 Daily Receipts/mois = 30 conversations ouvertes minimum
- Les réponses manager dans la fenêtre sont incluses
- Catégorie *utility*, France : ordre de grandeur **0,05 $/conversation** → **≈ 1,60 $/propriété/mois** *(à confirmer sur facture)*

**Coût variable total ≈ 2,35 $/propriété/mois** (0,75 LLM + 1,60 WhatsApp).

---

## 4. Trois scénarios de volume

| | 1 propriété | 10 propriétés | 50 propriétés |
|---|---:|---:|---:|
| **Fixe** — Fly.io | ~5,70 | ~5,70 | ~12 (montée en gamme) |
| **Fixe** — Supabase | 0 (free) | ~25 (Pro) | ~25 (Pro) |
| **Fixe** — Upstash | 0 (free) | 0 (free) | ~10 |
| **Sous-total fixe** | **~5,70** | **~30,70** | **~47** |
| **Variable** — 2,35 × N | 2,35 | 23,50 | 117,50 |
| **TOTAL / mois** | **~8,05 $** | **~54,20 $** | **~164,50 $** |
| **Coût / propriété** | **8,05 $** | **5,42 $** | **3,29 $** |

**Points de bascule à connaître** :

- **Supabase free → Pro** (~25 $/mois) : le saut le plus brutal. Il tombe entre 1 et 10 propriétés selon la croissance de `operational_memory` (pgvector). À 1 propriété il double presque le coût total.
- **Fly.io** : 1 GB de RAM suffit tant que Prophet `fit()` reste séquentiel. Au-delà de ~30 propriétés, le fit quotidien devient le facteur dimensionnant, pas le trafic HTTP.
- **Dérive non linéaire à surveiller** : le contexte RAG grossit avec la mémoire opérationnelle accumulée. Le coût LLM par appel n'est donc pas constant dans le temps, même à volumétrie d'usage constante. Non chiffrable aujourd'hui — à instrumenter via Logfire après le pilote.

---

## 5. Confrontation au pricing — marge brute

| Ancrage | Prix / propriété / mois | Source |
|---------|------------------------:|--------|
| **Venli** (concurrent Apaleo-native, mid-market) | 99 – 299 € | Watchlist §W12 — anchor identifié pour HOS-179 |
| **Reco interne Aetherix** | 500 – 2 500 $ | `open-decisions.md` §pricing |

Marge brute selon le scénario :

| Prix retenu | Coût @ 1 prop. | Coût @ 10 prop. | Marge @ 10 prop. |
|-------------|---------------:|----------------:|-----------------:|
| 99 € (~107 $) | 8,05 $ | 5,42 $ | **94,9 %** |
| 299 € (~323 $) | 8,05 $ | 5,42 $ | **98,3 %** |
| 500 $ | 8,05 $ | 5,42 $ | **98,9 %** |
| 2 500 $ | 8,05 $ | 5,42 $ | **99,8 %** |

### Conclusion pour HOS-179

**Les unit economics ne sont pas la contrainte.** La marge brute dépasse 94 % au prix le plus bas de la fourchette marché, dès 10 propriétés. Le coût marginal d'une propriété supplémentaire (~2,35 $) est négligeable devant tout prix envisageable.

**Conséquence directe sur la décision pricing** : elle ne peut pas être construite en cost-plus — le coût ne contraint rien. C'est un arbitrage **valeur / disposition à payer / positionnement**, à trancher sur :

1. la valeur mesurée chez le pilote (trust-KPI, [HOS-177](https://linear.app/hospitalityagent/issue/HOS-177)) — pas disponible avant novembre ;
2. l'ancrage concurrentiel (Venli 99-299 €, marché mid-market Apaleo) ;
3. l'écart à expliquer entre cet ancrage et la reco interne 500-2 500 $ — **un facteur 5 à 8 que ce modèle de coûts ne justifie pas** et qui doit se défendre sur la valeur.

**Le vrai risque économique n'est pas le coût de service, c'est le coût d'acquisition et le churn** — hors périmètre de cette story.

---

## 6. Limites

- **Aucun chiffre mesuré** (voir §Statut). Volumétrie nominale modélisée, pas observée.
- **Grilles infra à confronter aux factures réelles** — Fly.io, Supabase, Upstash, Twilio. Les ordres de grandeur suffisent à la conclusion §5 (la marge reste > 90 % même si les coûts infra doublent), mais pas à un business plan.
- **Twilio France, catégorie utility** — tarif à confirmer ; varie par pays et par catégorie de conversation.
- **Hors périmètre** : CAC, churn, LTV, coûts de support, temps fondateur. Cette story chiffre le **coût de service**, pas le modèle d'affaires.
- **À re-mesurer après HOS-176** — quand du trafic réel existe.

---

## Sources

- Tarifs Anthropic vérifiés le 2026-07-30 (Sonnet 4.6 : 3/15 $ · Haiku 4.5 : 1/5 $ par MTok)
- Configuration : `fly.toml` · `backend/app/providers/factory.py` · `backend/app/services/receipts.py:132` · `backend/app/main.py` (jobs APScheduler)
- Ancrages pricing : `docs/context/monitoring-watchlist.md` §W12 · `docs/context/open-decisions.md` §pricing
- Cadrage : `docs/planning/plan-90j-proof-visibility.md` §Phase C
