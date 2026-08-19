@echo off
REM ============================================================
REM  Copilot Managed-Settings-Vermittlung starten
REM  Startet die lokale Vermittlungsstelle unsichtbar (pythonw)
REM  und ohne Konsolenfenster.
REM  Hinweis: Sie bleibt aktiv, bis sie explizit gestoppt wird.
REM ============================================================
setlocal

set "DIR=%~dp0"
set "PY=pythonw.exe"
set "SCRIPT=%DIR%managed-settings-proxy.py"

REM Falls pythonw nicht im PATH: Python-Installation nutzen
where pythonw.exe >nul 2>nul
if %errorlevel%==0 goto :has_pythonw
where python.exe >nul 2>nul
if %errorlevel%==0 (
    set "PY=python.exe"
    goto :has_pythonw
)
echo [F] Python nicht gefunden. Bitte Python 3 installieren und PATH pruefen.
exit /b 1

:has_pythonw
if not exist "%SCRIPT%" (
    echo [F] %SCRIPT% nicht gefunden.
    exit /b 1
)

REM Bereits aktiv? (Pfad-Pruefung ueber eingehenden Port via curl)
powershell -NoProfile -Command "try{$r=Invoke-WebRequest -Uri 'http://127.0.0.1:8790/copilot_internal/managed_settings' -UseBasicParsing -TimeoutSec 2; if($r.StatusCode -eq 200){Write-Output 'ALREADY_RUNNING'}}catch{}" | findstr /C:"ALREADY_RUNNING" >nul
if %errorlevel%==0 (
    echo [*] Vermittlung laeuft bereits auf Port 8790.
    exit /b 0
)

echo [*] Starte Vermittlungsstelle unsichtbar ...
start "" /min %PY% "%SCRIPT%" --daemon
timeout /t 2 /nobreak >nul

REM Kurz nachpruefen
powershell -NoProfile -Command "try{$r=Invoke-WebRequest -Uri 'http://127.0.0.1:8790/copilot_internal/managed_settings' -UseBasicParsing -TimeoutSec 3; if($r.StatusCode -eq 200){Write-Output 'OK'}}catch{}" | findstr /C:"OK" >nul
if %errorlevel%==0 (
    echo [*] Vermittlung laeuft: http://127.0.0.1:8790
) else (
    echo [!] Vermittlung scheint nicht erreichbar. Log pruefen:
    echo     %DIR%copilot-proxy.log
)
exit /b 0
