#!/usr/bin/env python3
"""Probe a fresh server from the desktop-bundled Codex, without touching the running UI."""
import argparse
import json
from pathlib import Path
import queue
import subprocess
import threading
import time

BINARY = '/Applications/ChatGPT.app/Contents/Resources/codex'


class Server:
    def __init__(self, cwd, log):
        self.errors = log.with_suffix('.stderr').open('w')
        self.log = log.open('w')
        log.chmod(0o600)
        log.with_suffix('.stderr').chmod(0o600)
        self.process = subprocess.Popen([BINARY, 'app-server', '--stdio'], cwd=cwd,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self.errors, text=True, bufsize=1)
        self.events = queue.Queue()
        self.number = 0
        self.requests = {}
        def reader():
            for line in self.process.stdout:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                logged = event
                if self.requests.get(event.get('id')) == 'config/read' and 'result' in event:
                    config = event['result'].get('config', {})
                    logged = {'id': event['id'], 'result': {'config': {k: config.get(k) for k in
                              ('model', 'model_provider', 'model_catalog_json', 'openai_base_url')}}}
                self.log.write(json.dumps(logged) + '\n')
                self.log.flush()
                self.events.put(event)
            self.events.put({'processExited': True})
        self.reader = threading.Thread(target=reader, daemon=True)
        self.reader.start()
        self.call('initialize', {'clientInfo': {'name': 'cwg_desktop_acceptance', 'version': '1.0'},
                                 'capabilities': {'experimentalApi': True}})
        self.send({'method': 'initialized', 'params': {}})

    def send(self, value):
        self.process.stdin.write(json.dumps(value) + '\n')
        self.process.stdin.flush()

    def receive(self, timeout=60):
        event = self.events.get(timeout=timeout)
        if event.get('processExited'):
            raise RuntimeError('Desktop test server exited')
        # Never grant an unexpected approval automatically.
        if 'id' in event and 'method' in event:
            self.send({'id': event['id'], 'error': {'code': -32601,
                       'message': 'Unexpected request in automated acceptance'}})
            raise RuntimeError('Unexpected server request: ' + event['method'])
        return event

    def call(self, method, params):
        self.number += 1
        request_id = self.number
        self.requests[request_id] = method
        self.send({'id': request_id, 'method': method, 'params': params})
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            event = self.receive()
            if event.get('id') == request_id:
                if 'error' in event:
                    raise RuntimeError(str(event['error']))
                return event['result']
        raise TimeoutError(method)

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=8)
        self.reader.join(timeout=2)
        self.log.close()
        self.errors.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    server = Server(Path.cwd(), args.output.with_suffix('.jsonl'))
    try:
        config = server.call('config/read', {'cwd': str(Path.cwd()), 'includeLayers': False})
        models = server.call('model/list', {'includeHidden': False})
        c = config.get('config', {})
        result = {'binary': BINARY, 'version': subprocess.check_output([BINARY, '--version'], text=True).strip(),
                  'config': {k: c.get(k) for k in ('model', 'model_provider', 'model_catalog_json', 'openai_base_url')},
                  'models': models}
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, ensure_ascii=False))
    finally:
        server.close()


if __name__ == '__main__':
    main()
