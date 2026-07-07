# Plan 90 jours — Proof & Visibility (juillet → octobre 2026)

> Dérivé de [`docs/context/analyse-critique-2026-07.md`](../context/analyse-critique-2026-07.md) (07/07/2026).
> Thèse : le différenciateur des 90 prochains jours = **preuve empirique + visibilité publique**, pas plus d'architecture.
> À convertir en 1 epic Linear "Proof & Visibility 90j" (~12 stories). Pas de nouveau ADR ni d'extension Mesh pendant cette période (Anima/Learning Engine gelés).

---

## Arbitrages actés (07/07/2026)

1. **Aetherix reste PRIVÉ.** Un **nouveau repo public** (méta-repo, historique frais) est créé — exécution de la Décision #25, Étape "pré-candidatures".
2. **ADR-0012 + docs mesh sensibles restent dans le repo privé** (conforme Décision #31 : le Signal Contract ne migre jamais vers le public).
3. Ticket GitHub Support Q2-01 : **pas encore envoyé** → à envoyer (S1, draft ci-dessous). Non-bloquant tant qu'Aetherix reste privé, mais hygiène à clore.

---

## Phase A — Hygiène & dette (S1, ~2-3 jours)

- [ ] Nettoyer la racine : `smoke-test-*.log`, `fiche-rag-*.html/pdf` (déplacer vers `docs/` ou supprimer).
- [ ] Résoudre le doublon `backend/app/api/routes/webhook.py` vs `webhooks.py`.
- [ ] Sortir `backend/app/main_story1_1_patch.py` (intégrer ou archiver).
- [ ] `docs/ARCHITECTURE.md` obsolète : réécrire court ou rediriger vers CLAUDE.md + mesh-architecture.md.
- [ ] Réparer le workflow `veille-hebdomadaire.yml` (en failure).
- [ ] Vérifier qu'aucun chemin (WhatsApp, MCP) ne peut livrer le fallback mock de `prediction_engine.predict()` (45 couverts hardcodés) à un humain sans flag `is_mock` visible.
- [ ] Élagage docs : passe de consolidation (objectif ~30 docs vivants, INDEX.md seule porte d'entrée ; archiver handoff/bmad/session périmés).

## Phase B — Sécurité & méta-repo public (S1-S2)

- [ ] **Envoyer le ticket GitHub Support** (draft §Ticket ci-dessous).
- [ ] Créer le **méta-repo public** (nom proposé : `hospitality-agentic-mesh` ou `aetherix`) : README architecture expurgée, périmètre construit vs vision **explicitement séparés** (bus factor assumé — crédibilité), liens case study, MIT.
- [ ] Contenu méta-repo : vision Mesh (sans Signal Contract), architecture Aetherix haut niveau, extraits publiables (benchmark notebook Phase C, article eval-gate), badges honnêtes.
- [ ] Mentions claires en haut des READMEs (méta-repo ↔ tacet-app ↔ case study).
- [ ] **Corriger le lien GitHub 404 sur ivandemurard.com/aetherix** → pointer le méta-repo.
- [ ] Tacet : CI + tests unitaires moteur acoustique (haversine, bearing, shielding) ; README honnête (retirer P2P/triangulation non implémenté, "3D"→2.5D, réviser branding ISR).
- [ ] Mettre à jour la ligne Décision #25 dans CLAUDE.md une fois le méta-repo livré.

### Ticket GitHub Support — draft (à envoyer via https://support.github.com/request, catégorie "Remove data from GitHub" / sensitive data)

> **Subject:** Purge cached commits & PR refs after history rewrite (leaked secrets file)
>
> Repository: `IvandeMurard/aetherix-hospitality-ai` (currently **private**, no forks, solo maintainer).
> A file `.env.fly` containing production secrets was committed, then removed from the entire history via `git filter-repo` + force-push on branches `main` and `hos-175`. All credentials have since been rotated. The rewritten refs are fully pushed (no branch-protection blocks).
>
> **First changed commit(s)** (pre-rewrite SHAs introducing `.env.fly`, both dated 2026-05-19):
> - `707083706eb398620cc96e4a7f913afaab95cdec`
> - `16621dda0dbb7e911bf1912b17f31c2293ad97d3` (rebased twin)
>
> Verified residual: commit `7070837` is still reachable server-side (confirmed via the REST API on 2026-07-07) through cached pull-request refs.
>
> **Affected pull requests: 56** — #127, #129–#159, #161–#184 (their `refs/pull/*/head` histories still contain `.env.fly`).
>
> **No Git LFS** is used in this repository (no orphaned LFS objects).
>
> **Requests:**
> 1. Run server-side garbage collection to expunge unreachable objects containing `.env.fly` (notably `7070837`, `16621dd` and their pre-rewrite ancestors).
> 2. Dereference the 56 affected pull requests / purge their cached refs, diffs and commit views.
> 3. Confirm no forks retain the pre-rewrite history (none are expected — private personal repo).
>
> The repository will remain private; this request is defense-in-depth after credential rotation.

> ⚠️ À savoir avant envoi : le Support peut « dereference or delete » les 56 PRs concernées — les pages de discussion restent normalement, mais les vues diff/commits de ces PRs peuvent devenir inaccessibles. Acceptable (repo privé, historique de merge conservé sur `main`).
> Audit réalisé le 07/07/2026 via clone bare temporaire + fetch `refs/pull/*/head` (clone supprimé après extraction).

## Phase C — Preuve empirique (S2-S8) — LE gros morceau

- [ ] **Backtest données réelles publiques** : dataset Kaggle *Recruit Restaurant Visitor Forecasting* (fréquentation réelle de restaurants JP + météo + fériés). Pipeline Aetherix tel quel → MAPE J+1/J+3/J+7 vs **baseline naïve** (moyenne des 4 derniers mêmes jours de semaine) vs LightGBM. Livrable : notebook publiable + section case study. Coût : 3-5 j. **Critère de succès : Prophet bat la baseline de ≥ 5 pts, sinon pivot modèle.**
- [ ] **Shadow mode restaurant réel** : obtenir 1 export CSV POS (12+ mois de couverts) d'un restaurateur du réseau → backtest FR réel, anonymisé. Livrable : "MAPE X % sur un restaurant parisien réel, +Y pts vs baseline".
- [ ] **Interviews validation décisionnelle (maillon 3)** : 5 × 30 min avec des F&B managers — horizon de figeage des plannings, ce qu'un forecast J+1 fiable changerait, valeur perçue du Daily Receipt. Tranche la tension J+1 (prédit) vs J+7 (décidé). Zéro code.
- [ ] **Closed-loop demo sandbox Apaleo** : script rejouant 30 jours simulés (seed réservations sandbox → forecast J-1 → reco WhatsApp → feedback manager simulé → couverts "réels" injectés → recalibration). Prouve **la plomberie de la boucle**, pas l'accuracy — l'annoncer tel quel. Livrable : rapport + **vidéo démo 3 min**.
- [ ] **Observabilité** : Pydantic Logfire (`logfire.instrument_fastapi(app)` + `instrument_anthropic()`, free tier, ~1 jour). Spans manuels pipeline forecast + event par trip de guardrail (rend NFR2 visible). Livrable : dashboard + screenshots (artefacts d'entretien + ops pilote — détecter les pannes silencieuses type webhook cassé).
- [ ] **Unit economics** : coût complet/propriété/mois (Claude + Fly + Twilio + Upstash) vs fourchettes pricing. Nourrit HOS-179. ½ journée.

## Phase D — Visibilité & capitalisation (S3-S12, en continu)

- [ ] **Case study ivandemurard.com/aetherix** : fix lien 404 ; remplacer le MAPE synthétique mis en avant par le benchmark réel (Phase C) ; intégrer la vidéo 3 min ; ajouter section "Engineering" (screenshots dashboard Logfire, CI eval-gate, trace guardrail).
- [ ] **Article technique long** : "Blocking CI on ML eval: making Prophet deterministic in GitHub Actions" (matériel Décision #29 : canari 3 runs, variance 0.00pp). Dev.to/Medium + soumission HN.
- [ ] **Série LinkedIn** (4-6 posts / 6 semaines) : benchmark Recruit · eval-gate · guardrails · post-mortem incident Q2-01 (les post-mortems honnêtes performent) · closed-loop demo.
- [ ] **Écosystème MCP** : soumettre le serveur MCP Aetherix aux registries/listes communautaires MCP.
- [ ] **Écosystème hospitality tech** : communauté développeurs Apaleo (canal le plus qualifié, cf. Décision #21) ; viser 1 talk meetup IA/agents Paris.
- [ ] **Ciblage emploi** : candidatures directes Mews, Apaleo, Lighthouse, Amenitiz, Nory, Tenzo + équipes applied-AI, case study en annexe. Pitch : "comment je conçois, évalue et sécurise un système agentique en production".

## Phase E — Angles stratégiques à documenter (S4-S10, validés 07/07)

- [ ] **Note de positionnement wedge** : Daily Receipt = surface produit/rituel ; forecast = moteur. North-star = acceptance + weekly usage ; MAPE = exigence interne. (Coexistence, pas antinomie — hiérarchie.)
- [ ] **Doc moat** : mémoire cognitive par propriété (contexte + signal + feedback), PMS-agnostic (schéma canonique #28), effet réseau multi-propriété (Hive prior). Le tester contre la menace plateforme.
- [ ] **Menace plateforme** : que reste-t-il si Apaleo/Mews shippent un forecast F&B natif ? Réponse écrite.
- [ ] **Page concurrence frontale** : Nory / Tenzo / 5-Out / Avero — pourquoi ils n'ont pas gagné le segment hôtel.
- [ ] **One-pager conformité prospect** : DPA, RGPD WhatsApp (Q2-03), posture sandbox/non-PII — pour le premier hôtel sérieux.
- [ ] **Déclaration bus factor / périmètre honnête** dans le méta-repo : construit vs north star.

---

## Ce qu'on ne fait PAS pendant 90 jours

Nouveaux ADRs · extension Mesh (Anima, Learning Engine, ontologies) · features Phase 4-5 · raffinement gouvernance. Chaque heure de design fiction se paie en heures de preuve non faite.

## Critères de sortie (J+90)

1. Un benchmark MAPE sur données **réelles** publié (Recruit + si possible 1 resto FR).
2. Méta-repo public en ligne, case study réparé et enrichi (vidéo + engineering).
3. 1 article technique publié + série LinkedIn entamée.
4. Boucle outcome-capture démontrée end-to-end (sandbox) avec observabilité.
5. Réponse écrite aux 5 maillons de la chaîne de valeur (interviews incluses).
