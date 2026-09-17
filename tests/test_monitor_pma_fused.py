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
        response('intervene', message='Check both forms, not just one.'),
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
                     response('wait', after_turns=1)])
    sent = []
    monitor = MonitorAgent(client, workspace)
    monitor.intervention_callback = sent.append
    monitor.review('wake')
    assert not sent
    names = {t['function']['name'] for t in client.inputs[0][1]}
    assert {'intervene', 'allow_complete', 'wait'} <= names
    assert 'must not send' in client.inputs[1][0][1]['content']
    assert 'NOT been executed' in client.inputs[1][0][1]['content']


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


def test_comparison_has_one_output_protocol_and_wait_returns_immediately(workspace):
    client = Client([comparison('<maintenance_complete/>'), response('wait', after_turns=4, mode='patrol')])
    monitor = MonitorAgent(client, workspace)
    action = monitor.review('wake')
    assert action.payload == {'after_turns': 4, 'mode': 'patrol'}
    assert len(client.inputs) == 2  # no model confirmation or third review
    messages, tools, _ = client.inputs[1]
    text = json.dumps(messages)
    assert '<context_for_action>' not in text and '<no_intervention/>' not in text
    assert {'intervene', 'wait', 'allow_complete'} <= {t['function']['name'] for t in tools}


def test_maintenance_misplaced_reminder_explicitly_reports_not_sent(workspace):
    client = Client([comparison('<context_for_action>Concern</context_for_action>'),
                     comparison('<maintenance_complete/>'), response('intervene', message='Concern'),
                     response('wait', after_turns=1)])
    sent = []
    monitor = MonitorAgent(client, workspace)
    monitor.intervention_callback = sent.append
    monitor.review('wake')
    assert sent == ['Concern']
    feedback = json.loads(client.inputs[1][0][0]['content'])
    assert feedback['input_sent'] is False
    assert 'maintenance' in feedback['next']


def test_legacy_text_is_not_a_second_control_protocol(workspace):
    client = Client([comparison('<maintenance_complete/>'), comparison('<no_intervention/>'),
                     response('wait', after_turns=3)])
    monitor = MonitorAgent(client, workspace)
    assert monitor.review('wake').payload['after_turns'] == 3
    feedback = json.loads(client.inputs[2][0][0]['content'])
    assert 'No extra investigation' in feedback['next']


def test_no_reminder_cannot_approve_pending_completion(workspace):
    client = Client([comparison('<maintenance_complete/>'), response('wait', after_turns=2),
                     response('allow_complete')])
    monitor = MonitorAgent(client, workspace)
    assert monitor.review('handoff', completion_pending=True).kind == 'allow_complete'
    assert 'handoff_pending' in client.inputs[2][0][0]['tool_results'][0]['content']


