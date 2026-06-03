# sync_obsidian.ps1 -- Aetherix Project Context -> Obsidian Vault
# Usage : .\scripts\sync_obsidian.ps1 [-NoPull] [-DryRun]

param(
    [switch]$NoPull,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# --- Configuration ------------------------------------------------------------

$RepoRoot  = (Resolve-Path "$PSScriptRoot\..").Path
$VaultRoot = "C:\Users\ivand\OneDrive\Documents\Obsidian Vault"
$VaultDest = Join-Path $VaultRoot "Aetherix Project Context"

# Fichiers a synchroniser (chemins relatifs au repo)
$FilesToSync = @(
    "CLAUDE.md",
    "docs\context\demo-apaleo.md",
    "docs\context\linear-conventions.md",
    "docs\context\memory-architecture.md",
    "docs\context\open-decisions.md",
    "docs\context\strategy.md",
    "docs\context\veille.md",
    "docs\context\vision-future.md"
)

# --- Helpers ------------------------------------------------------------------

function Write-Log {
    param([string]$Msg, [string]$Level = "INFO")
    $prefix = switch ($Level) {
        "OK"   { "[+]" }
        "WARN" { "[!]" }
        "ERR"  { "[x]" }
        default { "[ ]" }
    }
    Write-Host "$prefix $Msg"
}

function Write-Separator { Write-Host ("-" * 55) }

# --- Header -------------------------------------------------------------------

$now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Write-Host ""
Write-Separator
Write-Host "  Obsidian Sync  |  $now"
Write-Separator
Write-Host ""

# --- 1. Git pull --------------------------------------------------------------

if (-not $NoPull) {
    Write-Log "git pull -- $([System.IO.Path]::GetFileName($RepoRoot))"
    if ($DryRun) {
        Write-Log "(dry-run) git pull ignore" "WARN"
    } else {
        $result = & git -C $RepoRoot pull --ff-only 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Log "git pull a echoue : $result" "ERR"
            Write-Log "Utiliser -NoPull pour forcer la sync sans pull." "WARN"
            exit 1
        }
        $summary = ($result | Out-String).Trim().Split("`n") | Select-Object -Last 1
        Write-Log $summary "OK"
    }
    Write-Host ""
}

# --- 2. Verifier le vault -----------------------------------------------------

if (-not $DryRun -and -not (Test-Path $VaultRoot)) {
    Write-Log "Vault Obsidian introuvable : $VaultRoot" "ERR"
    Write-Log "Verifier que OneDrive est monte." "WARN"
    exit 1
}

if (-not $DryRun) {
    New-Item -ItemType Directory -Path $VaultDest -Force | Out-Null
}

# --- 3. Synchroniser les fichiers ---------------------------------------------

$copied  = 0
$skipped = 0

foreach ($rel in $FilesToSync) {
    $src  = Join-Path $RepoRoot $rel
    $dest = Join-Path $VaultDest ([System.IO.Path]::GetFileName($rel))

    if (-not (Test-Path $src)) {
        Write-Log "Introuvable (ignore) : $rel" "WARN"
        continue
    }

    # Copier seulement si source plus recente
    if (Test-Path $dest) {
        $srcTime  = (Get-Item $src).LastWriteTimeUtc
        $destTime = (Get-Item $dest).LastWriteTimeUtc
        if ($srcTime -le $destTime) {
            $skipped++
            continue
        }
    }

    $filename = [System.IO.Path]::GetFileName($rel)
    if ($DryRun) {
        Write-Log "(dry-run) copierait : $filename -> Aetherix Project Context/"
    } else {
        Copy-Item -Path $src -Destination $dest -Force
        Write-Log "$filename -> Aetherix Project Context/" "OK"
    }
    $copied++
}

# --- 4. Mettre a jour _Index.md -----------------------------------------------

Write-Host ""
$indexPath = Join-Path $VaultDest "_Index.md"
$syncTime  = Get-Date -Format "yyyy-MM-dd HH:mm"

$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine("# Aetherix Project Context")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("*Derniere synchronisation : $syncTime*")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("## Fichiers")
[void]$sb.AppendLine("")

foreach ($rel in $FilesToSync) {
    $name = [System.IO.Path]::GetFileNameWithoutExtension($rel)
    [void]$sb.AppendLine("- [[$name]]")
}

[void]$sb.AppendLine("")
[void]$sb.AppendLine("---")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("*Genere automatiquement par sync_obsidian.ps1. Ne pas editer manuellement.*")

$indexContent = $sb.ToString()

if ($DryRun) {
    Write-Log "(dry-run) _Index.md non ecrit"
} else {
    [System.IO.File]::WriteAllText($indexPath, $indexContent, [System.Text.Encoding]::UTF8)
    Write-Log "_Index.md mis a jour" "OK"
}

# --- 5. Resume ----------------------------------------------------------------

Write-Host ""
Write-Separator
Write-Log "Termine -- $copied fichier(s) synchronise(s), $skipped inchange(s)" "OK"
Write-Separator
Write-Host ""
