# Anleitung: Eigene Modellwahl der Copilot CLI lokal behalten

Ziel: Auf dem lokalen Rechner soll das eigene gewaehlte Modell (z. B.
gpt-5.6-sol) in `%USERPROFILE%\.copilot\settings.json` gelten, statt dass die
CLI ausschliesslich eine entfernt verwaltete Vorgabe uebernimmt
("model is managed by your organization").

Hintergrund (belegt im CLI-Kern 1.0.80):
  Die CLI fragt in Unternehmens-/Organisations-Setups entfernt verwaltete
  Einstellungen (Managed Settings) ueber den Pfad `/copilot_internal/
  managed_settings` ab. Enthaelt die Antwort ein `model`-Feld, hat dieses
  Vorrang vor der lokalen Wahl.
  Dieser Abruf nutzt die Umgebungsvariable `COPILOT_DEBUG_GITHUB_API_URL`
  (belegt im Rust-Modul api_managed_settings.rs).
  Die beigefuegte Vermittlungsstelle beantwortet diesen einen Pfad mit einer
  leeren Antwort. So bleiben auf dem eigenen Rechner die lokal hinterlegten
  Einstellungen (z. B. die Modellwahl) massgeblich; uebrige Anfragen werden
  unveraendert an GitHub weitergegeben.

WICHTIG ZU settings.json:
  Das beigefuegte set-model.py setzt ausschliesslich den Key "model".
  Bestehende andere Einstellungen in einer vorhandenen settings.json bleiben
  unveraendert erhalten. Neu erstellt wird die Datei NUR, wenn sie noch nicht
  existiert. Der Schreibvorgang ist atomar (Temp-Datei + Umbenennen) - es
  entsteht nie eine halb geschriebene Datei.

Hinweis:
  - Bitte stimme die Nutzung mit den fuer dein Setup geltenden
    organisatorischen und vertraglichen Vorgaben ab.
  - Wirksam nur solange die Vermittlungsstelle laeuft; ohne sie gilt wieder
    die entfernt verwaltete Vorgabe.

------------------------------------------------------------
INHALT DIESER MAPPE
------------------------------------------------------------
  managed-settings-proxy.py   die Vermittlungsstelle (Python 3)
  start-proxy.bat             startet sie unsichtbar (wird auch durch
                              Autostart verwendet)
  install-autostart.bat       EINRICHTUNG: CLI-Patch (idempotent, mit Backup) +
                              Env-Var + Modellwahl (atomar) + Autostart
                              + sofortiger Start (ein Aufruf)
  patch-appjs.py              PATCHT die installierte app.js idempotent und
                              update-robust (Backup als app.js.original.bak).
                              Nach jedem CLI-Update erneut ausfuehrbar.
  set-model.py                setzt NUR die Modellwahl atomar; andere
                              Einstellungen bleiben erhalten
  stop-proxy.bat              stoppen / komplett deinstallieren
  status-proxy.bat            Status, Erreichbarkeit, Log
  github-copilot-win32-x64-1.0.80.tgz   originales npm-Bundle (Referenz 1.0.80)
  app.js.PATCHED              bereits durchpatchte Referenzdatei (1.0.80)
  settings.json               Vorlage (nur model-Key)
  settings.json.example       Vorlage (nur model-Key)

------------------------------------------------------------
WIE DER CLI-PATCH FUNKTIONIERT (update-robust)
------------------------------------------------------------
  install-autostart.bat ruft patch-appjs.py auf. Das wendet die 5 Anpassungen
  direkt auf die aktuell installierte app.js an (kein Kopieren einer festen
  Vorlagen-Datei). Pro Regel:
    - schon angewendet          -> ueberspringen
    - Original-Stelle vorhanden -> ersetzen
    - keines von beidem (Update hat Struktur geaendert) -> Warnung (CLI bleibt
      intakt, Regel wird nur nicht angewendet)

  Nach einem CLI-Update einfach ERNEUT ausfuehren:
    python patch-appjs.py
  Es macht bei Bedarf ein Backup (app.js.original.bak) und ist idempotent.

------------------------------------------------------------
SCHNELLSTART (empfohlen)
------------------------------------------------------------
1) Python 3 pruefen:
     python --version
   Falls fehlt: https://www.python.org/downloads/ , "Add to PATH" aktivieren,
   Terminal neu oeffnen.

2) Mappe auf dem Zielrechner ablegen, z. B.
     C:\copilot-proxy\

