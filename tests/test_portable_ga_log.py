"""Copied GA TXT body contract; no provider calls or GA runtime imports."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'
sys.path.insert(0, str(STAGE))
from ga_log_format import format_log_trajectory, prompt_body, response_body, section


def test_original_ga_writer_and_copied_body_are_character_equal(tmp_path):
    source = (ROOT / 'GenericAgent-main/llmcore.py').read_text()
    tree = ast.parse(source)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_write_llm_log')
    namespace = dict(os=os, datetime=datetime)
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<original-ga-writer>', 'exec'), namespace)
    messages = {'role': 'user', 'content': [{'type': 'text', 'text': '中文\n"quotes" \\ paths'},
        {'type': 'tool_result', 'tool_use_id': 'call-1', 'content': '{"x":"\\n"}'}]}
    blocks = [{'type': 'thinking', 'thinking': 'synthetic test value', 'signature': 'fake-fixture'},
              {'type': 'tool_use', 'id': 'call-2', 'name': 'read', 'input': {'a': True}}]
    pairs = [('Prompt', json.dumps(messages, ensure_ascii=False, indent=2), prompt_body(messages)),
             ('Response', str(blocks), response_body(str(blocks)))]
    for label, ga_value, copied_value in pairs:
        path = tmp_path / label
        namespace['_write_llm_log'](label, ga_value, str(path), model='fixture')
        original = path.read_text().split('\n', 1)[1]
        copied = section(label, copied_value).split('\n', 1)[1]
        assert original == copied


def test_independent_without_ga_and_duplicate_real_events(tmp_path):
    code = '''from public_trajectory import PublicTrajectory
from ga_log_format import format_log_trajectory
p=PublicTrajectory(1)
p.record('input:1','input',{'role':'user','content':'same','log_prompt':'same'})
p.record('input:2','input',{'role':'user','content':'same','log_prompt':'same'})
p.record('assistant','assistant',{'log_response':'raw same'})
s=format_log_trajectory(p.snapshot())
assert s.count('=== Prompt ===') == 2
assert s.count('same') == 3
q=PublicTrajectory(1)
assert q.snapshot()['events'] == []
'''
    env = dict(os.environ, PYTHONPATH=str(STAGE))
    result = subprocess.run([sys.executable, '-c', code], cwd=tmp_path, env=env,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_old_public_projection_is_not_forged_as_raw():
    import pytest
    with pytest.raises(KeyError, match='log_response'):
        format_log_trajectory({'events':[{'kind':'assistant','payload':{'content':[]}}]})


def test_candidate_dispatch_preserves_old_context_and_rejects_missing_raw(tmp_path):
    import pytest
    from episode import construct_upstream
    trajectory = {"schema": "public-task-trajectory-v1", "round": 1,
        "events": [{"event_id": "input", "sequence": 1, "kind": "input",
                    "payload": {"content": "old captured input"}},
                   {"event_id": "assistant", "sequence": 2, "kind": "assistant",
                    "payload": {"content": "old public response", "tool_call_ids": []}}]}
    entry = {"step": 1, "public_trajectory": trajectory}
    expected = json.dumps(trajectory, ensure_ascii=False, allow_nan=False, sort_keys=True)
    for candidate in ("pma_predictive_f838_v1", "pma_predictive_context_v1"):
        agent = construct_upstream(tmp_path / candidate, research_candidate=candidate)
        agent._public_active_batch = [entry]
        agent._task_description = "Original task"
        assert agent._format_step_entry(entry) == expected
        # Real context assembly used by the old candidate's memory call.
        assert agent._get_memory_agent_context() == (
            "[Task Description]\nOriginal task\n\n"
            "[Recent Trajectory (last 1 steps)]\n\n" + expected)
    current = construct_upstream(tmp_path / "current",
        research_candidate="pma_predictive_read_context_v1")
    with pytest.raises(KeyError, match="log_prompt"):
        current._format_step_entry(entry)
