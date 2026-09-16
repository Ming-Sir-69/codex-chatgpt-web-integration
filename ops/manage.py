#!/usr/bin/env python3
"""Small standalone entrypoint; requires Python 3.11+, Codex and the upstream launcher."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.request

ROOT = Path(__file__).resolve().parent
CORE = Path(os.environ.get('CODEX_CHATGPT_WEB_HOME', '~/.codex-chatgpt-web')).expanduser()
CODEX = Path(os.environ.get('CODEX_HOME', '~/.codex')).expanduser()
APP = Path('/Applications/Codex Web GPT.app')
MARKER = '# Managed by codex-chatgpt-web ops;'


def runtime():
    # The application manifest chooses the runtime, never the newest arbitrary directory.
    p = APP / 'Contents/Resources/runtime/bin/codex-chatgpt-web'
    if not p.is_file():
        raise RuntimeError('Install Codex Web GPT.app before using this command')
    return str(p)


def install_profiles():
    CODEX.mkdir(parents=True, exist_ok=True)
    for name in ('chatgpt-web', 'chatgpt-native'):
        source = ROOT / f'{name}.config.toml'
        target = CODEX / source.name
        if target.exists() and not target.read_text().startswith(MARKER):
            raise RuntimeError(f'Refusing to overwrite an unmanaged profile: {target}')
        data = source.read_text()
        temp = target.with_suffix('.tmp')
        with temp.open('x') as f:
            os.chmod(temp, 0o600)
            f.write(data)
        temp.replace(target)
        print(f'Installed {target}')


def install_command():
    destination = CORE / 'local-ops'
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name in ('manage.py', 'chatgpt-web.config.toml', 'chatgpt-native.config.toml'):
        source = ROOT / name
        target = destination / name
        if source.resolve() != target.resolve():
            shutil.copyfile(source, target)
        target.chmod(0o600)
    python = shutil.which('python3')
    if not python:
        raise RuntimeError('Python 3.11+ is required')
    subprocess.run([python, '-c', 'import tomllib'], check=True)
    command = Path.home() / '.local/bin/codex-web'
    command.parent.mkdir(parents=True, exist_ok=True)
    if command.exists() and MARKER not in command.read_text():
        raise RuntimeError(f'Refusing to replace another command: {command}')
    command.write_text('#!/bin/sh\n' + MARKER + '\nexec ' + shlex.quote(python)
                       + ' ' + shlex.quote(str(destination / 'manage.py')) + ' "$@"\n')
    command.chmod(0o700)
    print(f'Installed {command}')


def autostart(enable):
    label = 'local.codex-chatgpt-web.launcher'
    domain = f'gui/{os.getuid()}'
    target = Path.home() / 'Library/LaunchAgents' / f'{label}.plist'
    if not enable:
        if target.exists():
            subprocess.run(['launchctl', 'bootout', f'{domain}/{label}'], capture_output=True)
            target.unlink()
        return
    command = Path.home() / '.local/bin/codex-web'
    if not command.exists():
        raise RuntimeError('Run install-command first')
    if target.exists():
        existing = plistlib.loads(target.read_bytes())
        if existing.get('ProgramArguments') != [str(command), 'open']:
            raise RuntimeError(f'Refusing to overwrite another login task: {target}')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(plistlib.dumps({'Label': label, 'ProgramArguments': [str(command), 'open'],
                                      'RunAtLoad': True, 'LimitLoadToSessionType': 'Aqua',
                                      'ProcessType': 'Background'}))
    target.chmod(0o600)
    probe = subprocess.run(['launchctl', 'print', f'{domain}/{label}'], capture_output=True)
    if probe.returncode != 0:
        subprocess.run(['launchctl', 'bootstrap', domain, str(target)], check=True)
    print('Proxy-aware login startup installed; turn off the application own login item to avoid racing it.')


def health():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open('http://127.0.0.1:17841/healthz', timeout=5) as response:
        return json.load(response)


def desktop_config(enable):
    """Own only four desktop selections; leave upstream's route journal untouched."""
    target = CODEX / 'config.toml'
    journal = CORE / 'local-ops/desktop-integration.json'
    text = target.read_text()
    parsed = tomllib.loads(text)
    state = json.loads(journal.read_text()) if journal.exists() else None
    desired = {'model_provider': 'openai', 'model': 'chatgpt-web/high',
               'model_catalog_json': str(CORE / 'local-ops/web-models.json'),
               'service_tier': 'default'}
    lines = text.splitlines(keepends=True)

    def assignment(key):
        for i, line in enumerate(lines):
            if re.match(r'^\s*\[', line):
                break
            if re.match(r'^\s*' + re.escape(key) + r'\s*=', line):
                return i, line
        if key in tomllib.loads(''.join(lines)):
            raise RuntimeError('Unsupported assignment layout for ' + key)
        return None, None

    if enable:
        if parsed.get('openai_base_url') != 'http://127.0.0.1:17841/v1':
            raise RuntimeError('Connect the upstream loopback route before enabling desktop models')
        if not Path(desired['model_catalog_json']).is_file():
            raise RuntimeError('Run refresh-catalog before enabling desktop models')
        if state and state['phase'] in ('prepared', 'active'):
            for key in desired:
                if key != 'model' and parsed.get(key) != state['installed'][key]:
                    if state['phase'] != 'prepared' or parsed.get(key) != state['previous'][key]['value']:
                        raise RuntimeError('Desktop setting changed; review before overwriting: ' + key)
        else:
            state = {'phase': 'prepared', 'installed': desired, 'previous': {}}
            for key in desired:
                _, raw = assignment(key)
                state['previous'][key] = {'value': parsed.get(key), 'raw': raw}
            atomic_private_json(journal, state)
        values = {key: json.dumps(value) for key, value in desired.items()}
        replacements = {key: f'{key} = {value}\n' for key, value in values.items()}
    else:
        if not state or state['phase'] == 'inactive':
            return
        replacements = {}
        for key, installed in state['installed'].items():
            current = parsed.get(key)
            if key == 'model' and current != installed:
                # A model picker can persist another selection. Do not leave a Web
                # alias behind when restoring the old provider; preserve native picks.
                if not str(current).startswith('chatgpt-web/'):
                    continue
            elif current != installed:
                if current == state['previous'][key]['value']:
                    continue
                raise RuntimeError('Desktop setting changed; review before restoring: ' + key)
            replacements[key] = state['previous'][key]['raw']
    for key, raw in replacements.items():
        index, _ = assignment(key)
        if index is not None:
            if raw is None:
                lines.pop(index)
            else:
                lines[index] = raw
        elif raw is not None:
            lines.insert(0, raw)
    updated = ''.join(lines)
    tomllib.loads(updated)
    if target.read_text() != text:
        raise RuntimeError('Codex config changed concurrently; no config was overwritten')
    temp = target.with_name('config.toml.cwg-desktop.tmp')
    with temp.open('x') as output:
        os.chmod(temp, 0o600)
        output.write(updated)
    temp.replace(target)
    state['phase'] = 'active' if enable else 'inactive'
    atomic_private_json(journal, state)
    print('Desktop model selections enabled; restart Codex to reload.' if enable
          else 'Desktop model selections restored; unrelated settings preserved.')


