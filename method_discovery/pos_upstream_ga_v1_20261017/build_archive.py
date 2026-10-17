"""Mechanical public source/hash and fake-test archive builder; no live calls."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
COMMIT = '6818cfa6434dbc91fcf67f0b3eb12a91db47433f'
VENDOR = HERE / 'vendor'
UPSTREAM = HERE / 'upstream'
RAW = HERE / 'raw'


def git(*args):
    return subprocess.run(['git', '-C', str(UPSTREAM), *args],
                          capture_output=True, check=True).stdout


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(value)


def main():
    if git('rev-parse', 'HEAD').decode().strip() != COMMIT:
        raise RuntimeError('upstream clone moved')
    RAW.mkdir(exist_ok=True)
    files = []
    for path in sorted(VENDOR.rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts:
            continue
        relative = path.relative_to(VENDOR).as_posix()
        raw = path.read_bytes()
        blob = git('rev-parse', f'{COMMIT}:{relative}').decode().strip()
        expected = git('cat-file', 'blob', blob)
        if raw != expected:
            raise RuntimeError('vendor bytes differ: ' + relative)
        files.append({'path': 'vendor/' + relative, 'bytes': len(raw),
                      'sha256': sha(raw), 'git_blob': blob,
                      'match_fixed_upstream_blob': True})
    write(RAW / 'UPSTREAM_FILE_HASHES.json', json.dumps({
        'repository': 'https://github.com/luoyu100/PoS', 'commit': COMMIT,
        'files': files}, ensure_ascii=False, indent=2) + '\n')
    tests = [
        ('core', [r'C:\Python312\python.exe', '-B', str(HERE / 'test_offline.py')]),
        ('ga_seam', [sys.executable, '-B', str(HERE / 'test_ga_seam.py')]),
        ('legacy_ga_pma', [sys.executable, '-B', '-m', 'unittest',
          'method_discovery.curator_supervisor_convergence_v0.'
          'pma_full_upstream_ga_v1_20261013.test_synthetic_compat', '-v']),
    ]
    outcomes = []
    for name, command in tests:
        env = None
        if name == 'legacy_ga_pma':
            import os
            env = dict(os.environ)
            env['PYTHONPATH'] = os.pathsep.join((str(REPO / 'GenericAgent-main'),
                                                str(REPO)))
        result = subprocess.run(command, cwd=REPO, capture_output=True,
                                text=True, encoding='utf-8', timeout=60, env=env)
        write(RAW / (name + '.stdout.txt'), result.stdout)
        write(RAW / (name + '.stderr.txt'), result.stderr)
        outcomes.append({'test': name, 'exit_code': result.returncode,
                         'stdout': f'raw/{name}.stdout.txt',
                         'stderr': f'raw/{name}.stderr.txt'})
    write(RAW / 'TEST_RESULTS.json', json.dumps(outcomes, indent=2) + '\n')
    if any(row['exit_code'] for row in outcomes):
        raise RuntimeError('offline tests failed; raw outputs retained')
    # One permanent finite fixture transcript through the same isolated worker.
    sys.path.insert(0, str(HERE))
    from test_offline import replies
    fixed = RAW / 'fixture_replies.json'
    write(fixed, json.dumps(replies(), ensure_ascii=False, indent=2) + '\n')
    commands = [
        {'kind': 'reset', 'case_id': 'public/synthetic', 'task': 'Clean mug 1.',
         'observation': 'Mug dirty.', 'actions': []},
        {'kind': 'decision_view', 'observation': 'Mug dirty.', 'actions': []},
        {'kind': 'update', 'thought': 'Inspect.', 'action_batch': [
            {'id': 'c1', 'name': 'inspect', 'arguments': {}, 'order': 0,
             'status': 'executed', 'result': 'Still dirty.'}],
         'observation': 'Still dirty.'},
        {'kind': 'finish', 'reason': 'CURRENT_TASK_DONE'},
    ]
    input_text = ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in commands)
    write(RAW / 'worker_ipc_requests.jsonl', input_text)
    result = subprocess.run([sys.executable, '-B', '-u', str(HERE / 'worker.py'),
        '--vendor', str(VENDOR), '--episode-module', str(HERE / 'episode.py'),
        '--archive', str(RAW / 'worker_events.jsonl'), '--mode', 'fake',
        '--fake-replies', str(fixed)], input=input_text, text=True,
        capture_output=True, encoding='utf-8', timeout=20)
    write(RAW / 'worker_ipc_responses.jsonl', result.stdout)
    write(RAW / 'worker.stderr.txt', result.stderr)
    if result.returncode or len(result.stdout.splitlines()) != len(commands):
        raise RuntimeError('public fake worker transcript failed')
    sys.path.insert(0, str(REPO / 'GenericAgent-main'))
    from llmcore import NativeClaudeSession, NativeToolClient
    backend = NativeClaudeSession({'apibase': 'https://synthetic.invalid',
        'apikey': 'SYNTHETIC-NO-ACCESS', 'model': 'claude-opus-4-8',
        'max_tokens': 64, 'max_retries': 0})
    backend.history = [{'role': 'user', 'content': [{'type': 'text',
        'text': 'OLD_BACKEND_HISTORY_CANARY'}]}]
    payload = []
    def fake_raw(messages):
        payload.append({'messages': messages, 'system': backend.system,
                        'tools': backend.tools})
        if False:
            yield None
        return [{'type': 'text', 'text': 'done'}]
    backend.raw_ask = fake_raw
    client = NativeToolClient(backend)
    client._pending_tool_ids = ['OLD_TOOL_ID_CANARY']
    gen = client.chat(messages=[{'role': 'user', 'content': 'OLD_SUMMARY_CANARY'}],
        tools=[{'type': 'function', 'function': {'name': 'inspect',
               'parameters': {'type': 'object'}}}],
        request_view={'system': 'RUN_CONSTRAINT',
                      'user': 'ORIGINAL_TASK CURRENT_OBSERVATION ACTIVE_GAP'})
    try:
        while True:
            next(gen)
    except StopIteration:
        pass
    visible = json.dumps(payload, ensure_ascii=False, indent=2)
    if any(x in visible for x in ('OLD_BACKEND_HISTORY_CANARY',
                                  'OLD_TOOL_ID_CANARY', 'OLD_SUMMARY_CANARY')):
        raise RuntimeError('old history reached final Task payload')
    write(RAW / 'final_task_payload.json', visible + '\n')
    diff = subprocess.run(['git', 'diff', '--cached', '--binary', '--',
        'GenericAgent-main', 'long_context_bench/scripts/isolated_run_bundle.py',
        'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013',
        'method_discovery/pos_upstream_ga_v1_20261017',
        ':!method_discovery/pos_upstream_ga_v1_20261017/vendor',
        ':!method_discovery/pos_upstream_ga_v1_20261017/raw',
        ':!method_discovery/pos_upstream_ga_v1_20261017/plan_four'],
        cwd=REPO, capture_output=True, check=True).stdout
    (RAW / 'scoped_diff.patch').write_bytes(diff)
    public = [path for path in HERE.rglob('*') if path.is_file() and
              'upstream' not in path.parts and '__pycache__' not in path.parts and
              path.name != 'PUBLIC_FILE_SHA256.json']
    rows = [{'path': path.relative_to(HERE).as_posix(), 'bytes': path.stat().st_size,
             'sha256': sha(path.read_bytes())} for path in sorted(public)]
    write(HERE / 'PUBLIC_FILE_SHA256.json', json.dumps({
        'scope': 'public PoS handoff files except this generated manifest',
        'files': rows}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'upstream_files_verified': len(files),
                      'public_files_hashed': len(rows), 'tests': outcomes}, indent=2))


if __name__ == '__main__':
    main()
