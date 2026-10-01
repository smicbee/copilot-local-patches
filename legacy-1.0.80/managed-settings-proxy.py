#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copilot Managed-Settings-Vermittlung
====================================
Hintergrund: Die GitHub Copilot CLI fragt in Unternehmens-/Organisations-Setups
eine entfernt verwaltete Konfiguration (Managed Settings) ueber den Pfad
`/copilot_internal/managed_settings` ab. Dieses Modul bietet eine vor Ort
laufende Vermittlungsstelle, die genau diesen einen Pfad mit einer leeren
Antwort bedient. Dadurch bleibt auf dem eigenen Rechner die lokal hinterlegte
Konfiguration (z. B. Modellwahl in ~/.copilot/settings.json) massgeblich.

Gegenstand: Nur dieser eine Pfad wird mit einer leeren Antwort bedient. Alle
uebrigen Anfragen werden unveraendert an den zustaendigen GitHub-Dienst
weitergegeben. Zugangsdaten passieren nur zwischen CLI und GitHub; sie werden
nicht gespeichert, nicht protokolliert und nicht ausgewertet.

Hinweis:
- Bitte stimme die Nutzung mit den fuer dein Setup geltenden organisatorischen
  und vertraglichen Vorgaben ab.
- Wirksam nur solange sie laeuft; ohne sie gilt wieder die entfernt verwaltete
  Vorgabe.

Aufruf:
  python managed-settings-proxy.py            # Vordergrund (Debug)
  pythonw managed-settings-proxy.py --daemon  # Hintergrund, Log in Datei
"""

import http.server
import os
import sys
import time
import urllib.request

PORT = 8790
MANAGED_SETTINGS_PATH = "/copilot_internal/managed_settings"
UPSTREAM = "https://api.github.com"
UPSTREAM_COPILOT = "https://api.githubcopilot.com"
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "copilot-proxy.log")

_flush = print


def _log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    _flush(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _relay(self):
        if self.path.split("?")[0] == MANAGED_SETTINGS_PATH:
            self._respond_empty_managed_settings()
            return
        self._proxy_upstream()

    def _respond_empty_managed_settings(self):
        body = b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
        _log(f"Managed-Settings-Antwort: {self.command} {self.path}")

    def _proxy_upstream(self):
        url = self._choose_upstream() + self.path
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        headers = {}
        for k, v in self.headers.items():
            if k.lower() in ("host", "connection", "proxy-connection",
                             "content-length", "keep-alive", "transfer-encoding",
                             "upgrade"):
                continue
            headers[k] = v
        headers["Host"] = urllib.request.urlparse(url).netloc
        req = urllib.request.Request(url, data=body, method=self.command,
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                rbody = resp.read()
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() in ("content-length", "connection",
                                     "transfer-encoding", "keep-alive"):
                        continue
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(rbody)))
                self.end_headers()
                self.wfile.write(rbody)
                _log(f"Weitergeleitet: {self.command} {url} -> {resp.status}")
        except Exception as e:
            _log(f"Fehler bei {url}: {e}")
            self.send_response(502)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def _choose_upstream(self):
        return UPSTREAM

    def do_GET(self):    self._relay()
    def do_POST(self):   self._relay()
    def do_PUT(self):    self._relay()
    def do_DELETE(self): self._relay()
    def do_PATCH(self):  self._relay()

    def log_message(self, fmt, *args):
        pass


def main():
    daemon = "--daemon" in sys.argv
    host = "127.0.0.1"

    if daemon and sys.platform == "win32":
        # In den Hintergrund stellen (kein Konsolenfenster), Log nach Datei
        global _flush
        _flush = lambda *a, **k: None   # stummschalten, Log nur in Datei
        try:
            import subprocess
            # Wenn wir bereits von pythonw gestartet wurden, kein weiteres Kind.
            if not os.environ.get("_PROXY_CHILD"):
                os.environ["_PROXY_CHILD"] = "1"
                DETACHED = 0x00000008
                CREATE_NEW_PROCESS_GROUP = 0x00000200
                flags = DETACHED | CREATE_NEW_PROCESS_GROUP
                subprocess.Popen(
                    [sys.executable, os.path.abspath(__file__), "--daemon"],
                    close_fds=True, creationflags=flags,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)
                return
        except Exception as e:
            _log(f"Daemon-Hinweis: {e}")

    try:
        server = http.server.ThreadingHTTPServer((host, PORT), Handler)
    except OSError as e:
        _log(f"Start fehlgeschlagen: {e} (Port {PORT} belegt? bereits aktiv?)")
        return

    _log(f"Vermittlung laeuft auf http://{host}:{PORT}")
    _log(f"Beantwortet nur: {MANAGED_SETTINGS_PATH}")
    _log("Andere Anfragen -> github.com (unveraendert).")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _log("beendet.")
        server.server_close()


if __name__ == "__main__":
    main()
