#!/usr/bin/env python3
"""Offline desktop model-switch probe. Usage counts are simulated, no real model is called."""
import http.server
import json
import os
from pathlib import Path
import tempfile
import threading

from desktop_probe import Server


def probe(usage, output):
    requests = []
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            trigger = any(isinstance(x, dict) and x.get('type') == 'compaction_trigger'
                          for x in body.get('input', []))
            requests.append({'path': self.path, 'model': body.get('model'), 'compaction_trigger': trigger})
            compact = self.path.endswith('/compact') or trigger or (
                len(requests) > 1 and body.get('model') == 'gpt-6-astra')
            if compact:
                data = b'{"error":{"message":"OFFLINE_COMPACTION_SENTINEL","type":"invalid_request_error"}}'
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
            else:
                message = {'id': 'msg_probe', 'type': 'message', 'status': 'completed', 'role': 'assistant',
                           'content': [{'type': 'output_text', 'text': 'OFFLINE OK', 'annotations': []}]}
                response = {'id': 'resp_' + str(len(requests)), 'object': 'response', 'status': 'completed',
                            'model': body.get('model'), 'output': [message],
                            'usage': {'input_tokens': usage, 'output_tokens': 3, 'total_tokens': usage + 3,
                                      'input_tokens_details': {'cached_tokens': 0},
                                      'output_tokens_details': {'reasoning_tokens': 0}}}
                events = [
                    {'type': 'response.created', 'response': {'id': response['id'], 'status': 'in_progress', 'output': []}},
                    {'type': 'response.output_item.added', 'output_index': 0, 'item': message},
                    {'type': 'response.output_text.delta', 'item_id': 'msg_probe', 'output_index': 0,
                     'content_index': 0, 'delta': 'OFFLINE OK'},
                    {'type': 'response.output_item.done', 'output_index': 0, 'item': message},
                    {'type': 'response.completed', 'response': response},
                ]
                data = ''.join('event: ' + e['type'] + '\ndata: ' + json.dumps(e) + '\n\n' for e in events).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    sentinel = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=sentinel.serve_forever, daemon=True).start()
    old_home = os.environ.get('CODEX_HOME')
    with tempfile.TemporaryDirectory(prefix='cwg-context-switch-') as temp:
        root = Path(temp)
        (root / 'auth.json').write_text('{"OPENAI_API_KEY":"offline-context-test-not-a-key"}')
        (root / 'auth.json').chmod(0o600)
        catalog = Path.home() / '.codex-chatgpt-web/local-ops/web-models.json'
        (root / 'config.toml').write_text(
            'model="gpt-6-astra"\nmodel_provider="openai"\ncli_auth_credentials_store="file"\n'
            f'openai_base_url="http://127.0.0.1:{sentinel.server_port}/v1"\n'
            f'model_catalog_json={json.dumps(str(catalog))}\n'
            'model_context_window=1000000\nmodel_auto_compact_token_limit=900000\n'
            'approvals_reviewer="user"\n')
        os.environ['CODEX_HOME'] = temp
        server = Server(root, output.with_suffix('.jsonl'))
        try:
            start = server.call('thread/start', {'cwd': temp, 'approvalPolicy': 'never', 'sandbox': 'read-only'})
            thread = start['thread']['id']
            finished = []
            windows = []
            for model in ('gpt-6-astra', 'chatgpt-web/pro'):
                server.call('turn/start', {'threadId': thread, 'model': model,
                    'input': [{'type': 'text', 'text': 'Reply OFFLINE OK without tools.'}]})
                while True:
                    event = server.receive(timeout=90)
                    if event.get('method') == 'thread/tokenUsage/updated':
                        windows.append(event['params'].get('tokenUsage', {}))
                    if event.get('method') == 'turn/completed':
                        finished.append(event['params']['turn']['status'])
                        break
            result = {'simulated_input_tokens': usage, 'no_real_inference': True,
                      'turn_statuses': finished, 'requests': requests, 'token_usage_events': windows}
            output.write_text(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result))
        finally:
            server.close()
            if old_home is None:
                os.environ.pop('CODEX_HOME', None)
            else:
                os.environ['CODEX_HOME'] = old_home
            sentinel.shutdown()
            sentinel.server_close()


if __name__ == '__main__':
    root = Path(__file__).resolve().parent / 'evidence'
    for count in (50000, 500000):
        probe(count, root / f'context-switch-{count}.json')
