import ast
import json
from pathlib import Path

import pytest

from test_monitor_pma_memory import Client, comparison, response, workspace
from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.pma_observation import observation
from monitor_agent_core.vendor.pma_memory.memory_agent import MemoryAgent, PHASE1_SYSTEM, PHASE2_SYSTEM


@pytest.mark.skip(reason='Old prompt adaptation retired; fused path uses author prompts')
def test_author_process_runs_both_adapted_prompts(workspace, monkeypatch):
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
    from monitor_agent_core.pma_judgment import adapt
    from monitor_agent_core.vendor.pma_memory.memory_agent import BANK_TOOLS
    assert client.inputs[0][0][0]['content'] == adapt(PHASE1_SYSTEM, BANK_TOOLS)[0]
    assert 'Organize evidence for the next judgment' in client.inputs[0][0][0]['content']
    assert client.inputs[1][0][0]['content'] == adapt(PHASE2_SYSTEM, None)[0]
    assert 'discriminating observation' in client.inputs[1][0][0]['content']
    assert client.inputs[1][1] == []
    assert 'Potential missing contract' in str(client.inputs[2][0])
    assert not delivered  # A lead is not an automatic intervention.


@pytest.mark.parametrize('second', [RuntimeError('service failure'), comparison('unrecognized'),
                                   comparison('<think><no_intervention/></think>')])
@pytest.mark.skip(reason='Old one-shot comparison contract; fused failure propagation tested separately')
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


def test_inspection_output_carries_matching_command_and_source(workspace):
    audit = workspace.private_root / 'audit'
    audit.mkdir()
    rows = [
        {'event': 'tool_call', 'review_id': 'old', 'tool_id': 'same',
         'name': 'code_run', 'arguments': 'unrelated-command'},
        {'event': 'tool_call', 'review_id': 'new', 'tool_id': 'same',
         'name': 'code_run', 'arguments': 'echo ALL COMPLETE'},
        {'event': 'tool_result', 'review_id': 'new', 'tool_id': 'same',
         'data': {'stdout': 'ALL COMPLETE', 'exit_code': 0}},
        {'event': 'tool_result', 'review_id': 'new', 'tool_id': 'missing',
         'data': {'stdout': 'unmatched output'}},
    ]
    (audit / 'dialogue.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
    text = observation(workspace, 'wake')
    assert 'echo ALL COMPLETE' in text and 'unrelated-command' not in text
    assert '#L2' in text and '#L3' in text
    assert 'unmatched; do not infer' in text


def test_adaptation_does_not_mutate_author_tools():
    import copy
    from monitor_agent_core.pma_judgment import adapt
    from monitor_agent_core.vendor.pma_memory.memory_agent import BANK_TOOLS
    before = copy.deepcopy(BANK_TOOLS)
    system, adapted = adapt(PHASE1_SYSTEM, BANK_TOOLS)
    assert BANK_TOOLS == before and adapted != before
    assert 'Printed assertions' in system


def test_judgment_context_precedes_bank_and_process_is_inherited():
    from monitor_agent_core.pma_judgment import JudgmentMemoryAgent
    from monitor_agent_core.vendor.pma_memory.universal_memory import UniversalMemory
    agent = JudgmentMemoryAgent(llm=None, memory=UniversalMemory())
    assert JudgmentMemoryAgent.process is MemoryAgent.process
    for build in (agent._build_phase1_prompt, agent._build_phase2_prompt):
        prompt = build('ORIGINAL_REQUIREMENT', 1)
        assert prompt.index('ORIGINAL_REQUIREMENT') < prompt.index(agent._format_memory_bank('ORIGINAL_REQUIREMENT'))
    assert 'do not pre-decide completion' in agent._build_phase1_prompt('task', 1)
    assert '<no_intervention/>' in agent._build_phase2_prompt('task', 1)


def test_timed_old_inspection_is_distinct_from_later_write(workspace):
    # R2 pattern: an earlier inspection must not look like post-write verification.
    events = [
        {'task_turn': 74, 'boundary': 'post_model_pre_tool', 'archived_at': 200,
         'text': 'rewrite file', 'tool_calls': [{'name': 'file_write'}]},
        {'task_turn': 74, 'boundary': 'post_tool_pre_next_llm', 'archived_at': 202,
         'tool_results': [{'content': 'success'}]},
        {'task_turn': 75, 'boundary': 'post_model_pre_tool', 'text': 'next action'},
    ]
    (workspace.evidence_root / 'public_events.jsonl').write_text(
        ''.join(json.dumps(x) + '\n' for x in events), encoding='utf-8')
    audit = workspace.private_root / 'audit'
    audit.mkdir()
    rows = [
        {'event': 'tool_call', 'review_id': 'r', 'tool_id': 't', 'timestamp': 100,
         'name': 'code_run', 'arguments': 'read old file'},
        {'event': 'tool_result', 'review_id': 'r', 'tool_id': 't', 'timestamp': 101,
         'data': {'stdout': 'old contents'}},
    ]
    (audit / 'dialogue.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in rows), encoding='utf-8')
    text = observation(workspace, 'wake')
    for stamp in ('00:01:40.000+00:00', '00:01:41.000+00:00',
                  '00:03:20.000+00:00', '00:03:22.000+00:00'):
        assert stamp in text
    assert 'archived UTC unknown' in text
    assert 'not execution completion' in text


def test_runtime_archives_timestamp_without_changing_packet(tmp_path):
    import multiprocessing as mp
    import threading
    import time
    from monitor_agent_core.runtime import MonitorRuntime
    runtime = object.__new__(MonitorRuntime)
    runtime._archive_lock = threading.Lock()
    runtime._sequence = 0
    runtime._latest_task_turn = mp.Value('i', 0)
    runtime.events_path = tmp_path / 'events.jsonl'
    runtime.synopsis_path = tmp_path / 'synopsis.jsonl'
    packet = {'task_turn': 1, 'boundary': 'post_model_pre_tool', 'text': 'intent'}
    before = time.time()
    runtime._archive(packet)
    event = json.loads(runtime.events_path.read_text(encoding='utf-8'))
    assert before <= event['archived_at'] <= time.time()
    assert 'archived_at' not in packet
    assert event['text'] == 'intent'
