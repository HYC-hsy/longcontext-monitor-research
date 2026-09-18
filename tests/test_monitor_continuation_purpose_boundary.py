"""Completed note responses must reach the note validator through the provider."""

import json

import pytest

from monitor_agent_core.handoff_validation import ContinuationContractError
from monitor_agent_core.provider import RetryableProviderError
from test_monitor_continuation_mode import review, setup_monitor


def response_lines(reason, *, text=None, thinking=False, output_tokens=7):
    events = [{'type': 'message_start',
               'message': {'id': 'fixture', 'usage': {'input_tokens': 5}}}]
    if text is not None:
        events.extend([
            {'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text'}},
            {'type': 'content_block_delta', 'index': 0,
             'delta': {'type': 'text_delta', 'text': text}},
            {'type': 'content_block_stop', 'index': 0},
        ])
    if thinking:
        events.extend([
            {'type': 'content_block_start', 'index': 1,
             'content_block': {'type': 'thinking'}},
            {'type': 'content_block_delta', 'index': 1,
             'delta': {'type': 'thinking_delta', 'thinking': 'private reasoning'}},
            {'type': 'content_block_stop', 'index': 1},
        ])
    events.extend([
        {'type': 'message_delta', 'delta': {'stop_reason': reason},
         'usage': {'output_tokens': output_tokens}},
        {'type': 'message_stop'},
    ])
    return ['data: ' + json.dumps(event) for event in events]


def progress(monitor):
    path = monitor.workspace.private_root / 'audit/progress.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


@pytest.mark.parametrize('first,expected_code', [
    ({'reason': 'end_turn'}, 'empty_note'),
    ({'reason': 'max_tokens', 'thinking': True}, 'truncated_note'),
])
def test_completed_empty_note_uses_one_format_repair(
        tmp_path, monkeypatch, first, expected_code):
    client, monitor = setup_monitor(tmp_path)
    client.max_retries = 2
    client.history = sum((review(i) for i in range(6)), [])
    old = client.export_history()
    calls = []

    def request_once(tools):
        assert tools == []
        calls.append(client.request_purpose)
        assert client.history[:-1] == old
        if len(calls) == 1:
            return client._parse_anthropic(response_lines(**first))
        return client._parse_anthropic(response_lines('end_turn', text='Unresolved evidence remains.'))

    monkeypatch.setattr(client, '_request_once', request_once)
    client._compact_history()
    events = progress(monitor)
    archived = sorted((monitor.workspace.private_root / 'audit/continuation_responses').glob('*.json'))
    assert calls == ['continuation', 'format_repair']
    assert len(archived) == len(client.usage_records) == 2
    assert [e['code'] for e in events if e['event'] == 'continuation_rejected'] == [expected_code]
    assert len([e for e in events if e['event'] == 'continuation_format_repair']) == 1
    requests = [e for e in events if e['event'] == 'request_started']
    usages = [e for e in events if e['event'] == 'request_usage']
    assert len(requests) == len(usages) == 2
    assert {e['request_id'] for e in requests} == {e['request_id'] for e in usages}
    assert {json.loads(path.read_text(encoding='utf-8'))['request_id'] for path in archived} == {
        e['request_id'] for e in usages}
    assert {e['request_id'] for e in events if e['event'] == 'continuation_response_archived'} == {
        e['request_id'] for e in usages}
    assert sum(e['usage']['output_tokens'] for e in usages) == 14
    assert sum(e['output_tokens'] for e in client.usage_records) == 14
    assert len([e for e in events if e['event'] == 'compaction_committed']) == 1
    assert 'Unresolved evidence remains.' in json.dumps(client.history)
    assert client.request_purpose == 'review'


def test_empty_refusal_is_archived_once_and_not_retried(tmp_path, monkeypatch):
    client, monitor = setup_monitor(tmp_path)
    client.max_retries = 2
    old = client.export_history()
    calls = []

    def request_once(tools):
        calls.append(client.request_purpose)
        return client._parse_anthropic(response_lines('refusal'))

    monkeypatch.setattr(client, '_request_once', request_once)
    with pytest.raises(ContinuationContractError) as caught:
        monitor._prepare_continuation()
    assert caught.value.code == 'abnormal_stop'
    assert calls == ['continuation']
    assert client.history == old
    assert len(client.usage_records) == 1
    events = progress(monitor)
    assert len([e for e in events if e['event'] == 'request_usage']) == 1
    assert len([e for e in events if e['event'] == 'continuation_response_archived']) == 1
    assert not any(e['event'] in ('continuation_format_repair', 'continuation_saved') for e in events)


def test_two_empty_notes_preserve_history_and_bound_repair(tmp_path, monkeypatch):
    client, monitor = setup_monitor(tmp_path)
    client.max_retries = 2
    old = client.export_history()
    calls = []

    def request_once(tools):
        calls.append(client.request_purpose)
        return client._parse_anthropic(response_lines('end_turn'))

    monkeypatch.setattr(client, '_request_once', request_once)
    with pytest.raises(ContinuationContractError) as caught:
        monitor._prepare_continuation()
    assert caught.value.code == 'empty_note'
    assert calls == ['continuation', 'format_repair']
    assert client.history == old
    assert len(client.usage_records) == 2
    events = progress(monitor)
    assert len([e for e in events if e['event'] == 'continuation_response_archived']) == 2
    assert not any(e['event'] in ('continuation_saved', 'compaction_committed') for e in events)


def test_review_empty_response_keeps_existing_retry_rule(tmp_path, monkeypatch):
    client, monitor = setup_monitor(tmp_path)
    client.max_retries = 0
    client.request_purpose = 'review'
    monkeypatch.setattr(client, '_request_once',
                        lambda tools: client._parse_anthropic(response_lines('end_turn')))
    with pytest.raises(RetryableProviderError):
        client._request_batch([])
    assert any(e['event'] == 'response_empty' for e in progress(monitor))
