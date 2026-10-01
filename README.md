# Copilot CLI 1.0.90 – lokaler Managed-Settings-Server

## Was sich geändert hat

Das alte Paket war für 1.0.80. 1.0.90 liefert eine native ausführbare Datei
mit eingebettetem Runtime-Paket. Host-Auflösung und wesentliche Policy-/Modell-
Entscheidungen liegen inzwischen im nativen runtime.node. Die alten sieben
minifizierten JS-Ersetzungen sind dafür nicht geeignet.

`patch-appjs.py` ist daher jetzt ein versionsgeprüfter Start-Wrapper, kein
Binärpatcher. Er verändert weder die Installation noch die Signatur der EXE.
Die neue CLI unterstützt COPILOT_GH_HOST/GH_HOST selbst; der Wrapper verwendet
zusätzlich den in 1.0.90 nachgewiesenen COPILOT_DEBUG_GITHUB_API_URL-Einstieg.
Dieser Debug-Einstieg ist keine zugesicherte stabile öffentliche Schnittstelle.
Andere Versionen werden deshalb abgelehnt, statt stillschweigend falsch zu arbeiten.

## Start unter Windows

Voraussetzungen: Python 3.10+ und Copilot CLI **1.0.90**.

1. Dieses ZIP in einen eigenen Ordner entpacken. Den alten Autostart-Proxy
   vor der Nutzung beenden; er beantwortet /health nicht und darf Port 8790
   nicht weiter belegen. Alte Dateien nicht ungeprüft mit diesem Paket mischen.
2. `python patch-appjs.py --check` prüft die Version ohne Serverstart.
3. `copilot-managed.cmd` startet den lokalen Server und dann Copilot.
   CLI-Argumente können mitgegeben werden, z.B. `copilot-managed.cmd --help`.
4. Der Wrapper beendet nur den Server, den er selbst gestartet hat, wenn die
   CLI endet. Einen vorher separat gestarteten Server lässt er unverändert.

Alternativ den Server dauerhaft im Vordergrund starten:

    python managed-settings-proxy.py

Danach die CLI weiterhin über `copilot-managed.cmd` aufrufen. Der normale
`copilot`-Aufruf verwendet den lokalen Server nicht automatisch.
Keine globalen Environment-Änderungen, kein neuer Autostart und kein EXE-Austausch.

## Weboberfläche

Server starten (`python managed-settings-proxy.py`) und `http://127.0.0.1:8790/`
im Browser öffnen. Admin-Schlüssel (Inhalt von `.admin-key`) eingeben, dann
„Laden“. Die Seite enthält:

- alle 21 Managed-Settings-Schlüssel als Formular (Auswahl, Ja/Nein, JSON-Felder)
- Launcher-Umgebung, u. a. BYOK-Variablen (`COPILOT_PROVIDER_*`), Host, Offline
  (gespeichert in `launcher-env.json`; echte Umgebungsvariablen haben Vorrang)
- Rohansicht des JSON

Leere Felder werden entfernt. API-Schlüssel (`COPILOT_PROVIDER_API_KEY`) werden
bewusst nicht gespeichert, sondern bleiben echte Umgebungsvariablen. Die Seite
hat eine strikte Content-Security-Policy und nur Same-Origin-Aufrufe.

## Einstellungen ändern (Kommandozeile)

Beim ersten Serverstart entstehen `managed-settings.json` (anfangs `{}`)
und `.admin-key`. Schlüssel nicht weitergeben; er wird nicht ausgegeben.

Beispieldatei prüfen und nach Bedarf anpassen. Das dort gezeigte Modell ist
nur aus dem alten Setup übernommen, seine aktuelle Verfügbarkeit wird hier
nicht behauptet. Es gibt absichtlich keine erzwungene Modellwahl im Standard.

    python settingsctl.py get
    python settingsctl.py replace managed-settings.example.json
    python settingsctl.py patch meine-aenderung.json

`replace`: komplettes Objekt ersetzen.
`patch`: rekursiver JSON-Merge-Patch; `null` entfernt ein Feld.
Beispiel für `meine-aenderung.json`:

    {"model": "mein-verfuegbares-modell", "shellShortcut": false}

Zurücksetzen eines Overrides:

    {"model": null}

Die gespeicherte Datei wird bei jedem HTTP-Abruf neu gelesen. Serverneustart
ist nicht nötig. **CLI-Caches und laufende Sitzungen sind davon getrennt:**
Änderungen werden beim nächsten Managed-Settings-Refresh wirksam, zuverlässig
für neue Sitzungen nach einem CLI-Neustart. Kein behauptetes Hot-Reconfigure
aller bestehenden Agenten.

