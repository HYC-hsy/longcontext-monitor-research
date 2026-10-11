import threading
import time

import pytest

from monitor_agent_core.provider import (
    IncompleteStreamError, MonitorProviderClient, ProviderRecoveryExhausted,
    RetryableProviderError,
)


def client(enabled=True):
    instance = MonitorProviderClient('anthropic', {
        'apikey': 'offline', 'apibase': 'https://offline.invalid', 'model': 'offline',
        'max_retries': 0, 'incomplete_stream_recovery_v1': enabled,
    })
    instance.recovery_deadline = time.monotonic() + 100
    instance.recovery_stop = threading.Event()
    instance._cancelled.wait = lambda seconds: False
    return instance


def test_partial_stream_then_complete_commits_once(monkeypatch):
    instance = client()
    seen = []
    def once(tools):
        seen.append(len(instance.history))
        if len(seen) == 1:
            raise IncompleteStreamError('incomplete')
        return ([{'type': 'text', 'text': 'complete'}], {'input_tokens': 7})
    monkeypatch.setattr(instance, '_request_once', once)
    answer = instance._request_with_recovery([])
    assert answer[0][0]['text'] == 'complete'
    assert seen == [0, 0]
    assert [x['attempt'] for x in instance.request_attempts] == [1, 2]
    assert len({x['logical_request_id'] for x in instance.request_attempts}) == 1
    assert instance.request_attempts[0]['server_execution'] == 'unknown'


def test_three_total_attempts_and_no_fourth(monkeypatch):
    instance = client()
    instance.max_retries = 4
    instance.recovery_batches = 2
    attempts = []
    def broken(tools):
        attempts.append(1)
        raise IncompleteStreamError('incomplete')
    monkeypatch.setattr(instance, '_request_once', broken)
    with pytest.raises(ProviderRecoveryExhausted):
        instance._request_with_recovery([])
    assert len(attempts) == 3
    assert [x.get('retry_delay_seconds') for x in instance.request_attempts] == [2, 5, None]


def test_non_stream_failure_is_not_replayed(monkeypatch):
    instance = client()
    attempts = []
    def broken(tools):
        attempts.append(1)
        raise RetryableProviderError('HTTP 503')
    monkeypatch.setattr(instance, '_request_once', broken)
    with pytest.raises(ProviderRecoveryExhausted):
        instance._request_with_recovery([])
    assert len(attempts) == 1


def test_deadline_stop_and_default_policy(monkeypatch):
    instance = client()
    instance.recovery_stop.set()
    monkeypatch.setattr(instance, '_request_once', lambda tools: pytest.fail('sent after stop'))
    with pytest.raises(ProviderRecoveryExhausted):
        instance._request_with_recovery([])
    instance = client()
    instance.recovery_deadline = time.monotonic() - 1
    monkeypatch.setattr(instance, '_request_once', lambda tools: pytest.fail('sent after deadline'))
    with pytest.raises(ProviderRecoveryExhausted):
        instance._request_with_recovery([])
    default = client(False)
    default.recovery_batches = 1
    attempts = []
    def broken(tools):
        attempts.append(1)
        raise IncompleteStreamError('incomplete')
    monkeypatch.setattr(default, '_request_once', broken)
    with pytest.raises(ProviderRecoveryExhausted):
        default._request_with_recovery([])
    assert len(attempts) == 1


def test_incomplete_parser_preserves_partial_usage():
    instance = client()
    lines = [
        b'data: {"type":"message_start","message":{"id":"m","usage":{"input_tokens":5}}}',
        b'data: {"type":"content_block_start","content_block":{"type":"text"}}',
        b'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"partial"}}',
    ]
    with pytest.raises(IncompleteStreamError):
        instance._parse_anthropic(lines)
    assert instance.last_response_metadata['partial_usage'] == {'input_tokens': 5}
    assert instance.history == []


def test_cancel_after_partial_stream_does_not_retry(monkeypatch):
    instance = client()
    attempts = []
    def broken(tools):
        attempts.append(1)
        raise IncompleteStreamError('incomplete')
    monkeypatch.setattr(instance, '_request_once', broken)
    instance._cancelled.wait = lambda seconds: instance._cancelled.set() or True
    with pytest.raises(Exception, match='cancelled'):
        instance._request_with_recovery([])
    assert len(attempts) == 1
