# Kit LinkedIn — expérience Aetherix (v2, 09/07/2026)

> Story 16.14 / étape 5. **Remplacement copier-coller direct** de l'entrée LinkedIn actuelle.
> Garde la voix et les meilleures formules de la version précédente (triade cognitive,
> "power of a hive"), corrige 2 erreurs factuelles (Qdrant retiré, HiveMemory non shippée),
> réordonne pour mener avec le construit, intègre la preuve de juillet.
> Discipline : `positionnement-wedge.md` §Dire/Ne plus dire. **Zéro cadratin (contenu public).**

---

## ENTRÉE EXPÉRIENCE — version EN (à copier-coller)

**Founder & Product Engineer, Aetherix (Hospitality Agentic Mesh)** · Nov 2025 – present

Learning AI by building an operational memory for hotel operations: a network of specialized,
MCP-native agents that anticipate needs, check themselves against real outcomes, and learn from
every service. The forecast is an organ, not the product. Human-in-the-loop by design: agents
recommend, the manager validates.

The thesis (understand · measure · learn):
- Understand like a human: contextual reasoning grounded in each property's own history.
- Measure like a machine: every recommendation is captured next to its real outcome, so the
  system knows what it said and what happened.
- Learn like a network: per-property memory today, federated priors across properties next,
  to give independents the power of a hive.

What is actually built (Aetherix, the F&B node, live on staging):
- A closed learning loop: forecast, WhatsApp recommendation, manager feedback, outcome capture,
  weekly recalibration. In a 30-day regime-shift demo, recalibration cut post-shift error from
  15.9% to 12.3% (sandbox data, real mechanics, deterministic, script public).
