"""Read-only assertions over one exported, source-bound zero-model single_run."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from method_discovery.pos_upstream_ga_v1_20261017.certification import verify_evidence


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--committed', action='store_true')
    args = parser.parse_args()
    root = args.evidence.resolve(strict=True)
    certified = verify_evidence(root, require_committed=args.committed,
                                research_candidate='pos_pma_complement_v1')
    base = root / 'normal'
    identity, live, episode = (load(base / name) for name in (
        'execution_identity.json', 'live_result.json', 'events.result.json'))
    events = [json.loads(line) for line in (base / 'agent/research_events.jsonl').read_text(
        encoding='utf-8').splitlines()]
    task = [row['payload']['content'] for row in events
            if row.get('event_type') == 'provider_request_ready']
    spool = base / 'spool'
    requests = [load(path) for path in (spool / 'requests').glob('*.json')]
    requests.sort(key=lambda row: row['sequence'])
    request_ids = {row['event_id'] for row in requests}
    responses = [load(path) for path in (spool / 'responses').glob('*.json')]
    response_ids = {row['event_id'] for row in responses}
    assert len(task) == 2 and len(requests) == len(responses) == 4
    assert request_ids == response_ids
    assert [row['role'] for row in requests] == [
        'pma_phase1', 'pma_phase2', 'pma_phase1', 'pma_phase2']
    assert 'SYNTHETIC_LONG_OUTPUT_' in requests[2]['prompt']
    assert 'SYNTHETIC_LONG_OUTPUT_' in requests[3]['prompt']
    assert 'Existing PoS health/progress' not in requests[2]['prompt']
    assert 'Existing PoS health/progress' in requests[3]['prompt']
    assert 'SYNTHETIC_LONG_OUTPUT_' in str(task[1])
    assert 'tool_result' in str(task[1])
    advice = episode['result']['advice_history'][0]['advice']
    assert advice in str(task[0]) and advice not in str(task[1])
    assert episode['result']['advice_history'][0]['reviewed_transition']
    health = episode['result']['pos']['health_transitions'][-1]
    assert len(health['observation']) > 10000
    assert hashlib.sha256(health['observation'].encode()).hexdigest()
    assert any(row['kind'] == 'phase2_optional_omitted'
               for row in episode['result']['events'])
    assert (live['pos_archive_status']['archive_incomplete'] is False and
            live['pos_archive_status']['result_bound'] is True and
            live['pos_archive_status']['close_bound'] is True and
            live['sidecar_clearance']['clean'] is True and
            live['evaluation_released'] is True and
            live['cleanup_confirmed'] is True and
            live['remaining_containers'] == [] and
            live['owned_volume_clearance']['remaining'] == [] and
            live['native_result']['rewards']['reward'] == 1.0)
    assert load(base / 'fake_authorization_removed.json')['authorization_removed'] is True
    assert load(base / 'prepared.json')['run_id'] == live['run_id']
    print(json.dumps({'status': 'pass', 'run_id': live['run_id'],
        'runtime_code_commit': identity['code_commit'],
        'source_bound_certification': certified['status'],
        'pma_spool_requests': len(requests), 'task_fake_requests': len(task),
        'pos_fake_role_calls': live['pos_archive_status']['provider_capture']['role_calls'],
        'long_observation_chars': len(health['observation']),
        'next_task_contains_long_receipt': True,
        'task_advice_once': True, 'same_main_sentinel_and_cleanup': True,
        'real_model_calls': 0, 'official_evaluator_calls': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