3) Dateien entsperren (wichtig, sonst blockiert Windows):
     Rechtsklick auf managed-settings-proxy.py, start-proxy.bat,
     install-autostart.bat, set-model.py
     -> Eigenschaften -> unten "Zulassen" anhaken -> OK

4) Als Administrator ausfuehren:
     cd C:\copilot-proxy
     install-autostart.bat

   Das erledigt automatisch (ohne bestehende Einstellungen zu ueberschreiben):
     - setx COPILOT_DEBUG_GITHUB_API_URL=http://127.0.0.1:8790
     - setzt atomar die Modellwahl (set-model.py) - legt settings.json nur an,
       wenn sie fehlt; sonst wird nur der model-Key gesetzt
     - legt die Autostart-Aufgabe "ClawdiaCopilotManagedSettings" an
       (startet die Vermittlung bei jeder Anmeldung)
     - startet die Vermittlung sofort

5) NEUES Terminal/CLI-Fenster oeffnen (damit die Env-Var greift) und
     copilot

------------------------------------------------------------
MODELLWECHSEL (spaeter)
------------------------------------------------------------
Ohne etwas anderes anzufassen, nur die Modellwahl atomar setzen:
     python set-model.py <modell>
   Beispiele:
     python set-model.py gpt-5.6-sol
     python set-model.py claude-sonnet-4-5

------------------------------------------------------------
PRUEFEN
------------------------------------------------------------
Doppelklick auf status-proxy.bat  ODER:
  schtasks /query /tn ClawdiaCopilotManagedSettings
  curl http://127.0.0.1:8790/copilot_internal/managed_settings
In der CLI:  /model  -> sollte gpt-5.6-sol zeigen (nicht "managed...").

------------------------------------------------------------
NACH EINEM CLI-UPDATE (die CLI kann sich selbst aktualisieren)
------------------------------------------------------------
  Die Anpassungen an der app.js werden durch ein CLI-Update ueberschrieben.
  Einfach neu anwenden (idempotent, update-robust):
    python patch-appjs.py
    python managed-settings-proxy.py --daemon
  Fertig. patch-appjs.py meldet pro Regel, ob sie angewendet werden konnte.

  Optional - automatische Updates deaktivieren (damit nicht unerwartet
  ueberschrieben wird): setze in settings.json zusaetzlich
    "autoUpdate": false
  (set-model.py fasst das NICHT an; nur manuell ergaenzen, wenn gewuenscht.)

------------------------------------------------------------
AUTOSTART - Detail
------------------------------------------------------------
  Legt bei der Anmeldung an:
  schtasks /create /tn "ClawdiaCopilotManagedSettings" ^
           /tr "\"C:\copilot-proxy\start-proxy.bat\"" ^
           /sc onlogon /rl highest /f

Der Autostart fuehrt start-proxy.bat aus, das pythonw veranwendet und die
Vermittlung unsichtbar startet (Log: C:\copilot-proxy\copilot-proxy.log).
start-proxy.bat prueft zudem, ob die Vermittlung schon laeuft, und startet
sie nur einmal.

------------------------------------------------------------
STOPPEN / DEINSTALLIEREN
------------------------------------------------------------
  stop-proxy.bat stop         nur den Prozess stoppen
  stop-proxy.bat uninstall    Prozess stoppen + Autostart-Aufgabe entfernen
                              + Env-Var leeren
  (settings.json bleibt dabei unangetastet.)

------------------------------------------------------------
FEHLERSUCHE
------------------------------------------------------------
A) Vermittlung nicht erreichbar:
   -> status-proxy.bat; Env-Var pruefen (echo %COPILOT_DEBUG_GITHUB_API_URL%);
     neues Terminal verwenden.
   -> Falls der Kern http auf localhost ablehnt: lokale https-Variante mit
     selbstsigniertem Zertifikat (openssl req -x509) und URL anpassen.

B) "Fehler bei ..." fuer andere Pfade:
   -> Bei nicht existierenden Endpoints normal (502). Bei haeufigen 502 den
     Eintrag UPSTREAM in managed-settings-proxy.py pruefen.

C) Modell erscheint weiterhin als entfernt verwaltete Vorgabe:
   -> Stammt dann ggf. aus einer weiteren Quelle (Datei/Zwischenspeicher).
     Sofern vor Ort zulaessig: gecachten Managed-Settings-Eintrag entfernen
     (Hinweis im Log unter "managed-settings cache").

D) "Port already in use":
   -> Vermittlung laeuft evtl. schon (status-proxy.bat) ODER Port aendern
     (PORT in managed-settings-proxy.py) und Env-Var anpassen.
