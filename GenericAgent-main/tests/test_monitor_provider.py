import json
import pytest

from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.provider import ProviderError, RetryableProviderError, _remote_error


def answer_item(text):
    return {"type": "message", "role": "assistant", "content": [
        {"type": "output_text", "text": text}]}


def parse_events(client, events):
    return client._parse_openai_responses(['data: ' + json.dumps(e) for e in events])


def test_stream_metadata_is_not_promoted_to_conversation(monkeypatch):
    client = MonitorProviderClient('openai', config('gpt-test'))
    events = [
        {'type': 'response.created', 'response': {'id': 'transport-only-id'}},
        {'type': 'response.reasoning_summary_text.delta', 'delta': 'summary-only-delta'},
        {'type': 'response.output_text.delta', 'delta': 'Inspect the test.'},
        {'type': 'response.completed', 'response': {
            'id': 'transport-only-id', 'service_tier': 'transport-only-tier',
            'output': [answer_item('Inspect the test.')],
            'usage': {'input_tokens': 17, 'output_tokens': 4}}},
    ]
    lines = [': heartbeat', 'event: response.created']
    lines += ['data: ' + json.dumps(event) for event in events]
    lines += ['data: [DONE]']
    monkeypatch.setattr(client, '_request_once',
                        lambda tools: client._parse_openai_responses(lines))
    response = client.complete([{'role': 'user', 'content': 'Review.'}], [])
    assert response.content == 'Inspect the test.'
    assert response.usage == {'input_tokens': 17, 'output_tokens': 4}
    assert client.history[-1]['content'] == [{'type': 'text', 'text': 'Inspect the test.'}]
    wire = json.dumps(client._responses_history())
    for marker in ('transport-only', 'summary-only', 'heartbeat', '[DONE]'):
        assert marker not in wire
    assert client._openai_request([])[2]['stream'] is True


@pytest.mark.parametrize('source', ['item_done', 'completed'])
@pytest.mark.parametrize('delta', ['', 'The ', 'The note.'])
def test_final_body_recovers_missing_or_partial_delta(source, delta):
    client = MonitorProviderClient('openai', config('gpt-test'))
    events = [{'type': 'response.output_text.delta', 'delta': delta}]
    final = {'type': 'response.completed', 'response': {'usage': {}}}
    if source == 'item_done':
        events.append({'type': 'response.output_item.done', 'item': answer_item('The note.')})
    else:
        final['response']['output'] = [answer_item('The note.')]
    blocks, usage = parse_events(client, events + [final])
    assert blocks == [{'type': 'text', 'text': 'The note.'}]
    assert usage == {}  # Missing usage alone is not invalid text.


def test_completed_body_overrides_partial_done_without_duplicate_text():
    client = MonitorProviderClient('openai', config('gpt-test'))
    blocks, _ = parse_events(client, [
        {'type': 'response.output_item.done', 'item': answer_item('The ')},
        {'type': 'response.completed', 'response': {'output': [answer_item('The note.')]}}
    ])
    assert blocks == [{'type': 'text', 'text': 'The note.'}]


@pytest.mark.parametrize('output', [[], [answer_item('Unrelated body')]])
def test_delta_disagreeing_with_final_output_is_not_accepted(output):
    client = MonitorProviderClient('openai', config('gpt-test'))
    with pytest.raises(RetryableProviderError):
        parse_events(client, [
            {'type': 'response.output_text.delta', 'delta': 'Provisional text'},
            {'type': 'response.completed', 'response': {'output': output}},
        ])


@pytest.mark.parametrize('delta', [' ', '\n', '\r\n\t'])
def test_tool_only_padding_is_not_promoted_but_valid_tool_survives(delta):
    client = MonitorProviderClient('openai', config('gpt-test'))
    call = {'type': 'function_call', 'id': 'fc1', 'call_id': 'call1',
            'name': 'file_read', 'arguments': '{"path":"task/original_task.txt"}'}
    blocks, _ = parse_events(client, [
        {'type': 'response.output_text.delta', 'delta': delta},
        {'type': 'response.completed', 'response': {'output': [call]}},
    ])
    assert not any(b['type'] == 'text' for b in blocks)
    assert any(b['type'] == 'tool_use' and b['name'] == 'file_read' for b in blocks)


