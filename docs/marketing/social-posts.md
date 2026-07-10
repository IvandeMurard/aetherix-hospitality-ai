# Posts sociaux — banque prête à publier (Story 16.14 AC2)

> LinkedIn + X, courts, voix d'Ivan (réflexif, première personne, understated). Zéro cadratin,
> zéro flèche, honnête, adossé aux artefacts publics. Thèmes : mémoire cognitive (fil Aetherix +
> Anima + Lore) et évaluation. Discipline chiffres : `demo-kit.md` §4.
> Cadence suggérée : 1 post / semaine, alterner thème cognitif et thème technique.

---

## POST 1 — Le fil mémoire (LinkedIn) · le "in fewer words" promis

Leads with the payoff (les 3 questions), connecte les trois projets, tient en un écran.

```
I started building AI agents for hotel operations to answer a boring question: how many covers tomorrow, and how many staff.

A year later, the question I actually care about is memory.

Not storage. Memory in the organisational sense:
- What is worth remembering?
- How do you keep useful knowledge from leaving with the people who hold it?
- Once a system remembers, how does it know when a lesson still holds, when to revise it, or when to forget it entirely?

Three projects kept circling the same thing:
- Aetherix: what a restaurant actually does, service after service.
- Anima: what a hotel knows about a returning guest.
- Lore: the tacit expertise a senior technician never wrote down.

Different industries, one problem: operational knowledge is alive, and most software treats it as a filing cabinet.

The interesting work now is building memory that improves, revises itself, and knows what to forget. More soon, still in fewer words.
```

Lien à attacher : le méta-repo (COGNITION.md) ou le repo Lore selon l'audience.

---

## POST 1 — version X (thread de 2 tweets)

```
1/ I started building AI agents to forecast restaurant covers.

A year in, I care less about prediction than about memory: what's worth remembering, how to keep it from leaving with people, and how a system knows when a lesson still holds or should be forgotten.

2/ Three projects, one problem:
Aetherix (what a restaurant does, service after service), Anima (what a hotel knows about a guest), Lore (a technician's tacit expertise).

Operational knowledge is alive. Most software treats it like a filing cabinet.
```

---

## POST 2 — L'évaluation (LinkedIn) · le résultat honnête

Angle : le benchmark qui aurait dû décevoir, devenu raison de confiance. "Working vs reliable".

```
An honest benchmark result.

I tested my hotel demand-forecasting engine against the dumbest baseline I could think of: the average of the last four same weekdays. The thing any experienced manager computes in their head.

On 30 real restaurants, on the median day, they tie.

I could have hidden that. Instead it became the reason I trust the system more, not less. Because the forecast was never the point. What matters is whether the system knows when it is wrong, says so, and gets corrected.

So I treat evaluation as a build constraint, not an afterthought:
- an eval gate that blocks a merge on regression, the way a failing test does
- runtime checks that flag a shaky output instead of shipping it with false confidence
- real outcomes captured next to every recommendation, so "accurate" is measured, not claimed

Inspired by Qonto's "working vs reliable" framing. A demo that works once is easy. A system you can trust on Tuesday when it was wrong on Monday is the actual job.

Benchmark and code are public.
```

Lien : le méta-repo (benchmark/).

---

## POST 2 — version X

```
I tested my demand-forecasting engine against the dumbest baseline: the average of the last 4 same weekdays.

On 30 real restaurants, on the median day, they tie.

I published it anyway. The forecast was never the point. Knowing when you're wrong, and saying so, is.
```

---

## POST 3 — "Living operational architecture" (LinkedIn, optionnel/plus tard)

Le concept-chapeau, si Ivan veut poser le terme. À garder pour quand le pilote donne un fait réel.

```
A dashboard is a photograph. Operations are a film.

Most operational software hands you a snapshot and asks you to draw the conclusions. The direction I find interesting is the opposite: a living operational memory that improves with every service, notices when it drifts, and tells you before you have to ask.

The forecast is an organ, not the product. The product is the loop: anticipate, capture the real outcome, name the miss, recalibrate. What compounds is not the model, which anyone can retrain, but the memory of what this specific place actually does.

Building it in the open where I can. More soon.
```

---

## Règles (rappel)

- Jamais : "76,7% acceptance" (manager simulé), "MAPE 15,09%" (retiré), "-3 à -8% labor" (cible).
- Le benchmark réel (49,7 vs 55,9 %, "they tie on the median day") est le chiffre-signature honnête.
- Zéro cadratin / flèche dans le texte publié.
- Ordre de publication conseillé : Post 1 (accroche, large) → Post 2 (technique, crédibilité) →
  teaser article `article-operational-memory.md` → Post 3 (concept) → post-mortem Q2-01.
