"""Soft public P1 summaries: offline fixtures do not establish model adherence."""
import asyncio
import json

import pytest

from test_predictive_memory_read import Agent, Script, call, response, run
from test_predictive_tool_recovery import block_network  # noqa: F401
from test_predictive_visible_basis import install, provider_llm, rows
from memory_agent.memory.read_context_predictive_memory_agent import (
    UNIFIED_SYSTEM, PUBLIC_FORECAST_REMINDER, DECISION_RECOVERY_PROMPT, has_public_text)
from memory_agent.memory.predictive_memory_agent import PHASE2_SYSTEM

REMINDED = UNIFIED_SYSTEM + '\n\n' + PUBLIC_FORECAST_REMINDER


@pytest.mark.parametrize('text', [None, '', ' \t\n', '.', '...', '…', '。。。',
    '<summary>...</summary>', '<think>fixture</think>',
    '<thinking>fixture</thinking>', '<THINKING>fixture',
    '<tool_call><function=memory_add>fixture</function></tool_call>'])
def test_absent_public_text_is_only_a_lexical_signal(text):
    assert not has_public_text(text)


@pytest.mark.parametrize('text', ['OK', 'Finished.', '下一步可能需要核对接口。',
    '<summary>Check the next interface.</summary>',
    '<think>fixture</think>Brief public summary.',
    '<thinking>fixture</thinking>Public next step.'])
def test_text_presence_does_not_claim_forecast_quality(text):
    assert has_public_text(text)  # In particular, OK is not a verified forecast.


def test_tool_only_add_continues_with_lexical_reminder(tmp_path):
    a = Agent(llm=Script(
        response(call('memory_add', {'content': 'saved exactly'}, 'a1')),
        response(content='A public next step. <no_intervention/>'),
        response(content='Done. <no_intervention/>')))
    install(a, tmp_path)
    result = run(a)
    assert [operation.action for operation in result.operations] == ['add']
    assert len(a.llm.calls) == 2 and len(a.memory.knowledge) == 1
    assert [row['system'] for row in a.llm.calls] == [UNIFIED_SYSTEM, REMINDED]
    assert a.llm.calls[1]['prompt'] == 'Continue.'
    assert sum(m.get('tool_call_id') == 'a1' for m in a.llm.calls[1]['message_history']) == 1
    run(a, 'Exact raw batch <history>not rewritten</history>', 8)
    assert len(a.llm.calls) == 3
    assert a.llm.calls[2]['system'] == UNIFIED_SYSTEM
    assert a.llm.calls[2]['prompt'] == 'Exact raw batch <history>not rewritten</history>'
    assert PUBLIC_FORECAST_REMINDER not in str(a._phase1_history)
    assert a._phase2_history == []
    assert [row['system'] for row in rows(tmp_path, 'memory_payload.jsonl')] == [
        UNIFIED_SYSTEM, REMINDED, UNIFIED_SYSTEM]


def test_read_continuation_keeps_receipts_and_never_stacks_reminders():
    a = Agent(llm=Script(response(call('memory_read', {'bank_id': 'knowledge'}, 'r1')),
        response(call('memory_add', {'content': 'saved'}, 'a1'), content='...'),
        response(call('memory_read', {'bank_id': 'knowledge'}, 'r2')),
        response(content='Public summary. <no_intervention/>')))
    result = run(a)
    assert [operation.action for operation in result.operations] == ['read', 'add', 'read']
    assert len(a.llm.calls) == 4
    assert [row['system'] for row in a.llm.calls] == [
        UNIFIED_SYSTEM, REMINDED, REMINDED, REMINDED]
    for row in a.llm.calls[1:4]:
        assert row['prompt'] == 'Continue.'
        assert row['system'].count(PUBLIC_FORECAST_REMINDER) == 1
    assert [m['tool_call_id'] for m in a.llm.calls[3]['message_history']
            if m['role'] == 'tool'] == ['r1', 'a1', 'r2']
    assert len(a.memory.knowledge) == 1


