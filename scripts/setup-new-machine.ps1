# setup-new-machine.ps1
# Run once on any new Windows machine to wire Claude Code to OneDrive-synced data.
# Prereq: OneDrive must be signed in and syncing before running this.
#
# Usage: pwsh -ExecutionPolicy Bypass -File setup-new-machine.ps1

$claudeLocal  = "$env:USERPROFILE\.claude"
$claudeOneDrive = "$env:USERPROFILE\OneDrive\Documents\.claude"

if (-not (Test-Path $claudeOneDrive)) {
    Write-Error "OneDrive .claude folder not found at $claudeOneDrive — is OneDrive signed in and syncing?"
    exit 1
}

if (Test-Path $claudeLocal) {
    $item = Get-Item $claudeLocal -Force
    if ($item.LinkType -eq "Junction") {
        Write-Host "Junction already exists: $claudeLocal -> $($item.Target)" -ForegroundColor Green
        exit 0
    }
    Write-Warning "$claudeLocal exists and is NOT a junction. Backing it up before replacing."
    $backup = "$claudeLocal.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Move-Item $claudeLocal $backup
    Write-Host "Backed up to $backup"
}

New-Item -ItemType Junction -Path $claudeLocal -Target $claudeOneDrive | Out-Null
Write-Host "Junction created: $claudeLocal -> $claudeOneDrive" -ForegroundColor Green
Write-Host "Claude Code will now use your OneDrive-synced sessions and settings."
