"""Two-tool transport and recovery contracts, with no provider requests."""
import copy
import json
import socket
from types import SimpleNamespace

import pytest

from test_predictive_memory_read import Agent, Script, call, receipts, response, run
from memory_agent.memory.context_predictive_memory_agent import PMAPhaseError
from memory_agent.memory.ga_context_history import GAHistoryIntegrityError
from memory_agent.memory.read_context_predictive_memory_agent import (
    BANK_TOOLS, MAX_CONSECUTIVE_TOOL_ERROR_ROUNDS)


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    original_connect = socket.socket.connect
    original_socketpair = socket.socketpair
    def blocked(*args, **kwargs):
        raise AssertionError('Offline tool test attempted network access')
    def local_socketpair(*args, **kwargs):
        # Windows implements asyncio's local wakeup socketpair with a loopback
        # connect. Permit only that stdlib operation, not provider connections.
        with monkeypatch.context() as local:
            local.setattr(socket.socket, 'connect', original_connect)
            return original_socketpair(*args, **kwargs)
    monkeypatch.setattr(socket.socket, 'connect', blocked)
    monkeypatch.setattr(socket, 'create_connection', blocked)
    monkeypatch.setattr(socket, 'socketpair', local_socketpair)


def test_unknown_tool_recovers_before_p2_without_task_execution(tmp_path):
    marker = tmp_path / 'must-not-exist'
    script = f'open({str(marker)!r}, "w").write("bad")'
    a = Agent(llm=Script(response(call('code_run', {'script': script}, 'bad')),
        response(call('memory_add', {'content': 'recovered exact text'}, 'good')),
        response(), response()))
    result = run(a)
    assert len(a.llm.calls) == 4
    assert all(c.get('tools') for c in a.llm.calls[:3])
    error = receipts(a.llm.calls[1])[0]
    assert not error['success'] and error['action'] == 'code_run'
    assert 'memory_add, memory_read' in error['error']
    assert a.llm.calls[1]['message_history'][-1]['tool_call_id'] == 'bad'
    assert [o.success for o in result.operations] == [False, True]
    assert len(a.memory.knowledge) == 1 and not marker.exists()
    assert receipts(a.llm.calls[2])[-1]['memory_id'] == a.memory.knowledge[0].id
    run(a, 'next exact trajectory', 8)
    assert len(a.memory.knowledge) == 1  # History never replays calls.


@pytest.mark.parametrize('name,args', [
    ('memory_read', {'query': 'must not filter'}),
    ('memory_read', {'scope': 'all'}),
    ('memory_read', {'scope': 'recent'}),
    ('memory_read', {'scope': 'all', 'query': 'unsupported'}),
    ('memory_read', {'_noargs': 'different'}),
    ('memory_read', {'_noargs': 'unused'}),
    ('memory_read', {'_noargs': None}),
    ('memory_read', {'_noargs': 'unused', 'query': 'mixed'}),
    ('memory_add', {'content': 'must not save', 'extra': True}),
    ('memory_add', {'content': ''}),
    ('memory_add', {'content': 1}),
    ('memory_add', {}),
])
def test_invalid_arguments_are_receipted_same_wake_and_do_not_mutate(name, args):
    a = Agent(llm=Script(response(call(name, args, 'invalid')), response()))
    result = run(a)
    assert len(a.llm.calls) == 3 and a.llm.calls[1].get('tools')
    assert not receipts(a.llm.calls[1])[0]['success']
    assert result.operations[0].success is False and not a.memory.knowledge
    tool_call = next(m for m in a.llm.calls[1]['message_history'] if m.get('tool_calls'))
    assert json.loads(tool_call['tool_calls'][0]['function']['arguments']) == args


def test_error_limit_fails_closed_with_all_native_receipts():
    count = MAX_CONSECUTIVE_TOOL_ERROR_ROUNDS
    a = Agent(llm=Script(*(response(call('code_run', {}, f'bad-{i}'))
                           for i in range(count))))
    with pytest.raises(PMAPhaseError) as caught:
        run(a)
    assert caught.value.phase == 'P1'
    assert caught.value.error_type == 'PMAToolRecoveryExhausted'
    assert 'P2 not entered' in str(caught.value.__cause__)
    assert len(a.llm.calls) == count and all(c.get('tools') for c in a.llm.calls)
    results = [b for m in a._phase1_history for b in m['content']
               if b.get('type') == 'tool_result']
    assert [b['tool_use_id'] for b in results] == [f'bad-{i}' for i in range(count)]
    assert all(not json.loads(b['content'])['success'] for b in results)
    assert len(a._phase1_operations) == count and not a.memory.knowledge


