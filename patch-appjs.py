#!/usr/bin/env python3
"""Version-gated migration from app.js patching to the native settings route."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

BASE = Path(__file__).resolve().parent

def cli_command(args):
    exe = shutil.which('copilot.exe') or shutil.which('copilot') or shutil.which('copilot.cmd')
    roots = []
    if exe:
        roots.extend([Path(exe).parent / 'node_modules', Path(exe).resolve().parent.parent])
    if os.environ.get('APPDATA'):
        roots.append(Path(os.environ['APPDATA']) / 'npm' / 'node_modules')
    if os.name == 'nt' and (not exe or exe.lower().endswith(('.cmd', '.bat'))):
        for root in roots:
            candidates = list((root / '@github').glob('copilot-win32-*/copilot.exe'))
            if len(candidates) == 1:
                exe = str(candidates[0]); break
    if not exe:
        raise RuntimeError('Copilot not found on PATH. Install @github/copilot@1.0.90 first.')
    if os.name == 'nt' and exe.lower().endswith(('.cmd', '.bat')):
        raise RuntimeError('Native copilot.exe not found below npm shim. Unknown installation layout; refusing shell fallback.')
    return [exe, *args]

def version():
    result = subprocess.run(cli_command(['--version']), capture_output=True, text=True, timeout=30)
    if result.returncode or 'GitHub Copilot CLI 1.0.90.' not in result.stdout:
        raise RuntimeError('This integration is verified only for Copilot CLI 1.0.90; refusing a different/unknown version.')
    return result.stdout.strip()

def healthy():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8790/health', timeout=1) as response:
            value = json.load(response)
        return value.get('service') == 'copilot-managed-settings' and value.get('cli') == '1.0.90'
    except (OSError, ValueError):
        return False

def main():
    print(version(), flush=True)
    if '--check' in sys.argv[1:]:
        print('Host env support is native. No app.js or binary patches necessary.')
        return 0
    child = None
    if not healthy():
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        child = subprocess.Popen([sys.executable, str(BASE / 'managed-settings-proxy.py')],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
        deadline = time.monotonic() + 8
        while not healthy():
            if child.poll() is not None or time.monotonic() > deadline:
                if child.poll() is None: child.terminate()
                raise RuntimeError('Local server failed to start; no fallback to an unconfigured CLI.')
            time.sleep(.1)
    env = dict(os.environ)
    try:
        saved = json.loads((BASE / 'launcher-env.json').read_text(encoding='utf-8'))
        if isinstance(saved, dict):
            # Real process environment wins over UI-saved defaults.
            env.update({k: v for k, v in saved.items() if isinstance(v, str) and k not in os.environ})
    except (OSError, ValueError):
        pass
    env['COPILOT_DEBUG_GITHUB_API_URL'] = 'http://127.0.0.1:8790'
    try:
        return subprocess.call(cli_command(sys.argv[1:]), env=env)
    finally:
        if child is not None:
            child.terminate()
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired: child.kill(); child.wait()

if __name__ == '__main__':
    try: sys.exit(main())
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as e:
        print('ERROR:', e, file=sys.stderr)
        sys.exit(2)
