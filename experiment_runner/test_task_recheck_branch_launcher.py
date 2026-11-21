"""Zero-model host-side validation of the private Task branch launcher."""

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from task_recheck_branch_launcher import run_one


def test_dry_run_binds_checkpoint_source_and_bank(tmp_path):
    run = tmp_path / 'run-a'
    source = run / 'bundle/source'
    gateway = run / 'bundle/gateway'
    agent = run / 'jobs/agent'
    for directory in (source, gateway, agent):
        directory.mkdir(parents=True)
    (source / 'task_recheck_branch_entry.py').write_text('fixture', encoding='utf-8')
    (gateway / 'config.json').write_text('{}', encoding='utf-8')
    (gateway / 'transport.py').write_text('fixture', encoding='utf-8')
    (run / 'bundle/isolation.compose.json').write_text(json.dumps({
        'services': {'model-gateway': {'image': 'debian:bookworm-slim',
        'entrypoint': ['/opt/m4-runtime/ga-env/bin/python',
                       '/gateway/transport.py', 'gateway', '--config',
                       '/gateway/config.json']}}}), encoding='utf-8')
    state = {'schema': 'task-recheck-actor-state-v1', 'run_id': 'run-a',
             'actor_attempt': 9, 'backend_history': [],
             'task_environment': {'GA_TASK_DEADLINE_EPOCH': 'uncapped'},
             'pre_reminder_messages': [{'role': 'user', 'content': 'Continue'}],
             'messages': [{'role': 'user', 'content': 'Continue'}],
             'tools_schema': [], 'pending_reminder': None}
    (agent / 'task_recheck_before_actor_0009.json').write_text(
        json.dumps(state), encoding='utf-8')
    capture = tmp_path / 'private_capture/run-a/after-step-0008'
    capture.mkdir(parents=True)
    bank = b'{"entries":[]}'
    (capture / 'knowledge.json').write_bytes(bank)
    (capture / 'capture.json').write_text(json.dumps({
        'status': 'captured', 'run_id': 'run-a', 'actor_attempt': 9,
        'snapshot_image_id': 'sha256:fixture',
        'original_network_mode': 'none',
        'knowledge_sha256': hashlib.sha256(bank).hexdigest(),
        'original_mounts': [{'Destination': '/opt/m4-runtime',
            'Type': 'bind', 'RW': False, 'Source': str(tmp_path)}]}), encoding='utf-8')
    with patch('task_recheck_branch_launcher._docker',
               return_value=json.dumps([{'Id': 'sha256:fixture'}])):
        result = run_one(run, capture, tmp_path / 'branches', 'targeted', 1,
                         dry_run=True)
    assert result['status'] == 'validated_no_model'
    assert result['checkpoint_actor_attempt'] == 9
    assert result['bank_sha256'] == hashlib.sha256(bank).hexdigest()
    assert not (tmp_path / 'branches').exists()
