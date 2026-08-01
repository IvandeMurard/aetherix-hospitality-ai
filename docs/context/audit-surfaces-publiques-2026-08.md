# Audit des surfaces publiques — chiffres et statuts (01/08/2026)

> **Story 16.17 / HOS-318** (AC1). Portée : toute surface lisible par un tiers — méta-repo public, case study,
> README, deck, posts. Grep de référence : les deux graphies du MAPE synthétique et circulaire, plus `MAPE`.
> Convention appliquée : [`status-taxonomy.md`](status-taxonomy.md).

---

## Verdict par surface

| Surface | Occurrences | État avant | Action |
|---|---|---|---|
| Méta-repo `hospitality-agentic-mesh` — `COGNITION.md` | « Prophet tying a naive baseline on the median day » | ✅ Conforme — mène par la lecture médiane, la moins flatteuse | Aucune |
| Méta-repo — `demo/closed-loop/closed_loop_demo.md` | MAPE hebdo 8.4 → 11.6 % | ✅ Encadré — bandeau « données sandbox synthétiques… prouve la mécanique, pas l'accuracy » | Aucune |
| Méta-repo — `README.md` | aucun `15.09` | ⚠️ Taxonomie non conforme (`Built (PoC)`, `In Progress`) ; principes #4/#5 au présent de l'indicatif | **PR ouverte** (voir §PR méta-repo) |
| Case study `ivandemurard.com/aetherix` | « MAPE 15.09% on J+1 covers, 22% gate PASS » | ⚠️ Qualifié « synthetic backtest, not a headline » mais **ne dit pas circulaire** et **ne porte pas le chiffre Recruit** — HOS-307 AC5 resté ouvert | **Texte de remplacement prêt** (voir §Case study) |
| `README.md` (repo privé) l.54, l.125 | `15.09% MAPE` en ligne « Forecast accuracy » | ⚠️ Qualifié « synthetic backtest » mais présenté comme *l'*accuracy du produit | ✅ Corrigé |
| `docs/pilot/onboarding-kit.md` l.28, l.178 | `**15.09%**` en tableau de preuve | 🔴 **Le plus grave** — document remis au partenaire pilote, donc de facto public | ✅ Corrigé |
| `CLAUDE.md` / `AGENTS.md` l.80 | `MAPE J+1 synthétique 15.09%` | 🟡 Qualifié « synthétique », mais ne dit pas circulaire ni ne pointe Recruit | ✅ Corrigé (D1 : diff identique appliqué aux deux) |
| `docs/context/mape-benchmark.md` | 4 occurrences | ✅ Bandeau de qualification depuis le 08/07 — sert de modèle | Verdict AC4 réécrit (voir §Verdict) |
| `docs/planning/evaluation-by-design.md`, `docs/adr/0007-*.md`, `eval/baselines/forecast_baseline.json`, `scripts/` | 6 occurrences | ✅ Contexte historique daté (« run 2026-05-21 ») ou commentaire technique désignant le gate | Aucune — ce sont des archives, pas des claims |
| Pitch deck | — | Aucun deck versionné trouvé dans le repo ni le corpus de review | Non applicable — à passer au filtre D7 s'il est créé |
| Posts LinkedIn publiés | — | Aucun post publié à ce jour (la série est HOS-314, non démarrée) | Non applicable — HOS-314 applique la taxonomie dès rédaction (AC3) |

**Résultat :** aucune citation non qualifiée du MAPE synthétique ne subsiste sur une surface publique ou
pilote après cette story, sauf la case study, qui vit hors du repo et dont le correctif est fourni prêt à
coller ci-dessous.

---

## Case study `ivandemurard.com/aetherix` — texte de remplacement

**Remplacer** la ligne actuelle de la section « Where we are, honestly » :

> Calibration baseline (synthetic backtest, not a headline): MAPE 15.09% on J+1 covers, 22% gate PASS. Real-world MAPE begins with the pilot.

**par :**

> **Forecast, measured on real data.** On 829 real Japanese restaurants (Kaggle *Recruit*, 1,193 scored
> points, deterministic rerun), Prophet beats a naive same-weekday baseline by 6.15 points of mean MAPE
> (49.71% vs 55.86%) — but **ties it on the median day** (MdAPE 27.0% vs 27.6%), and is marginally *worse*
> than naive at J+1 on the median (28.5% vs 27.9%). The mean-MAPE gap comes from robustness on very
> low-traffic days, not from sharper forecasts on a typical service. A gradient-boosted baseline wins on
> the median (25.6%). We publish both readings because the flattering one alone would not be true.
>
> An earlier internal figure of 15.09% MAPE circulated on synthetic data; it is **circular** — the generator
> built covers from the same regressors Prophet consumes — and is retained only as an internal
> non-regression gate. It is not evidence of forecast skill.
>
> What decides whether the forecast is the product is pre-registered, not chosen after the fact: median-APE
> delta versus the naive baseline, at the decision horizon, on real hotel data (shadow mode, in progress).

**Ajouter** à la ligne de statut Aetherix (« Phase 3 · Pilot »), pour lever l'ambiguïté Built/adopté :

> Built and deployed on staging; **zero real users to date**. Measurement starts with the design partner.

**Aligner** enfin le tableau des nœuds sur la taxonomie : Anima est déjà *Synthetic PoC* ✅ ; Orchestrator
« Phase 3, stub » → **Design** ; ajouter HiveMemory → **Research** (la page mentionne « federated cohort prior
… is research » dans le corps, mais pas dans le tableau).

---

## PR méta-repo `hospitality-agentic-mesh`

Trois corrections, portée README uniquement (`COGNITION.md` et la démo closed-loop sont déjà conformes) :

1. **Table « What's built vs. what's vision »** — passer à la taxonomie à cinq étiquettes.
   `Built (PoC)` → **Synthetic PoC** (Anima) · `In Progress` → **Design** (Orchestrator) et **Research**
   (Meta-Learner / Hive) · ajouter la mention « 0 real users » sur la ligne Aetherix.
2. **Core Design Principles #4 et #5** — passer du présent de l'indicatif au conditionnel. « The system
   employs a dual learning strategy » et « a federated Hive layer shares anonymized priors » décrivent
   aujourd'hui du **Research** comme s'il tournait.
3. **Ajouter le résultat Recruit** dans la section « Current focus » — le benchmark est publié dans
   `benchmark/` mais aucun chiffre n'apparaît en README, ce qui laisse le lecteur sur la seule promesse.

---

## Ce que cet audit ne couvre pas

- Le case study et les posts LinkedIn ne sont pas versionnés ici : leur conformité n'est **pas** vérifiable
  par le détecteur D7. C'est une limite assumée — le contrôle y reste humain (HOS-313 / HOS-314, AC3).
- Les captures d'écran et la vidéo démo 3 min (HOS-310/Phase D) n'ont pas été auditées : elles n'existent pas
  encore. Elles tombent sous la même règle dès leur production.
- **`docs/veille/` est gitignoré** (convention local-only, 30/07). Deux notes y convertissaient le chiffre
  circulaire en argument de pitch — « ~85 % accuracy → dans la fourchette haute du marché » (20/07) et
  « directement utilisables… benchmarking externe de notre MAPE J+1 » (27/07). **Corrigées localement**, mais
  ces correctifs ne sont pas dans le commit et D7 ne les reverra pas en CI, faute de fichiers dans le
  checkout. Le vault Obsidian, où la veille vit désormais, échappe entièrement au détecteur : c'est la
  principale zone aveugle de cette gate.
