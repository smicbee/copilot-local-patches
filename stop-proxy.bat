@echo off
REM ============================================================
REM  Copilot-Managed-Settings-Vermittlung stoppen / deinstallieren
REM  Optionen:
REM    stop        -> stoppt den laufenden Prozess (falls moeglich)
REM    uninstall   -> stoppt UND entfernt Autostart-Aufgabe + Env-Var
REM ============================================================
setlocal
set "ACTION=%~1"
if "%ACTION%"=="" set "ACTION=stop"

set "TASK=ClawdiaCopilotManagedSettings"

echo == Stoppe Vermittlung (Port 8790) ==
powershell -NoProfile -Command "$c=Get-NetTCPConnection -LocalPort 8790 -State Listen -ErrorAction SilentlyContinue; if($c){$c|ForEach-Object{Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue}; Write-Output 'Prozess beendet.'}else{Write-Output 'Kein Prozess auf Port 8790 gefunden.'}"

if /i "%ACTION%"=="uninstall" (
    echo.
    echo == Entferne Autostart-Aufgabe ==
    schtasks /delete /tn "%TASK%" /f >nul 2>nul
    if %errorlevel%==0 (echo Aufgabe entfernt.) else (echo Aufgabe nicht gefunden/entfernt.)

    echo.
    echo == Entferne Umgebungsvariable ==
    setx COPILOT_DEBUG_GITHUB_API_URL ""
    echo Env-Var geleert (wirkt in neuen Terminals).
)

echo.
echo Fertig.
pause
