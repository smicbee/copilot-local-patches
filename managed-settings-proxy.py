#!/usr/bin/env python3
"""Loopback-only Copilot 1.0.90 settings server; no inference proxy."""
import argparse
import hashlib
import hmac
import http.server
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request

BASE = Path(__file__).resolve().parent
UI_FILE = BASE / 'ui.html'
MAX_BODY = 1024 * 1024
KEYS = set('allowedMcpServers allowManagedHooksOnly allowManagedMcpServersOnly deniedMcpServers enabledPlugins extraKnownMarketplaces forceLoginOrgs forceRemoteSettingsRefresh model autoTier effortLevel contextTier permissions policyHelper policyHelperFailureMode remoteControl sandbox shellShortcut strictKnownMarketplaces strictPluginOnlyCustomization telemetry'.split())
LOCK = threading.RLock()
ENV_KEYS = ('COPILOT_GH_HOST GH_HOST COPILOT_MODEL COPILOT_OFFLINE COPILOT_PROVIDER_BASE_URL COPILOT_PROVIDER_TYPE '
            'COPILOT_PROVIDER_WIRE_API COPILOT_PROVIDER_TRANSPORT COPILOT_PROVIDER_API_KEY_COMMAND COPILOT_PROVIDER_MODEL_ID '
            'COPILOT_PROVIDER_WIRE_MODEL COPILOT_PROVIDER_MAX_PROMPT_TOKENS COPILOT_PROVIDER_MAX_OUTPUT_TOKENS '
            'COPILOT_PROVIDER_HEADERS COPILOT_PROVIDER_AZURE_API_VERSION').split()

def validate_env(value):
    if not isinstance(value, dict):
        raise ValueError('Environment must be a JSON object')
    for k, v in value.items():
        if k not in ENV_KEYS:
            raise ValueError('Unsupported variable (secrets are never stored here): ' + str(k))
        if not isinstance(v, str) or len(v) > 4096 or '\x00' in v:
            raise ValueError(k + ' must be a string up to 4096 characters')
    return value

def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.settings-')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)

def validate(value):
    if not isinstance(value, dict):
        raise ValueError('Settings must be a JSON object')
    unknown = set(value) - KEYS
    if unknown:
        raise ValueError('Unsupported managed keys: ' + ', '.join(sorted(unknown)))
    for key in ('allowManagedHooksOnly', 'allowManagedMcpServersOnly', 'forceRemoteSettingsRefresh', 'shellShortcut'):
        if key in value and not isinstance(value[key], bool):
            raise ValueError(key + ' must be boolean')
    for key in ('model', 'effortLevel'):
        if key in value and not isinstance(value[key], str):
            raise ValueError(key + ' must be string')
    for key in ('permissions', 'sandbox', 'telemetry', 'enabledPlugins', 'extraKnownMarketplaces'):
        if key in value and not isinstance(value[key], dict):
            raise ValueError(key + ' must be object')
    for key in ('allowedMcpServers', 'deniedMcpServers', 'forceLoginOrgs'):
        if key in value and not isinstance(value[key], list):
            raise ValueError(key + ' must be array')
    for key, options in [('autoTier', ['efficiency', 'balance', 'intelligence']), ('contextTier', ['default', 'long_context'])]:
        if key in value and value[key] not in options:
            raise ValueError(key + ' invalid enum')
    for key in ('deny', 'ask', 'allow'):
        rules = value.get('permissions', {}).get(key)
        if rules is not None and (not isinstance(rules, list) or not all(isinstance(x, str) for x in rules)):
            raise ValueError('permissions.' + key + ' must be string array')
    return value

