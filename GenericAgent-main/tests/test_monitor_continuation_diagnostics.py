import json

import pytest

from monitor_agent_core.provider import HistoryCapacityError, failure_chain
from monitor_agent_core.handoff_validation import ContinuationContractError
from test_monitor_continuation_mode import setup_monitor, review


def stream(reason):
    events = [
        {'type': 'message_start', 'message': {'id': 'response-fixture', 'usage': {}}},
        {'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text'}},
        {'type': 'content_block_delta', 'index': 0,
         'delta': {'type': 'text_delta', 'text': 'uncertain grounds'}},
        {'type': 'content_block_stop', 'index': 0},
        {'type': 'message_delta', 'delta': {'stop_reason': reason}, 'usage': {'output_tokens': 2}},
        {'type': 'message_stop'},
    ]
    return ['data: ' + json.dumps(e) for e in events]


@pytest.mark.parametrize('reason', ['end_turn', 'max_tokens', 'tool_use'])
def test_stop_reason_separate_from_usage(tmp_path, reason):
    client, _ = setup_monitor(tmp_path)
    blocks, usage = client._parse_anthropic(stream(reason))
    assert client.last_response_metadata == {
        'provider': 'anthropic', 'stream_complete': True, 'stop_reason': reason,
        'provider_message_id': 'response-fixture', 'response_block_types': ['text']}
    assert usage == {'output_tokens': 2}
    assert blocks == [{'type': 'text', 'text': 'uncertain grounds'}]


@pytest.mark.parametrize('mixed', [False, True])
def test_rejected_response_archived_without_tool_execution(tmp_path, monkeypatch, mixed):
    client, monitor = setup_monitor(tmp_path)
    client.history = sum((review(i) for i in range(6)), [])
    old = client.export_history()
    blocks = [{'type': 'tool_use', 'name': 'wait', 'id': 'never-execute', 'input': {}}]
    if mixed:
        blocks.insert(0, {'type': 'text', 'text': 'PRIVATE_RESPONSE_SENTINEL'})
    calls = []
    def request(tools):
        calls.append(tools)
        client.last_response_metadata = {'stop_reason': 'tool_use', 'stream_complete': True}
        return blocks, {'output_tokens': 3}
    monkeypatch.setattr(client, '_request', request)
    with pytest.raises(HistoryCapacityError) as caught:
        client._compact_history()
    assert failure_chain(caught.value)[-1] == {
        'type': 'ContinuationContractError', 'code': 'unexpected_tool'}
    assert len(calls) == 2  # One bounded repair, never a new review.
    assert client.history == old
    response = next((monitor.workspace.private_root / 'audit/continuation_responses').glob('*.json'))
    assert json.loads(response.read_text(encoding='utf-8'))['blocks'] == blocks
    progress = (monitor.workspace.private_root / 'audit/progress.jsonl').read_text(encoding='utf-8')
    assert 'PRIVATE_RESPONSE_SENTINEL' not in progress
    assert 'note_validation' in progress and 'unexpected_tool' in progress
    assert 'compaction_committed' not in progress
    assert client.request_purpose == 'review'


def test_parser_to_note_to_compaction_records_distinct_commit(tmp_path, monkeypatch):
    client, monitor = setup_monitor(tmp_path)
    client.history = sum((review(i) for i in range(6)), [])
    monkeypatch.setattr(client, '_request_once', lambda tools: client._parse_anthropic(stream('end_turn')))
    client._compact_history()
    events = [json.loads(line) for line in
              (monitor.workspace.private_root / 'audit/progress.jsonl').read_text(encoding='utf-8').splitlines()]
    names = [e['event'] for e in events]
    assert names.index('continuation_response_archived') < names.index('continuation_note_validated')
    assert names.index('continuation_saved') < names.index('compaction_committed')
    request = next(e for e in events if e['event'] == 'request_started')
    archived = next(e for e in events if e['event'] == 'continuation_response_archived')
    committed = next(e for e in events if e['event'] == 'compaction_committed')
    assert request['request_id'] == archived['request_id']
    assert request['transaction_id'] == committed['transaction_id']
    assert request['purpose'] == 'continuation'
    assert 'uncertain grounds' in json.dumps(client.history)


def test_archive_failure_not_classified_as_model_contract_error(tmp_path, monkeypatch):
    client, monitor = setup_monitor(tmp_path)
    monkeypatch.setattr(client, '_request', lambda tools: ([{'type': 'text', 'text': 'note'}], {}))
    def fail(*args):
        raise OSError('storage unavailable')
    monkeypatch.setattr(monitor, '_atomic_private_text', fail)
    with pytest.raises(OSError):
        monitor._prepare_continuation()
    events = [json.loads(line) for line in
              (monitor.workspace.private_root / 'audit/progress.jsonl').read_text(encoding='utf-8').splitlines()]
    failure = next(e for e in events if e['event'] == 'continuation_failed')
    assert failure['stage'] == 'response_archive'
    assert failure['code'] is None
    assert client.request_purpose == 'review'
