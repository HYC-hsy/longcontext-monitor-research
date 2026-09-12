import json

import pytest

from monitor_agent_core.provider import MonitorProviderClient, RetryableProviderError
from test_monitor_provider import config, parse_events


def call(arguments, name='intervene', call_id='call-1'):
    return {'type': 'function_call', 'id': 'fc-1', 'call_id': call_id,
            'name': name, 'arguments': json.dumps(arguments)}


def stream(delta=None, done=None, item_done=None, final=None):
    events = [{'type': 'response.output_item.added', 'output_index': 0,
               'item': dict(call({}), arguments='')}]
    if delta is not None:
        events.append({'type': 'response.function_call_arguments.delta', 'output_index': 0, 'delta': delta})
    if done is not None:
        events.append({'type': 'response.function_call_arguments.done', 'output_index': 0,
                       'arguments': done})
    if item_done is not None:
        events.append({'type': 'response.output_item.done', 'output_index': 0, 'item': item_done})
    events.append({'type': 'response.completed', 'response': {'output': final or []}})
    return events


@pytest.mark.parametrize('layer', ['delta', 'done', 'item_done'])
def test_conflicting_message_never_becomes_tool_call(layer):
    client = MonitorProviderClient('openai', config('fixture'))
    kwargs = {layer: call({'message': 'contaminated'}) if layer == 'item_done'
              else json.dumps({'message': 'contaminated'})}
    with pytest.raises(RetryableProviderError, match='Tool stream contract mismatch'):
        parse_events(client, stream(**kwargs, final=[call({'message': 'correct'})]))


@pytest.mark.parametrize('delta', [None, '{"message":', '{ "message" : "keep" }'])
def test_partial_or_equivalent_delta_recovers_from_final(delta):
    client = MonitorProviderClient('openai', config('fixture'))
    blocks, _ = parse_events(client, stream(delta=delta, final=[call({'message': 'keep'})]))
    assert blocks == [{'type': 'tool_use', 'id': 'call-1', 'name': 'intervene',
                       'input': {'message': 'keep'}}]


def test_final_only_call_is_not_lost_and_literal_protocol_text_is_preserved():
    client = MonitorProviderClient('openai', config('fixture'))
    message = 'Explain to=functions.wait as literal source text.'
    blocks, _ = parse_events(client, [{'type': 'response.completed', 'response': {
        'output': [call({'message': message})]}}])
    assert blocks[0]['input']['message'] == message


@pytest.mark.parametrize('final', [[], [call({'message': 'ok'}, name='file_write')],
                                 [call({'message': 'ok'}, call_id='other')]])
def test_missing_or_changed_tool_identity_is_rejected(final):
    client = MonitorProviderClient('openai', config('fixture'))
    with pytest.raises(RetryableProviderError):
        parse_events(client, stream(done='{"message":"ok"}', final=final))


def test_retry_does_not_commit_rejected_call_to_history(monkeypatch):
    client = MonitorProviderClient('openai', config('fixture', max_retries=1))
    monkeypatch.setattr(client._cancelled, 'wait', lambda _: False)
    seen = []
    def request(tools):
        seen.append(client.export_history())
        return parse_events(client, stream(done=json.dumps({'message': 'bad' if len(seen) == 1 else 'ok'}),
                                           final=[call({'message': 'ok'})]))
    monkeypatch.setattr(client, '_request_once', request)
    result = client.complete([{'role': 'user', 'content': 'Inspect'}], [])
    assert seen[0] == seen[1]
    assert json.loads(result.tool_calls[0].arguments) == {'message': 'ok'}
    assert 'bad' not in json.dumps(client.export_history())


def test_relay_final_item_repackaging_preserves_actual_call_identity():
    client = MonitorProviderClient('openai', config('fixture'))
    events = stream(done='{"message":"ok"}', item_done=call({'message': 'ok'}),
                    final=[dict(call({'message': 'ok'}), id='item-new-envelope')])
    blocks, _ = parse_events(client, events)
    assert blocks[0]['id'] == 'call-1'
    assert blocks[0]['input'] == {'message': 'ok'}


def test_repackaging_does_not_allow_changed_arguments_or_stream_identity():
    client = MonitorProviderClient('openai', config('fixture'))
    with pytest.raises(RetryableProviderError):
        parse_events(client, stream(done='{"message":"old"}',
                                   final=[dict(call({'message': 'new'}), id='new')]))
    with pytest.raises(RetryableProviderError):
        parse_events(client, stream(done='{"message":"ok"}',
                                   item_done=dict(call({'message': 'ok'}), id='wrong-stream-id'),
                                   final=[call({'message': 'ok'})]))