def atomic_private_json(target, value):
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=target.parent, prefix=target.name + '.', delete=False) as output:
        temp = Path(output.name)
        json.dump(value, output, indent=2)
    temp.replace(target)


def catalog_inputs():
    bridge = json.loads((CORE / 'config.json').read_text())
    codex = tomllib.loads((CODEX / 'config.toml').read_text())
    # Only catalogue-affecting settings; never persist credentials or the full config.
    return {'bridge': {k: bridge.get(k) for k in (
        'browserInteractionMode', 'solAvailable', 'proAvailable', 'experimentalBiggerContext',
        'zeroRiskProEnabled', 'subagentProtocol', 'mode')},
        'codex': {k: codex.get(k) for k in ('model_context_window', 'model_auto_compact_token_limit')}}


def catalog_is_current():
    metadata = CORE / 'local-ops/catalog-state.json'
    catalog = CORE / 'local-ops/web-models.json'
    if not metadata.exists() or not catalog.exists():
        return False
    saved = json.loads(metadata.read_text())
    return (saved.get('inputs') == catalog_inputs()
            and saved.get('sha256') == hashlib.sha256(catalog.read_bytes()).hexdigest())


def sync_catalog():
    if catalog_is_current():
        return
    # The launcher's own restart can briefly overlap a Bigger Context toggle.
    for attempt in range(4):
        try:
            refresh_catalog()
            return
        except (OSError, RuntimeError, ValueError):
            if attempt == 3:
                raise
            time.sleep(2)


