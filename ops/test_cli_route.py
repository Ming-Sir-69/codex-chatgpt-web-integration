"""Offline routing test using real Codex and a loopback HTTP sentinel, with no real credentials."""
import http.server
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest

from manage import codex_command


class RouteTests(unittest.TestCase):
    def test_rejects_native_model_and_hidden_flags(self):
        profile = {'model': 'chatgpt-web/high'}
        for args in (['-m', 'gpt-6-astra'], ['--model=gpt-6-astra'], ['--']):
            with self.assertRaises(RuntimeError):
                codex_command(profile, args, True)

    def test_real_codex_exec_routes_after_ignore_user_config(self):
        requests = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                body = b'{"models": []}'
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
                requests.append({'path': self.path, 'model': data.get('model')})
                body = b'{"error":{"message":"OFFLINE_ROUTE_SENTINEL_NO_INFERENCE","type":"invalid_request_error"}}'
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        with tempfile.TemporaryDirectory(prefix='cwg-route-') as temp:
            root = Path(temp)
            auth = root / 'auth.json'
            auth.write_text('{"OPENAI_API_KEY":"offline-test-only-not-a-real-key"}')
            auth.chmod(0o600)
            profile = {'model_provider': 'openai', 'model': 'chatgpt-web/high',
                       'openai_base_url': f'http://127.0.0.1:{server.server_port}/v1',
                       'approvals_reviewer': 'user'}
            env = dict(os.environ, CODEX_HOME=temp)
            for name in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENAI_BASE_URL'):
                env.pop(name, None)
            command = codex_command(profile, ['exec', '--ignore-user-config', '--skip-git-repo-check',
                                               '--json', 'Reply ROUTE'], True)
            result = subprocess.run(command, cwd=temp, env=env, input='', text=True,
                                    capture_output=True, timeout=45)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(requests, (result.stdout + result.stderr)[-1200:])
            self.assertTrue(all(r['model'] == 'chatgpt-web/high' for r in requests), requests)
            self.assertIn('OFFLINE_ROUTE_SENTINEL_NO_INFERENCE', result.stdout + result.stderr)
            events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
            thread = next(e['thread_id'] for e in events if e.get('type') == 'thread.started')
            count = len(requests)
            command = codex_command(profile, ['exec', 'resume', thread, '--ignore-user-config',
                                               '--skip-git-repo-check', '--json', 'Continue ROUTE'], True)
            resumed = subprocess.run(command, cwd=temp, env=env, input='', text=True,
                                     capture_output=True, timeout=45)
            self.assertNotEqual(resumed.returncode, 0)
            self.assertGreater(len(requests), count, (resumed.stdout + resumed.stderr)[-1200:])
            self.assertTrue(all(r['model'] == 'chatgpt-web/high' for r in requests), requests)
            self.assertIn('OFFLINE_ROUTE_SENTINEL_NO_INFERENCE', resumed.stdout + resumed.stderr)


if __name__ == '__main__':
    unittest.main()