def test_nonwhitespace_or_contradictory_tool_is_still_rejected():
    call = {'type': 'function_call', 'id': 'fc1', 'call_id': 'call1',
            'name': 'file_read', 'arguments': '{"path":"task/original_task.txt"}'}
    client = MonitorProviderClient('openai', config('gpt-test'))
    with pytest.raises(RetryableProviderError):
        parse_events(client, [
            {'type': 'response.output_text.delta', 'delta': '.'},
            {'type': 'response.completed', 'response': {'output': [call]}},
        ])
    with pytest.raises(RetryableProviderError):
        parse_events(client, [
            {'type': 'response.output_text.delta', 'delta': '\n'},
            {'type': 'response.output_item.done', 'output_index': 0,
             'item': {**call, 'arguments': '{"path":"different"}'}},
            {'type': 'response.completed', 'response': {'output': [call]}},
        ])


@pytest.mark.parametrize('exhaust', [False, True])
def test_reasoning_echo_retries_same_history_without_committing(exhaust, monkeypatch):
    client = MonitorProviderClient('openai', config('gpt-test', max_retries=1))
    monkeypatch.setattr(client._cancelled, 'wait', lambda _: False)
    snapshots = []
    summary = '**Planning note revision****Checking evidence**'
    reasoning = {'type': 'reasoning', 'id': 'rs-test', 'status': 'completed',
                 'summary': [{'type': 'summary_text', 'text': summary}]}

    def request(tools):
        snapshots.append(client.export_history())
        body = summary if exhaust or len(snapshots) == 1 else 'Uncertainty remains; inspect the evidence.'
        return parse_events(client, [
            {'type': 'response.output_item.done', 'item': reasoning},
            {'type': 'response.output_text.delta', 'delta': body},
            {'type': 'response.completed', 'response': {'usage': {}}},
        ])

    monkeypatch.setattr(client, '_request_once', request)
    if exhaust:
        with pytest.raises(ProviderError):
            client.complete([{'role': 'user', 'content': 'continue'}], [])
        assert len(client.history) == 1
    else:
        response = client.complete([{'role': 'user', 'content': 'continue'}], [])
        assert response.content.startswith('Uncertainty remains')
        assert client.history[-1]['content'][0]['item'] == reasoning
    assert len(snapshots) == 2 and snapshots[0] == snapshots[1]
    assert client.request_attempts[0]['outcome'] == 'retryable_error'


def test_short_natural_note_or_headings_are_not_prohibited():
    client = MonitorProviderClient('openai', config('gpt-test'))
    for note in ['Unknown.', '# Status\nNeed evidence.']:
        blocks, _ = parse_events(client, [
            {'type': 'response.completed', 'response': {'output': [answer_item(note)]}}
        ])
        assert blocks == [{'type': 'text', 'text': note}]


@pytest.mark.parametrize('blank', ['', ' ', '\n\t'])
@pytest.mark.parametrize('exhaust', [False, True])
def test_blank_response_retries_before_history_commit(blank, exhaust, monkeypatch):
    client = MonitorProviderClient('openai', config('gpt-test', max_retries=1))
    monkeypatch.setattr(client._cancelled, 'wait', lambda _: False)
    snapshots = []

    def request(tools):
        snapshots.append(client.export_history())
        body = blank if exhaust or len(snapshots) == 1 else 'Continue investigating.'
        return parse_events(client, [
            {'type': 'response.output_text.delta', 'delta': body},
            {'type': 'response.completed', 'response': {
                'output': [answer_item(body)], 'usage': {}}},
        ])

    monkeypatch.setattr(client, '_request_once', request)
    if exhaust:
        with pytest.raises(ProviderError, match='Empty model response'):
            client.complete([{'role': 'user', 'content': 'review'}], [])
        assert len(client.history) == 1
        assert client.request_attempts[-1]['outcome'] == 'retries_exhausted'
    else:
        result = client.complete([{'role': 'user', 'content': 'review'}], [])
        assert result.content == 'Continue investigating.'
        assert len(client.history) == 2
    assert len(snapshots) == 2 and snapshots[0] == snapshots[1]
    assert client.request_attempts[0]['outcome'] == 'retryable_error'