@pytest.mark.parametrize('success_call', [
    call('memory_add', {'content': 'valid'}, 'valid'),
    call('memory_read', {}, 'valid'),
])
def test_error_budget_is_consecutive_not_cumulative(success_call):
    replies = [response(call('unknown', {}, f'bad-{i}')) for i in range(2)]
    replies += [response(success_call)]
    replies += [response(call('unknown', {}, f'bad-{i}')) for i in range(2, 4)]
    a = Agent(llm=Script(*replies, response()))
    result = run(a)
    assert len(a.llm.calls) == 7 and len(result.operations) == 5
    assert len(a.memory.knowledge) == int(success_call['function']['name'] == 'memory_add')


def test_successful_reads_are_not_capped_by_error_recovery_limit():
    count = MAX_CONSECUTIVE_TOOL_ERROR_ROUNDS + 2
    a = Agent(llm=Script(*(response(call('memory_read', {}, f'read-{i}'))
                           for i in range(count)), response()))
    result = run(a)
    assert len(result.operations) == count and all(o.success for o in result.operations)
    assert len(a.llm.calls) == count + 2


def test_error_budget_resets_on_a_new_wake():
    replies = []
    for wake in range(2):
        replies += [response(call('unknown', {}, f'bad-{wake}-{i}')) for i in range(2)]
        replies.append(response())
    a = Agent(llm=Script(*replies))
    run(a)
    result = run(a, 'next exact trajectory', 8)
    assert len(a.llm.calls) == 8 and len(result.operations) == 2


def test_mixed_round_with_an_error_counts_toward_recovery_limit():
    replies = [response(call('memory_add', {'content': str(i)}, f'good-{i}'),
                        call('unknown', {}, f'bad-{i}'))
               for i in range(MAX_CONSECUTIVE_TOOL_ERROR_ROUNDS)]
    a = Agent(llm=Script(*replies))
    with pytest.raises(PMAPhaseError):
        run(a)
    assert len(a.llm.calls) == MAX_CONSECUTIVE_TOOL_ERROR_ROUNDS
    assert len(a.memory.knowledge) == MAX_CONSECUTIVE_TOOL_ERROR_ROUNDS
    assert all(c.get('tools') for c in a.llm.calls)


@pytest.mark.parametrize('arguments', ['{', '[]', 'null', '"text"'])
def test_invalid_native_envelope_does_not_execute_any_call(arguments):
    bad = {'id': 'bad', 'function': {'name': 'memory_read', 'arguments': arguments}}
    a = Agent(llm=Script(response(call('memory_add', {'content': 'unsafe'}, 'first'), bad)))
    with pytest.raises(GAHistoryIntegrityError):
        run(a)
    assert not a.memory.knowledge and len(a.llm.calls) == 1


@pytest.mark.parametrize('ident,arguments', [
    ('bad', '{'), ('bad', '[]'), (None, '{}'), ('first', '{}'),
])
def test_object_native_envelope_is_validated_before_any_write(ident, arguments):
    bad = SimpleNamespace(id=ident,
        function=SimpleNamespace(name='memory_read', arguments=arguments))
    a = Agent(llm=Script(response(call('memory_add', {'content': 'unsafe'}, 'first'), bad)))
    with pytest.raises(GAHistoryIntegrityError):
        run(a)
    assert not a.memory.knowledge and len(a.llm.calls) == 1