def test_error_recovery_is_unchanged_and_not_triggered_by_missing_text():
    a = Agent(llm=Script(response(call('unknown', ident='bad')),
        response(call('memory_add', {'content': 'recovered'}, 'good'), content='Public summary.'),
        response(content='Done. <no_intervention/>')))
    result = run(a)
    assert len(a.llm.calls) == 3
    assert [operation.success for operation in result.operations] == [False, True]
    assert [row['system'] for row in a.llm.calls] == [
        UNIFIED_SYSTEM, REMINDED, UNIFIED_SYSTEM]
    assert json.loads(a.llm.calls[1]['message_history'][-1]['content'])['success'] is False


def test_reasoning_only_recovery_preserves_native_state():
    signed = [{'type': 'thinking', 'thinking': 'private fixture', 'signature': 'signed-fixture'}]
    opaque = [{'type': 'reasoning', 'id': 'opaque-fixture', 'encrypted_content': 'encrypted-fixture'}]
    a = Agent(llm=Script(response(content='', thinking_blocks=signed, openai_output_items=opaque),
        response(content='Public summary. <no_intervention/>')))
    run(a)
    assert len(a.llm.calls) == 2 and not a.memory.knowledge
    assert a.llm.calls[1]['system'] == REMINDED
    assert a.llm.calls[1]['prompt'] == DECISION_RECOVERY_PROMPT
    history = a.llm.calls[1]['message_history']
    assert history[-1]['thinking_blocks'] == signed
    assert history[-1]['_openai_output_items'] == opaque
    assert 'content' not in history[-1]
    assert 'private fixture' not in a.llm.calls[1]['system']


def test_reset_clears_pending_but_does_not_delete_memory():
    a = Agent(llm=Script(response(call('memory_add', {'content': 'retained'}, 'a1'),
                                content='<no_intervention/>'), response()))
    run(a)
    assert a._p1_public_text_missing
    a.reset_conversation_history()
    run(a, task='Different task')
    assert a.llm.calls[1]['system'] == UNIFIED_SYSTEM
    assert 'Original exact task' not in str(a.llm.calls[1])
    assert len(a.memory.knowledge) == 1


@pytest.mark.parametrize('provider', ['openai', 'anthropic'])
def test_provider_requests_and_public_audit_keep_private_state_private(provider, monkeypatch, tmp_path):
    replies = [
        {'text': '', 'calls': [('a1', 'memory_add', {'content': 'Saved fact.'})]},
        {'text': '<no_intervention/>'},
        {'text': 'Brief next-step summary.', 'calls': [('a2', 'memory_add', {'content': 'Next fact.'})]},
        {'text': '<no_intervention/>'}]
    llm, wire = provider_llm(provider, replies, monkeypatch)
    a = Agent(llm=llm)
    install(a, tmp_path)

    async def exercise():
        for step in (0, 8):
            a.set_phase1_context(task='Exact original task', trajectory=f'Exact batch {step}')
            await a.process('Unchanged P2 observation', step)
        if provider == 'openai':
            await llm.client.close()
    asyncio.run(exercise())
    assert len(wire) == 4 and len(a.memory.knowledge) == 2
    if provider == 'openai':
        assert [row['instructions'] for row in wire] == [
            UNIFIED_SYSTEM, REMINDED, REMINDED, UNIFIED_SYSTEM]
        assert any(item.get('encrypted_content') == 'opaque-private-fixture'
                   for item in wire[2]['input'])
        assert wire[2]['input'][-1] == {'role': 'user', 'content': 'Exact batch 8'}
    else:
        assert [''.join(block['text'] for block in row['system']) for row in wire] == [
            UNIFIED_SYSTEM, REMINDED, REMINDED, UNIFIED_SYSTEM]
        assert any(block.get('signature') == 'signed-private-fixture'
                   for item in wire[2]['messages'] for block in item['content'])
    visible = ''.join(path.read_text() for path in tmp_path.glob('*.jsonl'))
    assert 'opaque-private-fixture' not in visible
    assert 'private-fixture' not in visible and 'signed-private-fixture' not in visible
    assert [row['system'] for row in rows(tmp_path, 'memory_payload.jsonl')] == [
        UNIFIED_SYSTEM, REMINDED, REMINDED, UNIFIED_SYSTEM]
