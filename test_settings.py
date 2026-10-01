import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('server', BASE / 'managed-settings-proxy.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=BASE)
        self.file = Path(self.tmp.name) / 'settings.json'
        self.server = m.make_server(self.file, Path(self.tmp.name) / 'key', 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.tmp.cleanup()
    def request(self, path='/admin/settings', method='GET', body=None, auth=True, headers=None):
        h = {'Authorization':'Bearer ' + self.server.key} if auth else {}
        h.update(headers or {})
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=3) as r: return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)
    def test_health(self): self.assertEqual(self.request('/health')[1]['cli'], '1.0.90')
    def test_no_auth(self): self.assertEqual(self.request(auth=False)[0], 401)
    def test_write_no_auth(self): self.assertEqual(self.request(method='PUT', body={}, auth=False)[0], 401)
    def test_bad_origin(self): self.assertEqual(self.request(headers={'Origin':'https://evil.invalid'})[0], 403)
    def test_bad_host(self): self.assertEqual(self.request(headers={'Host':'evil.invalid'})[0], 403)
    def test_replace(self):
        self.assertEqual(self.request(method='PUT',body={'model':'test-model'})[0],200)
        self.assertEqual(self.request('/copilot_internal/managed_settings?client_version=1.0.90')[1], {'model':'test-model'})
    def test_merge_delete(self):
        self.request(method='PUT',body={'model':'a','permissions':{'deny':['shell(rm)'],'ask':['shell(git)']}})
        self.request(method='PATCH',body={'model':None,'permissions':{'ask':None}})
        self.assertEqual(self.request()[1],{'permissions':{'deny':['shell(rm)']}})
    def test_unknown_rejected(self): self.assertEqual(self.request(method='PUT',body={'bogus':True})[0],400)
    def test_bad_type_no_mutation(self):
        old=self.file.read_bytes(); self.assertEqual(self.request(method='PUT',body={'model':123})[0],400)
        self.assertEqual(self.file.read_bytes(),old)
    def test_invalid_file_fails_closed(self):
        self.file.write_text('broken'); self.assertEqual(self.request('/copilot_internal/managed_settings')[0],503)
    def test_method_boundary(self): self.assertEqual(self.request('/copilot_internal/managed_settings', method='PUT', body={})[0],405)
    def test_env_roundtrip_and_reject_secret(self):
        self.assertEqual(self.request('/admin/env')[1]['values'], {})
        self.assertEqual(self.request('/admin/env', 'PUT', {'COPILOT_PROVIDER_BASE_URL': 'http://127.0.0.1:1/v1'})[0], 200)
        self.assertEqual(self.request('/admin/env')[1]['values'], {'COPILOT_PROVIDER_BASE_URL': 'http://127.0.0.1:1/v1'})
        self.assertEqual(self.request('/admin/env', 'PUT', {'COPILOT_PROVIDER_API_KEY': 'x'})[0], 400)
        self.assertEqual(self.request('/admin/env', 'PUT', {'PATH': 'x'})[0], 400)
        self.assertEqual(self.request('/admin/env', 'PATCH', {'COPILOT_PROVIDER_BASE_URL': None})[0], 200)
        self.assertEqual(self.request('/admin/env')[1]['values'], {})
    def test_env_needs_auth(self): self.assertEqual(self.request('/admin/env', auth=False)[0], 401)
    def test_ui_served_with_csp(self):
        req = urllib.request.Request(self.url + '/')
        with urllib.request.urlopen(req, timeout=3) as r:
            self.assertIn('Content-Security-Policy', r.headers); self.assertIn(b'Managed Settings', r.read())
    def test_same_origin_allowed_foreign_blocked(self):
        self.assertEqual(self.request(headers={'Origin': self.url})[0], 200)
    def _fake_upstream(self, payload, status=200):
        class U(m.http.server.BaseHTTPRequestHandler):
            seen = {}
            def do_GET(h):
                U.seen['auth'] = h.headers.get('Authorization')
                b = json.dumps(payload).encode(); h.send_response(status); h.send_header('Content-Length', str(len(b))); h.end_headers(); h.wfile.write(b)
            def log_message(h, *a): pass
        srv = m.http.server.ThreadingHTTPServer(('127.0.0.1', 0), U)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown); self.addCleanup(srv.server_close)
        self.server.models_upstream = f'http://127.0.0.1:{srv.server_port}/models'
        return U
    def test_models_manual_roundtrip(self):
        self.assertEqual(self.request('/admin/models')[1], {'models': [], 'source': 'none'})
        self.assertEqual(self.request('/admin/models', 'PUT', {'models': ['a', 'b', 'a']})[1], {'models': ['a', 'b'], 'source': 'manual'})
        self.assertEqual(self.request('/admin/models')[1]['models'], ['a', 'b'])
        self.assertEqual(self.request('/admin/models', 'PUT', {'models': ['has space']})[0], 400)
        self.assertEqual(self.request('/admin/models', 'PUT', {'models': 'x'})[0], 400)
        self.assertEqual(self.request('/admin/models', auth=False)[0], 401)
    def test_models_refresh_without_token(self):
        for k in m.TOKEN_ENV: os.environ.pop(k, None)
        self.assertEqual(self.request('/admin/models/refresh', 'POST', {})[0], 409)
    def test_models_refresh_from_account(self):
        U = self._fake_upstream({'data': [{'id': 'm-one'}, {'id': 'm-two', 'model_picker_enabled': True}, {'id': 'hidden', 'model_picker_enabled': False}]})
        os.environ['GH_TOKEN'] = 'fixture-token'; self.addCleanup(os.environ.pop, 'GH_TOKEN', None)
        st, body = self.request('/admin/models/refresh', 'POST', {})
        self.assertEqual((st, body['models'], body['source']), (200, ['m-one', 'm-two'], 'account'))
        self.assertEqual(U.seen['auth'], 'Bearer fixture-token')
        self.assertNotIn('fixture-token', (Path(self.tmp.name) / 'models-cache.json').read_text())
    def test_models_refresh_failure_keeps_list(self):
        self.request('/admin/models', 'PUT', {'models': ['keep']})
        self._fake_upstream({'error': 'x'}, status=401)
        os.environ['GH_TOKEN'] = 'fixture-token'; self.addCleanup(os.environ.pop, 'GH_TOKEN', None)
        self.assertEqual(self.request('/admin/models/refresh', 'POST', {})[0], 502)
        self.assertEqual(self.request('/admin/models')[1]['models'], ['keep'])
    def test_persisted(self):
        self.request(method='PATCH',body={'shellShortcut':False})
        self.assertEqual(json.loads(self.file.read_text()),{'shellShortcut':False})
    @unittest.skipUnless(os.environ.get('COPILOT_TEST_RUNTIME'), 'native 1.0.90 runtime not supplied')
    def test_real_native_readback(self):
        settings={'model':'test-model','autoTier':'balance','effortLevel':'high','contextTier':'default','shellShortcut':False,'permissions':{'deny':['shell(rm)']}}
        self.request(method='PUT',body=settings)
        runtime=os.environ['COPILOT_TEST_RUNTIME']
        # Explicit unauthenticated test fixture for the runtime's account lookup.
        # No real GitHub credentials or network calls are used by this test.
        from unittest.mock import patch
        def fixture_user_info(handler): handler.respond(200, {})
        self.fixture_patch = patch.object(m.Handler, 'relay', fixture_user_info)
        self.fixture_patch.start()
        self.addCleanup(self.fixture_patch.stop)
        js='const b=require('+json.dumps(runtime)+');b.managedSettingsGetDirect({selfFetch:true,token:"local-test-fixture-only",userAgent:"test",platform:process.platform,homeDirectory:"/nonexistent",environment:{COPILOT_DEBUG_GITHUB_API_URL:'+json.dumps(self.url)+'}}).then(x=>console.log(JSON.stringify(x.resolved))).catch(e=>{console.error(e.message);process.exit(1)})'
        r=subprocess.run(['node','-e',js],capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stderr)
        value=json.loads(r.stdout)
        self.assertEqual(value['source'],'server'); self.assertTrue(value['serverManaged'])
        self.assertEqual(value['settings'],settings)
        # Update without server restart; next native fetch sees the new policy.
        self.request(method='PATCH',body={'model':'test-model-two'})
        r=subprocess.run(['node','-e',js],capture_output=True,text=True,timeout=20)
        self.assertEqual(json.loads(r.stdout)['settings']['model'],'test-model-two')

if __name__ == '__main__': unittest.main(verbosity=2)
