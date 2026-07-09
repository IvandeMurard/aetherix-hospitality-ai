# Kit LinkedIn — expérience Aetherix alignée sur le wedge (09/07/2026)

> Story 16.14 / étape 5. À copier-coller dans le profil. Deux versions (EN pour la portée
> internationale hospitality-tech + FR). Discipline de langage : `positionnement-wedge.md` §Dire/Ne plus dire.
> Règle de fond : chaque affirmation est adossée à un artefact public vérifiable.

---

## Expérience (entrée principale)

**Titre du poste** : Founder & Product Engineer — Aetherix (Hospitality Agentic Mesh)
**Type** : Independent project / Self-employed · **Dates** : Nov 2025 – aujourd'hui
**Lien média à attacher** : https://github.com/IvandeMurard/hospitality-agentic-mesh + https://ivandemurard.com/aetherix

### Version EN (recommandée en principal)

Building an operational memory system for hotel F&B: an AI agent that anticipates demand,
checks itself every morning, says so when it drifts, and learns from every service. Delivered
over WhatsApp where managers already work. Human-in-the-loop by design: the agent recommends,
the manager validates.

Solo, end to end: product thesis, architecture, code, evals, security, go-to-market.

- Closed learning loop in production-grade code: forecast → recommendation → manager feedback →
  outcome capture → weekly recalibration. In a 30-day regime-shift demo, recalibration cut
  post-shift error from 15.9% to 12.3% (sandbox data, real mechanics — script and full ledger
  public).
- Honest evaluation culture: real-data benchmark (30 restaurants, Kaggle Recruit) published
  including where the model does NOT beat the naive baseline; retired my own circular synthetic
  metric publicly. Forecast eval runs as a blocking CI gate (deterministic Prophet-in-CI).
- Reliability engineering: typed runtime guardrails (dead-man's switch, feedback-to-training
  bounds, output sanity), every trip logged with a machine-readable reason; OpenTelemetry/Logfire
  traces down to LLM cost per recommendation.
- Practiced incident response: leaked-secrets incident handled end to end (history rewrite,
  11/11 credential rotation, GitHub-side purge, public post-mortem).
- Stack: FastAPI · Python async · Supabase Postgres + pgvector · Prophet · Claude (multi-LLM
  provider abstraction) · MCP-native tools · Twilio WhatsApp · Apaleo PMS · Fly.io.

### Version FR

Conception d'un système de mémoire opérationnelle pour la restauration hôtelière : un agent IA
qui anticipe la demande, s'auto-évalue chaque matin, signale ses dérives et apprend de chaque
service. Livré sur WhatsApp, là où les managers travaillent déjà. Human-in-the-loop par
construction : l'agent recommande, le manager valide.

En solo, de bout en bout : thèse produit, architecture, code, évaluation, sécurité, distribution.

- Boucle d'apprentissage fermée : forecast → recommandation → feedback manager → capture des
  résultats → recalibration hebdomadaire. Sur un choc de demande de +25 %, la recalibration
  ramène l'erreur de 15,9 % à 12,3 % (données sandbox, mécanique réelle — script public).
- Culture d'évaluation honnête : benchmark sur données réelles publié y compris là où le modèle
  ne bat pas la baseline naïve ; gate d'éval bloquant en CI (Prophet déterministe).
- Fiabilité : guardrails runtime typés, chaque déclenchement loggé avec raison machine-lisible ;
  traces Logfire jusqu'au coût LLM par recommandation.
- Réponse à incident pratiquée : fuite de secrets gérée de bout en bout (réécriture d'historique,
  rotation 11/11 clés, purge GitHub, post-mortem public).

---

## Headline (le champ sous le nom)

EN : *Product engineer building operational memory for hospitality — AI agents that learn from
every service. Evals as merge gates, guardrails with typed reasons, human-in-the-loop by design.*

FR : *Je construis la mémoire opérationnelle de l'hôtellerie — des agents IA qui apprennent de
chaque service. Evals bloquantes en CI, guardrails typés, human-in-the-loop par construction.*

## À propos (bloc à insérer/adapter dans le résumé)

The prediction layer is commoditizing; memory is not. I build AI systems for hotel operations
around one loop: anticipate, capture the outcome, self-report the miss, guard the training
data, recalibrate. My benchmark showed my own model ties the naive baseline on the median day.
Publishing that made the product thesis stronger: the moat is the closed loop and the
per-property memory it compounds, not the model.

What I bring to a team: evals as blocking merge gates, typed failure reasons, ADR discipline
(31 indexed decisions), practiced incident response, and a weekly discovery routine (automated
market scan + adversarial architecture reviews with multiple frontier models).

## Règles d'usage

- **Ne jamais** mettre en avant : « 76,7 % acceptance » (manager simulé), « MAPE 15,09 % »
  (retiré, circulaire), « -3 à -8 % labor cost » (cible non mesurée).
- Le premier post de la série LinkedIn (16.14 AC2) = l'article `article-operational-memory.md`
  en teaser + lien. Les suivants : eval-gate déterministe · guardrails/G-3 · post-mortem Q2-01.
- Mettre à jour l'entrée après HOS-308 (premier chiffre restaurant FR réel) et après le pilote.
