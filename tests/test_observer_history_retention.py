"""Observer-only retention with real provider serialization and no network."""
import asyncio
import copy
import json
from types import SimpleNamespace

import httpx
import pytest

from test_predictive_memory_read import Agent
from test_predictive_tool_recovery import block_network  # noqa: F401
from test_predictive_visible_basis import install
from memory_agent.memory.ga_context_history import (
    GAHistoryConfig, GAHistoryIntegrityError, provider_history, trim_observer_history)
from responses_memory_llm import ResponsesMemoryLLM, response_input


def _profile():
    return dict(model='gpt-6.1-sol', model_context_window=200000, max_tokens=8192,
        reasoning_effort='high', max_retries=0, read_timeout=30,
        apikey='synthetic-not-a-key', apibase='https://example.invalid/v1')


def _opaque(ident):
    return {'type': 'reasoning', 'id': 'r-' + ident,
            'encrypted_content': 'opaque-' + ident, 'summary': []}


@pytest.mark.parametrize('empty_wake', [0, 1, 2])
def test_reasoning_only_is_replayed_without_invented_text_across_wakes(empty_wake, tmp_path):
    from openai import AsyncOpenAI
    wire, outputs = [], {}

    def handler(request):
        label = f'call-{len(wire)}'
        wire.append(json.loads(request.content))
        output = [_opaque(label)]
        if len(wire) - 1 != empty_wake:
            output.append({'type': 'message', 'id': 'm-' + label,
                'role': 'assistant', 'status': 'completed', 'content': [{
                    'type': 'output_text', 'text': '<no_intervention/>', 'annotations': []}]})
        outputs[label] = copy.deepcopy(output)
        return httpx.Response(200, json={'id': label, 'object': 'response',
            'created_at': 1, 'status': 'completed', 'model': 'gpt-6.1-sol',
            'output': output, 'usage': {'input_tokens': 1, 'output_tokens': 1,
                                     'total_tokens': 2}})

    async def run():
        llm = ResponsesMemoryLLM(_profile())
        await llm.client.close()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
            llm.client = AsyncOpenAI(api_key='synthetic-not-a-key', max_retries=0,
                base_url='https://example.invalid/v1', http_client=http_client)
            agent = Agent(llm=llm)
            install(agent, tmp_path)
            for epoch in range(3):
                agent.set_phase1_context(task='Exact original task', trajectory=f'batch-{epoch}')
                await agent.process(f'Exact original task\nbatch-{epoch}', epoch * 8)
        return agent

    agent = asyncio.run(run())
    assert len(wire) == 4
    for index in range(1, 4):
        for earlier in range(index):
            assert _opaque(f'call-{earlier}') in wire[index]['input']
    # The reasoning-only response is retained without an invented message item.
    assert outputs[f'call-{empty_wake}'] == [_opaque(f'call-{empty_wake}')]
    assert not any(item.get('role') == 'assistant' and item.get('content') == '.'
                   for request in wire for item in request['input'])
    assert all('include' not in request for request in wire)  # Keep the original request interface.
    assert all(request['store'] is False and request['reasoning'] == {'effort': 'high'}
               for request in wire)
    assert agent._phase1_history and agent._phase2_history == []
    visible = ''.join(path.read_text() for path in tmp_path.glob('*.jsonl'))
    assert 'opaque-' not in visible


def test_closed_tool_groups_evict_together_and_do_not_mutate_source():
    signature = [{'type': 'thinking', 'thinking': 'private-fixture', 'signature': 'signed'},
                 {'type': 'redacted_thinking', 'data': 'redacted'}]
    def group(ident):
        return [{'role': 'user', 'content': [{'type': 'text', 'text': ident * 1000}]},
            {'role': 'assistant', 'content': [{'type': 'tool_use', 'id': ident,
                'name': 'memory_read', 'input': {'bank_id': 'knowledge'}}],
                '_provider_thinking_blocks': copy.deepcopy(signature)},
            {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': ident,
                'content': json.dumps({'content': ident * 1000})}]}]
    old = group('old') + group('recent')
    original = copy.deepcopy(old)
    protected = [{'role': 'user', 'content': [{'type': 'text', 'text': 'Exact original task'}]}]
    trim_observer_history(old, protected, SimpleNamespace(context_win=10000,
                          trim_keep_rate=0.6, cut_msg_interval=5))
    assert old == original  # Below cap: every signature, call and receipt is exact.
    trim_observer_history(old, protected, SimpleNamespace(context_win=500,
                          trim_keep_rate=0.6, cut_msg_interval=5))
    assert old == []  # Over cap: no sanitized or orphaned result remains.
    assert original[1]['_provider_thinking_blocks'] == signature
    assert 'Exact original task' in str(protected)


