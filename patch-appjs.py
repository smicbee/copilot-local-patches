#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch-appjs.py - idempotenter In-place-Patch der Copilot-CLI app.js.

Wozu:
  Statt eine vorgefertigte app.js zu kopieren (die von CLI-Updates ueberschrieben
  wird), patcht dieses Werkzeug die 5 bekannten Stellen direkt in der aktuell
  installierten app.js. So kann es nach jedem CLI-Update erneut ausgefuehrt
  werden und die Anpassungen wiederholen.

Was es macht:
  - Findet die Copilot-CLI app.js (Windows: npm root -g + Standardpfade).
  - Legt einmalig ein Backup des Originals an (app.js.original.bak), wenn noch
    keines existiert (bei ungepatchter Datei).
  - Wendet die 5 string-basierten Ersetzungen an. Pro Regel:
      * schon angewendet (neuer Text vorhanden) -> ueberspringen
      * Original vorhanden                        -> ersetzen
      * keins von beidem (Struktur vom Update geaendert) -> Warnung + zaehlen
  - Schreibt atomar (Temp-Datei + os.replace).
  - Verifiziert anschliessend, welche Regeln aktiv sind.

Eigene Regeln (Code-Stellen in 1.0.80):
  1. mOi   Host-Fallback: Env vor https://github.com
  2. bOi   --host / Host-Env-Aufloesung
  3. help  --host-Hilfetext
  4. B1    mcp3pEnabled nicht aus Login ableiten, sondern aktiv setzen
  5. B2    Managed-Settings-Abfrage-Fehler: lokal statt blockierend

Hinweis:
  - Wirkt NUR, wenn die zugrundeliegenden Code-Stellen in der neuen CLI-Version
    noch erhalten sind. Wenn ein Update die Struktur aendert, meldet das Tool
    eine Warnung und fasst den Rest unveraendert - die Anpassung bricht dann
    nicht die CLI, sondern wird schlicht nicht angewendet. Dann Code-Stellen
    in der neuen app.js pruefen und die Regeln hier anpassen.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

# --- Patches: (Name, Original, Neu) -------------------------------------
PATCHES = [
    (
        "1-Host-mOi",
        'function mOi(t){return t?gCe(t):"https://github.com"}',
        'function mOi(t){return t?gCe(t):(process.env.COPILOT_GH_HOST||process.env.GH_HOST?gCe(process.env.COPILOT_GH_HOST||process.env.GH_HOST):"https://github.com")}',
    ),
    (
        "2-Host-bOi",
        'function bOi(t,e){if(t)return t;let n=yOi(e);if(!n)return;let r=n.lastIndexOf(e.name());if(r===-1)return;let o=n.slice(r+1);for(let s=0;s<o.length;s++){let a=o[s];if(a==="--")break;if(a==="--host")return OOn(o[s+1]);if(a.startsWith("--host="))return OOn(a.slice(7))}}',
        'function bOi(t,e){if(t)return t;let n=process.env.COPILOT_GH_HOST||process.env.GH_HOST;if(n)return n;let r=yOi(e);if(!r)return;let o=r.lastIndexOf(e.name());if(o===-1)return;let s=r.slice(o+1);for(let a=0;a<s.length;a++){let l=s[a];if(l==="--")break;if(l==="--host")return OOn(s[a+1]);if(l.startsWith("--host="))return OOn(l.slice(7))}}',
    ),
    (
        "3-Host-help",
        '"--host <host>","GitHub host URL (default: https://github.com)"',
        '"--host <host>","GitHub host URL (default: COPILOT_GH_HOST, GH_HOST, then https://github.com)"',
    ),
    (
        "4-MCP-B1",
        'e?.mcp3pEnabled??h.mcpConfigIsMcp3PEnabled(n==null?void 0:JSON.stringify(n))',
        'e?.mcp3pEnabled??!0',
    ),
    (
        "5-MCP-B2",
        '`),{mcp3pEnabled:!1,...o}}}',
        '`),{mcp3pEnabled:!0,...o}}}',
    ),
]


