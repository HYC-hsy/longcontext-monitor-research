"""Read-context contracts. Synthetic responses only; no model/network requests."""
import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from memory_agent.memory.read_context_predictive_memory_agent import (
    BANK_TOOLS, PHASE1_SYSTEM, UNIFIED_SYSTEM, ReadContextPredictiveMemoryAgent as Agent)
from memory_agent.memory.context_predictive_memory_agent import ContextPredictiveMemoryAgent
from memory_agent.memory.ga_context_history import GAHistoryConfig, GAHistoryIntegrityError
from memory_agent.memory.predictive_memory_agent import PHASE2_SYSTEM


def call(name, args=None, ident='call-1'):
    return {'id': ident, 'function': {'name': name, 'arguments': json.dumps(args or {})}}


_UNSET = object()

def response(*calls, content=_UNSET, **kwargs):
    if content is _UNSET:
        content = '' if calls else '<no_intervention/>'
    return SimpleNamespace(content=content, tool_calls=list(calls), **kwargs)


class Script:
    def __init__(self, *replies):
        self.replies = iter(replies)
        self.calls = []

    async def call(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        value = next(self.replies)
        if isinstance(value, BaseException):
            raise value
        return value


def run(agent, trajectory='', step=1, task='Original exact task'):
    agent.set_phase1_context(task=task, trajectory=trajectory)
    return asyncio.run(agent.process('UNCHANGED P2 OBSERVATION', step))


def receipts(request):
    return [json.loads(m['content']) for m in request['message_history'] if m['role'] == 'tool']


def test_prompt_schema_and_isolation():
    assert 'first anticipate the problems' in PHASE1_SYSTEM
    assert 'over the next 10 turns' in PHASE1_SYSTEM
    assert 'may be useful' not in PHASE1_SYSTEM
    assert [t['function']['name'] for t in BANK_TOOLS] == ['memory_add', 'memory_read']
    read_schema = BANK_TOOLS[1]['function']['parameters']
    assert read_schema == {'type': 'object', 'properties': {
        'bank_id': {'type': 'string', 'enum': ['knowledge'],
                    'description': 'Memory bank to read. Use knowledge.'}
    }, 'required': ['bank_id'], 'additionalProperties': False}
    assert BANK_TOOLS[1]['function']['description'] == (
        'Read all information currently saved in the knowledge memory bank.')
    a = Agent(llm=Script(response()))
    schema = a.get_tools_schema()
    schema[0]['function']['name'] = 'mutated'
    assert a.get_tools_schema() == BANK_TOOLS
    a.memory.save_knowledge('BANK NOT AUTOMATICALLY IN P1')
    run(a)
    assert 'BANK NOT AUTOMATICALLY' not in str(a.llm.calls[0])
    assert len(a.llm.calls) == 1
    assert a.llm.calls[0]['system'] == UNIFIED_SYSTEM
    assert a._phase2_history == []
    assert a._build_phase2_prompt('x', 4) == ContextPredictiveMemoryAgent()._build_phase2_prompt.__func__(a, 'x', 4)
    with pytest.raises(ValueError):
        Agent(use_structured_tools=False)


@pytest.mark.parametrize('nonempty', [False, True])
def test_read_add_finish_same_wake(nonempty):
    llm = Script(response(call('memory_read', {'bank_id': 'knowledge'})), response(call('memory_add', {'content': 'new'}, 'add-2')), response())
    a = Agent(llm=llm)
    if nonempty:
        a.memory.save_knowledge('existing original text')
        a.memory.save_procedural('legacy flat entry')
    before = copy.deepcopy(a.memory.to_dict())
    expected_read = a._format_memory_bank()
    result = run(a)
    assert len(llm.calls) == 3
    assert [op.action for op in result.operations] == ['read', 'add']
    assert not result.should_inject
    read = receipts(llm.calls[1])[0]
    assert read['success'] and read['action'] == 'read'
    assert read['content'] == expected_read
    assert a.memory.to_dict()['knowledge'][:-1] == before['knowledge']
    assert a.memory.to_dict()['procedural'] == before['procedural']
    assert ('existing original text' in read['content']) == nonempty
    assert ('legacy flat entry' in read['content']) == nonempty
    assert ('(empty)' in read['content']) != nonempty
    assert 'new' not in read['content']
    assert receipts(llm.calls[2])[-1]['memory_id'] == a.memory.knowledge[-1].id
    assert 'new' in str(llm.calls[-1]['message_history'])
    assert llm.calls[1]['prompt'] == llm.calls[2]['prompt'] == 'Continue.'


@pytest.mark.parametrize('add', [False, True])
def test_no_read_single_call_next_wake_does_not_reexecute(add):
    first = response(call('memory_add', {'content': 'saved'}), content='<no_intervention/>') if add else response()
    a = Agent(llm=Script(first, response()))
    run(a)
    assert len(a.llm.calls) == 1
    run(a, 'Only eight new actor steps', 8)
    assert len(a.llm.calls) == 2
    request = a.llm.calls[1]
    assert request['prompt'] == 'Only eight new actor steps'
    assert str(request).count('Original exact task') == 1
    assert len(a.memory.knowledge) == int(add)
    assert len(receipts(request)) == int(add)
    assert a._phase2_history == []
    assert 'UNCHANGED P2 OBSERVATION' not in str(request)


def test_ordered_multiple_reads_and_adds_are_snapshots():
    a = Agent(llm=Script(response(call('memory_read', {'bank_id': 'knowledge'}, ident='r1'),
        call('memory_add', {'content': 'value'}, 'a1'), call('memory_read', {'bank_id': 'knowledge'}, ident='r2')), response()))
    result = run(a)
    first, saved, last = receipts(a.llm.calls[1])
    assert '(empty)' in first['content'] and 'value' not in first['content']
    assert 'value' in last['content'] and saved['memory_id'] in last['content']
    assert len(result.operations) == 3 and len(a.memory.knowledge) == 1


@pytest.mark.parametrize('calls', [
    [call('memory_add', {'content': 'must not save'}), call('memory_read', {'bank_id': 'knowledge'})],
    [call('memory_add', {'content': 'must not save'}), call('memory_read', {'bank_id': 'knowledge'}, ident=None)],
    [{'id': 'bad-json', 'function': {'name': 'memory_read', 'arguments': '{'}}],
])
def test_integrity_rejects_entire_envelope_before_write(calls):
    a = Agent(llm=Script(response(*calls)))
    with pytest.raises(GAHistoryIntegrityError):
        run(a)
    assert a.memory.knowledge == [] and len(a.llm.calls) == 1


def test_tool_errors_return_receipts_and_native_read_beats_xml():
    a = Agent(llm=Script(response(call('memory_read', {'query': 'unsupported'}),
        call('memory_add', {'content': ''}, 'a2'), call('unknown', ident='a3'),
        content='<tool_call><function=memory_add>DO NOT EXECUTE</function></tool_call>'), response()))
    run(a)
    assert not a.memory.knowledge
    assert all(not r['success'] for r in receipts(a.llm.calls[1]))


def test_missing_signed_blocks_and_provider_failure_fail_closed():
    for r in [response(call('memory_read', {'bank_id': 'knowledge'}), reasoning_content='private'), RuntimeError('transport failed')]:
        a = Agent(llm=Script(r))
        with pytest.raises(GAHistoryIntegrityError):
            run(a)
        assert len(a.llm.calls) == 1


def test_long_history_pins_task_current_wake_and_tool_pairs(monkeypatch):
    monkeypatch.setattr(GAHistoryConfig, 'context_win', 800)
    replies = [response(content='history' * 100 + '<no_intervention/>') for _ in range(8)]
    replies += [response(call('memory_read', {'bank_id': 'knowledge'}, ident='final-read')), response()]
    a = Agent(llm=Script(*replies))
    for step in range(9):
        run(a, ('old' if step < 8 else 'LATEST') * 100, step)
    latest = a.llm.calls[-1]
    assert 'Original exact task' in str(latest)
    assert 'LATEST' * 100 in str(latest)
    assert any(m.get('tool_call_id') == 'final-read' for m in latest['message_history'])
    assert len(a._phase1_history) < 20
    assert latest['message_history'][0]['content'] == [{'type': 'text', 'text': '[Task Description]\nOriginal exact task'}]


def test_reset_bank_isolation_and_oversize(monkeypatch):
    a = Agent(llm=Script(response(call('memory_add', {'content': 'kept'}), content='<no_intervention/>'), response()))
    run(a)
    a.reset_conversation_history()
    run(a, task='Entirely new task')
    assert 'Original exact task' not in str(a.llm.calls[-1])
    assert len(a.memory.knowledge) == 1 and not Agent().memory.knowledge
    monkeypatch.setattr(GAHistoryConfig, 'context_win', 10)
    oversized = Agent(llm=Script(response()))
    run(oversized, task='unaltered task' * 100)
    assert oversized.llm.calls[0]['prompt'] == '[Task Description]\n' + 'unaltered task' * 100
    assert len(oversized.llm.calls) == 1
