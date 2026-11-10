"""Existing provider-native histories survive the prompt-only revision offline."""
import copy
import json

from test_predictive_memory_read import Agent, run
from test_predictive_visible_basis import install, rows
from test_predictive_tool_recovery import block_network  # noqa: F401
from memory_agent.memory.ga_context_history import compress_history_tags, prepare_history
from responses_memory_llm import response_input


def test_openai_native_items_continue_in_their_own_phase(tmp_path):
    import httpx
    from openai import AsyncOpenAI
    from responses_memory_llm import ResponsesMemoryLLM
    llm = ResponsesMemoryLLM(dict(model='gpt-6.1-sol', model_context_window=200000,
        max_tokens=8192, reasoning_effort='high', max_retries=0, read_timeout=30,
        apikey='synthetic-not-a-key', apibase='https://example.invalid/v1'))
    phases, wire = iter(['p1a', 'p2a', 'p1b', 'p2b']), []

    def handler(request):
        phase = next(phases)
        wire.append(json.loads(request.content))
        output = [{'type': 'reasoning', 'id': 'r-' + phase,
                   'encrypted_content': 'opaque-' + phase, 'summary': []},
                  {'type': 'message', 'id': 'm-' + phase, 'role': 'assistant',
                   'status': 'completed', 'content': [{'type': 'output_text',
                   'text': phase if phase.startswith('p1') else '<no_intervention/>',
                   'annotations': []}]}]
        if phase == 'p1a':
            output.append({'type': 'function_call', 'id': 'fc-a', 'call_id': 'a',
                           'name': 'memory_add', 'arguments': '{"content":"endpoint=/v1"}',
                           'status': 'completed'})
        return httpx.Response(200, json={'id': phase, 'object': 'response',
            'created_at': 1, 'status': 'completed', 'model': llm.model, 'output': output,
            'usage': {'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 2}})

    llm.client = AsyncOpenAI(api_key='synthetic-not-a-key', max_retries=0,
        base_url='https://example.invalid/v1',
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    agent = Agent(llm=llm)
    install(agent, tmp_path)
    run(agent)
    p1_native = copy.deepcopy(next(row['_openai_output_items']
        for row in agent._active_phase1 if '_openai_output_items' in row))
    p2_native = copy.deepcopy(next(row['_openai_output_items']
        for row in agent._phase2_history if '_openai_output_items' in row))
    run(agent, 'new trajectory', 8)
    assert len(wire) == 4
    for index, native, other in [(2, p1_native, p2_native), (3, p2_native, p1_native)]:
        assert all(item in wire[index]['input'] for item in native if item['type'] == 'reasoning')
        assert not any(item in wire[index]['input'] for item in other if item['type'] == 'reasoning')
    assert 'p1a' in json.dumps(wire[2]['input']) and 'p2a' not in json.dumps(wire[2]['input'])
    assert 'p2a' in json.dumps(wire[3]['input']) and 'p1a' not in json.dumps(wire[3]['input'])
    assert {'role': 'assistant', 'content': 'p1a'} in wire[2]['input']
    calls = [item for item in wire[2]['input'] if item.get('type') == 'function_call']
    outputs = [item for item in wire[2]['input'] if item.get('type') == 'function_call_output']
    assert len(calls) == len(outputs) == 1
    assert calls[0]['call_id'] == outputs[0]['call_id'] == 'a'
    assert calls[0]['name'] == 'memory_add'
    assert json.loads(calls[0]['arguments']) == {'content': 'endpoint=/v1'}
    assert json.loads(outputs[0]['output'])['success'] is True
    assert all(request['reasoning'] == {'effort': 'high'} for request in wire)
    assert all(request['store'] is False for request in wire)
    assert len(rows(tmp_path, 'memory_tool_results.jsonl')) == 2
    assert 'opaque-' not in ''.join(p.read_text() for p in tmp_path.glob('*.jsonl'))


def test_native_reasoning_stays_verbatim_when_visible_history_is_trimmed():
    native = [{'type': 'reasoning', 'id': 'r', 'encrypted_content': 'opaque-private',
               'summary': [{'type': 'summary_text', 'text': 'Provider item text'}]},
              {'type': 'message', 'content': [{'type': 'output_text', 'text': 'original'}]}]
    history = [{'role': 'assistant', 'content': [{'type': 'text',
                'text': '<tool_result>' + 'x' * 3000 + '</tool_result>'}],
                '_openai_output_items': copy.deepcopy(native)},
               {'role': 'user', 'content': [{'type': 'text', 'text': 'next'}]}]
    compress_history_tags(history, keep_recent=1, force=True)
    actual = response_input(prepare_history(history, 'Continue.'), 'Continue.')
    assert next(item for item in actual if item.get('type') == 'reasoning') == native[0]
    assert '[Truncated]' in json.dumps(actual) and 'x' * 3000 not in json.dumps(actual)


def test_claude_signed_and_redacted_blocks_replay_only_in_their_own_phase(monkeypatch):
    from harbor.llms import lite_llm
    from harbor.llms.lite_llm import LiteLLM
    from litellm.llms.anthropic.chat.transformation import AnthropicConfig
    phases = iter(['p1a', 'p2a', 'p1b', 'p2b'])
    native, wire = {}, []

    async def completion(**kwargs):
        phase = next(phases)
        wire.append(AnthropicConfig().transform_request(model='claude-opus-5',
            messages=copy.deepcopy(kwargs['messages']),
            optional_params={'max_tokens': 8192, 'thinking': {'type': 'adaptive'}},
            litellm_params={}, headers={}))
        native[phase] = [{'type': 'thinking', 'thinking': 'synthetic-' + phase,
                          'signature': 'signed-' + phase},
                         {'type': 'redacted_thinking', 'data': 'opaque-' + phase}]
        return {'choices': [{'message': {'content': 'P1 text' if kwargs.get('tools')
                        else '<no_intervention/>', 'thinking_blocks': native[phase]},
                            'finish_reason': 'stop'}]}

    monkeypatch.setattr(lite_llm.litellm, 'acompletion', completion)
    agent = Agent(llm=LiteLLM('anthropic/claude-opus-5', api_key='synthetic-not-a-key'))
    run(agent)
    run(agent, 'new trajectory', 8)
    assert len(wire) == 4
    for index, same, other in [(2, 'p1a', 'p2a'), (3, 'p2a', 'p1a')]:
        blocks = [block for message in wire[index]['messages'] for block in message['content']]
        assert all(block in blocks for block in native[same])
        assert not any(block in blocks for block in native[other])
