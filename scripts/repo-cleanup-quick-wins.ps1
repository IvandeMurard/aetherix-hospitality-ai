# repo-cleanup-quick-wins.ps1
# HOS-166 — Execute the shell-side operations of the repo cleanup quick wins.
#
# The Claude Code session that opened HOS-166 made the in-place file edits
# (README dedup, .gitignore update). This script handles everything that
# requires real shell access:
#
#   AC2 — git mv root research files to archive/research/mews/
#   AC3 — git rm all *.bak files under docs/bmad/_bmad/
#   AC4 — delete 4 stale remote branches (after gh-verified merge/no-PR)
#   AC5 — prune local worktrees whose branch is merged into main
#
# Run from the MAIN worktree (C:\Users\ivand\OneDrive\Documents\aetherix-hospitality-ai),
# NOT from inside .claude/worktrees/*. AC5 cannot remove the worktree
# the script is running in.
#
# Default mode is dry-run. Pass -Apply to actually execute.
#
# Usage:
#   pwsh -File scripts\repo-cleanup-quick-wins.ps1            # dry-run
#   pwsh -File scripts\repo-cleanup-quick-wins.ps1 -Apply     # execute
#   pwsh -File scripts\repo-cleanup-quick-wins.ps1 -Apply -SkipWorktrees   # all but AC5

[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$SkipWorktrees,
    [switch]$SkipBranches
)

$ErrorActionPreference = 'Stop'

function Write-Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Write-Do($msg)   { if ($Apply) { Write-Host "  [DO]    $msg" -ForegroundColor Yellow } else { Write-Host "  [DRY]   $msg" -ForegroundColor Gray } }
function Write-Ok($msg)   { Write-Host "  [OK]    $msg" -ForegroundColor Green }
function Write-Warn2($msg){ Write-Host "  [WARN]  $msg" -ForegroundColor Yellow }
function Write-Err2($msg) { Write-Host "  [ERR]   $msg" -ForegroundColor Red }

# Resolve repo root (must be a git repo, not a worktree under .claude/worktrees/)
$repoRoot = (git rev-parse --show-toplevel) 2>$null
if (-not $repoRoot) {
    Write-Err2 "Not in a git repository. Run from the main aetherix-hospitality-ai checkout."
    exit 1
}
if ($repoRoot -match '\.claude[\\/]worktrees') {
    Write-Err2 "You are running inside a worktree ($repoRoot). Run from the main checkout instead."
    exit 1
}
Set-Location $repoRoot
Write-Host "Repo root: $repoRoot"
if (-not $Apply) {
    Write-Host "Mode: DRY-RUN (pass -Apply to execute)" -ForegroundColor Yellow
} else {
    Write-Host "Mode: APPLY" -ForegroundColor Red
}

# ---------------------------------------------------------------------------
# AC2 — Move root research artifacts to archive/research/mews/
# ---------------------------------------------------------------------------
Write-Step "AC2 — Move Mews research files out of repo root"

$archiveDir = Join-Path $repoRoot 'archive\research\mews'
$rootFiles = @(
    'Mews_Trend-Report-2026_EN.pdf',
    'Mews Agentic AI Architecture.png'
)

$ac2Moved = 0
foreach ($f in $rootFiles) {
    $src = Join-Path $repoRoot $f
    if (-not (Test-Path $src)) {
        Write-Warn2 "Not found (skip): $f"
        continue
    }
    $dst = Join-Path $archiveDir $f
    if ($Apply) {
        if (-not (Test-Path $archiveDir)) {
            New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null
            Write-Ok "Created $archiveDir"
        }
        # git mv handles paths with spaces if quoted via PowerShell pipeline
        git mv -- "$f" "archive/research/mews/$f"
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "git mv `"$f`" → archive/research/mews/"
            $ac2Moved++
        } else {
            Write-Err2 "git mv failed for $f"
        }
    } else {
        Write-Do "git mv `"$f`" → archive/research/mews/"
        $ac2Moved++
    }
}

# ---------------------------------------------------------------------------
# AC3 — Purge .bak files under docs/bmad/_bmad/
# ---------------------------------------------------------------------------
Write-Step "AC3 — Purge .bak files under docs/bmad/_bmad/"

$bakFiles = git ls-files 'docs/bmad/_bmad/**/*.bak' 2>$null
if (-not $bakFiles) {
    Write-Ok "No .bak files tracked by git in docs/bmad/_bmad/ — nothing to do."
} else {
    $count = ($bakFiles | Measure-Object).Count
    Write-Host "  Found $count tracked .bak file(s)."
    if ($Apply) {
        # Pipe each path to `git rm` (handles paths with spaces)
        $bakFiles | ForEach-Object { git rm --quiet -- "$_" }
        Write-Ok "Removed $count .bak file(s) from git index"
    } else {
        Write-Do "git rm <$count files>"
    }
}

