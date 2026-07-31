# Dev Agent — Definition of Done

> Extrait de `CLAUDE.md` le 30/07/2026 — c'est du procédural, pas un fact de session (cf. `docs/INDEX.md` §Dette CLAUDE.md).
> Voisin : `context/linear-conventions.md` (conventions Epic/Story).

## Les 8 étapes

1. Lire le spec de la Linear issue (MCP Linear)
2. Auditer ce qui existe dans le codebase
3. Implémenter la story (migration DB, ORM, schemas, service, worker, route)
4. Tests — CI green
5. Commit + push sur la branche désignée (`claude/<story-suffix>`)
6. Ouvrir une PR contre `main`
7. Marquer la Linear issue → Done + poster l'URL de la PR en commentaire
8. **Eval gate (Décision #22)** — voir ci-dessous

## Étape 8 — Eval gate

Si la story touche `app/services/{forecast,staffing,recommendation,memory,inbound_parser}*`, `app/providers/`, ou les prompts :

- mettre à jour `eval/golden_dataset.jsonl` avec **≥ 1 scénario**
- `make eval` green
- `scripts/ci/check_eval_coverage.py` validé

**Exception** : label PR `eval-exempt` — refactor, doc, infra-only. Les stories documentaires (audits, spikes, décisions) tombent systématiquement dans cette catégorie.

## Gates

| Niveau | Condition |
|--------|-----------|
| **Merge** | CI vert — schema drift (Décision #16) + eval-by-design (Décision #22) → merge manuel SM |
| **Fin d'Epic** | Revue d'architecture |
| **Pré-pilote** | QA sign-off sur propriété réelle |

## Règle de contexte — où écrire quoi

| Nature | Destination |
|--------|-------------|
| Décision / contrainte / blocage **story-specific** | Commentaire sur la Linear issue |
| **Cross-cutting permanent** | Ligne d'index dans `CLAUDE.md` §Décisions architecturales + détail dans `context/decisions-architecturales.md` |

**Ne jamais écrire de contexte story-specific dans `CLAUDE.md`.** Le fichier est chargé à chaque session : tout ce qu'on y met est payé à chaque fois. Cf. la règle anti-surcharge en tête de `CLAUDE.md`.
