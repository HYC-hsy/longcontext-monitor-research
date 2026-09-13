import json
import pytest

from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.loop import MonitorLoopError
from test_monitor_pma_memory import Client, response, comparison, workspace


def test_maintenance_investigates_then_comparison_acts_without_third_reviewer(workspace):
    sent = []
    client = Client([
        response('file_read', path='task/original_task.txt'),
        response('memory_save_knowledge', content='Both forms required, neither yet tested.'),
        comparison('<maintenance_complete/>'),
        comparison('<context_for_action>Check both forms, not just one.</context_for_action>'),
        response('file_read', path='task/original_task.txt'),
        response('memory_update_status', content='Correction sent; uptake not yet established.'),
        response('wait', after_turns=1, mode='follow'),
    ])
    monitor = MonitorAgent(client, workspace)
    monitor.intervention_callback = sent.append
    action = monitor.review('initialization')
    assert action.kind == 'wait' and action.payload['mode'] == 'follow'
    assert sent == ['Check both forms, not just one.']
    assert len(client.inputs) == 7
    assert 'Both forms required' in client.inputs[3][0][1]['content']
    assert 'Correction sent' in monitor.pma_memory.memory.status
    assert client.history[0]['content'] == 'Previous investigation remains available.'
    assert not (workspace.private_root / 'task_model.md').exists()
    assert not (workspace.private_root / 'working.md').exists()


def test_bad_bank_operation_returns_error_then_model_can_repair(workspace):
    client = Client([response('memory_delete', memory_id='status'),
                     response('memory_update_status', content='Unverified.'),
                     comparison('<maintenance_complete/>'),
                     response('wait', after_turns=2, mode='patrol')])
    monitor = MonitorAgent(client, workspace)
    assert monitor.review('wake').kind == 'wait'
    receipt = client.inputs[1][0][0]['tool_results'][0]['content']
    assert 'ID not found' in receipt
    assert monitor.pma_memory.memory.status == 'Unverified.'


def test_maintenance_cannot_send_or_approve(workspace):
    client = Client([response('intervene', message='must not send'),
                     comparison('<maintenance_complete/>'),
                     response('wait', after_turns=1)])
    sent = []
    monitor = MonitorAgent(client, workspace)
    monitor.intervention_callback = sent.append
    monitor.review('wake')
    assert not sent
    names = {t['function']['name'] for t in client.inputs[0][1]}
    assert not names.intersection({'intervene', 'allow_complete', 'wait'})


def test_failure_does_not_continue_to_comparison(workspace):
    client = Client([RuntimeError('offline')])
    monitor = MonitorAgent(client, workspace)
    with pytest.raises(RuntimeError, match='offline'):
        monitor.review('wake')
    assert len(client.inputs) == 1


def test_second_phase_revision_survives_next_wake(workspace):
    client = Client([comparison('<maintenance_complete/>'),
                     response('memory_save_knowledge', content='New source contradicts old assumption.'),
                     response('wait', after_turns=1),
                     comparison('<maintenance_complete/>'), response('wait', after_turns=1)])
    monitor = MonitorAgent(client, workspace)
    monitor.review('first')
    monitor.review('second')
    assert 'New source contradicts' in client.inputs[3][0][1]['content']
    assert 'New source contradicts' in (workspace.private_root / 'pma_memory.json').read_text()


def test_budget_shared_across_both_phases(workspace):
    client = Client([comparison('<maintenance_complete/>'), comparison('<no_intervention/>')])
    monitor = MonitorAgent(client, workspace, max_review_turns=2)
    with pytest.raises(MonitorLoopError):
        monitor.review('wake')
    assert len(client.inputs) == 2


def test_old_task_model_manifest_fails_instead_of_silently_mixing(workspace):
    client = Client([])
    client.config = {'monitor_pma_memory': True, 'monitor_task_model': True}
    with pytest.raises(ValueError, match='retired'):
        MonitorAgent(client, workspace)


def test_real_provider_keeps_phase_tool_receipts_and_usage(workspace, monkeypatch):
    from monitor_agent_core.provider import MonitorProviderClient
    client = MonitorProviderClient('fixture', {'apikey': 'fake', 'apibase': 'http://invalid',
                                             'provider': 'anthropic', 'monitor_pma_memory': True})
    replies = iter([
        [{'type': 'tool_use', 'id': 'bank', 'name': 'memory_save_knowledge', 'input': {'content': 'Both forms'}}],
        [{'type': 'text', 'text': '<maintenance_complete/>'}],
        [{'type': 'tool_use', 'id': 'wait1', 'name': 'wait', 'input': {'after_turns': 1}}],
    ])
    monkeypatch.setattr(client, '_request', lambda tools: (next(replies), {'input_tokens': 7}))
    monitor = MonitorAgent(client, workspace)
    assert monitor.review('wake').kind == 'wait'
    history = json.dumps(client.export_history())
    assert 'Both forms' in history and 'tool_result' in history
    usages = [json.loads(x) for x in (workspace.private_root / 'audit/provider_usage.jsonl').read_text().splitlines()]
    assert [u['monitor_phase'] for u in usages] == ['pma_fused_maintenance'] * 2 + ['pma_fused_comparison']


def test_failure_in_comparison_preserves_committed_memory_and_raises(workspace):
    client = Client([response('memory_save_knowledge', content='Supported requirement'),
                     comparison('<maintenance_complete/>'), RuntimeError('comparison offline')])
    monitor = MonitorAgent(client, workspace)
    with pytest.raises(RuntimeError, match='comparison offline'):
        monitor.review('wake')
    assert 'Supported requirement' in (workspace.private_root / 'pma_memory.json').read_text()


def test_root_completion_and_task_isolation(workspace, tmp_path):
    from monitor_agent_core.workspace import MonitorWorkspace
    client = Client([comparison('<maintenance_complete/>'), response('allow_complete')])
    monitor = MonitorAgent(client, workspace)
    assert monitor.review('root completion', completion_pending=True).kind == 'allow_complete'
    other = MonitorWorkspace(workspace.evidence_root, tmp_path / 'other')
    assert MonitorAgent(Client([]), other).pma_memory.memory.status == ''


def test_bank_navigation_does_not_require_parallel_working_note(workspace):
    client = Client([comparison('<maintenance_complete/>'), response('wait', after_turns=1)])
    client.config = {'monitor_pma_memory': True, 'monitor_decision_context': True,
                     'monitor_active_working_context': True}
    monitor = MonitorAgent(client, workspace)
    monitor.review('wake')
    overview = (workspace.private_root / 'overview.md').read_text()
    assert 'Read and maintain monitor/working.md' not in overview
    assert 'monitor/pma_memory.json' in overview
    assert all('Keep monitor/working.md' not in str(x[0]) for x in client.inputs)
