import threading
import time
import json

import pytest

from monitor_agent_core.provider import (
    IncompleteStreamError, MonitorProviderClient, ProviderRecoveryExhausted,
    RetryableProviderError,
)
from monitor_agent_core.loop import run_review
from monitor_agent_core.actions import MonitorAction, ToolOutcome


def client(enabled=True):
    instance = MonitorProviderClient('anthropic', {
        'apikey': 'offline', 'apibase': 'https://offline.invalid', 'model': 'offline',
        'provider': 'anthropic', 'max_retries': 0,
        'incomplete_stream_recovery_v1': enabled,
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


def _sse(*events):
    return [b'data: ' + json.dumps(event).encode('utf-8') for event in events]


def _tool_stream(tool_id, name, complete=True):
    events = [
        {'type': 'message_start', 'message': {'id': 'offline', 'usage': {'input_tokens': 3}}},
        {'type': 'content_block_start', 'index': 0,
         'content_block': {'type': 'tool_use', 'id': tool_id, 'name': name}},
        {'type': 'content_block_delta', 'index': 0,
         'delta': {'type': 'input_json_delta', 'partial_json': '{}'}},
        {'type': 'content_block_stop', 'index': 0},
        {'type': 'message_delta', 'delta': {'stop_reason': 'tool_use'},
         'usage': {'output_tokens': 2}},
    ]
    if complete:
        events.append({'type': 'message_stop'})
    return _sse(*events)


class _OfflineResponse:
    status_code = 200

    def __init__(self, lines, after=None):
        self.lines = lines
        self.after = after

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def iter_lines(self):
        for index, line in enumerate(self.lines):
            if self.after and index == len(self.lines) - 1:
                self.after()
            yield line


def test_full_transport_partial_then_complete_tool_dispatch_once(monkeypatch):
    instance = client()
    payloads = []
    streams = [_tool_stream('discarded', 'probe', False),
               _tool_stream('accepted', 'probe'), _tool_stream('terminal', 'wait')]

    def post(*args, **kwargs):
        payloads.append(kwargs['json'])
        return _OfflineResponse(streams.pop(0))

    monkeypatch.setattr('monitor_agent_core.provider.requests.post', post)
    executed = []

    def dispatch(name, args):
        executed.append(name)
        if name == 'wait':
            return ToolOutcome({'status': 'ok'}, action=MonitorAction('wait', {}))
        return ToolOutcome({'status': 'ok'})

    action = run_review(instance, 'system', 'wake', [], dispatch, max_turns=2)
    assert action.kind == 'wait'
    assert executed == ['probe', 'wait']
    assert len(payloads) == 3
    assert [x['outcome'] for x in instance.request_attempts] == [
        'retryable_error', 'success', 'success']
    assert len([block for message in instance.history if message['role'] == 'assistant'
                for block in message['content'] if block.get('name') == 'probe']) == 1
    assert payloads[1]['messages'] == payloads[0]['messages']
    assert any(block.get('tool_use_id') == 'accepted' for message in payloads[2]['messages']
               for block in message['content'])


@pytest.mark.parametrize('reason', ['stopped', 'deadline', 'cancelled'])
def test_complete_response_discarded_before_history_or_tool_commit(monkeypatch, reason):
    instance = client()
    if reason == 'cancelled':
        change = instance._cancelled.set
    elif reason == 'stopped':
        change = instance.recovery_stop.set
    else:
        change = lambda: setattr(instance, 'recovery_deadline', time.monotonic() - 1)
    sent = []

    def post(*args, **kwargs):
        sent.append(kwargs['json'])
        return _OfflineResponse(_tool_stream('late', 'probe'), after=change)

    monkeypatch.setattr('monitor_agent_core.provider.requests.post', post)
    executed = []
    with pytest.raises(ProviderRecoveryExhausted, match='discarded'):
        run_review(instance, 'system', 'wake', [],
                   lambda name, args: executed.append(name), max_turns=2)
    assert len(sent) == 1
    assert not executed
    assert not any(message['role'] == 'assistant' for message in instance.history)
    assert instance.request_attempts[0]['outcome'] == 'response_discarded'
    assert instance.request_attempts[0]['discard_reason'] == reason
    assert instance.request_attempts[0]['response_usage']['input_tokens'] == 3
