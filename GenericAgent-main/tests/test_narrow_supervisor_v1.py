"""Zero-provider checks of the default-off narrow Supervisor route."""

import json

import pytest

from monitor_agent_core.agent import MONITOR_TOOLS, MonitorAgent
from monitor_agent_core.ase_v0 import SYSTEM_PROMPT as LEGACY_PROMPT
from monitor_agent_core.narrow_supervisor_v1 import METHOD_PROMPT
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.workspace import MonitorWorkspace
from monitor_agent_core.runtime import CompletionOutcome
from ga_monitor_adapter import GenericAgentMonitorAdapter


def monitor_at(tmp_path, narrow=True, **extra):
    evidence = tmp_path / 'evidence'
    evidence.mkdir(parents=True)
    (evidence / 'original_task.txt').write_text('Keep the public route working.', encoding='utf-8')
    (evidence / 'public_events.jsonl').write_text('', encoding='utf-8')
    task = tmp_path / 'task'
    task.mkdir()
    workspace = MonitorWorkspace(evidence, tmp_path / 'private', task_mounts={'workspace': task})
    config = {'apikey': 'offline', 'apibase': 'https://offline.invalid', 'model': 'offline',
              'max_retries': 0, 'monitor_adaptive_supervisory_environment': True,
              'monitor_narrow_supervisor_v1': narrow, **extra}
    client = MonitorProviderClient('anthropic', config)
    monitor = MonitorAgent(client, workspace)
    monitor.task_budget_state = lambda: (12, 300)
    return monitor, client, workspace


def responses(client, monkeypatch, actions):
    snapshots = []

    def once(tools):
        snapshots.append(client.assembled_request_snapshot(tools))
        name, arguments = actions[len(snapshots) - 1]
        return [{'type': 'tool_use', 'id': f'narrow-{len(snapshots)}',
                 'name': name, 'input': arguments}], {}

    monkeypatch.setattr(client, '_request_once', once)
    return snapshots


def handoff(monitor):
    value = {'generation': 1, 'request_id': 'completion-1', 'cursor': 1}
    (monitor.workspace.evidence_root / 'public_events.jsonl').write_text(
        json.dumps({'archive_sequence': 1, 'task_turn': 12, 'boundary': 'completion',
                    'text': 'Ready for review.', 'tool_calls': [], 'tool_results': []}) + '\n',
        encoding='utf-8')
    monitor.completion_state = lambda: value
    monitor._seen_completion = value
    return value


def test_default_off_and_strict_switches(tmp_path):
    old, _, _ = monitor_at(tmp_path / 'old', False)
    assert old.system_prompt == LEGACY_PROMPT
    assert len(MONITOR_TOOLS) == 7
    for index, switches in enumerate((
        {'monitor_contrastive_release_state': True},
        {'monitor_receding_horizon_release': True, 'monitor_contrastive_release_state': True},
        {'monitor_root_epistemic_reestimation': True, 'monitor_receding_horizon_release': True,
         'monitor_contrastive_release_state': True},
        {'monitor_history_projection': 'root_records_v1',
         'monitor_root_epistemic_reestimation': True, 'monitor_receding_horizon_release': True,
         'monitor_contrastive_release_state': True},
    )):
        with pytest.raises(ValueError):
            monitor_at(tmp_path / f'bad-{index}', True, **switches)


def test_reference_and_patrol_do_not_reconsider(tmp_path, monkeypatch):
    monitor, client, workspace = monitor_at(tmp_path)
    snapshots = responses(client, monkeypatch, [
        ('file_write', {'path': 'monitor/reference.md',
                        'content': 'The public route should remain available.'}),
        ('wait', {'after_turns': 1, 'mode': 'patrol'}),
        ('wait', {'after_turns': 1, 'mode': 'patrol'}),
    ])
    assert monitor.review('Initialization').kind == 'wait'
    assert workspace.resolve_read('monitor/reference.md').exists()
    assert monitor.review('Ordinary wake').kind == 'wait'
    assert len(snapshots) == 3
    assert all(METHOD_PROMPT in row['system'] for row in snapshots)
    assert 'whole-task correctness' in snapshots[-1]['system']


def test_root_allow_no_reconsideration_and_pending_wait_guard(tmp_path, monkeypatch):
    monitor, client, workspace = monitor_at(tmp_path)
    current = handoff(monitor)
    assert monitor.dispatch('wait', {'after_turns': 1}).data['status'] == 'handoff_pending'
    monitor._enter_root_frame(current)
    assert monitor.dispatch('allow_complete', {}).data['status'] == 'reference_invalid'
    workspace.write_text('monitor/reference.md', 'The public route should remain available.')
    snapshots = responses(client, monkeypatch, [('allow_complete', {})])
    action = monitor.review('Wake', completion_pending=True, root_handoff=current)
    assert action.kind == 'allow_complete'
    assert len(snapshots) == 1
    assert METHOD_PROMPT in snapshots[0]['system']
    assert 'certify whole-task correctness' in snapshots[0]['system']


def test_intervention_uses_existing_receipt_and_fresh_feedback(tmp_path, monkeypatch):
    monitor, client, workspace = monitor_at(tmp_path)
    workspace.write_text('monitor/reference.md', 'The public route should remain available.')
    receipts = []
    monitor.intervention_callback = lambda message: (
        receipts.append(message) or {'submission_id': 'sent-1', 'delivered': True})
    responses(client, monkeypatch, [('intervene', {'message': 'Inspect the route behavior.'})])
    assert monitor.review('Local wake').kind == 'local_intervened'
    assert receipts == ['Inspect the route behavior.']
    assert monitor.control_echo.active is not None


def test_accepted_completion_keeps_no_objection_semantics():
    adapter = GenericAgentMonitorAdapter.__new__(GenericAgentMonitorAdapter)
    adapter.runtime = type('Runtime', (), {'request_completion': lambda self, _: CompletionOutcome(
        True, reason='no_supervisory_objection')})()
    decision = adapter.review_completion(None, 1)
    assert decision.decision == 'ALLOW_COMPLETE'
    assert decision.reason_codes == ('MONITOR_ALLOWED', 'NO_SUPERVISORY_OBJECTION')
    adapter.runtime = type('Runtime', (), {'request_completion': lambda self, _: CompletionOutcome(
        True, reason='monitor_allowed')})()
    assert adapter.review_completion(None, 1).reason_codes == ('MONITOR_ALLOWED',)
