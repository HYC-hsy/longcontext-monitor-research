"""Documented public summaries and opaque continuity, using synthetic interfaces."""
import asyncio
import copy
import json

import httpx
import pytest

from test_predictive_memory_read import Agent, response, run
from test_predictive_visible_basis import install, rows, provider_llm
from test_predictive_tool_recovery import block_network  # noqa: F401
from memory_agent.memory.ga_context_history import compress_history_tags, prepare_history
from memory_agent.memory.context_predictive_memory_agent import PMAPhaseError
from pma_model_profile import load_profile, READ_CONTEXT
from responses_memory_llm import ResponsesMemoryLLM, public_reasoning_summary, response_input


def profile(**extra):
    return dict(provider='openai', api_mode='responses', model='gpt-6.1-sol',
                store=False, reasoning_effort='high', max_tokens=8192,
                model_context_window=200000, read_timeout=30, max_retries=0,
                apikey='synthetic-not-a-key', apibase='https://example.invalid/v1', **extra)


def native_llm(replies, *, requested=False):
    from openai import AsyncOpenAI
    queue, wire = iter(replies), []
    llm = ResponsesMemoryLLM(profile(request_public_summary=requested))

    def handler(request):
        wire.append(json.loads(request.content))
        reply = next(queue)
        if reply.get('error'):
            return httpx.Response(400, json={'error': {'message': 'summary unsupported',
                                  'type': 'invalid_request_error', 'code': 'unsupported'}})
        ident = reply['id']
        output = [{'type': 'reasoning', 'id': 'r-' + ident,
                   'encrypted_content': 'opaque-' + ident,
                   'summary': [{'type': 'summary_text', 'text': reply['summary']}]
                              if reply.get('summary') else []}]
        if reply.get('text'):
            output.append({'type': 'message', 'id': 'm-' + ident, 'role': 'assistant',
                           'status': 'completed', 'content': [{'type': 'output_text',
                           'text': reply['text'], 'annotations': []}]})
        output.extend({'type': 'function_call', 'id': 'fc-' + cid, 'call_id': cid,
                       'name': name, 'arguments': json.dumps(args), 'status': 'completed'}
                      for cid, name, args in reply.get('calls', []))
        return httpx.Response(200, json={'id': ident, 'object': 'response', 'created_at': 1,
              'status': 'completed', 'model': llm.model, 'output': output,
              'usage': {'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 2}})

    llm.client = AsyncOpenAI(api_key='synthetic-not-a-key', max_retries=0,
        base_url='https://example.invalid/v1',
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    return llm, wire


@pytest.mark.parametrize('requested', [False, True])
@pytest.mark.parametrize('summary', ['', 'The endpoint may be needed for the next request.'])
def test_real_sdk_public_summary_request_and_missing_status(requested, summary):
    llm, wire = native_llm([{'id': 'one', 'summary': summary}], requested=requested)
    result = asyncio.run(llm.call('prompt', system='system'))
    assert wire[0]['reasoning'] == ({'effort': 'high', 'summary': 'auto'} if requested
                                    else {'effort': 'high'})
    assert wire[0]['store'] is False and wire[0]['model'] == 'gpt-6.1-sol'
    assert 'include' not in wire[0]  # Do not change the existing continuation request.
    assert result.content == ''  # A summary is not manufactured assistant body text.
    assert result.public_reasoning_summary == {
        'request_status': 'requested' if requested else 'not_requested',
        'result_status': 'returned' if summary else 'not_returned',
        'source': 'openai.responses.reasoning.summary_text',
        'texts': [summary] if summary else []}
    assert result.openai_output_items[0]['encrypted_content'] == 'opaque-one'


def test_summary_projection_uses_only_documented_display_fields():
    output = [{'type': 'reasoning', 'encrypted_content': 'private-ciphertext',
               'reasoning_content': 'private-text', 'thinking': 'private-thinking',
               'summary': [{'type': 'summary_text', 'text': 'Public A', 'secret': 'private-x'},
                           {'type': 'thinking', 'text': 'private-y'},
                           {'type': 'summary_text', 'text': 12}, None]},
              {'type': 'reasoning', 'summary': 'private-malformed'},
              {'type': 'reasoning', 'summary': [{'type': 'summary_text', 'text': 'Public B'}]},
              {'type': 'message', 'summary': [{'type': 'summary_text', 'text': 'private-z'}]}]
    original = copy.deepcopy(output)
    result = public_reasoning_summary(output, requested=False)
    assert result['texts'] == ['Public A', 'Public B']
    assert 'private' not in json.dumps(result) and output == original


def test_phase_histories_continue_independently_and_audit_is_public(tmp_path):
    llm, wire = native_llm([
        {'id': 'p1a', 'summary': 'Public forecast one', 'text': 'I will save the endpoint.',
         'calls': [('a', 'memory_add', {'content': 'endpoint=/v1'})]},
        {'id': 'p2a', 'summary': 'Public decision one', 'text': '<no_intervention/>'},
        {'id': 'p1b', 'summary': 'Public forecast two', 'text': 'No new information.'},
        {'id': 'p2b', 'text': '<no_intervention/>'}])
    agent = Agent(llm=llm)
    install(agent, tmp_path)
    run(agent)
    run(agent, 'new trajectory', 8)
    assert len(wire) == 4
    sent1, sent2 = json.dumps(wire[2]), json.dumps(wire[3])
    assert 'opaque-p1a' in sent1 and 'Public forecast one' in sent1
    assert 'opaque-p2a' not in sent1 and 'Public decision one' not in sent1
    assert 'opaque-p2a' in sent2 and 'Public decision one' in sent2
    assert 'opaque-p1a' not in sent2 and 'Public forecast one' not in sent2
    assert 'I will save the endpoint.' not in sent2
    assert all('summary' not in request['reasoning'] for request in wire)
    responses = rows(tmp_path, 'memory_response.jsonl')
    assert responses[0]['content'] == 'I will save the endpoint.'
    assert responses[0]['public_reasoning_summary']['texts'] == ['Public forecast one']
    assert responses[3]['public_reasoning_summary']['result_status'] == 'not_returned'
    audit = ''.join(path.read_text() for path in tmp_path.glob('*.jsonl'))
    assert 'opaque-' not in audit
    assert len(rows(tmp_path, 'memory_tool_results.jsonl')) == 2


def test_native_reasoning_stays_verbatim_when_visible_history_is_trimmed():
    native = [{'type': 'reasoning', 'id': 'r', 'encrypted_content': 'opaque-private',
               'summary': [{'type': 'summary_text', 'text': 'Public summary'}]},
              {'type': 'message', 'content': [{'type': 'output_text', 'text': 'original'}]}]
    history = [{'role': 'assistant', 'content': [{'type': 'text',
                'text': '<tool_result>' + 'x' * 3000 + '</tool_result>'}],
                '_openai_output_items': copy.deepcopy(native)},
               {'role': 'user', 'content': [{'type': 'text', 'text': 'next'}]}]
    compress_history_tags(history, keep_recent=1, force=True)
    prior = prepare_history(history, 'Continue.')
    actual = response_input(prior, 'Continue.')
    assert next(item for item in actual if item.get('type') == 'reasoning') == native[0]
    assert '[Truncated]' in json.dumps(actual) and 'x' * 3000 not in json.dumps(actual)


def test_claude_native_blocks_do_not_become_a_public_summary(monkeypatch, tmp_path):
    llm, wire = provider_llm('anthropic', [
        {'text': '', 'calls': [('r', 'memory_read', {'bank_id': 'knowledge'})]},
        {'text': 'No addition needed.'}, {'text': '<no_intervention/>'}], monkeypatch)
    agent = Agent(llm=llm)
    install(agent, tmp_path)
    run(agent)
    assert 'signed-private-fixture' in json.dumps(wire[1])
    for row in rows(tmp_path, 'memory_response.jsonl'):
        assert row['public_reasoning_summary'] == {
            'request_status': 'not_requested', 'result_status': 'not_returned',
            'source': None, 'texts': []}
    assert 'private-fixture' not in ''.join(p.read_text() for p in tmp_path.glob('*.jsonl'))


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
        return {'choices': [{'message': {'content': 'Public forecast' if kwargs.get('tools')
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


@pytest.mark.parametrize('value', ['auto', 1, None])
def test_switch_rejects_non_boolean_values(value):
    with pytest.raises(ValueError, match='boolean'):
        ResponsesMemoryLLM(profile(request_public_summary=value))
    with pytest.raises(ValueError, match='boolean'):
        load_profile(json.dumps({'pma_model': profile(request_public_summary=value)}).encode(), READ_CONTEXT)


def test_summary_switch_is_explicit_responses_only():
    explicit = profile(request_public_summary=True)
    assert load_profile(json.dumps({'pma_model': explicit}).encode(), READ_CONTEXT)[1] == explicit
    claude = dict(provider='anthropic', api_mode='messages', model='claude-opus-5',
                  thinking_type='adaptive', temperature=1, apikey='synthetic',
                  apibase='https://example.invalid', request_public_summary=True)
    with pytest.raises(ValueError, match='Responses adapter'):
        load_profile(json.dumps({'pma_model': claude}).encode(), READ_CONTEXT)


def test_unsupported_summary_request_is_not_silently_retried_or_converted_to_noop(tmp_path):
    llm, wire = native_llm([{'error': True}], requested=True)
    agent = Agent(llm=llm)
    install(agent, tmp_path)
    with pytest.raises(PMAPhaseError):
        run(agent)
    assert len(wire) == 1 and not agent.memory.knowledge
    assert not (tmp_path / 'memory_response.jsonl').exists()
    assert rows(tmp_path, 'memory_transport.jsonl')[0]['status'] != 'complete'
