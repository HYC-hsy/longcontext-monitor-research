import json
from pathlib import Path

import pytest

from monitor_agent_core.agent import MonitorAgent, MONITOR_TOOLS
from monitor_agent_core.provider import ModelResponse, ToolCall
from monitor_agent_core.workspace import MonitorWorkspace
from monitor_agent_core.pma_memory import PMAMemoryMaintenance


def response(name, **arguments):
    return ModelResponse('', [ToolCall('call', name, json.dumps(arguments))], {'input_tokens': 11})


def comparison(text='<no_intervention/>'):
    return ModelResponse(text, [], {'input_tokens': 7})


class Client:
    config = {'monitor_pma_memory': True}

    def __init__(self, responses):
        self.responses = iter(responses)
        self.history = [{'role': 'user', 'content': 'Previous investigation remains available.'}]
        self.system = 'prior system'
        self.inputs = []

    def complete(self, messages, tools):
        active = getattr(self, 'prepare_active_context', None)
        self.inputs.append((messages, tools, active() if active else None))
        self.history.extend(messages)
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        self.history.append({'role': 'assistant', 'content': result.content})
        return result

    def export_history(self):
        return json.loads(json.dumps(self.history))

    def restore_history(self, history):
        self.history = history

    def history_measure(self):
        return {'items': len(self.history)}

    def record_tool_results(self, results):
        self.history.append({'role': 'user', 'tool_results': results})


@pytest.fixture
def workspace(tmp_path):
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    (evidence / 'original_task.txt').write_text('Support both short and long forms.', encoding='utf-8')
    return MonitorWorkspace(evidence, tmp_path / 'private')


def test_maintenance_reaches_existing_review_without_replacing_tools_or_history(workspace):
    client = Client([response('memory_save_knowledge', content='Short forms remain required.'),
                     comparison(),
                     response('wait', after_turns=2)])
    monitor = MonitorAgent(client, workspace)
    action = monitor.review('Initialization')
    assert action.kind == 'wait'
    assert 'Short forms remain required.' in client.inputs[2][2]
    assert 'Short forms remain required.' in client.inputs[1][0][1]['content']
    assert client.inputs[0][2] is None
    assert client.inputs[1][2] is None
    assert client.inputs[2][1] == MONITOR_TOOLS
    assert client.history[0]['content'] == 'Previous investigation remains available.'
    assert not any('Current Memory Bank' in str(item) for item in client.history)
    records = [json.loads(line) for line in (workspace.private_root / 'audit/dialogue.jsonl').read_text(encoding='utf-8').splitlines()]
    maintenance = next(r for r in records if r['event'] == 'pma_two_phase')
    assert maintenance['status'] == 'no_intervention'
    assert maintenance['phases'][0]['usage']['input_tokens'] == 11
    assert maintenance['phases'][1]['usage']['input_tokens'] == 7
    restored = PMAMemoryMaintenance(workspace, monitor._atomic_private_text, monitor._audit_dialogue)
    assert 'Short forms remain required.' in restored.context()


def test_failure_restores_history_hooks_and_bank(workspace):
    client = Client([RuntimeError('offline')])
    monitor = MonitorAgent(client, workspace)
    history = client.export_history()
    active = client.prepare_active_context
    with pytest.raises(RuntimeError, match='offline'):
        monitor.review('wake')
    assert client.export_history() == history
    assert client.system == 'prior system'
    assert client.prepare_active_context == active
    assert not (workspace.private_root / 'pma_memory.json').exists()


def test_delete_then_save_revises_and_preserves_audit(workspace):
    client = Client([])
    monitor = MonitorAgent(client, workspace)
    bank = monitor.pma_memory
    old = bank.memory.save_knowledge('Everything complete')
    client.responses = iter([ModelResponse('', [
        ToolCall('a', 'memory_delete', json.dumps({'memory_id': old})),
        ToolCall('b', 'memory_save_knowledge', json.dumps({'content': 'Short forms not checked'})),
    ], {}), comparison()])
    bank.update(client, 'New evidence', 'test')
    assert 'Everything complete' not in bank.context()
    assert 'Short forms not checked' in bank.context()
    log = (workspace.private_root / 'audit/dialogue.jsonl').read_text(encoding='utf-8')
    assert 'Everything complete' in log


def test_author_sources_unchanged():
    root = Path(__file__).resolve().parents[1]
    for name in ('memory_agent.py', 'universal_memory.py', 'bm25_search.py'):
        assert (root / 'pma_baseline' / name).read_text(encoding='utf-8') == (
            root / 'monitor_agent_core/vendor/pma_memory' / name).read_text(encoding='utf-8')


def test_bank_is_task_local_and_failure_is_not_silent(workspace, tmp_path):
    client = Client([response('memory_delete', memory_id='missing'), comparison()])
    monitor = MonitorAgent(client, workspace)
    with pytest.raises(RuntimeError, match='operation failed'):
        monitor.review('wake')
    other = MonitorWorkspace(workspace.evidence_root, tmp_path / 'other')
    assert not PMAMemoryMaintenance(other, lambda *a: None, lambda *a, **k: None).memory.knowledge


def test_actual_provider_history_is_restored_after_maintenance(workspace, monkeypatch):
    from monitor_agent_core.provider import MonitorProviderClient
    client = MonitorProviderClient('fixture', {'apikey': 'fake', 'apibase': 'http://invalid',
                                             'provider': 'anthropic', 'monitor_pma_memory': True})
    initial = [{'role': 'user', 'content': [{'type': 'text', 'text': 'Prior evidence'}]}]
    client.restore_history(initial)
    monitor = MonitorAgent(client, workspace)
    calls = []
    def request(tools):
        calls.append(tools)
        if not tools:
            return [{'type': 'text', 'text': '<no_intervention/>'}], {'input_tokens': 7}
        return [{'type': 'tool_use', 'id': 'bank', 'name': 'memory_save_knowledge',
                 'input': {'content': 'Requirement remains open'}}], {'input_tokens': 12}
    monkeypatch.setattr(client, '_request', request)
    monitor.pma_memory.update(client, 'wake', 'fixture')
    assert client.export_history() == initial
    assert calls[0][0]['function']['name'] == 'memory_save_knowledge'
    assert 'Requirement remains open' in client.prepare_active_context()


def test_followup_after_intervention_does_not_repeat_maintenance(workspace):
    client = Client([response('memory_save_knowledge', content='Check intended behavior.'),
                     comparison('<context_for_action>Check intended behavior.</context_for_action>'),
                     response('intervene', message='The test does not check the required behavior.'),
                     response('wait', after_turns=1)])
    monitor = MonitorAgent(client, workspace)
    delivered = []
    monitor.intervention_callback = lambda message: delivered.append(message)
    assert monitor.review('wake').kind == 'wait'
    assert len(delivered) == 1
    assert len(client.inputs) == 4
    assert client.inputs[3][1] == MONITOR_TOOLS
    assert 'Check intended behavior.' in str(client.inputs[2][0])


def test_new_switch_reaches_container():
    root = Path(__file__).resolve().parents[2]
    import ast
    source = (root / 'long_context_bench/adapters/harbor_ga_agent.py').read_text(encoding='utf-8')
    assignment = next(n for n in ast.parse(source).body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'FORWARDED_ENV_VARS' for t in n.targets))
    assert 'GA_MONITOR_PMA_MEMORY' in ast.literal_eval(assignment.value)