- Honest evaluation: a real-data benchmark (30 restaurants, Kaggle Recruit) published including
  where the model does NOT beat the naive baseline; the forecast eval runs as a blocking CI gate
  (deterministic Prophet-in-CI, inspired by Qonto's working-vs-reliable framework).
- Reliability: typed runtime guardrails (dead-man's switch, feedback-to-training bounds, output
  sanity), every trip logged with a machine-readable reason; a bad POS export (900 covers for
  120 seats) is rejected before it can poison training. OpenTelemetry/Logfire traces down to LLM
  cost per recommendation.
- Delivery: WhatsApp push with a natural-language feedback loop; per-property private memory with
  fallback on shared patterns; MCP server callable by any orchestration agent; tenant-scoped data.
- Practiced incident response: a leaked-secrets incident handled end to end (history rewrite,
  11/11 credential rotation, GitHub-side purge, public post-mortem).

The wider mesh (honest status, not all built):
- Aetherix, the F&B node: built (above).
- Tacet, the environmental-signal node: working prototype (acoustic ray-casting over building
  footprints), public repo.
- Orchestrator, the supervisory agent: proto-stub.
- Anima, the guest cognition node: design thesis (four memory layers, scope-gated, privacy-first
  with a DPIA gate before any build). Aetherix is the proof; Anima is the promise.

Architecture and the closed-loop demo are public on GitHub; roadmap tracked in Linear.

Stack: Python 3.12 · FastAPI · Claude Sonnet (multi-LLM provider abstraction) · Prophet ·
pgvector · Supabase · Redis · Twilio · Fly.io · Apaleo API (OAuth2 + native MCP).

---

## ENTRÉE EXPÉRIENCE — version FR

**Fondateur & Product Engineer, Aetherix (Hospitality Agentic Mesh)** · Nov 2025 – présent

Apprendre l'IA en construisant une mémoire opérationnelle pour l'hôtellerie : un réseau d'agents
spécialisés, MCP-natifs, qui anticipent les besoins, se confrontent aux résultats réels et
apprennent de chaque service. Le forecast est un organe, pas le produit. Human-in-the-loop par
construction : les agents recommandent, le manager valide.

La thèse (comprendre · mesurer · apprendre) :
- Comprendre comme un humain : raisonnement contextuel ancré dans l'historique propre à chaque
  établissement.
- Mesurer comme une machine : chaque recommandation est capturée à côté de son résultat réel, le
  système sait ce qu'il a dit et ce qui s'est passé.
- Apprendre comme un réseau : mémoire par établissement aujourd'hui, priors fédérés entre
  établissements ensuite, pour donner aux indépendants la puissance d'une ruche.

Ce qui est réellement construit (Aetherix, le nœud F&B, en ligne sur staging) :
- Une boucle d'apprentissage fermée : forecast, recommandation WhatsApp, feedback manager,
  capture du résultat, recalibration hebdomadaire. Sur un choc de demande de +25 %, la
  recalibration ramène l'erreur de 15,9 % à 12,3 % (données sandbox, mécanique réelle, script public).
- Évaluation honnête : benchmark sur données réelles (30 restaurants, Kaggle Recruit) publié y
  compris là où le modèle ne bat pas la baseline naïve ; l'éval forecast est un gate CI bloquant
  (Prophet déterministe, inspiré du cadre "working vs reliable" de Qonto).
- Fiabilité : guardrails runtime typés, chaque déclenchement loggé avec une raison machine-lisible ;
  un export POS aberrant (900 couverts pour 120 places) est rejeté avant de polluer l'apprentissage.
  Traces Logfire jusqu'au coût LLM par recommandation.
- Livraison : push WhatsApp avec boucle de feedback en langage naturel ; mémoire privée par
  établissement ; serveur MCP appelable par tout agent orchestrateur.
- Réponse à incident pratiquée : fuite de secrets gérée de bout en bout (réécriture d'historique,
  rotation 11/11 clés, purge GitHub, post-mortem public).

Le mesh élargi (statut honnête, tout n'est pas construit) :
- Aetherix, nœud F&B : construit (ci-dessus).
- Tacet, nœud de signaux environnementaux : prototype fonctionnel (ray-casting acoustique), public.
- Orchestrateur, agent superviseur : proto-stub.
- Anima, nœud de cognition guest : thèse de design (4 couches mémoire, accès scope-gated,
  privacy-first avec gate DPIA). Aetherix est la preuve, Anima est la promesse.

Stack : Python 3.12 · FastAPI · Claude Sonnet · Prophet · pgvector · Supabase · Redis · Twilio ·
Fly.io · Apaleo API (OAuth2 + MCP natif).

---

## Headline (champ sous le nom)

EN : *Product engineer building operational memory for hospitality: AI agents that learn from
every service. Evals as merge gates, typed guardrails, human-in-the-loop by design.*

FR : *Je construis la mémoire opérationnelle de l'hôtellerie : des agents IA qui apprennent de
chaque service. Evals bloquantes en CI, guardrails typés, human-in-the-loop par construction.*

## À propos (résumé)

The prediction layer is commoditizing; memory is not. I build AI systems for hotel operations
around one loop: anticipate, capture the outcome, self-report the miss, guard the training data,
recalibrate. My own benchmark showed the model ties a naive baseline on the median day.
Publishing that made the thesis stronger: the moat is the closed loop and the per-property memory
it compounds, not the model. What I bring to a team: evals as blocking merge gates, typed failure
reasons, ADR discipline (31 indexed decisions), practiced incident response, and a weekly
discovery routine (automated market scan plus adversarial architecture reviews with multiple
frontier models).

---

## Ce qui change vs la version précédente (pour référence)

| Correction | Avant | Après |
|---|---|---|
| **Erreur stack** | "Qdrant" listé | retiré (pgvector uniquement, HOS-99/Décision #3) |
| **Surclaim** | "cross-hotel pattern learning (HiveMemory)" sous *built* | mémoire privée par établissement (construit) + priors fédérés au futur |
| **Crédibilité nœuds** | "4 agents" à plat, Anima en tête | mène avec Aetherix construit ; statuts honnêtes prototype/stub/design |
| **Cadrage** | forecast-led | mémoire-led (le forecast est un organe) |
| **Fraîcheur** | "built May 2026" | preuve de juillet : benchmark réel, boucle fermée, guardrails, Logfire, incident |
| **Formules gardées** | — | triade comprendre/mesurer/apprendre · "power of a hive" (au futur) |

## Règles d'usage (inchangées)

- **Ne jamais** mettre en avant : "76,7 % acceptance" (manager simulé), "MAPE 15,09 %" (retiré,
  circulaire), "-3 à -8 % labor cost" (cible non mesurée).
- Post #1 de la série LinkedIn (16.14 AC2) = teaser de `article-operational-memory.md` + lien.
  Suivants : eval-gate déterministe · guardrails/G-3 · post-mortem Q2-01.
- Mettre à jour après HOS-308 (premier chiffre restaurant FR réel) et après le pilote.
- Contenu public = zéro cadratin (règle mémoire working-style, 08/07).
