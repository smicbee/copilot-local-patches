#!/usr/bin/env python3
"""Admin client. Tokens never printed or placed in command-line arguments."""
import argparse
import json
from pathlib import Path
import urllib.request

BASE = Path(__file__).resolve().parent

def main():
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['get', 'replace', 'patch'])
    p.add_argument('file', nargs='?')
    p.add_argument('--port', type=int, default=8790)
    args = p.parse_args()
    body = None
    method = 'GET'
    if args.action != 'get':
        if not args.file: p.error('JSON file required')
        body = json.dumps(json.loads(Path(args.file).read_text(encoding='utf-8')), allow_nan=False).encode()
        method = {'replace':'PUT','patch':'PATCH'}[args.action]
    req = urllib.request.Request(f'http://127.0.0.1:{args.port}/admin/settings', data=body, method=method,
        headers={'Authorization':'Bearer ' + (BASE / '.admin-key').read_text().strip(), 'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=10) as response:
        print(response.read().decode())

if __name__ == '__main__': main()