def catalog_watch(enable):
    label = 'local.codex-chatgpt-web.catalog'
    domain = f'gui/{os.getuid()}'
    target = Path.home() / 'Library/LaunchAgents' / f'{label}.plist'
    command = Path.home() / '.local/bin/codex-web'
    expected = [str(command), 'sync-catalog']
    if target.exists() and plistlib.loads(target.read_bytes()).get('ProgramArguments') != expected:
        raise RuntimeError('Refusing to replace an unrelated catalogue login task')
    if not enable:
        if target.exists():
            subprocess.run(['launchctl', 'bootout', f'{domain}/{label}'], capture_output=True)
            target.unlink()
        return
    if not command.exists():
        raise RuntimeError('Install the standalone command first')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(plistlib.dumps({'Label': label, 'ProgramArguments': expected,
        'RunAtLoad': True, 'WatchPaths': [str(CORE / 'config.json'), str(CODEX / 'config.toml')],
        'ThrottleInterval': 10, 'LimitLoadToSessionType': 'Aqua', 'ProcessType': 'Background'}))
    target.chmod(0o600)
    if subprocess.run(['launchctl', 'print', f'{domain}/{label}'], capture_output=True).returncode:
        subprocess.run(['launchctl', 'bootstrap', domain, str(target)], check=True)
    print('Catalogue sync enabled for bridge and Codex context-setting changes; no model inference.')


