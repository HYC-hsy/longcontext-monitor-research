"""Check committed, redacted native-SHARED synthetic evidence; never authorize a run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HARBOR_COMMIT = '459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc'
UPSTREAM = '6818cfa6434dbc91fcf67f0b3eb12a91db47433f'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_evidence(directory: Path, *, require_committed: bool = True,
                    research_candidate: str = 'PoS') -> dict:
    base = directory.resolve(strict=True)
    index_path = base / 'FILE_HASHES.json'
    index = json.loads(index_path.read_text(encoding='utf-8'))
    if index.get('schema') != 'pos-ga-native-shared-evidence-v1':
        raise RuntimeError('PoS evidence index schema differs')
    files = index.get('files')
    if not isinstance(files, list) or not files:
        raise RuntimeError('PoS evidence files missing')
    names = set()
    for row in files:
        name = row['path']
        path = (base / name).resolve(strict=True)
        if (name in names or not path.is_relative_to(base) or
                path.stat().st_size != row['bytes'] or sha(path) != row['sha256']):
            raise RuntimeError('PoS evidence member changed: ' + name)
        names.add(name)
        if require_committed:
            relative = path.relative_to(ROOT).as_posix()
            blob = subprocess.run(['git', 'show', 'HEAD:' + relative], cwd=ROOT,
                                  capture_output=True, check=True).stdout
            if hashlib.sha256(blob).hexdigest() != row['sha256']:
                raise RuntimeError('PoS evidence differs from committed Git blob: ' + name)
    if require_committed:
        relative = index_path.relative_to(ROOT).as_posix()
        blob = subprocess.run(['git', 'show', 'HEAD:' + relative], cwd=ROOT,
                              capture_output=True, check=True).stdout
        if hashlib.sha256(blob).hexdigest() != sha(index_path):
            raise RuntimeError('PoS index differs from committed Git blob')
    required = {'normal/execution_identity.json', 'normal/live_result.json',
                'normal/pos_archive_status.json', 'normal/events.result.json',
                'normal/events.close.json', 'normal/native_test_execution.json',
                'normal/writer_termination_check.json',
                'normal/verification_released.json',
                'normal/fake_requests/0001.json', 'normal/fake_requests/0002.json',
                'normal/verifier/test-stdout.txt', 'normal/verifier/reward.txt',
                'normal/synthetic_test.sh'}
    if not required <= names:
        raise RuntimeError('PoS evidence missing required native receipts')
    load = lambda name: json.loads((base / 'normal' / name).read_text(encoding='utf-8'))
    identity, result, status = (load(name) for name in
        ('execution_identity.json', 'live_result.json', 'pos_archive_status.json'))
    worker, closed, test, writers = (load(name) for name in
        ('events.result.json', 'events.close.json', 'native_test_execution.json',
         'writer_termination_check.json'))
    from .single_manifest import source_hashes, vendor_hashes
    from .single_manifest import SOURCE_FILES
    committed_sources = {name: hashlib.sha256(subprocess.run(
        ['git', 'cat-file', 'blob', f"{identity.get('code_commit')}:{name}"],
        cwd=ROOT, capture_output=True, check=True).stdout).hexdigest()
        for name in SOURCE_FILES}
    prepared = load('prepared.json')
    bundled = prepared.get('executed_pos_source_sha256')
    if research_candidate not in {'PoS', 'PoS-citation-fixed',
                                  'pos_pma_complement_v1'}:
        raise RuntimeError('PoS certification method identity invalid')
    executed_names = ('agent_loop.py', 'agentmain.py', 'ga.py', 'llmcore.py',
                      'research_runtime.py', 'pos_bridge.py',
                      'pos_runtime/worker.py', 'pos_runtime/episode.py',
                      'pos_runtime/citation_fix.py',
                      'pos_runtime/candidate.py',
                      'pos_runtime/memory_adapter.py',
                      'pos_runtime/event_spool.py')
    def source_name(name):
        if not name.startswith('pos_runtime/'):
            return 'GenericAgent-main/' + name
        leaf = Path(name).name
        if leaf in {'candidate.py', 'memory_adapter.py'}:
            directory = 'pos_pma_complement_v1_20261019'
        elif leaf == 'event_spool.py':
            directory = ('curator_supervisor_convergence_v0/'
                         'pma_full_upstream_ga_v1_20261013')
        else:
            directory = 'pos_upstream_ga_v1_20261017'
        return 'method_discovery/' + directory + '/' + leaf
    expected_executed = {name: identity['source_files'][
        source_name(name)]
        for name in executed_names}
    script = (base / 'normal/synthetic_test.sh').read_text(encoding='utf-8')
    candidate_profile = research_candidate == 'pos_pma_complement_v1'
    provider = status.get('provider_capture', {})
    if candidate_profile:
        host_ready = load('host_private/worker_ready.json')
        requests = {Path(name).name for name in names
                    if name.startswith('normal/spool/requests/')}
        responses = {Path(name).name for name in names
                     if name.startswith('normal/spool/responses/')}
        if (result.get('candidate_profile_fixture_only') is not True or
                result.get('fake_host_calls') != 4 or
                host_ready.get('fake_memory') is not False or
                host_ready.get('research_candidate') != research_candidate or
                host_ready.get('run_id') != result.get('run_id') or
                host_ready.get('task_id') != result.get('task') or
                len(requests) != 4 or requests != responses or
                'normal/host_private/fake_host_calls.jsonl' not in names or
                provider.get('mode') != 'profile' or
                provider.get('capture_complete') is not True or
                provider.get('role_calls') != 5 or
                provider.get('observable_attempts') != 5 or
                provider.get('observable_returns') != 5 or
                result.get('fake_provider_captures') != 7):
            raise RuntimeError('candidate profile fixture capture incomplete')
    if (identity.get('git_blob_source_files') != committed_sources or
            bundled != expected_executed or
            identity.get('harbor_commit') != HARBOR_COMMIT or
            identity.get('upstream_commit') != UPSTREAM or
            identity.get('source_files') != source_hashes() or
            identity.get('vendor_files') != vendor_hashes() or
            result.get('condition') != 'P' or
            result.get('research_candidate') != research_candidate or
            result.get('zero_model_fixture_only') is not True or
            result.get('harbor_return_code') != 0 or
            result.get('cleanup_confirmed') is not True or
            result.get('evaluation_released') is not True or
            (not candidate_profile and result.get('fake_provider_captures') != 2) or
            result.get('native_result', {}).get('status') != 'native_recorded' or
            result.get('native_result', {}).get('rewards', {}).get('reward') != 1 or
            status.get('archive_incomplete') is not False or
            status.get('result_bound') is not True or
            status.get('close_bound') is not True or
            worker.get('status') != 'completed' or
            (worker.get('result', {}).get('pos', {}).get('success_known')
             if research_candidate == 'pos_pma_complement_v1' else
             worker.get('result', {}).get('success_known')) is not False or
            closed.get('status') != 'graceful_exit' or
            closed.get('worker_return_code') != 0 or
            test.get('observed') is not True or
            writers.get('control_remaining') != [] or
            not writers.get('task_owned_pids_preserved') or
            'pos-fixture-marker.txt' not in script or
            'http://127.0.0.1:19173/' not in script):
        raise RuntimeError('PoS native-SHARED lifecycle evidence incomplete')
    return {'status': 'pass', 'run_id': result['run_id'],
            'research_candidate': research_candidate,
            'synthetic_task': result['task'], 'file_count': len(files),
            'real_model_calls': 0, 'official_evaluator_calls': 0}
