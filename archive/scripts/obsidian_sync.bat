@echo off
:: ─────────────────────────────────────────────
::  obsidian_sync.bat
::  Lance git pull + sync vers le vault Obsidian
::  Conçu pour Windows Task Scheduler
:: ─────────────────────────────────────────────

:: Chemin du repo (à adapter si besoin)
set REPO=C:\Users\IVAN\Documents\Hospitality-Operations-Agentic-AI-B2B

:: Log
set LOGFILE=%REPO%\scripts\obsidian_sync.log
echo. >> "%LOGFILE%"
echo [%date% %time%] Démarrage sync >> "%LOGFILE%"

:: Lancer le script Python
python "%REPO%\scripts\obsidian_sync.py" >> "%LOGFILE%" 2>&1

if %ERRORLEVEL% EQU 0 (
    echo [%date% %time%] Sync OK >> "%LOGFILE%"
) else (
    echo [%date% %time%] ERREUR (code %ERRORLEVEL%^) >> "%LOGFILE%"
)
