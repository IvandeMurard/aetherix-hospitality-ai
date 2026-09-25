# Public status sync — Aetherix → meta-repo README

> Décision #42 · ADR-0010 (public meta-repo, private execution nodes) · status labels: `docs/context/status-taxonomy.md`.
> Goal: what the public meta-repo says about Aetherix stays true, automatically, and never
> carries private content. Only **status and key elements** are synced; the vision text stays hand-written.

## How it works

```
public-status.yml ──(PR: check_public_status.py, blocking)──▶ main
        │
        └─(push to main)─▶ public-status-sync.yml
                             validate → render → check out meta-repo
                             → replace the marked block in README.md
                             → open / update PR from sync/aetherix-status
```

| Piece | Path | Role |
|---|---|---|
| Source | `public-status.yml` (repo root) | Curated by hand, reviewed in PRs. One entry per public capability. |
| Gate | `scripts/ci/check_public_status.py` | Schema, statuses, evidence, freshness, leak denylist. CI job `public-status` on every PR. |
| Renderer | `scripts/ci/render_public_status.py` | Deterministic Markdown table: capability · status · one line · live?. No LLM. |
| Action | `.github/workflows/public-status-sync.yml` | Push to main (when one of the four files above changes) + manual `workflow_dispatch`. |

## Updating the file

Edit `public-status.yml` in the same PR as the change it reflects (it is part of the PR definition
of done, `docs/context/dev-agent-dod.md`). Per entry:

| Field | Rule |
|---|---|
| `id` | kebab-case, unique, stable. Not published. |
| `name` | Public name, ≤ 60 characters. |
| `status` | `Built` · `Shadow-mode` · `Synthetic PoC` · `In progress` · `Design` · `Research`. |
| `description` | One public sentence, ≤ 220 characters. Design / Research use the conditional ("would"), never "the system does". |
| `deployed` | `true` · `false` · `unknown` · `n/a` (CI gate, eval harness). The table says **Yes** only for `true`. |
| `verified_on` | Day you last checked the entry against main. Older than `max_age_days` (60) → CI warning. |
| `evidence` | Repo-relative paths. **Required and must all exist for `Built`**. Never published. |

**`Built` in this file means merged on main and covered by tests** — not deployed, not used (the
node has zero real users). This is narrower than the taxonomy's wording ("deployed, exercised end to
end"), so the rendered table carries a footnote that says it, and deployment is a separate flag.
Set `deployed: true` only after checking which version runs (e.g. `fly status`, `fly releases` and the
commit it was built from), never because staging "should" have it.

Check locally:

```bash
pip install "pyyaml>=6,<7"   # or: cd backend && uv sync --group dev
python scripts/ci/check_public_status.py
python scripts/ci/render_public_status.py          # prints the block that would be synced
```

## What is never synced

- `evidence`, `id`, the file's comments: they stay in this repo.
- The vision text and everything outside the two markers of the meta-repo README.
- Anything the leak denylist catches in `name` / `status` / `description` (CI fails, and the renderer
  re-checks the rendered block): ADR-0012 and the Signal Contract (they never migrate — Décision #31),
  ticket IDs (`HOS-123`…), decision numbers (`Décision #N` / `Decision #N`), `§` section references,
  the private repo name, internal paths (`backend/`, `docs/context/`, `supabase/`, …), `.env`,
  staging hostnames, e-mail addresses, secret-looking strings.

The denylist is a net, not a proof: a sentence can reveal a mechanism without matching a pattern.
The PR review of `public-status.yml` remains the real control — and the meta-repo PR is a second look.

## What the Action does

1. Validates and renders (the block is shown in the run summary).
2. **No `META_REPO_TOKEN`** → warning *"Public status NOT SYNCED"* + summary, job **succeeds**. Nothing else depends on it.
3. Checks out `IvandeMurard/Hospitality-Multi-agent-Architecture` with the token.
4. Replaces the text between `<!-- aetherix-status:start -->` and `<!-- aetherix-status:end -->`.
   Markers missing, duplicated or reversed → job **fails** (a broken setup, not an absent one).
5. README already identical on the meta-repo's default branch → no PR; an obsolete sync PR is closed.
6. Otherwise pushes `sync/aetherix-status` (rebuilt from the default branch each run — manual commits
   on it are overwritten) and opens the PR, or updates the open one. A re-run with the same content
   creates no commit and no second PR. **It never pushes to the meta-repo's default branch** — you merge.

Run it by hand: *Actions → Public status sync → Run workflow* (branch `main`).

## Creating the token (one time)

A fine-grained personal access token restricted to the meta-repo:

1. GitHub → avatar (top right) → **Settings** → **Developer settings** (bottom of the left menu) →
   **Personal access tokens** → **Fine-grained tokens** → **Generate new token**.
2. **Token name**: `aetherix-public-status-sync`. **Expiration**: 1 year max (put a reminder a week before).
3. **Resource owner**: `IvandeMurard`.
4. **Repository access** → **Only select repositories** → pick `Hospitality-Multi-agent-Architecture` only.
5. **Permissions** → **Repository permissions**:
   - **Contents** → *Read and write* (push the sync branch)
   - **Pull requests** → *Read and write* (open / update / close the sync PR)
   - **Metadata** → *Read-only* (added automatically)
   - nothing else.
6. **Generate token**, copy it (shown once).
7. In **this** (private) repository: **Settings** → **Secrets and variables** → **Actions** →
   **New repository secret** → Name `META_REPO_TOKEN`, Secret = the token → **Add secret**.
8. *Actions → Public status sync → Run workflow* to check: the summary must say *Opened …* or
   *Already in sync*.

When the token expires, the meta-repo checkout step fails with an authentication error (the job is red,
not "not synced"): regenerate it with the same settings and update the secret.

## Meta-repo side (done separately, by hand)

Add exactly one marker pair where the Aetherix capability table should appear, e.g. under
*What's built vs. what's vision*, below the node-level table (which also covers the other nodes and
stays hand-written):

```markdown
<!-- aetherix-status:start -->
<!-- aetherix-status:end -->
```

That page's legend defines **Built** as "deployed and exercised end-to-end"; the synced table uses
*merged and tested* plus a **Live?** column. Align the legend when adding the markers, otherwise the
page carries two definitions of the same word.
