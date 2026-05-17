# setup-new-machine.ps1
# Run once on any new Windows machine to wire up Aetherix dev environment.
#
# Prereq: OneDrive must be signed in and syncing before running this.
#         The aetherix-hospitality-ai repo must already be in OneDrive\Documents.
#
# Usage: pwsh -ExecutionPolicy Bypass -File scripts\setup-new-machine.ps1
#
# What this script does:
#   1. Junctions ~/.claude to OneDrive\Documents\.claude (Claude Code sessions sync)
#   2. Installs flyctl (Fly.io CLI) if absent
#   3. Installs uv (Python package manager) if absent
#   4. Downloads Supabase CLI binary if absent
#   5. Prints the remaining manual steps (auth logins)
#
# Idempotent: re-running is safe.

$ErrorActionPreference = 'Continue'

# ---------------------------------------------------------------------------
# Step 1 — Junction ~/.claude → OneDrive\Documents\.claude
# ---------------------------------------------------------------------------

$claudeLocal    = "$env:USERPROFILE\.claude"
$claudeOneDrive = "$env:USERPROFILE\OneDrive\Documents\.claude"

Write-Host "[1/5] Configuring ~/.claude junction..." -ForegroundColor Cyan

if (-not (Test-Path $claudeOneDrive)) {
    Write-Error "OneDrive .claude folder not found at $claudeOneDrive — is OneDrive signed in and syncing?"
    exit 1
}

if (Test-Path $claudeLocal) {
    $item = Get-Item $claudeLocal -Force
    if ($item.LinkType -eq "Junction") {
        Write-Host "  Junction already exists: $claudeLocal -> $($item.Target)" -ForegroundColor Green
    } else {
        Write-Warning "  $claudeLocal exists and is NOT a junction. Backing it up before replacing."
        $backup = "$claudeLocal.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        Move-Item $claudeLocal $backup
        Write-Host "  Backed up to $backup"
        New-Item -ItemType Junction -Path $claudeLocal -Target $claudeOneDrive | Out-Null
        Write-Host "  Junction created: $claudeLocal -> $claudeOneDrive" -ForegroundColor Green
    }
} else {
    New-Item -ItemType Junction -Path $claudeLocal -Target $claudeOneDrive | Out-Null
    Write-Host "  Junction created: $claudeLocal -> $claudeOneDrive" -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Step 2 — Install flyctl (Fly.io CLI)
# ---------------------------------------------------------------------------

Write-Host "[2/5] Checking flyctl..." -ForegroundColor Cyan
$flyPath = "$env:USERPROFILE\.fly\bin\flyctl.exe"
if (Test-Path $flyPath) {
    Write-Host "  flyctl already installed: $flyPath" -ForegroundColor Green
} else {
    Write-Host "  Installing flyctl..."
    Invoke-RestMethod https://fly.io/install.ps1 | Invoke-Expression
    Write-Host "  flyctl installed at $flyPath" -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Step 3 — Install uv (Python package manager, used by backend deps)
# ---------------------------------------------------------------------------

Write-Host "[3/5] Checking uv..." -ForegroundColor Cyan
$uvPath = "$env:USERPROFILE\.local\bin\uv.exe"
if (Test-Path $uvPath) {
    Write-Host "  uv already installed: $uvPath" -ForegroundColor Green
} else {
    Write-Host "  Installing uv..."
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    Write-Host "  uv installed at $uvPath" -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Step 4 — Download Supabase CLI binary
# ---------------------------------------------------------------------------

Write-Host "[4/5] Checking Supabase CLI..." -ForegroundColor Cyan
$supabaseDir = "$env:USERPROFILE\supabase-cli"
$supabasePath = "$supabaseDir\supabase.exe"
if (Test-Path $supabasePath) {
    Write-Host "  Supabase CLI already installed: $supabasePath" -ForegroundColor Green
} else {
    Write-Host "  Downloading Supabase CLI binary..."
    $url = "https://github.com/supabase/cli/releases/latest/download/supabase_windows_amd64.tar.gz"
    $tar = "$env:USERPROFILE\Downloads\supabase_windows_amd64.tar.gz"
    Invoke-WebRequest -Uri $url -OutFile $tar
    New-Item -ItemType Directory -Force -Path $supabaseDir | Out-Null
    tar -xzf $tar -C $supabaseDir
    Remove-Item $tar
    Write-Host "  Supabase CLI installed at $supabasePath" -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Step 5 — Add tools to PATH (permanently for this user)
# ---------------------------------------------------------------------------

Write-Host "[5/5] Updating user PATH..." -ForegroundColor Cyan
$pathsToAdd = @(
    "$env:USERPROFILE\.fly\bin",
    "$env:USERPROFILE\.local\bin",
    $supabaseDir
)
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
$newPath = $currentPath
foreach ($p in $pathsToAdd) {
    if ($currentPath -notlike "*$p*") {
        $newPath = "$newPath;$p"
        Write-Host "  Added to PATH: $p"
    }
}
if ($newPath -ne $currentPath) {
    [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
    Write-Host "  User PATH updated — open a NEW PowerShell window for changes to take effect." -ForegroundColor Yellow
} else {
    Write-Host "  PATH already contains all tool directories." -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Done — print manual next steps
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host "Setup complete. Remaining MANUAL steps:" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  1. Close this PowerShell, open a NEW one (PATH refresh)"
Write-Host "  2. flyctl auth login                  (opens browser)"
Write-Host "  3. supabase login                     (opens browser)"
Write-Host "  4. gh auth login                      (if you use gh CLI)"
Write-Host "  5. cd to the repo:"
Write-Host "       cd `"$env:USERPROFILE\OneDrive\Documents\aetherix-hospitality-ai`""
Write-Host "  6. Test stack: python scripts\smoke_test_e2e.py"
Write-Host ""
Write-Host "Sessions Claude Code, .env, snapshots, migrations sync automatiquement via OneDrive." -ForegroundColor Green