def merge(old, change):
    result = dict(old)
    for k, v in change.items():
        if v is None:
            result.pop(k, None)
        elif isinstance(v, dict):
            result[k] = merge(result.get(k, {}) if isinstance(result.get(k), dict) else {}, v)
        else:
            result[k] = v
    return result

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *args):
        pass  # Never log URLs, headers, settings, or credentials.
    def respond(self, status, value):
        body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)
    def permitted(self):
        host = self.headers.get('Host', '')
        if host not in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'):
            self.respond(403, {'error': 'Invalid host'})
            return False
        origin = self.headers.get('Origin')
        if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'):
            self.respond(403, {'error': 'Foreign browser origins are not accepted'})
            return False
        return True
    def settings(self):
        return validate(json.loads(self.server.settings_file.read_text(encoding='utf-8')))
    def env_values(self):
        f = self.server.env_file
        return validate_env(json.loads(f.read_text(encoding='utf-8'))) if f.exists() else {}
    def admin(self):
        expected = 'Bearer ' + self.server.key
        if not hmac.compare_digest(self.headers.get('Authorization', ''), expected):
            self.respond(401, {'error': 'Admin authentication required'})
            return False
        return True
    def do_GET(self):
        if not self.permitted(): return
        path = urllib.parse.urlsplit(self.path).path
        try:
            if path == '/health':
                self.respond(200, {'service': 'copilot-managed-settings', 'cli': '1.0.90'})
            elif path == '/copilot_internal/managed_settings':
                with LOCK: self.respond(200, self.settings())
            elif path in ('/', '/ui'):
                body = UI_FILE.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'")
                self.send_header('X-Frame-Options', 'DENY')
                self.end_headers(); self.wfile.write(body)
            elif path == '/admin/env':
                if self.admin():
                    with LOCK: self.respond(200, {'values': self.env_values(), 'allowed': ENV_KEYS})
            elif path == '/admin/settings':
                if self.admin():
                    with LOCK: self.respond(200, self.settings())
            elif path.startswith('/admin/'):
                self.respond(404, {'error': 'Unknown admin endpoint'})
            else:
                self.relay()
        except (ValueError, OSError):
            self.respond(503, {'error': 'Settings unavailable or invalid; no empty fallback'})
    def do_PUT(self): self.change(False)
    def do_PATCH(self): self.change(True)
    def change(self, patch):
        if not self.permitted(): return
        route = urllib.parse.urlsplit(self.path).path
        if route not in ('/admin/settings', '/admin/env'):
            self.respond(405, {'error': 'Method not allowed'}); return
        env = route == '/admin/env'
        if not self.admin(): return
        try:
            if self.headers.get('Transfer-Encoding'): raise ValueError('Chunked input not supported')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BODY: raise ValueError('Invalid body size')
            value = json.loads(self.rfile.read(length), parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Non-finite JSON')))
            if not isinstance(value, dict): raise ValueError('Object required')
            with LOCK:
                if env:
                    new = validate_env(merge(self.env_values(), value) if patch else value)
                    new = {k: v for k, v in new.items() if v != ''}
                    atomic(self.server.env_file, (json.dumps(new, indent=2, allow_nan=False) + '\n').encode())
                    note = 'Launcher environment applies on the next copilot-managed start'
                else:
                    new = validate(merge(self.settings(), value) if patch else value)
                    atomic(self.server.settings_file, (json.dumps(new, indent=2, allow_nan=False) + '\n').encode())
                    note = 'CLI applies on its next managed-settings refresh / restart'
            self.respond(200, {'saved': True, 'note': note})
        except (ValueError, OSError) as e:
            self.respond(400, {'error': str(e) if isinstance(e, ValueError) else 'Write failed'})
    def relay(self):
        # Debug GitHub API URL routes more than managed settings. Fixed HTTPS
        # upstream, GET only, no redirects, no arbitrary absolute URL / SSRF.
        if not self.path.startswith('/') or self.path.startswith('//'):
            self.respond(400, {'error': 'Invalid path'}); return
        headers = {k:v for k,v in self.headers.items() if k.lower() in ('authorization', 'accept', 'user-agent', 'x-github-api-version')}
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs): return None
        req = urllib.request.Request('https://api.github.com' + self.path, headers=headers)
        try:
            try:
                resp = urllib.request.build_opener(NoRedirect).open(req, timeout=30)
            except urllib.error.HTTPError as e:
                resp = e
            with resp:
                body = resp.read(MAX_BODY + 1)
                if len(body) > MAX_BODY: raise ValueError('Response too large')
                self.send_response(resp.code)
                self.send_header('Content-Type', resp.headers.get('Content-Type', 'application/json'))
                self.send_header('Content-Length', str(len(body)))
                self.end_headers(); self.wfile.write(body)
        except (OSError, ValueError):
            self.respond(502, {'error': 'GitHub upstream unavailable'})

def make_server(settings_file, key_file, port=8790, env_file=None):
    settings_file, key_file = Path(settings_file), Path(key_file)
    env_file = Path(env_file) if env_file else settings_file.parent / 'launcher-env.json'
    if not settings_file.exists(): atomic(settings_file, b'{}\n')
    validate(json.loads(settings_file.read_text()))
    if not key_file.exists(): atomic(key_file, secrets.token_urlsafe(32).encode())
    server = http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.settings_file = settings_file
    server.env_file = env_file
    server.key = key_file.read_text().strip()
    if len(server.key) < 32: raise ValueError('Invalid admin key')
    return server

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--settings', default=str(BASE / 'managed-settings.json'))
    p.add_argument('--key-file', default=str(BASE / '.admin-key'))
    p.add_argument('--port', type=int, default=8790)
    args = p.parse_args()
    server = make_server(args.settings, args.key_file, args.port)
    print(f'Copilot settings server: http://127.0.0.1:{server.server_port}', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__ == '__main__': main()
