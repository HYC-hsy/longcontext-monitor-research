"""Public explanations and actual tool receipts; synthetic providers, no network."""
import asyncio
import copy
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_predictive_memory_read import Agent, Script, call, response, run
from test_predictive_memory_read_integration import CANDIDATE, STAGE, load_definition
from test_predictive_tool_recovery import block_network  # noqa: F401
from memory_agent.memory.context_predictive_memory_agent import PMAPhaseError
from memory_agent.memory.ga_context_history import GAHistoryIntegrityError
from memory_agent.memory.read_context_predictive_memory_agent import UNIFIED_SYSTEM, PUBLIC_FORECAST_REMINDER, has_public_text, DECISION_RECOVERY_PROMPT
from memory_agent.memory.predictive_memory_agent import PHASE2_SYSTEM


class AuditError(BaseException):
    pass


def install(agent, directory):
    namespace = dict(copy=copy, json=json, os=os, time=time, Path=Path,
                     PMAAuditIntegrityError=AuditError)
    namespace['append_private_audit'] = load_definition(
        STAGE / 'worker_main.py', 'append_private_audit', namespace)
    hook = load_definition(STAGE / 'worker_main.py', 'install_transport_audit', namespace)
    hook(SimpleNamespace(_memory_llm=agent.llm, _memory_agent=agent,
                         _research_candidate=CANDIDATE), directory)


def rows(directory, name):
    return [json.loads(line) for line in (directory / name).read_text().splitlines()]


def native(name, args, ident='one'):
    return SimpleNamespace(id=ident, function=SimpleNamespace(name=name, arguments=args))


