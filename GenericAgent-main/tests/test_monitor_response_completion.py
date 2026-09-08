import json
import pytest

from monitor_agent_core.provider import (
    MonitorProviderClient, ProviderError, RetryableProviderError, _remote_error,
)


def client():
    return MonitorProviderClient('openai', {
        'apikey': 'test', 'apibase': 'https://example.test', 'model': 'test', 'max_retries': 1,
    })


def lines(events):
    return [('data: ' + json.dumps(e)).encode() for e in events]


def test_stream_rate_limit_retries_same_request(monkeypatch):
    c = client()
    attempts = []
    monkeypatch.setattr(c._cancelled, 'wait', lambda _: False)
    def request(tools):
        attempts.append(c.export_history())
        events = ([{'type': 'error', 'error': {'code': 'rate_limit_exceeded'}}]
                  if len(attempts) == 1 else [
                      {'type': 'response.output_text.delta', 'delta': 'Ready'},
                      {'type': 'response.completed', 'response': {'usage': {}}},
                  ])
        return c._parse_openai_responses(lines(events))
    monkeypatch.setattr(c, '_request_once', request)
    result = c.complete([{'role': 'user', 'content': 'Inspect'}], [])
    assert result.content == 'Ready'
    assert attempts[0] == attempts[1]
    assert type(_remote_error({'code': 'insufficient_quota'})) is ProviderError


def test_truncated_tool_never_enters_history(monkeypatch):
    c = client()
    monkeypatch.setattr(c._cancelled, 'wait', lambda _: False)
    def request(_):
        return c._parse_openai_responses(lines([
            {'type': 'response.output_item.added', 'output_index': 0,
             'item': {'type': 'function_call', 'call_id': 'x', 'name': 'intervene'}},
            {'type': 'response.function_call_arguments.delta', 'output_index': 0,
             'delta': '{"message":"unfinished'},
        ]))
    monkeypatch.setattr(c, '_request_once', request)
    with pytest.raises(ProviderError):
        c.complete([{'role': 'user', 'content': 'Inspect'}], [])
    assert not any(m['role'] == 'assistant' for m in c.history)


def test_completed_text_without_tools_remains_valid():
    blocks, _ = client()._parse_openai_responses(lines([
        {'type': 'response.output_text.delta', 'delta': 'I need to inspect the changed test.'},
        {'type': 'response.completed', 'response': {'usage': {}}},
    ]))
    assert blocks[0]['text'].startswith('I need')


def test_explicit_incomplete_is_not_blindly_retryable():
    with pytest.raises(ProviderError) as error:
        client()._parse_openai_responses(lines([
            {'type': 'response.incomplete', 'response': {'incomplete_details': {'reason': 'max_output_tokens'}}},
        ]))
    assert not isinstance(error.value, RetryableProviderError)


def test_invalid_completed_tool_arguments_report_protocol_error():
    with pytest.raises(RetryableProviderError, match='JSON'):
        client()._parse_openai_responses(lines([
            {'type': 'response.output_item.added', 'output_index': 0,
             'item': {'type': 'function_call', 'call_id': 'x', 'name': 'wait'}},
            {'type': 'response.function_call_arguments.done', 'output_index': 0, 'arguments': '{broken'},
            {'type': 'response.completed', 'response': {}},
        ]))
