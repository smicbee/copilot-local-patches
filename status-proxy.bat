@echo off
REM ============================================================
REM  Status der Copilot-Managed-Settings-Vermittlung
REM ============================================================
setlocal
set "DIR=%~dp0"

echo == Task-Scheduler-Aufgabe ==
schtasks /query /tn "ClawdiaCopilotManagedSettings" 2>nul | findstr /i "ClawdiaCopilot Managed Status"
echo.

echo == Erreichbarkeit (Port 8790) ==
powershell -NoProfile -Command "try{$r=Invoke-WebRequest -Uri 'http://127.0.0.1:8790/copilot_internal/managed_settings' -UseBasicParsing -TimeoutSec 3; Write-Output ('Antwortstatus: '+$r.StatusCode); Write-Output ('Antwort: '+$r.Content)}catch{Write-Output 'NICHT erreichbar'}"
echo.

echo == Umgebungsvariable ==
echo COPILOT_DEBUG_GITHUB_API_URL=%COPILOT_DEBUG_GITHUB_API_URL%
echo.
echo == Log (letzte 10 Zeilen) ==
if exist "%DIR%copilot-proxy.log" (
    powershell -NoProfile -Command "Get-Content '%DIR%copilot-proxy.log' -Tail 10"
) else (
    echo (Kein Log - Vermittlung lief noch nie oder Log entfernt.)
)
pause