def provider_llm(provider, replies, monkeypatch):
    """Exercise the existing adapter with real provider-shaped synthetic output."""
    import httpx
    wire = []
    queue = iter(replies)
    if provider == 'openai':
        from openai import AsyncOpenAI
        from responses_memory_llm import ResponsesMemoryLLM
        llm = ResponsesMemoryLLM({
            'model': 'gpt-6.1-sol', 'model_context_window': 200000,
            'max_tokens': 8192, 'reasoning_effort': 'high', 'max_retries': 0,
            'apikey': 'synthetic-not-a-key', 'apibase': 'https://example.invalid/v1',
            'read_timeout': 30})

        def handler(request):
            wire.append(json.loads(request.content))
            reply = next(queue)
            output = [{'type': 'reasoning', 'id': 'reasoning-fixture',
                       'summary': [], 'encrypted_content': 'opaque-private-fixture'}]
            if reply['text']:
                output.append({'type': 'message', 'id': 'message-fixture',
                    'role': 'assistant', 'status': 'completed', 'content': [
                    {'type': 'output_text', 'text': reply['text'], 'annotations': []}]})
            output.extend({'type': 'function_call', 'id': 'fc-' + ident,
                'call_id': ident, 'name': name, 'arguments': json.dumps(args),
                'status': 'completed'} for ident, name, args in reply.get('calls', []))
            return httpx.Response(200, json={'id': 'response-fixture',
                'object': 'response', 'created_at': 1, 'status': 'completed',
                'model': 'gpt-6.1-sol', 'output': output,
                'usage': {'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 2}})

        llm.client = AsyncOpenAI(api_key='synthetic-not-a-key', max_retries=0,
            base_url='https://example.invalid/v1',
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    else:
        import litellm
        from harbor.llms import lite_llm
        from harbor.llms.lite_llm import LiteLLM
        from litellm.llms.anthropic.chat.transformation import AnthropicConfig

        async def completion(**kwargs):
            config = AnthropicConfig()
            options = {'max_tokens': 8192, 'thinking': {'type': 'adaptive'}}
            if kwargs.get('tools'):
                options['tools'], _ = config._map_tools(copy.deepcopy(kwargs['tools']))
            wire.append(config.transform_request(model='claude-opus-4-8',
                messages=copy.deepcopy(kwargs['messages']), optional_params=options,
                litellm_params={}, headers={}))
            reply = next(queue)
            content = [{'type': 'thinking', 'thinking': 'private-fixture',
                        'signature': 'signed-private-fixture'}]
            if reply['text']:
                content.append({'type': 'text', 'text': reply['text']})
            content.extend({'type': 'tool_use', 'id': ident, 'name': name, 'input': args}
                           for ident, name, args in reply.get('calls', []))
            raw = httpx.Response(200, json={'id': 'message-fixture', 'type': 'message',
                'role': 'assistant', 'model': 'claude-opus-4-8', 'content': content,
                'stop_reason': 'tool_use' if reply.get('calls') else 'end_turn',
                'stop_sequence': None, 'usage': {'input_tokens': 1, 'output_tokens': 1}})
            return config.transform_response(model='claude-opus-4-8', raw_response=raw,
                model_response=litellm.ModelResponse(), logging_obj=SimpleNamespace(
                    post_call=lambda **_: None), request_data={}, messages=[],
                optional_params={}, litellm_params={}, encoding=litellm.encoding, api_key='synthetic')

        monkeypatch.setattr(lite_llm.litellm, 'acompletion', completion)
        llm = LiteLLM('anthropic/claude-opus-4-8', api_key='synthetic-not-a-key')
    return llm, wire


@pytest.mark.parametrize('provider', ['anthropic', 'openai'])
@pytest.mark.parametrize('text', ['I will save the endpoint because it is needed for the next request.', ''])
def test_same_response_text_and_add_only_receipt_without_extra_call(provider, text, monkeypatch, tmp_path):
    llm, wire = provider_llm(provider, [
        {'text': text, 'calls': [('add-one', 'memory_add', {'content': 'endpoint = /v1'})]},
        {'text': '<no_intervention/>'}], monkeypatch)
    agent = Agent(llm=llm)
    install(agent, tmp_path)
    result = run(agent, task='Exact task <history>not rewritten</history>')
    assert len(wire) == 2 and len(result.operations) == 1
    assert result.operations[0].success and not result.should_inject
    response_row = rows(tmp_path, 'memory_response.jsonl')[0]
    assert response_row['content'] == text  # Missing text stays missing, not repaired.
    assert response_row['tool_calls'][0]['id'] == 'add-one'
    receipt_row = rows(tmp_path, 'memory_tool_results.jsonl')[0]
    assert receipt_row['call_sequence'] == response_row['call_sequence'] == 1
    assert receipt_row['recording_error_type'] is None
    receipt = receipt_row['tool_results'][0]
    assert receipt['tool_use_id'] == 'add-one'
    assert json.loads(receipt['content'])['memory_id'] == agent.memory.knowledge[0].id
    assert json.loads(receipt['content'])['success'] is True
    payload = rows(tmp_path, 'memory_payload.jsonl')
    assert [row['system'] for row in payload] == [UNIFIED_SYSTEM, UNIFIED_SYSTEM + ('\n\n' + PUBLIC_FORECAST_REMINDER if not has_public_text(text) else '')]
    assert payload[0]['prompt'] == '[Task Description]\nExact task <history>not rewritten</history>'
    assert result.reasoning_phase1 is result.reasoning_phase2 is None
    assert 'private-fixture' not in ''.join(p.read_text() for p in tmp_path.glob('*.jsonl'))


@pytest.mark.parametrize('provider', ['anthropic', 'openai'])
def test_existing_read_loop_keeps_public_text_receipts_and_private_replay_separate(provider, monkeypatch, tmp_path):
    llm, wire = provider_llm(provider, [
        {'text': 'I will look up the saved endpoint before adding a duplicate.',
         'calls': [('read-one', 'memory_read', {'bank_id': 'knowledge'})]},
        {'text': 'The new endpoint differs, so I will save it.',
         'calls': [('add-two', 'memory_add', {'content': 'endpoint = /v2'})]},
        {'text': 'No more information needs saving now. <no_intervention/>'}], monkeypatch)
    agent = Agent(llm=llm)
    agent.memory.save_knowledge('endpoint = /v1')
    install(agent, tmp_path)
    result = run(agent)
    assert len(wire) == 3 and [op.action for op in result.operations] == ['read', 'add']
    receipts = rows(tmp_path, 'memory_tool_results.jsonl')
    assert [row['call_sequence'] for row in receipts] == [1, 2, 3]
    assert [b['tool_use_id'] for row in receipts for b in row['tool_results']] == ['read-one', 'add-two']
    assert 'endpoint = /v1' in receipts[0]['tool_results'][0]['content']
    assert receipts[2]['tool_results'] == []
    sent = json.dumps(wire[1])
    assert 'look up the saved endpoint' in sent and 'read-one' in sent
    assert 'private-fixture' in sent  # Opaque provider continuity, never public explanation.
    audit = ''.join(p.read_text() for p in tmp_path.glob('*.jsonl'))
    assert 'private-fixture' not in audit and 'look up the saved endpoint' in audit


@pytest.mark.parametrize('text', ['', 'No new information is useful for the next steps.'])
def test_no_action_and_empty_response_require_explicit_decision(text, tmp_path):
    agent = Agent(llm=Script(response(content=text), response()))
    install(agent, tmp_path)
    result = run(agent)
    assert len(agent.llm.calls) == 2 and not result.operations
    assert agent.llm.calls[1]['prompt'] == DECISION_RECOVERY_PROMPT
    assert rows(tmp_path, 'memory_response.jsonl')[0]['content'] == text
    assert rows(tmp_path, 'memory_tool_results.jsonl')[0]['tool_results'] == []


def test_failed_tool_receipt_is_not_a_success_or_reason_to_hide_public_text(tmp_path):
    agent = Agent(llm=Script(response(native('memory_read', {}), content='I will look it up.'), response()))
    install(agent, tmp_path)
    result = run(agent)
    assert not result.operations[0].success and len(agent.llm.calls) == 2
    assert rows(tmp_path, 'memory_response.jsonl')[0]['content'] == 'I will look it up.'
    receipt = rows(tmp_path, 'memory_tool_results.jsonl')[0]['tool_results'][0]
    assert receipt['tool_use_id'] == 'one' and json.loads(receipt['content'])['success'] is False


def test_invalid_envelope_does_not_invent_a_receipt(tmp_path):
    agent = Agent(llm=Script(response(native('memory_add', {'content': 'must not save'}, ident=None))))
    install(agent, tmp_path)
    with pytest.raises(GAHistoryIntegrityError):
        run(agent)
    row = rows(tmp_path, 'memory_tool_results.jsonl')[0]
    assert row['recording_error_type'] == 'GAHistoryIntegrityError'
    assert row['tool_results'] == [] and not agent.memory.knowledge


def test_provider_failure_does_not_invent_response_or_execution(tmp_path):
    agent = Agent(llm=Script(RuntimeError('synthetic transport failure')))
    install(agent, tmp_path)
    with pytest.raises(PMAPhaseError):
        run(agent)
    assert not (tmp_path / 'memory_response.jsonl').exists()
    assert not (tmp_path / 'memory_tool_results.jsonl').exists()
    assert rows(tmp_path, 'memory_transport.jsonl')[0]['status'] == 'RuntimeError'


def test_receipt_log_failure_stops_without_retrying_an_already_executed_add(tmp_path):
    (tmp_path / 'memory_tool_results.jsonl').mkdir()
    agent = Agent(llm=Script(response(native('memory_add', {'content': 'saved once'}))))
    install(agent, tmp_path)
    with pytest.raises(AuditError):
        run(agent)
    assert len(agent.memory.knowledge) == len(agent.llm.calls) == 1


def test_mixed_tool_results_keep_native_ids_and_actual_outcomes(tmp_path):
    agent = Agent(llm=Script(response(
        native('memory_add', {'content': 'saved once'}, 'good'),
        native('memory_read', {}, 'bad')), response()))
    install(agent, tmp_path)
    result = run(agent)
    receipt = rows(tmp_path, 'memory_tool_results.jsonl')[0]
    assert [b['tool_use_id'] for b in receipt['tool_results']] == ['good', 'bad']
    assert [json.loads(b['content'])['success'] for b in receipt['tool_results']] == [True, False]
    assert [op.success for op in result.operations] == [True, False]
    assert len(agent.memory.knowledge) == 1


@pytest.mark.parametrize('failure', [RuntimeError('Continuation failed'), asyncio.CancelledError()])
def test_add_receipt_survives_continuation_failure_or_cancellation(failure, tmp_path):
    agent = Agent(llm=Script(response(native('memory_add', {'content': 'saved once'})), failure))
    install(agent, tmp_path)
    with pytest.raises((PMAPhaseError, asyncio.CancelledError)):
        run(agent)
    assert len(agent.memory.knowledge) == 1
    receipt = rows(tmp_path, 'memory_tool_results.jsonl')[0]['tool_results'][0]
    assert json.loads(receipt['content'])['success'] is True
    assert rows(tmp_path, 'memory_transport.jsonl')[-1]['status'] == type(failure).__name__