def test_blank_retry_does_not_consume_review_turn(monkeypatch):
    from monitor_agent_core.actions import MonitorAction, ToolOutcome
    from monitor_agent_core.loop import run_review

    client = MonitorProviderClient('openai', config('gpt-test', max_retries=1))
    monkeypatch.setattr(client._cancelled, 'wait', lambda _: False)
    responses = iter([
        ([{'type': 'text', 'text': ' '}], {}),
        ([{'type': 'tool_use', 'id': 'call_wait', 'name': 'wait', 'input': {}}], {}),
    ])
    monkeypatch.setattr(client, '_request_once', lambda tools: next(responses))
    action = run_review(
        client, 'monitor', 'review', [],
        lambda *args: ToolOutcome({}, action=MonitorAction('wait', {})), max_turns=1,
    )
    assert action.kind == 'wait'
    assert len(client.request_attempts) == 2
    assert not any(b.get('text') == ' ' for m in client.history for b in m['content'])


def test_blank_usage_is_recorded_and_retry_remains_cancellable(monkeypatch):
    client = MonitorProviderClient('openai', config('gpt-test', max_retries=2))
    events = []
    monkeypatch.setattr(client, '_progress', lambda event, **data: events.append((event, data)))
    monkeypatch.setattr(client, '_request_once', lambda tools: (
        [{'type': 'text', 'text': ' '}], {'input_tokens': 123}))

    def cancel_during_backoff(delay):
        client._cancelled.set()
        return True

    monkeypatch.setattr(client._cancelled, 'wait', cancel_during_backoff)
    with pytest.raises(ProviderError, match='cancelled'):
        client.complete([{'role': 'user', 'content': 'review'}], [])
    assert len(client.history) == 1
    assert len(client.request_attempts) == 1
    assert client.request_attempts[0]['outcome'] == 'cancelled'
    assert [data['usage'] for event, data in events if event == 'request_usage'] == [
        {'input_tokens': 123}]
    assert any(event == 'response_empty' for event, _ in events)


def config(model="claude-test", **overrides):
    return {
        "apikey": "test", "apibase": "https://example.test", "model": model,
        **overrides,
    }


@pytest.mark.parametrize('code', ['upstream_error', 'server_error', 'stream_read_error'])
def test_temporary_stream_error_classification(code):
    assert isinstance(_remote_error({'type': code}), RetryableProviderError)


@pytest.mark.parametrize('code', ['insufficient_quota', 'authentication_error', 'invalid_request_error'])
def test_permanent_error_takes_priority(code):
    error = _remote_error({'type': 'upstream_error', 'code': code})
    assert type(error) is ProviderError


def test_stream_failure_retries_same_history_and_discards_partial_tool(monkeypatch):
    client = MonitorProviderClient('openai', config('gpt-test', max_retries=2))
    monkeypatch.setattr(client._cancelled, 'wait', lambda delay: False)
    snapshots = []
    def request(tools):
        snapshots.append(client.export_history())
        events = [
            {'type': 'response.output_item.added', 'output_index': 0,
             'item': {'type': 'function_call', 'call_id': 'bad', 'name': 'file_write'}},
            {'type': 'error', 'error': {'type': 'upstream_error'}},
        ] if len(snapshots) == 1 else [
            {'type': 'response.output_text.delta', 'delta': 'recovered'},
            {'type': 'response.completed', 'response': {'usage': {}}},
        ]
        return client._parse_openai_responses(['data: ' + json.dumps(e) for e in events])
    monkeypatch.setattr(client, '_request_once', request)
    response = client.complete([{'role': 'user', 'content': 'continue'}], [])
    assert snapshots[0] == snapshots[1]
    assert response.content == 'recovered' and not response.tool_calls
    assert len(client.history) == 2
    assert 'bad' not in json.dumps(client.history)
    assert [r['outcome'] for r in client.drain_telemetry()['request_attempts']] == ['retryable_error', 'success']