def _find_npm_root():
    try:
        out = subprocess.run(["npm", "root", "-g"],
                             capture_output=True, text=True, timeout=30)
        if out.returncode == 0 and out.stdout.strip() and \
                os.path.isdir(out.stdout.strip()):
            return out.stdout.strip()
    except Exception:
        pass
    return None


def _find_target_appjs():
    roots = []
    nr = _find_npm_root()
    if nr:
        roots.append(nr)
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    appdata = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
    localappdata = os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
    candidates = [
        os.path.join(appdata, "npm", "node_modules"),
        os.path.join(localappdata, "npm", "node_modules"),
        os.path.join(home, "npm", "node_modules"),
        os.path.join(home, "AppData", "Roaming", "npm", "node_modules"),
        os.path.join(home, "AppData", "Local", "npm", "node_modules"),
        os.path.expanduser("~/.npm-global/lib/node_modules"),
        os.path.expanduser("~/nvm/node_modules"),
        os.path.expanduser("~/scoop/apps/nodejs/current/node_modules"),
        "C:\\Program Files\\nodejs\\node_modules",
    ]
    for c in candidates:
        if c not in roots:
            roots.append(c)
    for root in roots:
        for sub in ("@github/copilot-win32-x64/package/app.js",
                    "@github/copilot/package/app.js",
                    "copilot-win32-x64/package/app.js"):
            path = os.path.join(root, sub)
            if os.path.isfile(path):
                return path
    return None


def _atomic_write(path, data):
    directory = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(prefix=".appjs.patch.", suffix=".tmp",
                               dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def main():
    target = _find_target_appjs()
    if target is None:
        print("[!] Copilot-CLI app.js nicht gefunden. Zuletzt gepflegter "
              "Standardpfad wird erwartet - manueller Austausch noetig.")
        return 2

    print(f"[*] Ziel: {target}")
    try:
        data = open(target, encoding="utf-8").read()
    except OSError as e:
        print(f"[!] Lesen fehlgeschlagen: {e}")
        return 1

    backup = os.path.join(os.path.dirname(target), "app.js.original.bak")

    # Zustand der Regeln ermitteln
    will_change = False
    results = []
    for name, old, new in PATCHES:
        if new in data:
            results.append((name, "bereits-aktiv", ""))
        elif old in data:
            results.append((name, "ersetzt", ""))
            will_change = True
        else:
            results.append((name, "nicht-findbar", "Struktur geaendert"))

    # Backup NUR anlegen, wenn wir gleich tatsaechlich ungepatcht->gepatcht gehen
    already_all_active = all(r[1] == "bereits-aktiv" for r in results)

    if not already_all_active and will_change and not os.path.isfile(backup):
        shutil.copy2(target, backup)
        print(f"[*] Backup des Originals angelegt: {backup}")
    elif not os.path.isfile(backup) and os.path.isfile(target):
        # Selbst wenn nichts aenderbar ist, nur wenn keine Patches aktiv
        if not already_all_active:
            shutil.copy2(target, backup)
            print(f"[*] Backup angelegt (vor Patch-Versuch): {backup}")

    if will_change:
        for name, old, new in PATCHES:
            if old in data:
                data = data.replace(old, new, 1)
        _atomic_write(target, data)
        print("[*] Angepasst und atomar geschrieben.")

    print("\n-- Regelstatus --")
    changed = 0
    for name, status, note in results:
        if status == "bereits-aktiv":
            print(f"  [ok]   {name}: aktiv")
        elif status == "ersetzt":
            print(f"  [OK]   {name}: neu angewendet")
            changed += 1
        else:
            print(f"  [WARN] {name}: {note} - nicht anwendbar (Update-Struktur?)")
    print()
    if not already_all_active and changed == 0 and not will_change:
        print("[!] Keine Regel anwendbar: Schauen, ob die Zieldatei wirklich die "
              "Erwartete ist, oder Regeln an die neue Version anpassen.")
        return 3
    if not already_all_active and will_change:
        print("[ok] Patch angewendet. Wiederholen des Tools nach jedem CLI-Update.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