## Enterprise-/Managed-Einstellungen

Der Server akzeptiert die 21 Top-Level-Keys, die die originale 1.0.90-Runtime
über `userSettingsGovernanceKeys().managed` als Managed-Einstellungen ausweist:

- Modell: model, autoTier, effortLevel, contextTier
- MCP: allowedMcpServers, deniedMcpServers, allowManagedMcpServersOnly
- Hooks: allowManagedHooksOnly
- Plugins: enabledPlugins, extraKnownMarketplaces, strictKnownMarketplaces,
  strictPluginOnlyCustomization
- Anmeldung/Abruf: forceLoginOrgs, forceRemoteSettingsRefresh
- Berechtigungen: permissions
- Policy-Helfer: policyHelper, policyHelperFailureMode
- Sonstiges: remoteControl, sandbox, shellShortcut, telemetry

Geschachtelte Objekte werden vollständig übertragen, nicht auf unsere bisherigen
zwei Sonderfälle reduziert. Die grundlegenden Typen werden lokal geprüft;
komplexe Unterstrukturen und deren tatsächliche Wirkung beurteilt weiterhin die
CLI. Diese Liste bedeutet **nicht**, dass jede Kombination end-to-end getestet
wurde. Für unbekannte Top-Level-Keys liefert die Admin-API 400 statt scheinbaren
Erfolg. Der originale CLI-Resolver bleibt unverändert, einschließlich seiner
weiteren verwalteten Quellen und Fail-Closed-Entscheidungen.

Dies steuert die vom **Client** gelesenen Managed Settings. Es ändert keine
GitHub-Enterprise-/Organisationseinstellungen im Konto, keine Lizenzen, Quoten
oder serverseitigen Modellfreigaben. Der frühere pauschale MCP-Fallback und
Gpt-5.6-only-Katalogfilter sind **nicht** wieder eingebaut. `model` legt die
Modellwahl fest, beschränkt aber nicht den gesamten Modellpicker/Subagentkatalog.
Eine neue Katalogbeschränkung ist also nicht Teil dieser Lieferung.

## HTTP-Schnittstellen / Schutz

- GET /health: Dienstkennung und geprüfte CLI-Version
- GET /copilot_internal/managed_settings: flaches Managed-Settings-Objekt,
  auch mit CLI-Queryparametern
- GET /admin/settings: konfigurierte Werte lesen
- PUT /admin/settings: ersetzen
- PATCH /admin/settings: ändern/entfernen

Admin-Aufrufe benötigen `Authorization: Bearer <lokaler Schlüssel>`.
settingsctl.py liest den Schlüssel selbst aus der Datei. Nur 127.0.0.1;
Host-Prüfung, keine CORS-Freigabe, Browser-Origin-Anfragen abgewiesen.
Keine Request-/Header-/Credential-Logs. Atomare Speicherung; Bodylimit 1 MiB.
Ungültige Dateien werden mit 503 beantwortet, nicht heimlich als `{}`.
Andere GET-Anfragen gehen zum festen HTTPS-Upstream api.github.com;
Statuscodes werden erhalten und Weiterleitungen nicht automatisch verfolgt.
Kein allgemeiner HTTP-/Inference-Proxy. Keine beliebigen Ziel-URLs.

## Nachweise und Grenzen

- 13 automatisierte Tests erfolgreich: CRUD/Merge/Delete, Persistenz, Auth,
  Host/Origin-Abweisung, Typfehler, Fail-Closed und Methodengrenzen.
- Echter nativer **Linux ARM64 1.0.90**-Resolver: Modell, Auto-Tier,
  Reasoning-Effort, Kontext-Tier und Shell-Shortcut aus dem HTTP-Server gelesen;
  geändertes Modell beim zweiten Abruf ohne Serverneustart übernommen.
- Test verwendet explizite Account-Info-Fixture und Dummy-Token, keine echte
  Anmeldung, keine bezahlte Modellanfrage. Das ist kein authentifizierter
  Windows-/Enterprise-Livetest.
- Echter nativer CLI-Start über den Wrapper: --help, Exitcode 0.
- Windows-1.0.90-Paket untersucht und die native Settings-Struktur abgeglichen.
  Windows-Ausführung und dein persönliches Enterprise-Login bleiben ungetestet.

    python test_settings.py

Der Native-Test wird ohne COPILOT_TEST_RUNTIME übersprungen. Mit dem Pfad zu
einem originalen 1.0.90-runtime.node der laufenden Plattform wird er ausgeführt.
Keine Schlüssel, Accountdaten oder Copilot-Binaries sind im ZIP enthalten.
