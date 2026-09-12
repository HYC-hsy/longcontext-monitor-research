import json

import pytest

from monitor_agent_core.provider import (
    HistoryCapacityError, MonitorProviderClient, ProviderRecoveryExhausted,
)


def make_client(limit=4000):
    client = MonitorProviderClient('openai', {
        'apikey': 'fixture', 'apibase': 'https://example.test',
        'monitor_history_char_limit': limit,
    })
    client.prepare_continuation = lambda: 'Still checking the original requirement; uptake unobserved.'
    archives = []
    client.archive_continuation_history = lambda history: (
        archives.append(history) or 'monitor/audit/history/fixture.json'
    )
    return client, archives


def exchange(index, size=500):
    return [
        {'role': 'assistant', 'content': [
            {'type': 'text', 'text': 'why ' + 'x' * size},
            {'type': 'tool_use', 'id': str(index), 'name': 'file_read', 'input': {}},
        ]},
        {'role': 'user', 'content': [
            {'type': 'tool_result', 'tool_use_id': str(index), 'content': 'evidence ' + 'y' * size},
        ]},
    ]


def test_long_unfinished_review_compacts_without_wait_or_releasing_concern():
    client, archives = make_client()
    client.history = sum([exchange(n) for n in range(10)], [])
    original = client.export_history()
    assert client._review_boundaries() == []
    client._compact_history()
    assert archives == [original]
    assert client.history[-2:] == original[-2:]
    assert 'uptake unobserved' in client.history[0]['content'][0]['text']
    assert client.history_measure()['characters'] <= client.history_char_limit
    assert client.history_transforms[-1]['boundary_kind'] == 'protocol_exchange'


def test_parallel_tool_batch_and_reasoning_are_not_split():
    client, _ = make_client()
    signed = {'type': 'openai_item', 'item': {'type': 'reasoning', 'encrypted_content': 'opaque'}}
    client.history = [
        {'role': 'assistant', 'content': [signed,
            {'type': 'tool_use', 'id': 'a', 'name': 'file_read'},
            {'type': 'tool_use', 'id': 'b', 'name': 'file_read'}]},
        {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': 'a', 'content': 'A'}]},
        {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': 'b', 'content': 'B'}]},
    ]
    assert client._exchange_boundaries() == [3]
    assert client.history[0]['content'][0] == signed


def test_pending_batch_survives_prefix_retirement():
    client, _ = make_client()
    client.history = sum([exchange(n) for n in range(8)], [])
    pending = exchange('pending')[0]
    client.history.append(pending)
    client._compact_history()
    assert client.history[-1] == pending
    assert client.history[-3:-1] == exchange(7)


def test_failed_handoff_preserves_original_and_is_terminal_not_another_wake():
    client, archives = make_client()
    client.history = sum([exchange(n) for n in range(8)], [])
    original = client.export_history()
    client.prepare_continuation = lambda: (_ for _ in ()).throw(ValueError('empty'))
    with pytest.raises(HistoryCapacityError) as error:
        client._compact_history()
    assert isinstance(error.value, ProviderRecoveryExhausted)
    assert client.history == original
    assert archives == [original]


def test_single_oversized_unretirable_exchange_is_explicit_failure():
    client, _ = make_client()
    client.history = exchange(1, 3000)
    original = client.export_history()
    with pytest.raises(HistoryCapacityError):
        client._compact_history()
    assert client.history == original


def test_oversized_handoff_never_replaces_original_history():
    client, _ = make_client()
    client.history = sum([exchange(n) for n in range(8)], [])
    original = client.export_history()
    client.prepare_continuation = lambda: 'z' * 10000
    with pytest.raises(HistoryCapacityError):
        client._compact_history()
    assert client.history == original


def test_successive_continuations_do_not_accumulate_previous_handoff():
    client, archives = make_client()
    for batch in range(4):
        client.history.extend(sum([exchange(f'{batch}-{n}') for n in range(8)], []))
        client._compact_history()
        assert json.dumps(client.history).count('Current working understanding') == 1
        assert client.history_measure()['characters'] <= client.history_char_limit
    assert len(archives) == 4


def test_worker_capacity_failure_does_not_consume_another_wake(tmp_path, monkeypatch):
    import queue
    from monitor_agent_core.runtime import _worker
    import monitor_agent_core.agent as module
    calls = []

    class FailedMonitor:
        def __init__(self, *args):
            pass

        def review(self, *args, **kwargs):
            calls.append(1)
            raise HistoryCapacityError('fixture capacity failure')

    monkeypatch.setattr(module, 'MonitorAgent', FailedMonitor)
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    commands, outputs = queue.Queue(), queue.Queue()
    commands.put({'kind': 'boundary', 'cursor': 10, 'task_turn': 5})
    _worker(dict(config_name='openai', model_config={'apikey': 'fixture',
                 'apibase': 'https://example.test', 'model': 'fixture'},
                 evidence_root=evidence, private_root=tmp_path / 'private',
                 task_workspace=tmp_path, max_review_turns=20,
                 task_original_path='original_task.txt'), commands, outputs)
    failure = outputs.get_nowait()
    assert calls == [1], failure
    assert commands.qsize() == 1
    assert failure['kind'] == 'failure' and 'HistoryCapacityError' in failure['error']
    assert outputs.empty()
