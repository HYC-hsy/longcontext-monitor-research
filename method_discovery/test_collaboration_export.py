"""Publication boundary checks; no model calls or archive mutation."""
import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).parent / 'scripts/build_collaboration_bundle.py'
spec = importlib.util.spec_from_file_location('collaboration_export', SCRIPT)
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


def test_cycle_export_is_allowlisted_and_traceable():
    secret = 'FULL_TASK_BODY_SENTINEL'
    source = {'event': 'pma_fused_cycle', 'result': {
        'operations': [], 'should_inject': False, 'context_for_action': None,
        'user_prompt_phase1': secret, 'user_prompt_phase2': secret,
        'raw_response_phase1': secret, 'reasoning_phase2': secret,
        'future_nested_input': {'content': secret},
    }, 'action': {'kind': 'wait'}}
    before = json.dumps(source)
    exported = bundle.dialogue(before)
    assert secret not in exported
    row = json.loads(exported)
    assert row['source_line'] == 1
    assert row['action'] == {'kind': 'wait'}
    assert row['result']['operations'] == []
    assert len(row['result']['omitted_fields']) == 5
    assert json.dumps(source) == before


def test_original_task_read_redacted_but_public_observation_kept():
    rows = [
        {'event': 'tool_result', 'data': {'path': 'task/original_task.txt',
                                       'content': 'FULL_TASK_BODY_SENTINEL'}},
        {'event': 'tool_result', 'data': {'stdout': 'public build failed', 'exit_code': 1}},
        {'event': 'model_input', 'content': 'FULL_TASK_BODY_SENTINEL'},
    ]
    out = bundle.dialogue('\n'.join(map(json.dumps, rows)))
    assert 'FULL_TASK_BODY_SENTINEL' not in out
    assert 'public build failed' in out
    assert len(out.splitlines()) == 2


def test_existing_r8_r9_cycles_exclude_all_prompt_copies():
    root = Path(__file__).resolve().parents[1] / 'research_collaboration_private/evidence'
    for run in ['automatic_fyne_r8', 'automatic_fyne_r9']:
        original = (root / run / 'decisions.jsonl').read_text(encoding='utf-8')
        exported = bundle.dialogue(original)
        for line in exported.splitlines():
            row = json.loads(line)
            if row['event'] == 'pma_fused_cycle':
                assert set(row['result']) <= {
                    'operations', 'should_inject', 'context_for_action', 'omitted_fields'}