@pytest.mark.parametrize('messages', [
    [{'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': 'orphan', 'content': 'x'}]}],
    [{'role': 'assistant', 'content': [{'type': 'tool_use', 'id': 'pending', 'name': 'read', 'input': {}}]}],
])
def test_invalid_native_groups_fail_before_sanitization(messages):
    with pytest.raises(GAHistoryIntegrityError):
        trim_observer_history(messages, [], GAHistoryConfig())


def test_compresses_only_old_visible_text_not_provider_or_native_payloads():
    native = [_opaque('old'), {'type': 'message', 'content': [{
        'type': 'output_text', 'text': '<tool_result>' + 'x' * 5000 + '</tool_result>'}]}]
    old = [{'role': 'assistant', 'content': [{'type': 'text', 'text': native[1]['content'][0]['text']}],
            '_openai_output_items': copy.deepcopy(native)}]
    old += [{'role': 'user', 'content': [{'type': 'text', 'text': 'short'}]} for _ in range(11)]
    protected = [{'role': 'user', 'content': [{'type': 'text', 'text': '<tool_result>' + 'z' * 2000 + '</tool_result>'}]}]
    before = copy.deepcopy(protected)
    trim_observer_history(old, protected, GAHistoryConfig(), round_number=5)
    actual = response_input(provider_history(old), 'Continue.')
    assert '[Truncated]' in str(actual)
    assert old[0]['_openai_output_items'] == native
    assert native[0] in actual
    assert protected == before