def test_retry_exhaustion_is_bounded(monkeypatch):
    client = MonitorProviderClient('openai', config('gpt-test', max_retries=2))
    monkeypatch.setattr(client._cancelled, 'wait', lambda delay: False)
    def fail(tools): raise RetryableProviderError('temporary')
    monkeypatch.setattr(client, '_request_once', fail)
    with pytest.raises(ProviderError):
        client.complete([{'role': 'user', 'content': 'continue'}], [])
    assert len(client.request_attempts) == 3
    assert client.request_attempts[-1]['outcome'] == 'retries_exhausted'
    assert len(client.history) == 1


def test_cancel_does_not_restart_request(monkeypatch):
    client = MonitorProviderClient('openai', config('gpt-test', max_retries=2))
    def fail(tools):
        client._cancelled.set()
        raise RetryableProviderError('cancelled stream')
    monkeypatch.setattr(client, '_request_once', fail)
    with pytest.raises(ProviderError, match='cancelled'):
        client._request([])
    assert len(client.request_attempts) == 1
    assert client.request_attempts[0]['outcome'] == 'cancelled'


@pytest.mark.parametrize('status,error,retry', [
    (503, {}, True), (429, {'code': 'insufficient_quota'}, False),
    (401, {}, False), (400, {'type': 'invalid_request_error'}, False),
])
def test_http_error_routing(monkeypatch, status, error, retry):
    client = MonitorProviderClient('openai', config('gpt-test', max_retries=1))
    monkeypatch.setattr(client._cancelled, 'wait', lambda delay: False)
    calls = []
    class HTTPResponse:
        status_code = status
        text = json.dumps({'error': error})
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def json(self): return {'error': error}
    def post(*args, **kwargs):
        calls.append(1)
        return HTTPResponse()
    monkeypatch.setattr('monitor_agent_core.provider.requests.post', post)
    with pytest.raises(ProviderError): client._request([])
    assert len(calls) == (2 if retry else 1)


def test_provider_kind_comes_from_explicit_config_or_model():
    assert MonitorProviderClient("anything", {**config(), "provider": "anthropic"}).provider == "anthropic"
    assert MonitorProviderClient("native_openai", config("gpt-5.6")).provider == "openai"


def test_anthropic_sse_preserves_thinking_signature_and_tool_call():
    client = MonitorProviderClient("native_claude", config())
    events = [
        {"type": "message_start", "message": {"usage": {"input_tokens": 10}}},
        {"type": "content_block_start", "content_block": {"type": "thinking"}},
        {"type": "content_block_delta", "delta": {"type": "thinking_delta", "thinking": "inspect"}},
        {"type": "content_block_delta", "delta": {"type": "signature_delta", "signature": "signed"}},
        {"type": "content_block_stop"},
        {"type": "content_block_start", "content_block": {"type": "tool_use", "id": "c1", "name": "file_read"}},
        {"type": "content_block_delta", "delta": {"type": "input_json_delta", "partial_json": '{"path":"task/x"}'}},
        {"type": "content_block_stop"},
        {"type": "message_delta", "usage": {"output_tokens": 5}},
        {"type": "message_stop"},
    ]
    lines = [("data: " + json.dumps(event)).encode() for event in events]
    blocks, usage = client._parse_anthropic(lines)
    assert blocks[0] == {"type": "thinking", "thinking": "inspect", "signature": "signed"}
    assert blocks[1]["input"] == {"path": "task/x"}
    assert usage == {"input_tokens": 10, "output_tokens": 5}


