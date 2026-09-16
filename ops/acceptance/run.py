#!/usr/bin/env python3
"""Run a real two-turn Codex Web development acceptance; never substitutes a model."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def turn(work, name, args, prompt):
    with (work / f'{name}.jsonl').open('w') as output, (work / f'{name}.stderr').open('w') as errors:
        result = subprocess.run(args, cwd=work / 'project', input=prompt, text=True,
                                stdout=output, stderr=errors, timeout=1200)
    events = []
    for line in (work / f'{name}.jsonl').read_text().splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    if result.returncode or any(e.get('type') == 'turn.failed' for e in events):
        raise RuntimeError(f'{name} failed; inspect the local logs. No fallback was attempted.')
    if not any(e.get('type') == 'turn.completed' for e in events):
        raise RuntimeError(f'{name} returned no completed turn')
    return events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--model', default='chatgpt-web/high')
    parser.add_argument('--without-native-auth', action='store_true',
                        help='Use an isolated Codex home with a deliberately invalid test API key')
    args = parser.parse_args()
    work = HERE / 'runs' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    work.mkdir(parents=True, mode=0o700)
    project = work / 'project'
    shutil.copytree(HERE / 'fixture', project, ignore=shutil.ignore_patterns('__pycache__'))
    subprocess.run(['git', 'init', '-q', str(project)], check=True)
    print(f'Acceptance workspace: {work}', flush=True)
    if args.prepare_only:
        return
    if not args.model.startswith('chatgpt-web/'):
        raise RuntimeError('Acceptance only permits explicit web models')
    if args.without_native_auth:
        codex_home = work / 'codex-home'
        codex_home.mkdir(mode=0o700)
        shutil.copyfile(HERE.parent / 'chatgpt-web.config.toml', codex_home / 'chatgpt-web.config.toml')
        auth = codex_home / 'auth.json'
        auth.write_text('{"OPENAI_API_KEY":"offline-isolation-test-not-a-real-key"}')
        auth.chmod(0o600)
        os.environ['CODEX_HOME'] = str(codex_home)
        for name in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENAI_BASE_URL'):
            os.environ.pop(name, None)
    command = str(Path.home() / '.local/bin/codex-web')
    base = [command, 'web', 'exec', '--ignore-user-config', '--json',
            '--model', args.model, '-c', 'cli_auth_credentials_store="file"',
            '-c', 'approval_policy="never"', '-c', 'sandbox_mode="workspace-write"']
    events = turn(work, 'turn1', base,
                  '请读取当前项目 README.md、audit.py 和 test_audit.py，实现校验器，保持测试不变，'
                  '执行 python3 -m unittest -v，并报告结果。只在当前项目操作，不调用其他模型或子代理。')
    thread = next((e.get('thread_id') for e in events if e.get('type') == 'thread.started'), None)
    if not thread:
        raise RuntimeError('No thread ID for continuation')
    subprocess.run([sys.executable, '-m', 'unittest', '-v'], cwd=project, check=True,
                   stdout=(work / 'validation1.txt').open('w'), stderr=subprocess.STDOUT)
    if (project / 'test_audit.py').read_bytes() != (HERE / 'fixture/test_audit.py').read_bytes():
        raise RuntimeError('First turn changed the acceptance tests')
    resume_args = [command, 'web', 'exec', 'resume', thread, '--ignore-user-config', '--json',
                   '--model', args.model, '-c', 'cli_auth_credentials_store="file"',
                   '-c', 'approval_policy="never"', '-c', 'sandbox_mode="workspace-write"']
    events2 = turn(work, 'turn2', resume_args,
                   '继续刚才的校验器，保持已有函数合同。增加 CLI：python3 audit.py ROOT MANIFEST --json。'
                   'MANIFEST 为 JSON 文件；标准输出只打印函数结果 JSON；ok 为 true 时退出 0，否则退出 1。'
                   '补充必要测试并执行全部测试，不调用其他模型或子代理。')
    subprocess.run([sys.executable, '-m', 'unittest', '-v'], cwd=project, check=True,
                   stdout=(work / 'validation2.txt').open('w'), stderr=subprocess.STDOUT)
    data = project / 'sample'
    data.mkdir()
    (data / 'artifact.bin').write_bytes(b'release')
    manifest = project / 'manifest.json'
    manifest.write_text(json.dumps({'artifact.bin': hashlib.sha256(b'release').hexdigest()}))
    for expected in (0, 1):
        if expected:
            (data / 'artifact.bin').write_bytes(b'changed')
        run = subprocess.run([sys.executable, 'audit.py', str(data), str(manifest), '--json'],
                             cwd=project, capture_output=True, text=True, timeout=10)
        try:
            payload = json.loads(run.stdout)
        except ValueError as error:
            raise RuntimeError('Independent CLI validation failed: stdout is not JSON; '
                               'a completed model turn is not task completion') from error
        if run.returncode != expected or payload.get('ok') != (expected == 0):
            raise RuntimeError('Independent CLI validation failed: incorrect result or exit code')
    summary = {'two_turns_completed': True, 'thread_id': thread,
               'model_alias': args.model, 'isolated_invalid_native_auth': args.without_native_auth,
               'function_tests_passed': True, 'cli_success_and_failure_passed': True,
               'model_route_requires_separate_bridge_evidence': True}
    (work / 'result.json').write_text(json.dumps(summary, indent=2) + '\n')
    print('Development checks passed; verify bridge/model evidence before claiming overall acceptance.')


if __name__ == '__main__':
    main()