def refresh_catalog():
    """Cache real bridge metadata so Codex selects native tools before its first request."""
    inputs = catalog_inputs()
    live = health()
    if live.get('service') != 'codex-chatgpt-web' or live.get('mode') != 'full':
        raise RuntimeError('Start the Full bridge before refreshing its model catalog')
    codex = shutil.which('codex')
    if not codex:
        # launchd has no Homebrew PATH; prefer the standalone desktop binary over
        # the npm wrapper, whose /usr/bin/env node would fail in that environment.
        codex = next((str(p) for p in (Path('/Applications/ChatGPT.app/Contents/Resources/codex'),
                     Path('/opt/homebrew/bin/codex')) if p.is_file()), None)
    if not codex:
        raise RuntimeError('Codex is unavailable for catalogue refresh')
    version = subprocess.check_output([codex, '--version'], text=True).strip()
    match = re.search(r'\b(\d+\.\d+\.\d+)\b', version)
    if not match:
        raise RuntimeError('Cannot identify the installed Codex version')
    auth = json.loads((CODEX / 'auth.json').read_text()).get('tokens', {})
    if not auth.get('access_token'):
        raise RuntimeError('A Codex ChatGPT login in auth.json is needed to refresh the catalog')
    headers = {'Authorization': 'Bearer ' + auth['access_token'],
               'User-Agent': 'codex_cli_rs/' + match[1]}
    if auth.get('account_id'):
        headers['ChatGPT-Account-ID'] = auth['account_id']
    request = urllib.request.Request(
        'http://127.0.0.1:17841/v1/models?client_version=' + match[1], headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=45) as response:
        catalog = json.load(response)
    web_models = [m for m in catalog.get('models', []) if m.get('slug', '').startswith('chatgpt-web/')]
    if not web_models or any(m.get('apply_patch_tool_type') != 'freeform' for m in web_models):
        raise RuntimeError('The bridge returned an incomplete native tool catalog; old snapshot preserved')
    if (live.get('version') == '5.0.6' and inputs['bridge'].get('proAvailable')
            and inputs['bridge'].get('browserInteractionMode') != 'manual'):
        expected = 95000 * (3 if inputs['bridge'].get('experimentalBiggerContext') else 1)
        if any(m.get('auto_compact_token_limit') != expected for m in web_models):
            raise RuntimeError('The running bridge has not loaded the new context setting; retry after its restart')
    if inputs != catalog_inputs():
        raise RuntimeError('Context settings changed during catalogue refresh; old snapshot preserved')
    target = CORE / 'local-ops/web-models.json'
    atomic_private_json(target, catalog)
    atomic_private_json(CORE / 'local-ops/catalog-state.json', {
        'inputs': inputs, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    print('Saved live bridge model metadata privately; no model inference was requested.')


def codex_command(profile, extra, web):
    if '--' in extra:
        raise RuntimeError('The -- separator would hide required route flags; omit it')
    model = profile['model']
    forwarded = []
    iterator = iter(extra)
    for arg in iterator:
        if arg in ('-m', '--model'):
            model = next(iterator, '')
        elif arg.startswith('--model='):
            model = arg.split('=', 1)[1]
        else:
            forwarded.append(arg)
    if not model or (web and not model.startswith('chatgpt-web/')):
        raise RuntimeError('The web entrypoint only accepts chatgpt-web/ models; use native to switch explicitly')
    options = []
    for key, value in profile.items():
        if key != 'model':
            options += ['-c', f'{key}={json.dumps(value, ensure_ascii=False)}']
    # On 0.154, exec/resume have independent config argument parsing. Putting
    # these on the innermost command also survives --ignore-user-config.
    return ['codex', *forwarded, *options, '--model', model]


def open_app():
    # LaunchServices does not inherit shell proxy variables. Use current macOS settings,
    # so this remains independent of any particular proxy app or personal shell setup.
    result = subprocess.run(['scutil', '--proxy'], capture_output=True, text=True, check=True)
    settings = {}
    for line in result.stdout.splitlines():
        if ' : ' in line:
            key, value = line.strip().split(' : ', 1)
            settings[key] = value
    command = ['open']
    for scheme in ('HTTP', 'HTTPS'):
        if settings.get(scheme + 'Enable') == '1':
            host, port = settings.get(scheme + 'Proxy'), settings.get(scheme + 'Port')
            if host and port and port.isdigit():
                command += ['--env', f'{scheme}_PROXY=http://{host}:{port}']
    command += ['--env', 'NO_PROXY=localhost,127.0.0.1,::1', str(APP)]
    subprocess.run(command, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['open', 'install-profiles', 'remove-profiles', 'install-command',
                                         'autostart-on', 'autostart-off', 'refresh-catalog', 'sync-catalog',
                                         'catalog-watch-on', 'catalog-watch-off', 'install-desktop', 'status',
                                         'doctor', 'connect', 'disconnect', 'web', 'native', 'cli'])
    parser.add_argument('extra', nargs=argparse.REMAINDER, help='Arguments passed to Codex or upstream CLI')
    args = parser.parse_args()
    extra = args.extra
    if args.action == 'install-profiles':
        install_profiles()
    elif args.action == 'install-command':
        install_command()
    elif args.action in ('autostart-on', 'autostart-off'):
        autostart(args.action == 'autostart-on')
    elif args.action == 'remove-profiles':
        for name in ('chatgpt-web', 'chatgpt-native'):
            target = CODEX / f'{name}.config.toml'
            if target.exists():
                if target.read_bytes() != (ROOT / target.name).read_bytes():
                    raise RuntimeError(f'Profile changed; review it before removal: {target}')
                target.unlink()
                print(f'Removed {target}')
    elif args.action == 'open':
        open_app()
    elif args.action == 'refresh-catalog':
        refresh_catalog()
    elif args.action == 'sync-catalog':
        sync_catalog()
    elif args.action in ('catalog-watch-on', 'catalog-watch-off'):
        catalog_watch(args.action == 'catalog-watch-on')
    elif args.action == 'install-desktop':
        desktop_config(True)
    elif args.action in ('connect', 'disconnect'):
        if args.action == 'disconnect':
            desktop_config(False)
        subprocess.run([runtime(), 'route', args.action, *extra], check=True)
        if args.action == 'connect' and (CORE / 'local-ops/desktop-integration.json').exists():
            desktop_config(True)
    elif args.action in ('web', 'native'):
        name = 'chatgpt-web' if args.action == 'web' else 'chatgpt-native'
        if not (CODEX / f'{name}.config.toml').is_file():
            raise RuntimeError('Run install-profiles first')
        if args.action == 'web':
            if CODEX.resolve() == (Path.home() / '.codex').resolve():
                sync_catalog()
            config = json.loads((CORE / 'config.json').read_text())
            if config.get('mode') != 'full':
                raise RuntimeError('Full harness is not configured. Complete MCP setup in the launcher; no fallback was attempted.')
            live = health()
            if (live.get('service') != 'codex-chatgpt-web' or live.get('mode') != 'full'
                    or live.get('status') != 'ok' or live.get('accepting_turns') is not True):
                raise RuntimeError('The local Full bridge is not ready; no fallback was attempted.')
        # Codex 0.154 ignores profile files together with --ignore-user-config. Explicit
        # CLI overrides keep this wrapper's route in force even during isolated acceptance.
        profile = tomllib.loads((CODEX / f'{name}.config.toml').read_text())
        if args.action == 'web' and (profile.get('model_provider') != 'openai'
                or profile.get('openai_base_url') != 'http://127.0.0.1:17841/v1'):
            raise RuntimeError('The web profile route changed; inspect it before use. No fallback was attempted.')
        if args.action == 'web':
            catalog = CORE / 'local-ops/web-models.json'
            if not catalog.is_file():
                raise RuntimeError('Run codex-web refresh-catalog once to install native tool metadata')
            profile['model_catalog_json'] = str(catalog)
        command = codex_command(profile, extra, args.action == 'web')
        os.execvp('codex', command)
    elif args.action == 'status':
        subprocess.run([runtime(), 'route', 'status'], check=True)
        print(json.dumps(health(), ensure_ascii=False, indent=2))
        journal = CORE / 'local-ops/desktop-integration.json'
        if journal.exists():
            settings = tomllib.loads((CODEX / 'config.toml').read_text())
            print(json.dumps({'desktop_config': {
                'phase': json.loads(journal.read_text())['phase'],
                'model': settings.get('model'), 'provider': settings.get('model_provider'),
                'catalog_configured': settings.get('model_catalog_json') == str(CORE / 'local-ops/web-models.json'),
                'catalog_matches_context_settings': catalog_is_current(),
                'scope': 'on-disk configuration; running desktop must reload after changes',
            }}, ensure_ascii=False, indent=2))
    else:
        command = ([args.action] if args.action == 'doctor'
                   else ['route', args.action] if args.action in ('connect', 'disconnect') else [])
        os.execv(runtime(), [runtime(), *command, *extra])


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f'codex-chatgpt-web: {error}', file=sys.stderr)
        sys.exit(1)
