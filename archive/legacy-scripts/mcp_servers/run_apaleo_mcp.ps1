# Wrapper: loads .env then starts the Apaleo FastMCP server (stdio transport)
$envFile = Join-Path $PSScriptRoot "..\..\..\.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^([^#=\s][^=]*)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process')
        }
    }
}
python (Join-Path $PSScriptRoot "pms_server.py")
