"""The optional PMA audit must not change provider delivery semantics."""

from types import SimpleNamespace

import pytest

import llmcore
from research_runtime import research_context


class Response:
    status_code = 200
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


@pytest.mark.parametrize('capture,kind', [(False, 'text'), (False, 'tool_use'),
                                          (True, 'text'), (True, 'tool_use')])
def test_optional_and_required_capture_preserve_accepted_blocks(monkeypatch, capture, kind):
    monkeypatch.setenv('GA_PMA_CAPTURE_TASK_REQUESTS', '1' if capture else '0')
    sent = []
    monkeypatch.setattr(llmcore.requests, 'post', lambda *_a, **_k: sent.append(1) or Response())
    session = SimpleNamespace(max_retries=0, stream=False, connect_timeout=1,
                              read_timeout=1, proxies=None, verify=True, api_key='fake')
    block = ({'type': 'text', 'text': 'answer'} if kind == 'text' else
             {'type': 'tool_use', 'id': 'one', 'name': 'noop', 'input': {}})

    def parser(_response):
        if False:
            yield None
        return [block]

    events = []
    with research_context({'run_id': 'capture-fixture'}, events.append):
        stream = llmcore._stream_with_retry(session, 'https://offline.invalid', {},
                                            {'messages': []}, parser)
        with pytest.raises(StopIteration) as result:
            while True:
                next(stream)
    assert result.value.value == [block]
    assert sent == [1]
    assert bool([e for e in events if e['event_type'] == 'provider_response_content']) == capture


def test_disabled_telemetry_does_not_read_uninitialized_capture(monkeypatch):
    monkeypatch.delenv('GA_PMA_CAPTURE_TASK_REQUESTS', raising=False)
    monkeypatch.setattr(llmcore.requests, 'post', lambda *_a, **_k: Response())
    session = SimpleNamespace(max_retries=0, stream=False, connect_timeout=1,
                              read_timeout=1, proxies=None, verify=True)

    def parser(_response):
        if False:
            yield None
        return [{'type': 'text', 'text': 'answer'}]

    with pytest.raises(StopIteration) as result:
        next(llmcore._stream_with_retry(session, 'https://offline.invalid', {}, {}, parser))
    assert result.value.value == [{'type': 'text', 'text': 'answer'}]


def test_accepted_response_capture_failure_never_resends(monkeypatch):
    monkeypatch.setenv('GA_PMA_CAPTURE_TASK_REQUESTS', '1')
    sent = []
    monkeypatch.setattr(llmcore.requests, 'post', lambda *_a, **_k: sent.append(1) or Response())
    session = SimpleNamespace(max_retries=1, stream=False, connect_timeout=1,
                              read_timeout=1, proxies=None, verify=True, api_key='fake')

    def parser(_response):
        if False:
            yield None
        return [{'type': 'text', 'text': 'accepted'}]

    events = []

    def sink(event):
        if event['event_type'] == 'provider_response_content':
            raise OSError('fixture capture failure')
        events.append(event)

    with research_context({'run_id': 'capture-fixture'}, sink):
        with pytest.raises(StopIteration) as result:
            next(llmcore._stream_with_retry(session, 'https://offline.invalid', {}, {}, parser))
        assert result.value.value == [{'type': 'text', 'text': 'accepted'}]
        with pytest.raises(RuntimeError, match='capture failed'):
            next(llmcore._stream_with_retry(session, 'https://offline.invalid', {}, {}, parser))
    assert sent == [1]
