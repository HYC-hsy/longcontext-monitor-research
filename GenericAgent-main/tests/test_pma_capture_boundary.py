"""The optional PMA audit must not change provider delivery semantics."""

from types import SimpleNamespace

import pytest

import llmcore
from research_runtime import research_context, temporary_exporter, register_provider_call


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


@pytest.mark.parametrize('failed_event', ['provider_request_ready',
                                           'provider_request_attempt'])
def test_required_sink_failure_blocks_send_despite_optional_exporter(
        monkeypatch, failed_event):
    monkeypatch.setenv('GA_PMA_CAPTURE_TASK_REQUESTS', '1')
    sent, optional = [], []
    monkeypatch.setattr(llmcore.requests, 'post', lambda *_a, **_k: sent.append(1))
    session = SimpleNamespace(max_retries=0, stream=False, connect_timeout=1,
                              read_timeout=1, proxies=None, verify=True, api_key='fake')
    def sink(event):
        if event['event_type'] == failed_event:
            raise OSError('required sink failed')
    with temporary_exporter(optional.append), research_context({}, sink):
        with pytest.raises(RuntimeError, match='required research'):
            next(llmcore._stream_with_retry(session, 'https://offline.invalid',
                                            {}, {}, lambda _: iter(())))
    assert sent == []
    assert any(row['event_type'] == failed_event for row in optional)


def test_required_capture_without_sink_blocks_send(monkeypatch):
    monkeypatch.setenv('GA_PMA_CAPTURE_TASK_REQUESTS', '1')
    sent = []
    monkeypatch.setattr(llmcore.requests, 'post', lambda *_a, **_k: sent.append(1))
    session = SimpleNamespace(max_retries=0, stream=False, connect_timeout=1,
                              read_timeout=1, proxies=None, verify=True, api_key='fake')
    with pytest.raises(RuntimeError, match='required research'):
        next(llmcore._stream_with_retry(session, 'https://offline.invalid', {}, {},
                                        lambda _: iter(())))
    assert sent == []


def test_optional_exporter_does_not_require_persistent_sink(monkeypatch):
    monkeypatch.delenv('GA_PMA_CAPTURE_TASK_REQUESTS', raising=False)
    sent, optional = [], []
    monkeypatch.setattr(llmcore.requests, 'post',
                        lambda *_a, **_k: sent.append(1) or Response())
    session = SimpleNamespace(max_retries=0, stream=False, connect_timeout=1,
                              read_timeout=1, proxies=None, verify=True)
    def parser(_response):
        if False:
            yield None
        return [{'type': 'text', 'text': 'accepted'}]
    with temporary_exporter(optional.append):
        with pytest.raises(StopIteration) as result:
            next(llmcore._stream_with_retry(session, 'https://offline.invalid', {},
                                            {}, parser))
    assert result.value.value == [{'type': 'text', 'text': 'accepted'}]
    assert sent == [1]


def test_usage_distinguishes_returned_zero_from_missing_cache(monkeypatch):
    events = []
    with research_context({}, events.append):
        register_provider_call({'llm_call_id': 'usage-fixture'})
        llmcore._record_usage({'input_tokens': 0, 'output_tokens': 1}, 'messages')
    usage = next(row['payload'] for row in events
                 if row['event_type'] == 'provider_usage')
    assert usage['input_tokens'] == 0
    assert usage['cache_read_input_tokens'] is None
    assert usage['cache_creation_input_tokens'] is None


@pytest.mark.parametrize('body, expected', [
    ('{"error":{"type":"billing_error","message":"SECRET_ENDPOINT"}}',
     'billing_error'),
    ('{"error":{"code":"insufficient_quota","message":"SECRET_ENDPOINT"}}',
     'insufficient_quota'),
    ('<html>private route SECRET_ENDPOINT</html>', None),
])
def test_auxiliary_http_error_records_safe_diagnosis_without_retry(
        monkeypatch, body, expected):
    monkeypatch.setenv('GA_PMA_CAPTURE_TASK_REQUESTS', '1')
    posts, events = [], []

    class ErrorResponse(Response):
        status_code = 502
        headers = {'content-type': 'application/json; charset=utf-8',
                   'x-request-id': 'SECRET_REQUEST_ID',
                   'authorization': 'SECRET_AUTH'}
        text = body

    monkeypatch.setattr(llmcore.requests, 'post',
                        lambda *_a, **_k: posts.append(1) or ErrorResponse())
    session = SimpleNamespace(max_retries=0, stream=True, connect_timeout=1,
                              read_timeout=1, proxies=None, verify=True,
                              api_key='SECRET_KEY', candidate_auxiliary_integrity=True)
    with research_context({'run_id': 'safe-error-fixture'}, events.append):
        with pytest.raises(llmcore.AuxiliaryResponseRejected, match='http_error'):
            next(llmcore._stream_with_retry(session, 'https://offline.invalid',
                                            {}, {'messages': []}, lambda _: iter(())))
    assert posts == [1]
    result = next(event['payload'] for event in events
                  if event['event_type'] == 'provider_response')
    assert result['status_code'] == 502
    assert result.get('error_type', result.get('error_code')) == expected
    assert result['error_body_captured_bytes'] == len(body.encode())
    assert len(result['error_body_sha256']) == 64
    assert len(result['request_id_sha256']) == 64
    assert result['content_type'] == 'application/json' or expected is None
    assert all(secret not in str(events) for secret in
               ('SECRET_ENDPOINT', 'SECRET_REQUEST_ID', 'SECRET_AUTH', 'SECRET_KEY'))


def test_auxiliary_error_receipt_failure_does_not_resend(monkeypatch):
    monkeypatch.setenv('GA_PMA_CAPTURE_TASK_REQUESTS', '1')
    posts = []

    class ErrorResponse(Response):
        status_code = 502
        text = '{"error":{"type":"billing_error"}}'

    monkeypatch.setattr(llmcore.requests, 'post',
                        lambda *_a, **_k: posts.append(1) or ErrorResponse())
    session = SimpleNamespace(max_retries=0, stream=True, connect_timeout=1,
                              read_timeout=1, proxies=None, verify=True,
                              api_key='fake', candidate_auxiliary_integrity=True)

    def sink(event):
        if event['event_type'] == 'provider_response':
            raise OSError('fixture sink failure')

    with research_context({'run_id': 'safe-error-fixture'}, sink):
        with pytest.raises(llmcore.AuxiliaryResponseRejected, match='capture_failed'):
            next(llmcore._stream_with_retry(session, 'https://offline.invalid',
                                            {}, {'messages': []}, lambda _: iter(())))
    assert posts == [1]