def test_openai_responses_sse_parses_text_and_function_call():
    client = MonitorProviderClient("native_openai", config("gpt-5.6"))
    events = [
        {"type": "response.output_item.done", "output_index": 0, "item": {
            "type": "reasoning", "id": "rs_1", "encrypted_content": "opaque",
        }},
        {"type": "response.output_text.delta", "delta": "checking"},
        {"type": "response.output_item.added", "output_index": 1, "item": {
            "type": "function_call", "call_id": "call-1", "name": "wait",
        }},
        {"type": "response.function_call_arguments.delta", "output_index": 1, "delta": '{"after_turns":'},
        {"type": "response.function_call_arguments.done", "output_index": 1, "arguments": '{"after_turns":3}'},
        {"type": "response.completed", "response": {"usage": {"input_tokens": 20, "output_tokens": 4}}},
    ]
    blocks, usage = client._parse_openai_responses([
        ("data: " + json.dumps(event)).encode() for event in events
    ])
    assert blocks[0]["type"] == "openai_item"
    assert blocks[0]["item"]["encrypted_content"] == "opaque"
    assert blocks[1] == {"type": "text", "text": "checking"}
    assert blocks[2]["name"] == "wait"
    assert blocks[2]["input"] == {"after_turns": 3}
    assert usage["input_tokens"] == 20

    client.history = [{"role": "assistant", "content": blocks}]
    rebuilt = client._responses_history()
    assert rebuilt[1]["encrypted_content"] == "opaque"
    assert rebuilt[2]["type"] == "function_call"


def test_history_export_and_restore_are_independent_copies():
    first = MonitorProviderClient("native_claude", config())
    first.history = [{"role": "user", "content": [{"type": "text", "text": "state"}]}]
    exported = first.export_history()
    second = MonitorProviderClient("native_claude", config())
    second.restore_history(exported)
    exported[0]["content"][0]["text"] = "mutated"
    assert second.history[0]["content"][0]["text"] == "state"


def test_reasoning_status_is_removed_only_from_wire_copy():
    client = MonitorProviderClient('openai', config('gpt-test'))
    original = {
        'id': 'rs-final', 'type': 'reasoning', 'status': 'completed',
        'summary': [{'type': 'summary_text', 'text': 'Inspect the evidence'}],
        'encrypted_content': 'opaque-context',
    }
    client.history = [{'role': 'assistant', 'content': [
        {'type': 'openai_item', 'item': original},
        {'type': 'tool_use', 'id': 'call-1', 'name': 'intervene',
         'input': {'message': 'Check the test', 'status': 'meaningful-argument'}},
    ]}]
    before = client.export_history()
    wire = client._responses_history()
    assert wire[0] == {key: value for key, value in original.items() if key != 'status'}
    assert json.loads(wire[1]['arguments'])['status'] == 'meaningful-argument'
    assert client.export_history() == before
    restored = MonitorProviderClient('openai', config('gpt-test'))
    restored.restore_history(before)
    assert restored._responses_history() == wire


def test_large_window_compaction_keeps_initialization_and_recent_repair():
    client = MonitorProviderClient(
        "native_openai", config("gpt-5.6-sol", monitor_history_char_limit=6000)
    )
    def review(label, result_size):
        return [
            {"role": "user", "content": [{"type": "text", "text": f"wake-{label}"}]},
            {"role": "assistant", "content": [{
                "type": "tool_use", "id": f"read-{label}", "name": "file_read", "input": {},
            }]},
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": f"read-{label}",
                "content": "x" * result_size,
            }]},
            {"role": "assistant", "content": [{
                "type": "tool_use", "id": f"wait-{label}", "name": "wait",
                "input": {"after_turns": 2},
            }]},
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": f"wait-{label}",
                "content": '{"status":"accepted"}',
            }]},
        ]

    initialization = review("init", 20)
    middle = sum((review(f"old-{index}", 1500) for index in range(8)), start=[])
    recent = sum((review(f"repair-{index}", 20) for index in range(4)), start=[])
    client.history = initialization + middle + recent

    client._compact_history()

    assert client.history[:len(initialization)] == initialization
    assert client.history[-len(recent):] == recent
    assert client.history_transforms[-1]["removed_messages"] > 0
    assert client.history_measure()["characters"] <= client.history_char_limit
    rebuilt = client._responses_history()
    calls = {item["call_id"] for item in rebuilt if item.get("type") == "function_call"}
    outputs = {
        item["call_id"] for item in rebuilt if item.get("type") == "function_call_output"
    }
    assert calls == outputs


