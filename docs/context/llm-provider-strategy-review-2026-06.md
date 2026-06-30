# LLM Provider Strategy — Revue d'architecture reasoning (2026-06-23)

> Analyse différentielle pré-pilote de la stratégie LLM. Déclencheur : question PM « est-il pertinent de laisser le reasoning à Claude Sonnet seul ? »
> Statut : analyse close → 3 stories de remédiation créées ([HOS-282](https://linear.app/hospitalityagent/issue/HOS-282), [HOS-283](https://linear.app/hospitalityagent/issue/HOS-283), [HOS-284](https://linear.app/hospitalityagent/issue/HOS-284)).
> Ne remet PAS en cause la Décision #1 (Claude Sonnet > Mistral/GPT) ni la Décision #9 (abstraction `LLMProvider`).

---

## 1. État réel (vérifié dans le code)

| Couche | Modèle | Rôle |
|---|---|---|
| Reasoning / explainability | **Claude Sonnet** (`claude-sonnet-4-6`) | Raisonnement + explicabilité |
| Fallback | **Gemini** (puis OpenAI prévu) | Résilience sur panne primaire |
| Embeddings | **Mistral** (`mistral-embed`, 1024d) | Vectorisation mémoire — **PAS du reasoning** |
| Forecast | **Prophet** (Meta) | Time-series covers — le vrai ML |

**Correction d'un malentendu fréquent :** Mistral n'est pas « le ML ». Mistral fait les **embeddings**. Le ML de prévision = Prophet. Le reasoning = Claude Sonnet.

---

## 2. Le fallback ne couvre PAS l'hallucination

`FallbackLLMProvider` (`backend/app/providers/fallback_provider.py`) est un **parachute de disponibilité** : il se déclenche uniquement quand le primaire **plante** (5xx / timeout / réseau ; les 4xx sont re-raise immédiatement car identiques sur le secours). Si Claude répond « normalement » (HTTP 200) mais **hallucine ou raisonne faux**, le fallback ne se déclenche jamais.

Trois mécanismes distincts — à ne pas confondre :

| Mécanisme | Se déclenche quand… | Couvre l'hallucination ? | Statut Aetherix |
|---|---|---|---|
| **Fallback** (failover) | Le LLM primaire **plante** | ❌ Non | ✅ En place (Claude→Gemini) |
| **Ensemble / cross-check** | Toujours (2 modèles comparent) | ✅ Oui | ❌ Absent |
| **Verifier / LLM-judge** | 2e appel valide le 1er | ✅ Oui | ❌ Absent (spike → HOS-284) |
| **Human-in-the-loop** | L'humain valide avant action | ✅ Oui (humain) | ✅ En place (Décision #6) |

**Garde-fou actuel contre le mauvais raisonnement = l'humain** (HITL, Décision #6 pas d'auto-actions MVP + Décision #5 reasoning visible). C'est volontaire et, tant que l'humain valide, plus robuste qu'un 2e LLM (qui hallucine aussi). La question « faut-il un verifier LLM ? » ne devient critique que le jour où l'on retire l'humain de la boucle (auto-actions, Phase 4+).

---

## 3. Conclusion stratégique : garder Sonnet primaire jusqu'à fin de pilote

Le débat n'est pas « Claude seul » (faux problème : résilience + portabilité déjà acquises) mais « single-model primaire vs routing/ensemble ». Verdict : **rester single-model primaire**, car :

1. **Pas de lock-in** — l'abstraction `LLMProvider` (#9) + le fallback sont l'assurance ; inutile de l'exercer sans données.
2. **Harnais calibré sur un comportement** — eval gate (#22) + prompts tunés Sonnet ; fragmenter = ré-évaluer chaque chemin au pire moment (pré-pilote).
3. **La concentration Anthropic est un atout GTM** (Décision #21, sales evidence) — diversifier le primaire affaiblit le narratif ; le fallback Gemini donne déjà l'argument « pas de SPOF ».
4. **Simplicité > optimisation** avant product-market fit.

Le vrai levier court terme est **vertical** (tiering dans la famille Claude), pas latéral (autres vendeurs).

---

## 4. Le « taux de rejet proche de 0% » est un piège

Distinguer trois métriques que l'objectif PM mélangeait :

| Métrique | Définition | Cible saine |
|---|---|---|
| **Taux d'erreur** | Reco factuellement fausse / mauvaise | → proche de 0% |
| **Taux de rejet** | Manager décline d'agir | **PAS 0%** |
| **Taux d'acceptation** (`recommendation_acceptance_rate`) | Recos suivies | Élevé, mais pas 100% ; alerte si < 30% |

Un taux de rejet à 0% = HITL devenu théâtre (validation aveugle, plus de contre-pouvoir). Un peu de rejet = supervision humaine qui fonctionne. Pas de benchmark sectoriel propre (très produit-spécifique). Proxies objectifs existants : **MAPE < 15%** + **acceptance_rate**.

« Outputs fiables et vérifiés » — la moitié existe déjà :
1. Eval-by-design amont (Décision #22) → ✅ Epic 11 ([HOS-203](https://linear.app/hospitalityagent/issue/HOS-203))
2. Gating par confiance (dégrader sous seuil) → ✅ [HOS-251](https://linear.app/hospitalityagent/issue/HOS-251)
3. Grounding / citations (receipts) → ✅
4. Alerting sur dérive → ✅ [HOS-249](https://linear.app/hospitalityagent/issue/HOS-249)
5. Verifier / LLM-judge sur outputs fort impact → ❌ manquant
6. Boucle outcome (réel vs prédit) → ✅ feedback ingestion (HOS-250)

---

## 5. Findings → remédiations

| # | Finding | Story | Priorité |
|---|---|---|---|
| F1 | Fallback couvert uniquement par tests **mockés** → pourrit en silence (clé Gemini expirée / contrat dérivé → CI verte mais parachute mort) | [HOS-282](https://linear.app/hospitalityagent/issue/HOS-282) — canari d'intégration réel | 🟠 High |
| F2 | Classifieur inbound nommé « Haiku » (`receipts.py:477`) mais tourne sur **Sonnet** (singleton modèle fixe, pas d'override `model=`) → surcoût | [HOS-283](https://linear.app/hospitalityagent/issue/HOS-283) — override `model=` + Haiku réel | 🟡 Medium |
| F3a | Pas d'instrumentation accept/reject explicite ni de mesure du taux « confidently wrong » | [HOS-284](https://linear.app/hospitalityagent/issue/HOS-284) — instrumentation (fondation) | 🟡 Medium |
| F3b | Pas de vérification (judge) sur outputs fort impact | [HOS-286](https://linear.app/hospitalityagent/issue/HOS-286) — spike verifier (VoI), bloqué par HOS-284 | 🟡 Medium |
| F3c | Échecs « confidently wrong » non transformés en tests permanents | [HOS-287](https://linear.app/hospitalityagent/issue/HOS-287) — boucle apprentissage→golden dataset, bloqué par HOS-284 | 🟡 Medium |

**Décision technique tranchée (F2) :** override `model: str | None = None` sur `complete()` plutôt qu'une 2e instance de provider dans le `lifespan` (moins d'objets, pas de duplication de la logique fallback). Tiering reste dans la famille Claude (Haiku/Sonnet).

**Posture (F3) :** instrumentation d'abord, verifier en spike gated — ne construire le 2e LLM que si la donnée pilote montre un besoin, tant que l'humain valide.

---

## 6. Raffinements (dialogue PM, 2026-06-23) — repris dans HOS-284 / HOS-286 / HOS-287

**Trust = north-star, pas levier.** L'érosion de confiance opérateur est le risque n°1 du pilote, mesurée au Niveau 3 (`recommendation_acceptance_rate`, `weekly_operational_usage`). Mais c'est un *outcome* gagné via le Niveau 1 (accuracy/MAPE) — à lire **conjointement** : acceptance élevé + MAPE dégradé = manager qui valide en aveugle (piège du rejet-0%, bis).

**Deux clients, un seul exposé pendant le pilote.** L'opérateur B2B voit la mauvaise reco *même rejetée* → confiance érodée, HITL ne couvre PAS. Le guest est lui médiatisé par le HITL. Le risque dominant du pilote = confiance B2B.

**Le « 3e client à critères stricts » = eval-as-contract.** Bonne intuition ; il a deux incarnations : (i) **eval-contract offline** (golden dataset, Epic 11) — déterministe, ~gratuit, à renforcer en priorité ; (ii) **judge runtime** — coûteux, réservé aux outputs fort impact, sur la seule classe résiduelle « confidently wrong » (passe le confidence-gating mais faux). Garde-fou : les critères du judge doivent s'ancrer dans du déterministe / label humain — pas de LLM qui se valident sans sol.

**Pricer le judge = Value-of-Information**, pas la formule heuristique `taux_bad_rec × élasticité × scale × autonomie` (cadrage d'intuition, non standard, non validé). VoI = `P(reco fausse) × coût(erreur)` vs coût judge, **faux positifs du judge inclus** (supprimer une reco correcte érode la confiance par l'autre bout).

**Apprentissage autonome — 3 niveaux à ne pas confondre :**
- (a) Apprendre de l'outcome → ✅ sûr, existe (HOS-250 + `operational_memory`).
- (b) Diagnostiquer la cause racine → 🟡 assistif seulement (zone n°1 d'hallucination), human-reviewed.
- (c) Auto-corriger logique/modèle sans humain → 🔴 hors scope, ligne rouge gouvernance (Décision #6). Renvoi décisions ouvertes Phase 5 (Learning Engine, off-policy eval).

La boucle d'apprentissage *sûre et durable* : échec → capture outcome → flag hypothèse → mémoire → **promotion en cas du golden dataset** (ne plus jamais régresser). L'apprentissage qui compose sans auto-modification.