def test_two_interventions_share_comparison_and_bank_receipts(workspace):
    client = Client([comparison('<maintenance_complete/>'), response('intervene', message='First'),
                     response('memory_update_status', content='First advice misunderstood; new evidence.'),
                     response('intervene', message='Clarification'), response('wait', after_turns=1)])
    sent = []
    monitor = MonitorAgent(client, workspace)
    monitor.intervention_callback = sent.append
    monitor.review('wake')
    assert sent == ['First', 'Clarification']
    records = [json.loads(x) for x in (workspace.private_root / 'audit/dialogue.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len([r for r in records if r['event'] == 'pma_fused_phase_started']) == 2
    cycle = next(r for r in records if r['event'] == 'pma_fused_cycle')
    assert cycle['interventions'] == sent and cycle['result']['should_inject']


def test_pending_intent_transfers_updated_bank_and_only_confirmed_message_is_sent(workspace):
    client = Client([
        response('memory_save_knowledge', content='Both forms still required.'),
        response('intervene', message='Draft correction'),
        response('intervene', message='Revised correction'),
        response('wait', after_turns=1, mode='follow'),
    ])
    sent = []
    monitor = MonitorAgent(client, workspace)
    monitor.intervention_callback = sent.append
    assert monitor.review('wake').kind == 'wait'
    assert sent == ['Revised correction']
    assert len(client.inputs) == 4
    prompt = client.inputs[2][0][1]['content']
    assert 'Draft correction' in prompt and 'Both forms still required.' in prompt
    results = [json.loads(r['content']) for m in client.history
               for r in m.get('tool_results', [])]
    transferred = next(r for r in results if r.get('result', {}).get('status') == 'intent_transferred')
    assert transferred['control_action'] == 'maintenance_complete'
    assert transferred['result']['input_sent'] is False
    records = [json.loads(x) for x in (workspace.private_root / 'audit/dialogue.jsonl')
               .read_text(encoding='utf-8').splitlines()]
    assert len([r for r in records if r['event'] == 'pma_control_intent_handoff']) == 1
    assert len([r for r in records if r['event'] == 'pma_control_intent_received']) == 1
    assert next(r for r in records if r['event'] == 'pma_fused_cycle')['interventions'] == sent


@pytest.mark.parametrize('name,args', [('wait', {'after_turns': 9, 'mode': 'patrol'}),
                                     ('allow_complete', {})])
def test_maintenance_control_never_calls_host_and_judgment_can_revise(workspace, name, args):
    client = Client([response(name, **args), response('wait', after_turns=2, mode='follow')])
    monitor = MonitorAgent(client, workspace)
    host_calls = []
    original = monitor.dispatch

    def dispatch(tool, arguments):
        host_calls.append((tool, arguments))
        return original(tool, arguments)

    monitor.dispatch = dispatch
    action = monitor.review('wake')
    assert action.kind == 'wait' and action.payload == {'after_turns': 2, 'mode': 'follow'}
    assert host_calls == [('wait', {'after_turns': 2, 'mode': 'follow'})]


def test_confirmed_completion_still_requires_valid_root_request(workspace):
    client = Client([response('allow_complete'), response('allow_complete'),
                     response('wait', after_turns=1)])
    monitor = MonitorAgent(client, workspace)
    assert monitor.review('not a root request').kind == 'wait'
    assert 'No root completion is pending' in str(client.inputs[2][0])


def test_confirmed_completion_for_valid_root_request(workspace):
    client = Client([response('allow_complete'), response('allow_complete')])
    monitor = MonitorAgent(client, workspace)
    assert monitor.review('root', completion_pending=True).kind == 'allow_complete'
    assert len(client.inputs) == 2


def test_handoff_failure_does_not_send_or_leak_proposal_into_next_review(workspace):
    client = Client([response('intervene', message='Obsolete draft'), RuntimeError('offline'),
                     comparison('<maintenance_complete/>'), response('wait', after_turns=1)])
    sent = []
    monitor = MonitorAgent(client, workspace)
    monitor.intervention_callback = sent.append
    with pytest.raises(RuntimeError, match='offline'):
        monitor.review('first')
    assert not sent
    monitor.review('second')
    assert 'Obsolete draft' not in client.inputs[-1][0][1]['content']
    # Historical failed intent remains auditable, but is not a new pending proposal.
    assert 'Obsolete draft' in json.dumps(client.history)


def test_handoff_batch_retains_receipts_without_executing_later_calls(workspace):
    from monitor_agent_core.provider import ModelResponse, ToolCall
    client = Client([ModelResponse('', [
        ToolCall('save', 'memory_save_knowledge', json.dumps({'content': 'Saved before handoff'})),
        ToolCall('draft', 'intervene', json.dumps({'message': 'Draft'})),
        ToolCall('late', 'memory_update_status', json.dumps({'content': 'Must not execute'})),
    ], {}), response('wait', after_turns=1)])
    monitor = MonitorAgent(client, workspace)
    assert monitor.review('wake').kind == 'wait'
    assert 'Saved before handoff' in monitor.pma_memory.context()
    assert monitor.pma_memory.memory.status == ''
    receipts = next(m['tool_results'] for m in client.history if 'tool_results' in m)
    assert [r['tool_use_id'] for r in receipts] == ['save', 'draft', 'late']
    assert json.loads(receipts[-1]['content'])['status'] == 'not_executed'


def test_transfer_respects_shared_budget_without_dispatch(workspace):
    client = Client([response('intervene', message='Unconfirmed')])
    monitor = MonitorAgent(client, workspace, max_review_turns=1)
    sent = []
    monitor.intervention_callback = sent.append
    with pytest.raises(MonitorLoopError, match='shared model-call budget'):
        monitor.review('wake')
    assert not sent and len(client.inputs) == 1


def test_real_provider_phase_handoff_has_complete_tool_receipt(workspace, monkeypatch):
    from monitor_agent_core.provider import MonitorProviderClient
    client = MonitorProviderClient('fixture', {'apikey': 'fake', 'apibase': 'http://invalid',
                                             'provider': 'anthropic', 'monitor_pma_memory': True})
    requests = []
    replies = iter([
        [{'type': 'tool_use', 'id': 'draft', 'name': 'intervene', 'input': {'message': 'Draft'}}],
        [{'type': 'tool_use', 'id': 'decision', 'name': 'wait', 'input': {'after_turns': 1}}],
    ])

    def request(tools):
        requests.append(json.loads(json.dumps(client.export_history())))
        return next(replies), {'input_tokens': 7}

    monkeypatch.setattr(client, '_request', request)
    monitor = MonitorAgent(client, workspace)
    assert monitor.review('wake').kind == 'wait'
    blocks = [b for m in requests[1] for b in m.get('content', []) if isinstance(b, dict)]
    receipt = next(b for b in blocks if b.get('tool_use_id') == 'draft')
    assert json.loads(receipt['content'])['result']['executed'] is False
    assert 'Draft' in str(requests[1])
    # Phase-specific descriptions must not mutate shared tool definitions.
    from monitor_agent_core.agent import MONITOR_TOOLS
    assert all('Finish maintenance' not in t['function']['description'] for t in MONITOR_TOOLS)
