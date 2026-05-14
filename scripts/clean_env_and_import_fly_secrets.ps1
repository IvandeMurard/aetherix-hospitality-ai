<#
CleanEnvAndImportFlySecrets.ps1
Usage: coller et exécuter dans le dossier du repo.
Options:
    -EnvFile   : chemin du fichier .env à importer (défaut: .env.fly)
    -DryRun    : affiche les paires clé=valeur filtrées sans appeler flyctl
#>
param(
        [string]$EnvFile = '.env.fly',
        [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$envPath = Join-Path -Path (Get-Location) -ChildPath $EnvFile
if (-not (Test-Path $envPath)) {
    Write-Error "Fichier introuvable : $envPath"
    exit 2
}

# Lire le fichier en mode binaire
[byte[]]$bytes = [System.IO.File]::ReadAllBytes($envPath)
if ($bytes.Length -eq 0) {
    Write-Error ".env est vide."
    exit 3
}

# Détecter BOM et décoder en string correctement
$content = $null
if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
    # UTF-8 BOM
    $content = [System.Text.Encoding]::UTF8.GetString($bytes, 3, $bytes.Length - 3)
    Write-Host "BOM détecté : UTF-8 (enlevé)"
}
elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) {
    # UTF-16 LE BOM
    $content = [System.Text.Encoding]::Unicode.GetString($bytes, 2, $bytes.Length - 2)
    Write-Host "BOM détecté : UTF-16 LE (converti en UTF-8)"
}
elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFE -and $bytes[1] -eq 0xFF) {
    # UTF-16 BE BOM
    $content = [System.Text.Encoding]::BigEndianUnicode.GetString($bytes, 2, $bytes.Length - 2)
    Write-Host "BOM détecté : UTF-16 BE (converti en UTF-8)"
}
else {
    # Pas de BOM : essayer UTF-8, si présence de NULs -> suspecter UTF-16
    $content = [System.Text.Encoding]::UTF8.GetString($bytes)
    if ($content -match "`0") {
        # Probablement UTF-16 sans BOM : essayer LE puis BE
        try {
            $candidateLE = [System.Text.Encoding]::Unicode.GetString($bytes)
            if (-not ($candidateLE -match "`0")) {
                $content = $candidateLE
                Write-Host "Pas de BOM mais encodage détecté : UTF-16 LE (converti)"
            }
            else {
                $content = [System.Text.Encoding]::BigEndianUnicode.GetString($bytes)
                Write-Host "Pas de BOM mais encodage détecté : UTF-16 BE (converti)"
            }
        } catch {
            Write-Warning "Encodage inconnu, fallback sur UTF-8 (chars may be garbled)"
        }
    } else {
        Write-Host "Pas de BOM détecté — supposé UTF-8"
    }
}

# Normaliser les fins de ligne (LF)
$content = $content -replace "`r`n", "`n"
$content = $content -replace "`r", "`n"

# Réécrire .env en UTF-8 sans BOM (préserver le contenu décodé)
[byte[]]$utf8Bytes = [System.Text.Encoding]::UTF8.GetBytes($content)
[System.IO.File]::WriteAllBytes($envPath, $utf8Bytes)
Write-Host "$envPath réécrit en UTF-8 sans BOM."

# Filtrer les lignes qui correspondent strictement à KEY= (sans espaces initiaux)
$lines = $content -split "`n"
$filtered = $lines | Where-Object { $_ -match '^[A-Z_][A-Z0-9_]*=' }

if (-not $filtered -or $filtered.Count -eq 0) {
    Write-Warning "Aucune ligne correspondant au pattern ^[A-Z_][A-Z0-9_]*= trouvée. Rien à importer."
    exit 0
}

# Recomposer le contenu filtré en conservant les valeurs intactes
$filteredString = ($filtered -join "`n") + "`n"

if ($DryRun) {
    Write-Host "`n--- Dry run: contenu qui serait importé vers flyctl (ne contient pas d'appel à flyctl) ---`n"
    $filtered | ForEach-Object { Write-Host $_ }
    Write-Host "`n--- Fin du dry run ---`n"
    exit 0
}

# Vérifier que flyctl est disponible
$flyCmd = Get-Command -Name flyctl -ErrorAction SilentlyContinue
if (-not $flyCmd) {
    Write-Error "'flyctl' introuvable dans le PATH. Installez flyctl ou ajoutez-le au PATH."
    exit 4
}

# Appeler flyctl en écrivant le contenu UTF-8 via STDIN (préserve tous les caractères)
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $flyCmd.Source
$psi.Arguments = 'secrets import --app aetherix-backend'
$psi.UseShellExecute = $false
$psi.RedirectStandardInput = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true

try {
    $proc = [System.Diagnostics.Process]::Start($psi)
} catch {
    Write-Error "Impossible de démarrer 'flyctl': $_"
    exit 5
}

# Écrire les octets UTF-8 directement dans le flux d'entrée
$inBytes = [System.Text.Encoding]::UTF8.GetBytes($filteredString)
$baseStream = $proc.StandardInput.BaseStream
$baseStream.Write($inBytes, 0, $inBytes.Length)
$baseStream.Flush()
$proc.StandardInput.Close()

# Lire sortie et erreur
$out = $proc.StandardOutput.ReadToEnd()
$err = $proc.StandardError.ReadToEnd()
$proc.WaitForExit()

if ($out) { Write-Host $out }
if ($err) { Write-Error $err }

if ($proc.ExitCode -ne 0) {
    Write-Error "flyctl a retourné le code de sortie $($proc.ExitCode). Voir messages ci-dessus."
    exit $proc.ExitCode
}

Write-Host "Import des secrets via flyctl terminé avec succès."