# ---------------------------------------------------------------------------
# AC4 — Delete stale remote branches (after gh verification)
# ---------------------------------------------------------------------------
if ($SkipBranches) {
    Write-Step "AC4 — SKIPPED (-SkipBranches)"
} else {
    Write-Step "AC4 — Delete stale remote branches"

    $staleBranches = @(
        'api-client',
        'claude/aetherix-market-analysis-5JiJ1',
        'claude/implement-aetherix-orchestrator-z4kim',
        'claude/implement-hos-106-bGrXC'
    )

    foreach ($br in $staleBranches) {
        # Check open PRs targeting main from this branch — if any, skip
        $openPRs = gh pr list --state open --head $br --json number 2>$null
        if ($openPRs -and $openPRs -ne '[]') {
            Write-Warn2 "Open PR(s) exist for $br — skipping. Resolve first."
            continue
        }
        # Confirm the branch actually exists on origin
        $exists = git ls-remote --heads origin $br 2>$null
        if (-not $exists) {
            Write-Ok "$br — already absent from origin (nothing to do)"
            continue
        }
        if ($Apply) {
            git push origin --delete $br
            if ($LASTEXITCODE -eq 0) {
                Write-Ok "Deleted origin/$br"
            } else {
                Write-Err2 "Failed to delete origin/$br"
            }
        } else {
            Write-Do "git push origin --delete $br"
        }
    }
}

# ---------------------------------------------------------------------------
# AC5 — Prune local worktrees whose branch is merged into main
# ---------------------------------------------------------------------------
if ($SkipWorktrees) {
    Write-Step "AC5 — SKIPPED (-SkipWorktrees)"
} else {
    Write-Step "AC5 — Prune merged local worktrees"

    # Parse `git worktree list --porcelain`
    $wtRaw = git worktree list --porcelain
    $worktrees = @()
    $current = $null
    foreach ($line in $wtRaw) {
        if ($line -match '^worktree (.+)$') {
            if ($current) { $worktrees += $current }
            $current = @{ Path = $matches[1]; Branch = $null; Detached = $false }
        } elseif ($line -match '^branch refs/heads/(.+)$') {
            $current.Branch = $matches[1]
        } elseif ($line -eq 'detached') {
            $current.Detached = $true
        }
    }
    if ($current) { $worktrees += $current }

    # Refresh main tip
    git fetch origin main --quiet 2>$null

    $candidates = @()
    foreach ($wt in $worktrees) {
        # Skip the main worktree itself
        if ($wt.Path -eq $repoRoot) { continue }
        # Only consider worktrees under .claude/worktrees/
        if ($wt.Path -notmatch '\.claude[\\/]worktrees') { continue }
        if (-not $wt.Branch) {
            Write-Warn2 "$($wt.Path) is detached — skipping"
            continue
        }
        # Check if branch tip is reachable from origin/main
        $isMerged = $false
        try {
            $mergeBase = git merge-base origin/main $wt.Branch 2>$null
            $branchTip = git rev-parse $wt.Branch 2>$null
            if ($mergeBase -and $branchTip -and ($mergeBase -eq $branchTip)) {
                $isMerged = $true
            }
        } catch {}
        if ($isMerged) {
            $candidates += $wt
        } else {
            Write-Warn2 "$($wt.Branch) NOT merged into origin/main — keep: $($wt.Path)"
        }
    }

    Write-Host "  $($candidates.Count) worktree(s) safe to remove (branch merged to origin/main)."
    foreach ($wt in $candidates) {
        if ($Apply) {
            git worktree remove --force $wt.Path
            if ($LASTEXITCODE -eq 0) {
                Write-Ok "Removed $($wt.Path)"
            } else {
                Write-Err2 "Failed to remove $($wt.Path)"
            }
        } else {
            Write-Do "git worktree remove --force `"$($wt.Path)`""
        }
    }
    if ($Apply -and $candidates.Count -gt 0) {
        git worktree prune
        Write-Ok "git worktree prune done"
    }
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Step "Summary"
if (-not $Apply) {
    Write-Host "Dry-run complete. Re-run with -Apply to execute." -ForegroundColor Yellow
} else {
    Write-Host "Apply complete." -ForegroundColor Green
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. git status              # review staged changes from AC2 + AC3"
    Write-Host "  2. git diff --cached       # confirm moves + .bak deletions"
    Write-Host "  3. Commit on the claude/focused-noyce-51b507 branch (or current feature branch)"
    Write-Host "  4. Push + open PR referencing HOS-166"
}
