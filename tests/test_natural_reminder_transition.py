"""Nonterminal public decisions and current-state continuation; no live calls."""
import json
from pathlib import Path

import pytest
from test_remind_first_loop import make, read, add, done, decision, run, response, call
from test_predictive_tool_recovery import block_network  # noqa: F401
from memory_agent.memory.read_context_predictive_memory_agent import parse_final_decision

CASES = json.loads((Path(__file__).parent/'fixtures/reminder_stage_regressions.json').read_text())


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['task'])
def test_actual_tail_prose_accepts_original_decision_without_format_retry(case):
    raw = case['raw_public_reply']
    expected = (case['expected_decision'], case['expected_reminder'])
    assert parse_final_decision(raw) == expected
    a = make(read(), add('new fact', content=raw), done())
    result = run(a)
    assert result.context_for_action == expected[1]
    assert result.should_inject == (expected[0] == 'context_for_action')
    assert len(a.llm.calls) == 3
    assert result.loop_rounds[1]['decision_accepted']
    assert all(op.success for op in result.operations)


@pytest.mark.parametrize('tag,kind,body', [
    ('<no_intervention/>', 'no_intervention', None),
    ('<context_for_action>exact\n```python\nx=1\n```</context_for_action>',
     'context_for_action', 'exact\n```python\nx=1\n```')])
def test_public_decision_anywhere_not_requires_end(tag,kind,body):
    assert parse_final_decision('Before.\n'+tag+'\nAfter.') == (kind,body)


def test_successful_read_continues_without_stale_read_instruction():
    a=make(read(),decision())
    run(a)
    assert a.llm.calls[1]['prompt']=='Continue.'


@pytest.mark.parametrize('raw', [
    '<no_intervention/><context_for_action>x</context_for_action> trailing',
    '<context_for_action>a</context_for_action><context_for_action>b</context_for_action>',
    '<context_for_action>unclosed',
    '```xml\n<no_intervention/>\n``` tail',
    '<think><no_intervention/></think> tail',
    '<tool_call><context_for_action>x</context_for_action></tool_call> tail',
])
def test_nonterminal_relaxation_does_not_accept_ambiguous_or_nonpublic_decisions(raw):
    assert parse_final_decision(raw)==(None,None)
