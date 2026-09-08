import json

import pytest
import requests

import llmcore
from agent_loop import exhaust


class Transport:
    status_code = 200
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def close(self):
        pass


def setup_stream(monkeypatch, failures=1, cancel=False):
    monkeypatch.delenv('GA_PROVIDER_MAX_RETRIES', raising=False)
    session = llmcore.NativeClaudeSession({
        'apikey': 'test', 'apibase': 'https://example.invalid',
        'model': 'test', 'max_retries': 1,
    })
    payloads = []
    parses = []

    def post(*args, **kwargs):
        payloads.append(json.dumps(kwargs['json'], sort_keys=True))
        return Transport()

    def parse(response):
        parses.append(1)
        yield 'partial tool arguments'
        if len(parses) <= failures:
            if cancel:
                session._cancel_response.set()
            raise requests.exceptions.ChunkedEncodingError('cut stream')
        return [{'type': 'tool_use', 'id': 'good', 'name': 'code_run',
                 'input': {'code': 'print(1)'}}]

    session.raw_ask = lambda messages: llmcore._stream_with_retry(
        session, 'https://example.invalid', {}, {'messages': messages}, parse)
    monkeypatch.setattr(llmcore.requests, 'post', post)
    monkeypatch.setattr(llmcore.time, 'sleep', lambda _: None)
    return session, payloads


def test_partial_tool_response_retries_without_history_contamination(monkeypatch):
    session, payloads = setup_stream(monkeypatch)
    response = exhaust(session.ask({'role': 'user', 'content': [
        {'type': 'text', 'text': 'task'}]}))
    assert len(payloads) == 2 and payloads[0] == payloads[1]
    assert len(session.history) == 2
    assert 'partial tool arguments' not in json.dumps(session.history)
    assert [call.id for call in response.tool_calls] == ['good']


def test_exhausted_partial_response_is_not_committed(monkeypatch):
    session, payloads = setup_stream(monkeypatch, failures=3)
    response = exhaust(session.ask({'role': 'user', 'content': [
        {'type': 'text', 'text': 'task'}]}))
    assert len(payloads) == 2
    assert len(session.history) == 1
    assert response.content.startswith('!!!Error:')
    assert not response.tool_calls


def test_explicit_cancellation_never_retries(monkeypatch):
    session, payloads = setup_stream(monkeypatch, cancel=True)
    with pytest.raises(llmcore.ProviderResponseCancelled):
        exhaust(session.ask({'role': 'user', 'content': [
            {'type': 'text', 'text': 'task'}]}))
    assert len(payloads) == 1
    assert len(session.history) == 1