def test_gpt56_default_monitor_budget_is_wider_than_ga_baseline():
    client = MonitorProviderClient(
        "native_openai", config("gpt-5.6-sol", context_win=200000)
    )
    assert client.history_char_limit == 700000


def test_telemetry_drain_is_incremental():
    client = MonitorProviderClient("native_openai", config("gpt-5.6-sol"))
    client.usage_records.append({"input_tokens": 30, "output_tokens": 4})
    client.history_transforms.append({"kind": "monitor_history_compaction"})

    first = client.drain_telemetry()
    second = client.drain_telemetry()

    assert first["usage"] == [{"input_tokens": 30, "output_tokens": 4}]
    assert first["history_transforms"] == [{"kind": "monitor_history_compaction"}]
    assert second == {"usage": [], "history_transforms": []}


def test_control_tool_result_closes_call_before_next_wake():
    client = MonitorProviderClient("native_openai", config("gpt-5.6-sol"))
    client.history = [
        {"role": "user", "content": [{"type": "text", "text": "wake"}]},
        {"role": "assistant", "content": [{
            "type": "tool_use", "id": "wait-1", "name": "wait",
            "input": {"after_turns": 3},
        }]},
    ]
    client.record_tool_results([{
        "tool_use_id": "wait-1", "content": '{"status":"accepted"}',
    }])
    client.history.append({
        "role": "user", "content": [{"type": "text", "text": "next wake"}],
    })

    rebuilt = client._responses_history()

    assert [item.get("type") for item in rebuilt if "type" in item] == [
        "function_call", "function_call_output",
    ]
    assert rebuilt[-1] == {"role": "user", "content": "next wake"}


def test_pending_wait_is_not_a_completed_review_for_compaction():
    client = MonitorProviderClient('native_openai', config('gpt-5.6-sol'))
    client.history = [
        {'role': 'assistant', 'content': [{'type': 'tool_use', 'id': 'w', 'name': 'wait', 'input': {}}]},
        {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': 'w',
                                     'content': '{"status":"handoff_pending"}'}]},
    ]
    assert client._review_boundaries() == []
    client.history += [
        {'role': 'assistant', 'content': [{'type': 'tool_use', 'id': 'a', 'name': 'allow_complete', 'input': {}}]},
        {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': 'a',
                                     'content': '{"status":"accepted"}'}]},
    ]
    assert client._review_boundaries() == [4]


@pytest.mark.parametrize('name', ['wait', 'allow_complete', 'intervene'])
def test_maintenance_transfer_is_exchange_not_review_boundary(name):
    client = MonitorProviderClient('native_openai', config('gpt-5.6-sol'))
    def exchange(call_id, tool, receipt):
        return [
            {'role': 'assistant', 'content': [{'type': 'tool_use',
             'id': call_id, 'name': tool, 'input': {}}]},
            {'role': 'user', 'content': [{'type': 'tool_result',
             'tool_use_id': call_id, 'content': json.dumps(receipt)}]},
        ]
    client.history = exchange('proposal', name, {
        'status': 'accepted', 'control_action': 'maintenance_complete',
        'result': {'status': 'intent_transferred', 'executed': False, 'input_sent': False},
    })
    assert client._review_boundaries() == []
    assert client._exchange_boundaries() == [2]
    client.history += exchange('actual', 'wait', {
        'status': 'accepted', 'control_action': 'wait',
    })
    assert client._review_boundaries() == [4]
    assert client._exchange_boundaries() == [2, 4]