@pytest.mark.parametrize('provider', ['responses', 'claude'])
def test_real_http_body_preserves_oversize_current_batch_and_native_history(provider, monkeypatch):
    """OpenAI SDK and LiteLLM provider HTTP serialization with mocked transport.

    Invoke LiteLLM's real Anthropic handler directly to avoid an unrelated MCP
    dependency import in its global router. No request/response is fabricated
    above the HTTP transport boundary.
    """
    wire = []
    labels = ['first', 'read', 'decide', 'next']
    batch = '<tool_result>' + '当前原文-α-🙂-EXACT-' * 8000 + '</tool_result>'
    task = 'Original task must stay exact.'
    signatures = {}

    def handler(request):
        label = labels[len(wire)]
        wire.append(json.loads(request.content))
        tool = label == 'read'
        if provider == 'responses':
            output = [_opaque(label)]
            if tool:
                output.append({'type': 'function_call', 'id': 'fc-read-b',
                    'call_id': 'read-b', 'name': 'memory_read',
                    'arguments': '{"bank_id":"knowledge"}', 'status': 'completed'})
            else:
                output.append({'type': 'message', 'id': 'm-' + label, 'role': 'assistant',
                    'status': 'completed', 'content': [{'type': 'output_text',
                    'text': '<no_intervention/>',
                    'annotations': []}]})
            return httpx.Response(200, json={'id': label, 'object': 'response',
                'created_at': 1, 'status': 'completed', 'model': 'gpt-6.1-sol',
                'output': output, 'usage': {'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 2}})
        signed = [{'type': 'thinking', 'thinking': 'private-' + label, 'signature': 'signed-' + label},
                  {'type': 'redacted_thinking', 'data': 'redacted-' + label}]
        signatures[label] = signed
        content = copy.deepcopy(signed) + ([{'type': 'tool_use', 'id': 'read-b',
            'name': 'memory_read', 'input': {'bank_id': 'knowledge'}}] if tool else [{
            'type': 'text', 'text': '<no_intervention/>'}])
        return httpx.Response(200, json={'id': 'msg-' + label, 'type': 'message',
            'role': 'assistant', 'model': 'claude-opus-4-8', 'content': content,
            'stop_reason': 'tool_use' if tool else 'end_turn', 'stop_sequence': None,
            'usage': {'input_tokens': 1, 'output_tokens': 1}})

    async def run():
        transport = httpx.MockTransport(handler)
        if provider == 'responses':
            from openai import AsyncOpenAI
            llm = ResponsesMemoryLLM(_profile())
            await llm.client.close()
            llm.client = AsyncOpenAI(api_key='synthetic-not-a-key', max_retries=0,
                base_url='https://example.invalid/v1', http_client=httpx.AsyncClient(transport=transport))
            close = llm.client.close
        else:
            import litellm
            from harbor.llms import lite_llm
            from harbor.llms.lite_llm import LiteLLM
            from litellm.llms.anthropic.chat import handler as anthropic_handler
            from litellm.llms.anthropic.chat.transformation import AnthropicConfig
            from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler
            client = AsyncHTTPHandler(transport=transport)
            async def provider_completion(**kwargs):
                config = AnthropicConfig()
                options = {'max_tokens': 8192, 'thinking': {'type': 'adaptive'}}
                if kwargs.get('tools'):
                    options['tools'], _ = config._map_tools(copy.deepcopy(kwargs['tools']))
                body = config.transform_request(model='claude-opus-4-8',
                    messages=copy.deepcopy(kwargs['messages']), optional_params=options,
                    litellm_params={}, headers={})
                return await anthropic_handler.AnthropicChatCompletion().acompletion_function(
                    model='claude-opus-4-8', messages=kwargs['messages'],
                    api_base='https://example.invalid/v1/messages', custom_prompt_dict={},
                    model_response=litellm.ModelResponse(), print_verbose=lambda *args: None,
                    timeout=30, encoding=None, api_key='synthetic-not-a-key',
                    logging_obj=SimpleNamespace(post_call=lambda **kwargs: None), stream=False,
                    _is_function_call=bool(kwargs.get('tools')), data=body, optional_params=options,
                    json_mode=False, litellm_params={}, provider_config=config, client=client)
            monkeypatch.setattr(lite_llm.litellm, 'acompletion', provider_completion)
            llm = LiteLLM('anthropic/claude-opus-4-8', api_key='synthetic-not-a-key',
                          api_base='https://example.invalid', reasoning_effort='high')
            close = client.client.aclose
        agent = Agent(llm=llm)
        agent.set_phase1_context(task=task, trajectory='')
        await agent.process(task, 0)
        agent.set_phase1_context(task=task, trajectory=batch)
        await agent.process(task + '\n' + batch, 8)
        assert agent._history_transforms[-1]['protected_over_budget'] is True
        # A large *budget* on the next wake permits checking previously protected
        # tool groups and opaque metadata through their next real HTTP request.
        monkeypatch.setattr(GAHistoryConfig, 'context_win', 200000)
        agent.set_phase1_context(task=task, trajectory='next complete batch')
        await agent.process(task + '\nnext complete batch', 16)
        await close()
        return agent

    asyncio.run(run())
    assert len(wire) == 4
    for index in (1, 2, 3):
        body = wire[index]['input'] if provider == 'responses' else wire[index]['messages']
        text = json.dumps(body, ensure_ascii=False)
        assert batch in text and task in text
    if provider == 'responses':
        assert _opaque('read') in wire[3]['input']
        assert _opaque('decide') in wire[3]['input']
        calls = [x['call_id'] for x in wire[3]['input'] if x.get('type') == 'function_call']
        receipts = [x['call_id'] for x in wire[3]['input'] if x.get('type') == 'function_call_output']
    else:
        blocks = [block for message in wire[3]['messages'] for block in message['content']]
        assert all(block in blocks for block in signatures['read'])
        assert all(block in blocks for block in signatures['decide'])
        calls = [x['id'] for x in blocks if x.get('type') == 'tool_use']
        receipts = [x['tool_use_id'] for x in blocks if x.get('type') == 'tool_result']
    assert calls == receipts == ['read-b']


def test_empty_observer_reply_never_fabricates_an_utterance():
    assert provider_history([{"role": "assistant", "content": []}]) == []
    for field, value in (("_openai_output_items", [_opaque("only")]),
            ("_provider_thinking_blocks", [{"type": "redacted_thinking", "data": "opaque"}])):
        converted = provider_history([{"role": "assistant", "content": [], field: value}])
        assert len(converted) == 1 and "content" not in converted[0]
