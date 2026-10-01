@echo off
REM ============================================================
REM  Copilot-Managed-Settings-Vermittlung: Autostart & Einrichtung
REM  - Setzt die Umgebungsvariable zur Vermittlung (COPILOT_DEBUG_GITHUB_API_URL)
REM  - Ersetzt die app.js der Copilot-CLI (mit Backup des Originals)
REM  - Setzt die Modellwahl atomar (set-model.py, andere Einstellungen bleiben)
REM  - Legt eine Aufgabe an, die die Vermittlung bei der Anmeldung startet.
REM ============================================================
setlocal enabledelayedexpansion

set "DIR=%~dp0"
set "TASK=ClawdiaCopilotManagedSettings"
set "SCRIPT=%DIR%start-proxy.bat"
set "SETTINGS=%USERPROFILE%\.copilot\settings.json"

echo ============================================================
echo  Einrichtung der Copilot-Vermittlung
echo ============================================================
echo.

set "PY=python"
where python.exe >nul 2>nul || set "PY=python"
echo [*] Python: %PY%

REM --- 1) patcht die app.js der Copilot-CLI idempotent (Backup des Originals) ---
set "PATCHCLI=%DIR%patch-appjs.py"
if not exist "%PATCHCLI%" (
    echo [!] %PATCHCLI% nicht gefunden - CLI-Patch uebersprungen.
) else (
    REM patch-appjs.py: wendet die 5 Anpassungen direkt auf die aktuelle
    REM app.js an (nicht abhaengig von einer Vorlagendatei), macht ein Backup
    REM des Originals (app.js.original.bak) und laesst sich nach jedem
    REM CLI-Update erneut ausfuehren.
    %PY% "%PATCHCLI%"
    echo     (Original als app.js.original.bak gesichert.)
)
echo.

REM --- 2) Umgebungsvariable (neue Terminals uebernehmen sie) ---
setx COPILOT_DEBUG_GITHUB_API_URL http://127.0.0.1:8790
echo [*] Umgebungsvariable COPILOT_DEBUG_GITHUB_API_URL gesetzt.
echo     WICHTIG: Nur NEUE Terminal-/CLI-Fenster verwenden sie.
echo.

REM --- 3) Modellwahl setzen (setzt NUR den model-Key, atomar) ---
set "SETMODEL=%DIR%set-model.py"
if not exist "%SETMODEL%" (
    echo [!] %SETMODEL% nicht gefunden.
) else (
    %PY% "%SETMODEL%" gpt-5.6-sol
    echo     Andere Einstellungen in settings.json bleiben erhalten.
)
echo.
REM    (set-model.py: legt die Datei an, falls fehlt; oder setzt nur "model".
REM     Bestehende andere Einstellungen werden NICHT ueberschrieben,
REM     Schreibvorgang erfolgt atomar: Temp-Datei + Umbenennen.)

REM --- 4) Autostart-Aufgabe (bei Anmeldung) ---
schtasks /query /tn "%TASK%" >nul 2>nul
if %errorlevel%==0 (
    echo [*] Aufgabe %TASK% existiert bereits.
) else (
    schtasks /create /tn "%TASK%" /tr "\"%SCRIPT%\"" /sc onlogon /rl highest /f
    if %errorlevel%==0 (
        echo [*] Autostart-Aufgabe %TASK% angelegt (bei Anmeldung).
    ) else (
        echo [!] Aufgabe konnte nicht angelegt werden.
        echo     Moeglicherweise Berechtigungen. Als Administrator laufen lassen.
    )
)
echo.

REM --- 5) Sofort starten (damit fuer dieses System greift) ---
call "%SCRIPT%"
echo.
echo Fertig. Hinweise in der ANLEITUNG-PROXY.md.
pause
