# Kit LinkedIn — expérience Aetherix (v2, 09/07/2026)

> Story 16.14 / étape 5. **Remplacement copier-coller direct** de l'entrée LinkedIn actuelle.
> Garde la voix et les meilleures formules de la version précédente (triade cognitive,
> "power of a hive"), corrige 2 erreurs factuelles (Qdrant retiré, HiveMemory non shippée),
> réordonne pour mener avec le construit, intègre la preuve de juillet.
> Discipline : `positionnement-wedge.md` §Dire/Ne plus dire. **Zéro cadratin (contenu public).**

---

## ENTRÉE EXPÉRIENCE — version EN (à copier-coller)

**Founder & Product Engineer, Aetherix (Hospitality Agentic Mesh)** · Nov 2025 – present

Learning AI by building a living operational memory for hotels, one that improves with every
service. A network of specialized, MCP-native agents that anticipate needs, check themselves
against real outcomes, and learn as they go. The forecast is an organ, not the product.
Human-in-the-loop by design: agents recommend, the manager stays in control.

The thesis (understand · measure · learn):
- Understand like a human: contextual reasoning grounded in each property's own history.
- Measure like a machine: every recommendation is captured next to its real outcome, so the
  system knows what it said and what happened.
- Learn like a network: per-property memory today, federated priors across properties next,
  to give independents the power of a hive.

What it does for a manager (Aetherix, the F&B node, live on staging):
- A daily rhythm you actually keep: the evening before, one WhatsApp message with tomorrow's
  expected covers and the staffing to match. One tap to accept, or reply with your own number.
  Your correction is what trains the model.
- An agent that asks only when it matters: when it is unsure, it says so and shows a safe
  fallback instead of a confident guess, and it stays quiet unless something is genuinely wrong.
  No dashboard to check, no alert fatigue.
- It gets better every week: yesterday's real covers come back, the miss is named out loud, and
  the model recalibrates. When demand jumped 25% overnight in a stress test, the error fell back
  from 15.9% to 12.3% on its own.
- Honest about what it can and can't do: benchmarked on 30 real restaurants and published in
  full, including the days it only matches a simple baseline. No inflated demo numbers.

Under the hood, for the engineers: a closed learning loop with typed runtime guardrails (bad POS
export of 900 covers for 120 seats is rejected before it can poison training), a blocking
eval-gate in CI (deterministic Prophet-in-CI, inspired by Qonto's working-vs-reliable framework),
end-to-end Logfire tracing down to LLM cost per recommendation, and a real leaked-secrets
incident handled end to end (history rewrite, 11/11 credential rotation, public post-mortem).

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

Apprendre l'IA en construisant une mémoire opérationnelle vivante pour l'hôtellerie, qui
s'améliore à chaque service. Un réseau d'agents spécialisés, MCP-natifs, qui anticipent les
besoins, se confrontent aux résultats réels et apprennent au fil de l'eau. Le forecast est un
organe, pas le produit. Human-in-the-loop par construction : les agents recommandent, le manager
garde le contrôle.

La thèse (comprendre · mesurer · apprendre) :
- Comprendre comme un humain : raisonnement contextuel ancré dans l'historique propre à chaque
  établissement.
- Mesurer comme une machine : chaque recommandation est capturée à côté de son résultat réel, le
  système sait ce qu'il a dit et ce qui s'est passé.
- Apprendre comme un réseau : mémoire par établissement aujourd'hui, priors fédérés entre
  établissements ensuite, pour donner aux indépendants la puissance d'une ruche.

Ce que ça fait pour un manager (Aetherix, le nœud F&B, en ligne sur staging) :
- Un rituel quotidien qu'on tient vraiment : la veille au soir, un message WhatsApp avec les
  couverts attendus demain et le staffing qui va avec. Un tap pour valider, ou votre propre
  chiffre en réponse. Votre correction est ce qui entraîne le modèle.
- Un agent qui ne sollicite que quand ça compte : en cas de doute, il le dit et propose un repli
  sûr plutôt qu'une estimation péremptoire, et il reste silencieux sauf vrai problème. Pas de
  dashboard à surveiller, pas de fatigue d'alertes.
- Il progresse chaque semaine : les couverts réels de la veille reviennent, l'écart est nommé, le
  modèle se recalibre. Quand la demande a bondi de 25 % du jour au lendemain en test, l'erreur
  est retombée de 15,9 % à 12,3 % d'elle-même.
- Honnête sur ce qu'il sait et ne sait pas faire : benchmark sur 30 restaurants réels, publié en
  entier, y compris les jours où il égale seulement une baseline simple. Pas de chiffres de démo gonflés.

Sous le capot, pour les ingénieurs : boucle d'apprentissage fermée avec guardrails runtime typés
(un export POS de 900 couverts pour 120 places est rejeté avant de polluer l'entraînement),
eval-gate bloquant en CI (Prophet déterministe, inspiré du cadre "working vs reliable" de Qonto),
tracing Logfire de bout en bout jusqu'au coût LLM par recommandation, et une vraie fuite de
secrets gérée de A à Z (réécriture d'historique, rotation 11/11 clés, post-mortem public).

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

## Angle anti-fatigue HITL (matière à post + preuve en entretien)

Le HITL d'Aetherix est conçu pour ne pas épuiser le manager. Cinq décisions le portent — utile
en entretien ("comment évitez-vous la fatigue de validation ?") et comme post LinkedIn dédié :

- **Décision #5** : raisonnement replié par défaut (réduction de charge cognitive).
- **ADR-0007 §D6** : contrat d'abstention `AgentAbstention` — l'agent dit "je ne sais pas" plutôt
  que d'émettre du bruit ; abstention partielle (le forecast reste affiché si la reco s'abstient).
- **ADR-0009 G-4** : circuit-breaker à confiance étagée — confiance basse → rétrograde/flague,
  jamais ne supprime ; seul le Tier 2 (dégradation grave) alerte, le Tier 1 est un caveat silencieux.
- **Décision #15** : feedback entrant auto-classifié (auto-`modified` si confiance < 0.6) — l'agent
  range le retour plutôt que de relancer.
- **Décision #6 + seuils config-driven** : le manager contrôle quelles tâches exigent validation,
  réglable en pilote sans redéploiement.

Punchline : *"The agent earns trust by asking only when it matters."*

## Règles d'usage (inchangées)

- **Ne jamais** mettre en avant : "76,7 % acceptance" (manager simulé), "MAPE 15,09 %" (retiré,
  circulaire), "-3 à -8 % labor cost" (cible non mesurée).
- Post #1 de la série LinkedIn (16.14 AC2) = teaser de `article-operational-memory.md` + lien.
  Suivants : eval-gate déterministe · guardrails/G-3 · post-mortem Q2-01.
- Mettre à jour après HOS-308 (premier chiffre restaurant FR réel) et après le pilote.
- Contenu public = zéro cadratin (règle mémoire working-style, 08/07).
