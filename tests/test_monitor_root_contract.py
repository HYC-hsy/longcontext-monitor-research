import json
import ast
from pathlib import Path

import pytest

from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.pma_fused import ROOT_DECISION
from test_monitor_pma_memory import Client, response, comparison, workspace


def configured(responses, enabled=True):
    client = Client(responses)
    client.config = {'monitor_pma_memory': True,
                     'monitor_root_decision_contract': enabled}
    return client


def system_at(client, index):
    return next(m['content'] for m in client.inputs[index][0] if m['role'] == 'system')


def test_disabled_candidate_preserves_baseline_inputs(workspace):
    def run(enabled):
        client = configured([comparison('<maintenance_complete/>'),
                             response('wait', after_turns=1)], enabled)
        monitor = MonitorAgent(client, workspace)
        monitor.review('wake')
        return client
    baseline, enabled = run(False), run(True)
    # Both phases retain identical inputs while no root proposal exists.
    assert baseline.inputs == enabled.inputs


def test_root_replaces_reminder_system_but_retains_bank_and_tools(workspace):
    client = configured([response('memory_save_knowledge', content='Grounds remain uncertain'),
                         comparison('<maintenance_complete/>'),
                         response('allow_complete')])
    monitor = MonitorAgent(client, workspace)
    monitor.completion_state = lambda: {'generation': 1, 'cursor': 8, 'request_id': 'root-1'}
    action = monitor.review('root handoff', completion_pending=True)
    assert action.kind == 'allow_complete'
    assert ROOT_DECISION not in system_at(client, 0)
    final_system = system_at(client, 2)
    assert ROOT_DECISION in final_system
    assert 'Your DEFAULT is wait' not in final_system
    assert 'Does the agent need a context reminder right now?' not in final_system
    assert 'Grounds remain uncertain' in str(client.inputs[2])
    assert {t['function']['name'] for t in client.inputs[2][1]} >= {
        'code_run', 'file_read', 'memory_update_status', 'allow_complete', 'intervene'}
    assert len(client.inputs) == 3  # No added model pass.


def test_mid_review_arrival_replacement_and_withdrawal(workspace):
    client = configured([comparison('<maintenance_complete/>'),
                         response('file_read', path='task/original_task.txt'),
                         response('file_read', path='task/original_task.txt'),
                         response('file_read', path='task/original_task.txt'),
                         response('wait', after_turns=1)])
    monitor = MonitorAgent(client, workspace)
    current = {'value': None}
    monitor.completion_state = lambda: current['value']
    complete = client.complete
    def next_response(messages, tools):
        result = complete(messages, tools)
        n = len(client.inputs)
        if n == 2:
            current['value'] = {'generation': 1, 'cursor': 8}
        elif n == 3:
            current['value'] = {'generation': 2, 'cursor': 9}
        elif n == 4:
            current['value'] = None
        return result
    client.complete = next_response
    monitor.review('ordinary')
    assert ROOT_DECISION not in system_at(client, 1)
    assert ROOT_DECISION in system_at(client, 2)
    assert ROOT_DECISION in system_at(client, 3)
    assert ROOT_DECISION not in system_at(client, 4)
    events = [json.loads(line) for line in
              (workspace.private_root / 'audit/dialogue.jsonl').read_text(encoding='utf-8').splitlines()]
    selections = [e for e in events if e['event'] == 'root_decision_contract_selected']
    assert [(e['mode'], e['generation']) for e in selections] == [
        ('ordinary', None), ('root', 1), ('root', 2), ('ordinary', None)]


@pytest.mark.parametrize('value', ['1', None, 1])
def test_invalid_candidate_config_fails(value, workspace):
    client = configured([])
    client.config['monitor_root_decision_contract'] = value
    with pytest.raises(ValueError, match='boolean'):
        MonitorAgent(client, workspace)


def test_candidate_requires_fused_memory(workspace):
    client = configured([])
    client.config['monitor_pma_memory'] = False
    with pytest.raises(ValueError, match='requires'):
        MonitorAgent(client, workspace)


def test_real_provider_replaces_system_without_resetting_history(workspace, monkeypatch):
    from monitor_agent_core.provider import MonitorProviderClient
    client = MonitorProviderClient('fixture', {
        'apikey': 'fake', 'apibase': 'http://invalid', 'provider': 'anthropic',
        'monitor_pma_memory': True, 'monitor_root_decision_contract': True})
    seen = []
    replies = iter([
        [{'type': 'text', 'text': '<maintenance_complete/>'}],
        [{'type': 'tool_use', 'id': 'read', 'name': 'file_read',
          'input': {'path': 'task/original_task.txt'}}],
        [{'type': 'tool_use', 'id': 'wait', 'name': 'wait', 'input': {'after_turns': 1}}],
    ])
    monitor = MonitorAgent(client, workspace)
    state = {'value': {'generation': 1, 'cursor': 8, 'request_id': 'root-1'}}
    monitor.completion_state = lambda: state['value']
    def request(tools):
        seen.append((client.system, json.dumps(client.export_history())))
        if len(seen) == 2:
            state['value'] = None
        return next(replies), {'input_tokens': 7}
    monkeypatch.setattr(client, '_request', request)
    monitor.review('root', completion_pending=True)
    assert ROOT_DECISION in seen[1][0]
    assert ROOT_DECISION not in seen[2][0]
    assert 'Selective Attention module' in seen[2][0]
    assert 'tool_result' in seen[2][1]
    assert 'Support both short and long forms.' in seen[2][1]


def test_simple_control_uses_same_tools_and_call_count(workspace):
    from monitor_agent_core.pma_fused import ROOT_SIMPLE_CHECK
    client = configured([comparison('<maintenance_complete/>'), response('allow_complete')], False)
    client.config['monitor_root_simple_check'] = True
    monitor = MonitorAgent(client, workspace)
    monitor.completion_state = lambda: {'generation': 1, 'cursor': 8, 'request_id': 'root-1'}
    assert monitor.review('root', completion_pending=True).kind == 'allow_complete'
    assert ROOT_SIMPLE_CHECK in system_at(client, 1)
    assert ROOT_DECISION not in system_at(client, 1)
    assert len(client.inputs) == 2


def test_controls_cannot_be_enabled_together(workspace):
    client = configured([])
    client.config['monitor_root_simple_check'] = True
    with pytest.raises(ValueError, match='exclusive'):
        MonitorAgent(client, workspace)


def test_candidate_flags_reach_manifest_and_container():
    root = Path(__file__).resolve().parents[2]
    for path, variable in [
        ('long_context_bench/scripts/run_ultralong_m12_proofs.py', 'MANIFEST_CONTROLLED_ENV_KEYS'),
        ('long_context_bench/adapters/harbor_ga_agent.py', 'FORWARDED_ENV_VARS'),
    ]:
        tree = ast.parse((root / path).read_text(encoding='utf-8'))
        assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == variable for t in n.targets))
        assert {'GA_MONITOR_ROOT_DECISION_CONTRACT', 'GA_MONITOR_ROOT_SIMPLE_CHECK'} <= set(
            ast.literal_eval(assignment.value))
