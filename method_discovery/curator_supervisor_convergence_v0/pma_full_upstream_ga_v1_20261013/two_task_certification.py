"""Check the archived real-launcher/Docker fixture before V3 live authorization."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_evidence(evidence: Path, checkout: Path, slots: list[dict]) -> dict:
    evidence = evidence.resolve(strict=True)
    checkout = checkout.resolve(strict=True)
    index = json.loads((evidence / 'FILE_HASHES.json').read_text(encoding='utf-8'))
    if index.get('schema') != 'pma-ga-two-task-zero-model-evidence-v1':
        raise RuntimeError('V3 evidence index schema mismatch')
    files = index.get('files')
    if not isinstance(files, list) or not files:
        raise RuntimeError('V3 evidence inventory absent')
    paths = set()
    for row in files:
        path = (checkout / row['path']).resolve(strict=True)
        if (path in paths or not path.is_relative_to(evidence) or
                path.is_symlink() or _sha(path) != row['sha256'] or
                path.stat().st_size != row['bytes']):
            raise RuntimeError('V3 raw evidence differs from hashed inventory')
        paths.add(path)
    def read(relative: str) -> dict:
        path = evidence / relative
        if path.resolve(strict=True) not in paths:
            raise RuntimeError('V3 required raw record not indexed')
        return json.loads(path.read_text(encoding='utf-8'))
    fixture_manifest = read('manifest.json')
    batch = read('batch.json')
    removed = read('fake_authorization_removed.json')
    if (fixture_manifest.get('planned_order') != slots or
            fixture_manifest.get('zero_model_fixture_only') is not True or
            removed.get('authorization_removed') is not True or
            batch.get('not_started') != [] or batch.get('stop_reason') is not None or
            len(batch.get('arms', [])) != len(slots)):
        raise RuntimeError('V3 fixture plan, completion or fake authorization invalid')
    for number, arm in enumerate(batch['arms'], 1):
        prefix = f'run-{number}/'
        status = read(prefix + 'archive/live_result.json')
        started = read(prefix + 'archive/agent_start_identity.json')
        ended = read(prefix + 'archive/agent_end_native.json')
        upload = read(prefix + 'archive/native_evaluator_uploaded.json')
        executions = read(prefix + 'archive/native_test_execution.json')
        if (arm.get('order') != number or arm.get('disposition') != 'completed' or
                arm.get('status') != status or
                status.get('task') != slots[number - 1]['task'] or
                status.get('condition') != slots[number - 1]['condition'] or
                status.get('zero_model_fixture_only') is not True or
                status.get('cleanup_confirmed') is not True or
                status.get('native_result', {}).get('rewards') != {'reward': 1.0} or
                status.get('native_reports_checked') is not True or
                status.get('native_script_observed') is not True or
                started.get('hidden_tests_absent') is not True or
                started.get('provider_key_env_absent') is not True or
                started.get('network_mode') == 'none' or
                ended.get('writers_stopped') is not True or
                ended.get('sidecar_clean') is not True or
                upload.get('source_commit') != 'synthetic_no_official_evaluator' or
                set(upload.get('files', {})) != {'tests/test.sh'} or
                len(executions.get('executions', [])) != 1):
            raise RuntimeError(f'V3 slot {number} lifecycle or synthetic evaluation incomplete')
        captures = [path for path in paths if path.parent == evidence /
                    f'run-{number}/archive/fake_provider_requests' and
                    path.suffix == '.json']
        if len(captures) != status.get('fake_provider_captures') or len(captures) < 2:
            raise RuntimeError(f'V3 slot {number} fake send captures incomplete')
        task_traces = [path for path in paths if path.name == 'research_events.jsonl'
                       and f'run-{number}/jobs/' in path.as_posix()]
        if len(task_traces) != 1:
            raise RuntimeError('V3 Task provider event stream absent')
        task_events = [json.loads(line) for line in task_traces[0].read_text(
            encoding='utf-8').splitlines()]
        if (not any(row['event_type'] == 'provider_request_ready' and
                    row['payload'].get('content_availability') == 'complete'
                    for row in task_events) or
                not any(row['event_type'] == 'provider_response_content' and
                        row['payload'].get('parsed_visible_blocks')
                        for row in task_events)):
            raise RuntimeError('V3 provider request or parsed response text not captured')
        if slots[number - 1]['condition'] == 'B':
            memory_path = evidence / prefix / 'host_private/archive/memory_payload.jsonl'
            events_path = evidence / prefix / 'host_private/archive/events.jsonl'
            if memory_path not in paths or events_path not in paths:
                raise RuntimeError('V3 PMA two-stage raw record absent')
            phases = [json.loads(line)['phase'] for line in memory_path.read_text(
                encoding='utf-8').splitlines()]
            events = [json.loads(line) for line in events_path.read_text(
                encoding='utf-8').splitlines()]
            second = read(prefix + 'archive/fake_provider_requests/0002.json')
            if (not {'bank_management', 'context_decision'} <= set(phases) or
                    not any(row.get('result', {}).get('reminder') for row in events) or
                    'Offline PMA reminder.' not in json.dumps(second, ensure_ascii=False)):
                raise RuntimeError('V3 PMA reminder not visible in second GA request')
        elif (evidence / prefix / 'host_private/archive/memory_payload.jsonl') in paths:
            raise RuntimeError('V3 GA-only slot made PMA calls')
    for first, second in ((1, 2), (4, 3)):
        a = read(f'run-{first}/archive/fake_provider_requests/0001.json')['body']
        b = read(f'run-{second}/archive/fake_provider_requests/0001.json')['body']
        a.pop('metadata', None)
        b.pop('metadata', None)
        if a != b:
            raise RuntimeError('V3 paired first GA request differs beyond metadata')
    return {'index_sha256': _sha(evidence / 'FILE_HASHES.json'),
            'archive_sha256': _sha(evidence / 'raw_trajectories.zip'),
            'batch_sha256': _sha(evidence / 'batch.json'),
            'files': len(files)}
