import ast
import json
from pathlib import Path

import pytest

from test_monitor_pma_memory import Client, comparison, response, workspace
from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.pma_observation import observation
from monitor_agent_core.vendor.pma_memory.memory_agent import MemoryAgent, PHASE1_SYSTEM, PHASE2_SYSTEM


def test_author_process_runs_both_original_prompts(workspace, monkeypatch):
    called = []
    original = MemoryAgent.process
    async def spy(self, *args, **kwargs):
        called.append(True)
        return await original(self, *args, **kwargs)
    monkeypatch.setattr(MemoryAgent, 'process', spy)
    client = Client([response('memory_save_knowledge', content='Original contract'),
                     comparison('<context_for_action>Potential missing contract</context_for_action>'),
                     response('wait', after_turns=1)])
    monitor = MonitorAgent(client, workspace)
    delivered = []
    monitor.intervention_callback = lambda m: delivered.append(m)
    assert monitor.review('wake').kind == 'wait'
    assert called == [True]
    assert client.inputs[0][0][0]['content'] == PHASE1_SYSTEM
    assert client.inputs[1][0][0]['content'] == PHASE2_SYSTEM
    assert client.inputs[1][1] == []
    assert 'Potential missing contract' in str(client.inputs[2][0])
    assert not delivered  # A lead is not an automatic intervention.


@pytest.mark.parametrize('second', [RuntimeError('service failure'), comparison('unrecognized'),
                                   comparison('<think><no_intervention/></think>')])
def test_comparison_failure_does_not_become_silence_or_pollute_history(workspace, second):
    client = Client([response('memory_save_knowledge', content='attempt'), second])
    initial = client.export_history()
    monitor = MonitorAgent(client, workspace)
    with pytest.raises(RuntimeError):
        monitor.review('wake')
    assert client.export_history() == initial
    assert not monitor.pma_memory.memory.knowledge
    assert not (workspace.private_root / 'pma_memory.json').exists()


def test_recent_input_uses_eight_turns_not_eight_boundary_records(workspace):
    events = []
    for turn in range(1, 11):
        events.extend([
            {'task_turn': turn, 'text': f'intent-{turn}', 'tool_calls': [{'name': 'inspect'}]},
            {'task_turn': turn, 'text': f'intent-{turn}', 'tool_results': [{'content': f'result-{turn}'}]},
        ])
    (workspace.evidence_root / 'public_events.jsonl').write_text(
        ''.join(json.dumps(x) + '\n' for x in events) + '{partial', encoding='utf-8')
    text = observation(workspace, 'wake')
    assert '[Recent Trajectory (last 8 steps)]' in text
    assert '[Step 2]' not in text
    for turn in range(3, 11):
        assert f'[Step {turn}]' in text
        assert f'intent-{turn}' in text and f'result-{turn}' in text


def test_inspection_receipts_not_repeated_model_conclusions(workspace):
    audit = workspace.private_root / 'audit'
    audit.mkdir()
    (audit / 'dialogue.jsonl').write_text('\n'.join(map(json.dumps, [
        {'event': 'model_output', 'content': 'EVERYTHING IS COMPLETE'},
        {'event': 'tool_result', 'data': {'path': 'task/workspace/a.py', 'content': 'actual source'}},
    ])) + '\n', encoding='utf-8')
    text = observation(workspace, 'wake')
    assert 'actual source' in text
    assert 'EVERYTHING IS COMPLETE' not in text


def test_extracted_author_context_methods_are_unchanged():
    root = Path(__file__).resolve().parents[2]
    upstream = root / 'some_research/research_library/02_direct_methods/repositories/yifannnwu__proactive-memory-agent/src/memory_agent/memory_enabled_agent.py'
    local = root / 'GenericAgent-main/monitor_agent_core/vendor/pma_memory/context.py'
    def methods(path):
        source = path.read_text(encoding='utf-8')
        return {node.name: ast.dump(node, include_attributes=False)
                for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef)
                and node.name in {'_get_memory_agent_context', '_format_step_entry'}}
    assert methods(upstream) == methods(local)
