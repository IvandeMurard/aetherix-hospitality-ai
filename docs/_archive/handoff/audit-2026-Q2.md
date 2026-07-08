# Hand-off — Audit différentiel pré-pilote (HOS-277)

> **Statut :** cadrage validé SM 2026-06-20 · **Linear :** [HOS-277](https://linear.app/hospitalityagent/issue/HOS-277) (Epic) · **Gate aval :** pilote HOS-176
> **Pour :** agent QA / Architect, session dédiée. Tu **audites**, tu ne développes pas de feature.

Ce document survit hors-chat : c'est le plan d'action + le hand-off self-contained. Source de vérité = HOS-277 (peut diverger si amendé).

---

## 0. Bootstrap — lire en premier

1. **HOS-277** (Linear) — cadrage, scope, axes, méthode, DoD.
2. **Audit d'origine** `docs/context/security-review-2026-05-01.md` (608 l., 8 axes, **format à répliquer**).
   ⚠️ Ce fichier vit sur la branche `claude/epic12-conformite-closure` (PR #176) tant qu'elle n'est pas mergée. Récupère-le via `git show claude/epic12-conformite-closure:docs/context/security-review-2026-05-01.md`.

## 1. Contexte & environnement

- **Repo actif** : `aetherix-hospitality-ai` — **PAS** le clone `Hospitality-Operations-Agentic-AI-B2B` (divergent, branche apaleo-sandbox). Cette divergence 2-repos est elle-même l'**axe 10**.
- **Python** : `backend/.venv/Scripts/python.exe` (3.12.10) ou `uv run --project backend`.
- **Base du diff** : **`c613a71`** (base de l'audit 01/05). Auditer `git diff c613a71..main` = **+17 026 / −1 285, 180 fichiers, 103 commits backend**.
- **PRs récentes** : #175 (HOS-274 eval-gate refreeze) **mergée** ; #176 (clôture conformité Epic 12) en attente.

## 2. Scope

- **IN** : Aetherix F&B execution node, delta `c613a71..main`.
- **OUT** : Anima, POS (Epic 13), Context Graph (Epic 14), frontend (thin). **Cold-start meta-learner (sprint 9, HOS-192/193/195) → auditer APRÈS son merge.**

## 3. Méthode (cœur de l'optimisation : différentiel + gate-leverage)

Par axe, demander **« y a-t-il un gate CI ? »** :
- **Gate existant** → vérifier *gate vert + couvre le nouveau code* (ne PAS re-trouver à la main ce que le CI attrape) :
  `scripts/ci/check_schema_drift.py` (schéma), `audit_id_types.py` (types id), `audit_rls_policies.py` (RLS/tenant), `check_eval_coverage.py` (eval), `smoke_test_e2e.py` (E2E). Workflows : `ci.yml`, `ci-integration.yml`, `eval-gate.yml`.
- **Pas de gate** → revue LLM/humaine du **delta uniquement**.

| # | Axe | Gate |
|---|---|---|
| 1 Sécurité (auth/secrets/PII-in-logs) | partiel — manuel sur nouveaux endpoints |
| 2 Logique métier | ❌ |
| 3 Async / concurrence | ❌ (pattern session-in-`gather`) |
| 4 Résilience | partiel (heartbeats G-1 ✅) |
| 5 Intégrité données | ✅ schema_drift + id_types |
| 6 Cohérence archi | ❌ (dont divergence 2 repos) |
| 7 Performance | ❌ |
| 8 Observabilité | partiel |
| **9 (NEW) PII / RGPD** (données réelles) | ❌ |
| **10 (NEW) Intégrité repo/doc** (2 repos divergents ; ADR-0005 & audit historiquement non trackés) | ❌ |

## 4. Livrable A — Verify-the-fixes (audit 01/05 → Epic 9, 14 stories TOUTES Done)

Confirmer pour chaque ligne que le fix a atterri **ET** qu'un gate/test empêche la régression :

| Story (Done) | Findings | Preuve à confirmer |
|---|---|---|
| 9.0 HOS-162 | CI/CD | `ci.yml` = pytest+coverage+drift sur chaque PR |
| 9.1 HOS-149 | 1.1–1.4 | `AUTH_SECRET` fail-fast (pas de `SECRET_CHANGE_ME`) · HMAC webhook · auth+scope sur `/predict`,`/train`,`/auth/register` |
| 9.2 HOS-150 | 2.3,2.4,2.5,4.6,5.1,5.2,5.3 | `check_schema_drift.py` vert · plus de `Base.metadata.create_all` au boot |
| 9.3 HOS-151 | 2.1,2.2 | RAG/Memory/Recall reçoivent une session DB |
| 9.4 HOS-152 | 1.5,3.5,3.6 | `echo=False` · `pool_pre_ping`/`pool_recycle` |
| 9.5 HOS-153 | 3.1,3.2,3.3 | plus de session partagée dans `gather` · claim atomique |
| 9.6 HOS-154 | 8.3 | `agent_action_log` en session séparée (survit rollback) |
| 9.7 HOS-155 | 1.7,1.8,3.7,4.5 | HMAC URL derrière proxy · timeout/retry/DLQ |
| 9.8 HOS-156 | 3.4,4.3 | APScheduler unique · alerting d'exception |
| 9.9 HOS-157 | 2.6–2.9 | engine singleton via lifespan · `asyncio.to_thread` |
| 9.10 HOS-158 | 4.1,4.4,6.3–6.5,8.1–8.5 | Prometheus · JSON logs · fallback non sur-agressif |
| 9.11 HOS-159 | 5.4 | `audit_id_types.py` vert |
| 9.12 HOS-160 | 1.9,7.2,7.3 | cache embeddings · cache token OAuth Apaleo |
| 9.13 HOS-161 | §10 | `smoke_test_e2e.py` PASS sur staging |

**Vigilance régression prioritaire** (forte surface depuis) :
- (a) **non-retour de `echo=True` / PII-in-logs** — le quick-win data-réelle #1.
- (b) **gate RLS couvre les nouvelles tables** (`scheduler_event`, colonnes abstention, MV) avant données réelles.
- (c) **HOS-211** (path MAPE alert) replié dans G-1 — confirmer le wiring.
- (d) **findings « non tracés »** du 01/05 (§1.10, 1.11, 2.10–2.13, 5.5–5.9, 6.1, 6.2, 6.6, 7.1, 7.4–7.6) — non orphelins.

## 5. Livrable B — Audit différentiel

Revue du delta `c613a71..main` sur les 10 axes (§3). **Cibler le risque pilote** : paths PII/RLS, write-path feedback→training (G-3), path abstention/télémétrie (EVAL-2), migration staging du 20/06, secrets, scheduler/heartbeats.

**Sortie** : `docs/context/security-review-2026-Q2.md`, **format identique au 01/05** :
`§ par axe` → finding = `sévérité [CRITIQUE/ÉLEVÉ/MOYEN/FAIBLE]` / `module fichier:ligne` / `problème` / `impact` / `fix` / `story Linear`. Diffable contre l'ancien.

## 6. DoD (= HOS-277)

- [ ] Verify-the-fixes : 14 lignes confirmées (preuve code/gate/test)
- [ ] Audit différentiel livré ; findings tracés
  - ⚠️ **Workspace Linear au plafond free-tier** — créer des issues est bloqué. Lister les findings **dans le doc** (+ TODO upgrade) plutôt que des issues, tant que le plafond n'est pas levé.
- [ ] Quick-wins data-réelle vérifiés : `echo`/PII-in-logs + gate RLS couvre nouvelles tables
- [ ] Verdict pilote go/no-go documenté → input HOS-176
- [ ] Commit + PR contre `main` ; HOS-277 → commentaire + statut

## 7. Note inter-sessions

Plusieurs sessions peuvent partager le working dir `aetherix-hospitality-ai`. Travaille sur ta branche dédiée (`ivandemurard/hos-277-…` ou équivalent) ; ce hand-off a été committé via un worktree isolé pour ne pas perturber ta session.
