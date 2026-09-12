import json

import pytest

from monitor_agent_core.agent import (
    MONITOR_SYSTEM_PROMPT, TOOL_FEEDBACK_GUIDANCE, monitor_system_prompt,
)
from test_monitor_inquiry import make
from test_monitor_agent import response


def test_only_one_paragraph_changes():
    assert monitor_system_prompt(False) == MONITOR_SYSTEM_PROMPT
    original = MONITOR_SYSTEM_PROMPT.split('\n\n')
    treatment = monitor_system_prompt(True).split('\n\n')
    assert len(original) == len(treatment)
    changed = [(a, b) for a, b in zip(original, treatment) if a != b]
    assert len(changed) == 1 and changed[0][1] == TOOL_FEEDBACK_GUIDANCE


@pytest.mark.parametrize('enabled', [False, True])
def test_real_review_prompt_tools_and_direct_intervention(tmp_path, enabled):
    m = make(tmp_path, enabled=False)
    m.client.config['monitor_tool_feedback'] = enabled
    m = type(m)(m.client, m.workspace)
    m.client.responses = iter([response('intervene', {'message': 'Concrete discrepancy.'})])
    assert m.review('Inspect').kind == 'intervene'
    assert m.client.history[0]['content'].startswith(monitor_system_prompt(enabled))
    rows = [json.loads(line) for line in
            (m.workspace.private_root / 'audit/dialogue.jsonl').read_text().splitlines()]
    context = next(row for row in rows if row['event'] == 'review_context')
    assert {t['function']['name'] for t in context['tools']} == {
        'file_read', 'file_write', 'file_patch', 'code_run', 'wait', 'intervene', 'allow_complete'}


@pytest.mark.parametrize('value', ['0', '1', 'invalid'])
def test_adapter_flag(monkeypatch, value):
    import ga_monitor_adapter as adapter
    captured = {}
    monkeypatch.setenv('GA_MONITOR_TOOL_FEEDBACK', value)
    monkeypatch.setattr(adapter, 'MonitorRuntime', lambda **kw: captured.update(kw))
    if value == 'invalid':
        with pytest.raises(ValueError):
            adapter.GenericAgentMonitorAdapter(model_config={})
    else:
        adapter.GenericAgentMonitorAdapter(model_config={})
        assert captured['model_config']['monitor_tool_feedback'] == (value == '1')


def test_prepared_conditions_are_isolated(tmp_path, monkeypatch):
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'method_discovery'))
    import prepare_tool_feedback_run as prep
    monkeypatch.setattr(prep, 'build_manifest', lambda *args: {
        'status': 'prepared_not_executed', 'runs': [{'environment': {}}]})
    baseline = prep.prepare(tmp_path / 'base.json', 'base')
    treatment = prep.prepare(tmp_path / 'treatment.json', 'treatment', True)
    a, b = [d['runs'][0]['environment'] for d in (baseline, treatment)]
    assert {key for key in a if a[key] != b[key]} == {'GA_MONITOR_TOOL_FEEDBACK'}
    assert all(a[key] == b[key] == '0' for key in (
        'GA_MONITOR_INQUIRY', 'GA_MONITOR_GROUNDED_CONTEXT', 'GA_MONITOR_HANDOFF_VALIDATION',
        'GA_MONITOR_ADVICE_REVISION', 'GA_MONITOR_FEEDBACK_FOCUS'))
    assert baseline['guidance_comparison']['stable_system_prompt'] == MONITOR_SYSTEM_PROMPT
    with pytest.raises(FileExistsError):
        prep.prepare(tmp_path / 'base.json', 'base')
