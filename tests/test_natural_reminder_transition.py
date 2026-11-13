"""Nonterminal public decisions and current-state continuation; no live calls."""
import json
from pathlib import Path

import pytest
from test_remind_first_loop import make, read, add, done, decision, run, response, call
from test_predictive_tool_recovery import block_network  # noqa: F401
from memory_agent.memory.read_context_predictive_memory_agent import (
    parse_final_decision, REMIND_DECISION_PROMPT, REMIND_READ_PROMPT,
    REMIND_TOOL_RECOVERY_PROMPT, ORGANIZE_START_PROMPT)

CASES = json.loads((Path(__file__).parent/'fixtures/reminder_stage_regressions.json').read_text())


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['task'])
def test_actual_tail_prose_accepts_original_decision_without_format_retry(case):
    raw = case['raw_public_reply']
    expected = (case['expected_decision'], case['expected_reminder'])
    assert parse_final_decision(raw) == expected
    a = make(read(), response(content=raw), add('new fact'), done())
    result = run(a)
    assert result.context_for_action == expected[1]
    assert result.should_inject == (expected[0] == 'context_for_action')
    assert len(a.llm.calls) == 4
    assert result.loop_rounds[1]['decision_accepted']
    assert not result.loop_rounds[1]['organize_completed']
    assert a.llm.calls[2]['prompt'] == ORGANIZE_START_PROMPT
    assert [op.action for op in result.operations] == ['read', 'add']
    assert all(op.success for op in result.operations)


@pytest.mark.parametrize('tag,kind,body', [
    ('<no_intervention/>', 'no_intervention', None),
    ('<context_for_action>exact\n```python\nx=1\n```</context_for_action>',
     'context_for_action', 'exact\n```python\nx=1\n```')])
def test_public_decision_anywhere_not_requires_end(tag,kind,body):
    assert parse_final_decision('Before.\n'+tag+'\nAfter.') == (kind,body)


def test_successful_read_gets_decision_prompt_not_another_read_instruction():
    a=make(read(),decision(),done())
    run(a)
    assert a.llm.calls[1]['prompt']==REMIND_DECISION_PROMPT
    assert 'result is available' in a.llm.calls[1]['prompt']
    assert REMIND_READ_PROMPT not in [r['prompt'] for r in a.llm.calls]


def test_same_call_read_and_nonterminal_tag_still_waits_for_receipt():
    a=make(read(content='<no_intervention/>\nNow organize.'),
           decision('After reading.'),done())
    result=run(a)
    assert not result.loop_rounds[0]['decision_accepted']
    assert a.llm.calls[1]['prompt']==REMIND_DECISION_PROMPT
    assert result.context_for_action=='After reading.'


def test_failed_read_and_early_decision_do_not_claim_bank_available():
    a=make(response(call('memory_read',{'query':'bad'},'bad')),
           response(content='<no_intervention/>\nDone.'),read(),decision(),done())
    result=run(a)
    assert a.llm.calls[1]['prompt']==REMIND_TOOL_RECOVERY_PROMPT
    assert a.llm.calls[2]['prompt']==REMIND_READ_PROMPT
    assert a.llm.calls[3]['prompt']==REMIND_DECISION_PROMPT
    assert not result.loop_rounds[1]['decision_accepted']


def test_malformed_after_read_recovers_in_reminder_stage_not_managing_memory():
    a=make(read(),response(content='I have not decided.'),decision(),done())
    run(a)
    assert a.llm.calls[2]['prompt']==REMIND_DECISION_PROMPT
    assert 'Do not save' in a.llm.calls[2]['prompt']


def test_tag_plus_early_write_still_cannot_transition_or_mutate():
    a=make(read(),response(call('memory_add',{'content':'blocked'},'early'),
        content='<no_intervention/>\nStarting organization.'),decision(),done())
    result=run(a)
    assert not result.loop_rounds[1]['decision_accepted']
    assert result.operations[1].success is False
    assert not a.memory.knowledge
    assert a.llm.calls[2]['prompt']==REMIND_TOOL_RECOVERY_PROMPT


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
