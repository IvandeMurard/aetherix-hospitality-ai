<#
generate_env_fly.ps1
Génère .env.fly à partir de .env en retirant les variables "local-only".
Usage: exécuter depuis la racine du repo.
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$pwd = Get-Location
$srcPath = Join-Path $pwd '.env'
$outPath = Join-Path $pwd '.env.fly'

if (-not (Test-Path $srcPath)) {
    Write-Error ".env introuvable à l'emplacement actuel : $srcPath"
    exit 2
}

# Variables à exclure du fichier Fly (LOCAL-ONLY)
$skipVars = @(
    'OBSIDIAN_VAULT_PATH',
    'LINEAR_API_KEY',
    'LINEAR_TEAM_ID',
    'TEST_DATABASE_URL',
    'MAIL_SERVER',
    'CORS_ORIGINS'
)

# Lire en binaire et gérer BOMs (UTF-8 / UTF-16 LE / UTF-16 BE)
[byte[]]$bytes = [System.IO.File]::ReadAllBytes($srcPath)
$content = $null
if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
    $content = [System.Text.Encoding]::UTF8.GetString($bytes, 3, $bytes.Length - 3)
} elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) {
    $content = [System.Text.Encoding]::Unicode.GetString($bytes, 2, $bytes.Length - 2)
} elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFE -and $bytes[1] -eq 0xFF) {
    $content = [System.Text.Encoding]::BigEndianUnicode.GetString($bytes, 2, $bytes.Length - 2)
} else {
    $content = [System.Text.Encoding]::UTF8.GetString($bytes)
    if ($content -match "`0") {
        try {
            $candidateLE = [System.Text.Encoding]::Unicode.GetString($bytes)
            if (-not ($candidateLE -match "`0")) { $content = $candidateLE }
            else { $content = [System.Text.Encoding]::BigEndianUnicode.GetString($bytes) }
        } catch { Write-Warning "Encodage inconnu, fallback UTF-8" }
    }
}

# Normaliser EOL
$content = $content -replace "`r`n", "`n"
$content = $content -replace "`r", "`n"

# Filtrer les lignes KEY= et exclure les skipVars
$lines = $content -split "`n"
$kept = @()
foreach ($l in $lines) {
    if ($l -match '^([A-Z_][A-Z0-9_]*)=') {
        $name = $matches[1]
        if ($name -notin $skipVars) { $kept += $l }
    }
}

# Écrire .env.fly en UTF-8 sans BOM
[System.IO.File]::WriteAllText($outPath, ($kept -join "`n") + "`n", [System.Text.UTF8Encoding]::new($false))
Write-Host "Créé $outPath avec $($kept.Count) variables (exclues: $($skipVars -join ', '))."
