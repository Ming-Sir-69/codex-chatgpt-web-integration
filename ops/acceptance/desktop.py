#!/usr/bin/env python3
"""Exercise desktop-bundled app-server model selection and real local development."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from desktop_probe import Server, BINARY


def turn(server, thread, prompt):
    server.call('turn/start', {'threadId': thread,
                             'input': [{'type': 'text', 'text': prompt}]})
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        try:
            event = server.receive(timeout=30)
        except queue.Empty:
            continue
        if event.get('method') == 'turn/completed' and event['params'].get('threadId') == thread:
            result = event['params']['turn']
            if result.get('status') != 'completed':
                raise RuntimeError('Desktop turn failed: ' + json.dumps(result.get('error')))
            return
    raise TimeoutError('Desktop development turn did not finish')


def validate(project, output):
    with output.open('w') as log:
        subprocess.run([sys.executable, '-m', 'unittest', '-v'], cwd=project,
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=60)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', nargs='+', default=['high', 'light', 'medium', 'extra-high', 'pro'])
    args = parser.parse_args()
    if any(m not in ('high', 'light', 'medium', 'extra-high', 'pro') for m in args.models):
        parser.error('Only explicit ChatGPT Web aliases are permitted')
    work = HERE / 'runs' / ('desktop-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    work.mkdir(mode=0o700, parents=True)
    print('Desktop acceptance:', work, flush=True)
    results = []
    for alias in args.models:
        root = work / alias
        root.mkdir()
        project = root / 'project'
        shutil.copytree(HERE / 'fixture', project, ignore=shutil.ignore_patterns('__pycache__'))
        subprocess.run(['git', 'init', '-q', str(project)], check=True)
        server = Server(project, root / 'app-server.jsonl')
        result = {'model': 'chatgpt-web/' + alias, 'passed': False}
        try:
            params = {'cwd': str(project), 'approvalPolicy': 'never',
                      'approvalsReviewer': 'user', 'sandbox': 'workspace-write',
                      'developerInstructions': '只在当前验收项目读写和执行测试；不读父目录或个人资料，不调用其他模型或子代理。'}
            # High must come from the real default desktop configuration, not overrides.
            if alias != 'high':
                params['model'] = result['model']
            started = server.call('thread/start', params)
            assert started['model'] == result['model'], 'Desktop loaded the wrong model'
            assert started['modelProvider'] == 'openai', 'Desktop loaded the wrong provider'
            thread = started['thread']['id']
            result.update(thread_id=thread, model_provider=started['modelProvider'])
            print('Started', result['model'], thread, flush=True)
            turn(server, thread, '读取当前目录 README.md、audit.py、test_audit.py，实现校验器并执行 python3 -m unittest -v。'
                 '保持已有测试不变，只操作当前项目，不调用其他模型或子代理。必须实际修改文件并执行验证。')
            validate(project, root / 'validation1.txt')
            assert (project / 'test_audit.py').read_bytes() == (HERE / 'fixture/test_audit.py').read_bytes()
            result['function_tests_passed'] = 6
            if alias == 'high':
                turn(server, thread, '继续当前校验器，保持原函数合同，增加 python3 audit.py ROOT MANIFEST --json。'
                     'MANIFEST 是 JSON 文件，stdout 只打印函数结果 JSON，ok=true 时退出 0，否则退出 1。补充测试并执行全部测试。')
                validate(project, root / 'validation2.txt')
                with tempfile.TemporaryDirectory(dir=root) as temp:
                    data = Path(temp)
                    manifest = data / 'manifest.json'
                    manifest.write_text(json.dumps({'artifact': hashlib.sha256(b'release').hexdigest()}))
                    for expected in (0, 1):
                        (data / 'artifact').write_bytes(b'release' if expected == 0 else b'changed')
                        run = subprocess.run([sys.executable, 'audit.py', str(data), str(manifest), '--json'],
                                             cwd=project, capture_output=True, text=True, timeout=10)
                        assert run.returncode == expected and json.loads(run.stdout)['ok'] == (expected == 0)
                result['same_thread_continuation_and_cli_checks_passed'] = True
            result['passed'] = True
            print('PASS', result['model'], flush=True)
        except Exception as error:
            result['error'] = str(error)
            print('FAIL', result['model'], str(error), flush=True)
        finally:
            server.close()
            results.append(result)
            (work / 'result.json').write_text(json.dumps({'binary': BINARY, 'results': results}, indent=2) + '\n')
    if not all(r['passed'] for r in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