@pytest.mark.parametrize('nonempty_bank', [False, True])
@pytest.mark.parametrize('invalid_call', [
    ('code_run', {'script': 'DO NOT EXECUTE'}),
    ('memory_read', {'_noargs': 'unused'}),
    ('memory_read', {'scope': 'all'}),
])
def test_real_litellm_anthropic_tools_and_receipts_roundtrip(monkeypatch, nonempty_bank, invalid_call):
    from harbor.llms.lite_llm import LiteLLM
    from harbor.llms import lite_llm
    from litellm.llms.anthropic.chat.transformation import AnthropicConfig
    import httpx
    import litellm

    signed = [{'type': 'thinking', 'thinking': 'private synthetic',
               'signature': 'synthetic-signature'}]
    provider_replies = iter([
        [('bad', *invalid_call)],
        [('read', 'memory_read', {})],
        [('add', 'memory_add', {'content': 'saved exact <tool_call> text'})],
        [], [],
    ])
    bodies, wire = [], []

    async def completion(**kwargs):
        config = AnthropicConfig()
        wire.append(copy.deepcopy(kwargs))
        options = {'max_tokens': 1024, 'thinking': {'type': 'adaptive'}}
        if kwargs.get('tools'):
            mapped, mcp_servers = config._map_tools(copy.deepcopy(kwargs['tools']))
            assert not mcp_servers
            options['tools'] = mapped
        body = config.transform_request(model='claude-opus-4-8',
            messages=copy.deepcopy(kwargs['messages']), optional_params=options,
            litellm_params={}, headers={})
        bodies.append(body)
        calls = [{'type': 'tool_use', 'id': ident, 'name': name, 'input': args}
                 for ident, name, args in next(provider_replies)]
        content = copy.deepcopy(signed) + (calls or [
            {'type': 'text', 'text': '<no_intervention/>'}])
        raw = httpx.Response(200, json={
            'id': 'msg_offline_fixture', 'type': 'message', 'role': 'assistant',
            'model': 'claude-opus-4-8', 'content': content,
            'stop_reason': 'tool_use' if calls else 'end_turn', 'stop_sequence': None,
            'usage': {'input_tokens': 1, 'output_tokens': 1}})
        return config.transform_response(model='claude-opus-4-8', raw_response=raw,
            model_response=litellm.ModelResponse(),
            logging_obj=SimpleNamespace(post_call=lambda **kwargs: None),
            request_data=body, messages=kwargs['messages'], optional_params=options,
            litellm_params={}, encoding=None)

    monkeypatch.setattr(lite_llm.litellm, 'acompletion', completion)
    a = Agent(llm=LiteLLM('anthropic/claude-opus-4-8', api_key='synthetic-not-a-key'))
    if nonempty_bank:
        a.memory.save_knowledge('existing exact saved information')
    result = run(a, task='Exact task mentions code_run and memory_read. Do not rewrite it.')
    assert len(wire) == 5 and [o.success for o in result.operations] == [False, True, True]
    read = result.operations[1]
    assert ('existing exact saved information' in read.content) == nonempty_bank
    assert ('(empty)' in read.content) != nonempty_bank
    assert len(a.memory.knowledge) == 1 + int(nonempty_bank)
    for body in bodies[:-1]:
        assert [t['name'] for t in body['tools']] == ['memory_add', 'memory_read']
        for expected, actual in zip(BANK_TOOLS, body['tools']):
            assert actual['input_schema'] == expected['function']['parameters']
    for index, expected in [(1, ['bad']), (2, ['bad', 'read']), (3, ['bad', 'read', 'add'])]:
        blocks = [b for m in bodies[index]['messages'] for b in m['content']]
        assert [b['id'] for b in blocks if b['type'] == 'tool_use'] == expected
        assert [b['tool_use_id'] for b in blocks if b['type'] == 'tool_result'] == expected
        assert any(b.get('signature') == 'synthetic-signature' for b in blocks)
        assert all(b.get('text') for b in blocks if b['type'] == 'text')
        bad_call = next(b for b in blocks if b.get('id') == 'bad')
        assert bad_call['input'] == invalid_call[1]
        error = next(b for b in blocks if b.get('tool_use_id') == 'bad')
        content = error['content']
        if isinstance(content, list):  # Anthropic cached text-block form.
            content = ''.join(b['text'] for b in content)
        assert not json.loads(content)['success']
    assert 'tools' not in wire[-1] and 'tools' not in bodies[-1]
    assert 'Exact task mentions code_run and memory_read. Do not rewrite it.' in str(bodies[1])
    assert 'saved exact <tool_call> text' in str(bodies[-1])
