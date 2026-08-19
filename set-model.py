#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
set-model.py - setzt ausschliesslich die Modellwahl in settings.json.

Verhalten:
  - Liest die bestehende ~/.copilot/settings.json (falls vorhanden).
  - Aendert NUR den Key "model". Alle anderen Einstellungen bleiben exakt
    erhalten.
  - Schreibt atomar (zuerst in eine Temp-Datei im selben Verzeichnis,
    anschliessend einheitliches Umbenennen). Dadurch entsteht nie eine
    halb geschriebene Datei.
  - Wenn keine settings.json existiert, wird eine neue mit nur dem model-Key
    angelegt (ebenfalls atomar).

Aufruf:
  python set-model.py [modell]        z. B. python set-model.py gpt-5.6-sol

Falls kein Modell angegeben wird: zeigt das aktuell gesetzte Modell an.
"""

import json
import os
import sys
import tempfile

DEFAULT_MODEL = "gpt-5.6-sol"


def settings_path():
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    return os.path.join(home, ".copilot", "settings.json")


def _read_existing(path):
    """Liefert dict der bestehenden settings.json oder None wenn nicht da."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise SystemExit(f"settings.json konnte nicht gelesen werden: {e}")


def _atomic_write(path, data):
    """Schreibt data atomar: temp im selben Ordner, dann umbenennen."""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".settings.", suffix=".tmp",
                                    dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)  # atomar auf demselben Dateisystem
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def main():
    path = settings_path()
    model = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL

    existing = _read_existing(path)
    if existing is None:
        data = {"model": model}
        _atomic_write(path, data)
        print(f"[ok] settings.json angelegt (nur model={model!r}): {path}")
        return

    # Bestehende Datei: nur model aendern, alles andere erhalten.
    before = existing.get("model")
    existing["model"] = model
    _atomic_write(path, existing)

    if before != model:
        print(f"[ok] Modell in settings.json angepasst: {before!r} -> {model!r}")
    else:
        print(f"[ok] Modell ist bereits {model!r}; unveraendert.")
    print(f"     Settings-Datei: {path}")
    changed = [k for k in existing.keys() if k != "model"]
    if changed:
        print(f"     Andere Einstellungen unveraendert erhalten: {len(changed)}")
    else:
        print("     Keine anderen Einstellungen vorhanden.")


if __name__ == "__main__":
    main()
