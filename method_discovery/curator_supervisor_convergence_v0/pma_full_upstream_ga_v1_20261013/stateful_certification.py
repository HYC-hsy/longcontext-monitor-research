"""Single-B, same-run stateful-memory Harbor fake certification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .prepare_six_task_manifest import V3_SOURCE_FILES, _committed_source_sha
from .single_run_certification import HARBOR_COMMIT, vendor_identity


RUN = ('method_discovery/curator_supervisor_convergence_v0/'
       'pma_full_upstream_ga_v1_20261013/')
CORE = 'method_discovery/pma_stateful_memory_v1_20261021/'
SOURCE_FILES = tuple(dict.fromkeys(V3_SOURCE_FILES + (
    'GenericAgent-main/ga.py',
    'GenericAgent-main/stateful_memory_bridge.py',
    'long_context_bench/scripts/isolated_run_bundle.py',
    RUN + 'vendor/pma_89e5c0d/src/memory_agent/memory/bm25_search.py',
    *(CORE + name + '.py' for name in (
        '__init__', 'audit', 'budget', 'engine', 'ga_fake_provider', 'model_output',
        'projection', 'prompts', 'proposal', 'reminder', 'retrieval',
        'schema', 'source', 'store')),
    *(RUN + name for name in (
        'batch_controller.py', 'event_spool.py', 'single_run.py',
        'single_run_fixture.py', 'stateful_fixture_replies.json',
        'stateful_memory_worker.py', 'stateful_native_count.py',
        'stateful_role_provider.py', 'stateful_runtime_policy.py', 'stateful_certification.py',
        'collect_stateful_fixture.py')),
)))
REQUIRED = (
    'execution_identity.json', 'live_result.json', 'prepared.json',
    'agent_start_identity.json', 'agent_end_native.json',
    'stateful_task_terminal.json', 'writer_termination_check.json',
    'control_process_registry.json', 'native_test_execution.json',
    'native_reports_checked.json', 'native_evaluator_uploaded.json',
    'verification_released.json', 'fake_authorization_removed.json',
    'synthetic_test.sh', 'worker_ready.json', 'worker_exit.json',
    'host_events.jsonl', 'research_events.jsonl', 'task_requests.json',
)


def source_identity(checkout: Path) -> dict[str, str]:
    return {name: _committed_source_sha(checkout, name) for name in SOURCE_FILES}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_evidence(evidence: Path, *, require_committed: bool = True) -> dict:
    checkout = Path(__file__).resolve().parents[3]
    evidence = evidence.resolve(strict=True)
    if require_committed and not evidence.is_relative_to(checkout):
        raise RuntimeError('stateful certification must be committed in this repository')
    hashes = {}
    for name in REQUIRED:
        path = evidence / name
        if not path.is_file():
            raise RuntimeError('stateful certification missing: ' + name)
        if require_committed:
            hashes[name] = _committed_source_sha(checkout,
                path.relative_to(checkout).as_posix())
        else:
            hashes[name] = _hash(path)
    load = lambda name: json.loads((evidence / name).read_text(encoding='utf-8'))
    execution, result, terminal = (load(name) for name in (
        'execution_identity.json', 'live_result.json', 'stateful_task_terminal.json'))
    ready, exited, requests = (load(name) for name in (
        'worker_ready.json', 'worker_exit.json', 'task_requests.json'))
    started, ended = load('agent_start_identity.json'), load('agent_end_native.json')
    if (execution.get('source_files') != source_identity(checkout) or
            execution.get('vendor_files') != vendor_identity(checkout) or
            execution.get('harbor_commit') != HARBOR_COMMIT):
        raise RuntimeError('stateful certified source identity differs')
    run_id, task = result.get('run_id'), result.get('task')
    final = terminal.get('stateful_finalization') or {}
    events = [json.loads(line) for line in (evidence / 'host_events.jsonl').read_text(
        encoding='utf-8').splitlines()]
    kinds = [event.get('kind') for event in events]
    if (result.get('research_candidate') != 'pma_stateful_memory_v1' or
            result.get('zero_model_fixture_only') is not True or
            result.get('harbor_return_code') != 0 or
            result.get('worker_return_code') != 0 or
            result.get('cleanup_confirmed') is not True or
            result.get('native_result', {}).get('status') != 'native_recorded' or
            result.get('native_script_observed') is not True or
            result.get('native_reports_checked') is not True or
            terminal.get('run_id') != run_id or terminal.get('task_id') != task or
            terminal.get('result') != 'CURRENT_TASK_DONE' or
            final.get('closed') is not True or final.get('cycle_count', 0) < 2 or
            ready.get('run_id') != run_id or exited.get('run_id') != run_id or
            ready.get('mode') != 'fake-only' or
            started.get('container_id') != ended.get('container_id') or
            ended.get('writers_stopped') is not True or
            load('fake_authorization_removed.json').get('authorization_removed') is not True or
            kinds.count('initialize') != 1 or kinds.count('action_batch') != 1 or
            kinds.count('confirm_task') != 1 or kinds.count('finish') != 1 or
            requests.get('reminder_counts') != [0, 1] or
            requests.get('request_count') != 2):
        raise RuntimeError('stateful same-run fake chain incomplete')
    return {'run_id': run_id, 'task': task, 'source_files': len(SOURCE_FILES),
            'host_events': len(events), 'task_requests': requests['request_count'],
            'file_sha256': hashes}

