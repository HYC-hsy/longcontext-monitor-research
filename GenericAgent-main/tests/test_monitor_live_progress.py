import json
import threading

import pytest

from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.workspace import MonitorWorkspace


def client():
    return MonitorProviderClient('openai', {
        'apikey': 'test-secret', 'apibase': 'https://example.test', 'model': 'gpt-test',
    })


def test_completed_stops_stream_preserves_tool_usage_and_closes_http(monkeypatch):
    closed = []

    class Response:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            closed.append(True)

        def iter_lines(self):
            events = [
                {'type': 'response.output_item.added', 'output_index': 0,
                 'item': {'type': 'function_call', 'call_id': 'c1', 'name': 'wait'}},
                {'type': 'response.function_call_arguments.done', 'output_index': 0,
                 'arguments': '{"after_turns":2}'},
                {'type': 'response.completed', 'response': {'usage': {'input_tokens': 12}}},
            ]
            for event in events:
                yield ('data: ' + json.dumps(event)).encode()
            raise AssertionError('Must not wait for EOF after completed')

    monkeypatch.setattr('monitor_agent_core.provider.requests.post', lambda *a, **k: Response())
    c = client()
    result = c.complete([{'role': 'user', 'content': 'continue'}], [])
    assert result.tool_calls[0].name == 'wait'
    assert json.loads(result.tool_calls[0].arguments) == {'after_turns': 2}
    assert result.usage == {'input_tokens': 12}
    assert closed == [True]
    assert c._active_response is None


def test_request_started_is_durable_before_request_returns(tmp_path, monkeypatch):
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    c = client()
    agent = MonitorAgent(c, MonitorWorkspace(evidence, tmp_path / 'private'))
    entered, release = threading.Event(), threading.Event()
    results = []

    def request(tools):
        entered.set()
        release.wait(3)
        return [{'type': 'text', 'text': 'done'}], {'input_tokens': 1}

    monkeypatch.setattr(c, '_request_once', request)
    thread = threading.Thread(target=lambda: results.append(c.complete(
        [{'role': 'user', 'content': 'PRIVATE PROMPT'}], [])))
    thread.start()
    try:
        assert entered.wait(2)
        path = tmp_path / 'private/audit/progress.jsonl'
        rows = [json.loads(x) for x in path.read_text().splitlines()]
        assert [r['event'] for r in rows] == ['request_started']
        assert 'PRIVATE PROMPT' not in path.read_text()
        assert 'test-secret' not in path.read_text()
    finally:
        release.set()
        thread.join(3)
    assert len(results) == 1
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    assert [r['event'] for r in rows] == ['request_started', 'request_usage', 'request_finished']
    assert len({r['request_id'] for r in rows}) == 1
    agent.dispatch('file_read', {'path': 'task/missing'})
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    assert [r['event'] for r in rows[-2:]] == ['tool_started', 'tool_finished']
    assert rows[-1]['tool_id'] == rows[-2]['tool_id']


def test_progress_write_failure_does_not_disable_tool(tmp_path):
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    (evidence / 'original.txt').write_text('requirements')
    agent = MonitorAgent(client(), MonitorWorkspace(evidence, tmp_path / 'private'))
    (tmp_path / 'private/audit').write_text('block directory creation')
    with pytest.warns(UserWarning, match='progress recording unavailable'):
        result = agent.dispatch('file_read', {'path': 'task/original.txt'})
    assert result.data['content'] == 'requirements'
