"""Generate a new immutable fake-only audit set; never rewrite the v1 archive."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RAW = HERE / 'raw_v4'
BASE = 'fc0a1e5a4febd8166d60ab538152d964f4d19e08'
UPSTREAM = '6818cfa6434dbc91fcf67f0b3eb12a91db47433f'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def new_text(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as out:
        out.write(value)


def command(name, argv, *, env=None):
    run = subprocess.run(argv, cwd=REPO, capture_output=True, text=True,
                         encoding='utf-8', errors='replace', timeout=90, env=env)
    new_text(RAW / (name + '.stdout.txt'), run.stdout)
    new_text(RAW / (name + '.stderr.txt'), run.stderr)
    return {'name': name, 'exit_code': run.returncode,
            'stdout': 'raw_v4/' + name + '.stdout.txt',
            'stderr': 'raw_v4/' + name + '.stderr.txt'}


def make_loop_traces():
    sys.path.insert(0, str(HERE))
    sys.path.insert(0, str(REPO / 'GenericAgent-main'))
    from agent_loop import agent_runner_loop, exhaust
    from test_ga_seam import Handler, Client, response
    from test_offline import replies
    from types import SimpleNamespace

    for label, failed in (('normal', False), ('terminal_pos_failure', True)):
        fake = RAW / (label + '_replies.json')
        fixture = replies()
        if failed:
            fixture['belief'] = fixture['belief'][:2]
        new_text(fake, json.dumps(fixture, ensure_ascii=False, indent=2) + '\n')
        archive = RAW / (label + '_events.jsonl')
        env = {'GA_POS_ENABLED': '1', 'GA_PMA_ENABLED': '0',
               'GA_PMA_UPSTREAM_ENABLED': '0', 'GA_MONITOR_ENABLED': '0',
               'GA_M0_MONITOR_ENABLED': '0', 'GA_POS_TRANSPORT': 'fake',
               'GA_POS_WORKER_SCRIPT': str(HERE / 'worker.py'),
               'GA_POS_VENDOR_ROOT': str(HERE / 'vendor'),
               'GA_POS_EPISODE_MODULE': str(HERE / 'episode.py'),
               'GA_POS_ARCHIVE': str(archive), 'GA_POS_FAKE_REPLIES': str(fake),
               'GA_BENCH_TASK_ID': 'synthetic/mug'}
        if failed:
            calls = [SimpleNamespace(id='stop-1', function=SimpleNamespace(
                name='stop', arguments='{}'))]
            scripted = [response('', calls)]
        else:
            calls = [SimpleNamespace(id='probe-1', function=SimpleNamespace(
                name='probe', arguments='{}'))]
            scripted = [response('Inspect the mug.', calls), response('Done.')]
        client = Client(scripted)
        with patch.dict(os.environ, env):
            outcome = exhaust(agent_runner_loop(client, 'Synthetic run constraint.',
                'Clean mug 1.', Handler(), [{'type': 'function', 'function':
                {'name': 'stop' if failed else 'probe',
                 'parameters': {'type': 'object'}}}],
                max_turns=len(scripted), verbose=False))
        if outcome.get('result') != 'CURRENT_TASK_DONE':
            raise RuntimeError(label + ': host terminal differed')
        new_text(RAW / (label + '_task_views.json'),
                 json.dumps(client.views, ensure_ascii=False, indent=2) + '\n')
        saved = json.loads(archive.with_suffix('.result.json').read_text(encoding='utf-8'))
        if saved['status'] != ('partial' if failed else 'completed'):
            raise RuntimeError(label + ': PoS saved status differed')


def main():
    if RAW.exists():
        raise FileExistsError('v2 archive already exists; preserve it')
    RAW.mkdir()
    upstream_root = HERE / 'upstream'
    head = subprocess.run(['git', '-C', str(upstream_root), 'rev-parse', 'HEAD'],
                          capture_output=True, text=True, check=True).stdout.strip()
    if head != UPSTREAM:
        raise RuntimeError('upstream checkout moved')
    vendor_rows = []
    for path in sorted((HERE / 'vendor').rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts:
            continue
        relative = path.relative_to(HERE / 'vendor').as_posix()
        blob = subprocess.run(['git', '-C', str(upstream_root), 'rev-parse',
            UPSTREAM + ':' + relative], capture_output=True, text=True,
            check=True).stdout.strip()
        original = subprocess.run(['git', '-C', str(upstream_root), 'cat-file',
            'blob', blob], capture_output=True, check=True).stdout
        if original != path.read_bytes():
            raise RuntimeError('vendor mismatch: ' + relative)
        vendor_rows.append({'path': 'vendor/' + relative, 'git_blob': blob,
                            'sha256': digest(path), 'bytes': path.stat().st_size,
                            'matches_upstream': True})
    new_text(RAW / 'UPSTREAM_FILE_HASHES.json', json.dumps({
        'upstream_commit': UPSTREAM, 'files': vendor_rows}, indent=2) + '\n')

    env = dict(os.environ)
    env['POS_AUDIT_HTTP_CAPTURE'] = str(RAW / 'http_boundary_payload.json')
    tests = [command('core', [sys.executable, '-B', str(HERE / 'test_offline.py')]),
             command('ga_seam', [sys.executable, '-B', str(HERE / 'test_ga_seam.py')],
                     env=env)]
    legacy = dict(os.environ)
    legacy['PYTHONPATH'] = os.pathsep.join((str(REPO / 'GenericAgent-main'), str(REPO)))
    tests.append(command('legacy_ga_pma', [sys.executable, '-B', '-m', 'unittest',
        'method_discovery.curator_supervisor_convergence_v0.'
        'pma_full_upstream_ga_v1_20261013.test_synthetic_compat', '-v'],
        env=legacy))
    new_text(RAW / 'TEST_RESULTS.json', json.dumps(tests, indent=2) + '\n')
    if any(item['exit_code'] for item in tests):
        raise RuntimeError('offline test failed; original test outputs retained')
    make_loop_traces()
    diff = subprocess.run(['git', 'diff', '--cached', BASE, '--',
        'GenericAgent-main/agent_loop.py', 'GenericAgent-main/ga.py',
        'GenericAgent-main/llmcore.py', 'GenericAgent-main/pos_bridge.py',
        'method_discovery/pos_upstream_ga_v1_20261017',
        'method_discovery/curator_supervisor_convergence_v0/'
        'pma_full_upstream_ga_v1_20261013/harbor_adapter.py',
        'method_discovery/curator_supervisor_convergence_v0/'
        'pma_full_upstream_ga_v1_20261013/offline_launcher.py',
        ':!method_discovery/pos_upstream_ga_v1_20261017/vendor',
        ':!method_discovery/pos_upstream_ga_v1_20261017/raw',
        ':!method_discovery/pos_upstream_ga_v1_20261017/raw_v2',
        ':!method_discovery/pos_upstream_ga_v1_20261017/raw_v3',
        ':!method_discovery/pos_upstream_ga_v1_20261017/raw_v4',
        ':!method_discovery/pos_upstream_ga_v1_20261017/AUDIT_V2.txt',
        ':!method_discovery/pos_upstream_ga_v1_20261017/CODE_FILE_SHA256.txt'],
        cwd=REPO, capture_output=True, check=True).stdout
    (RAW / 'scoped_diff.patch').write_bytes(diff)
    rows = []
    for directory in (HERE / 'raw_v2', HERE / 'raw_v3', RAW):
        for path in sorted(directory.rglob('*')):
            if path.is_file() and path.name != 'FILE_SHA256.json':
                rows.append({'path': path.relative_to(HERE).as_posix(),
                             'bytes': path.stat().st_size, 'sha256': digest(path)})
    new_text(RAW / 'FILE_SHA256.json', json.dumps({'files': rows}, indent=2) + '\n')
    context = (HERE / 'AUDIT_V2_CONTEXT.txt').read_text(encoding='utf-8')
    audit = (context + '\n\n=== COMPLETE SCOPED DIFF ===\n' +
             diff.decode('utf-8') + '\n=== TEST RESULTS ===\n' +
             json.dumps(tests, indent=2) + '\n=== RAW FILE HASHES ===\n' +
             (RAW / 'FILE_SHA256.json').read_text(encoding='utf-8'))
    new_text(HERE / 'AUDIT_V3.txt', audit)
    print(json.dumps({'vendor_files_checked': len(vendor_rows),
                      'raw_files_hashed': len(rows), 'tests': tests,
                      'audit_sha256': digest(HERE / 'AUDIT_V3.txt')}, indent=2))


if __name__ == '__main__':
    main()
