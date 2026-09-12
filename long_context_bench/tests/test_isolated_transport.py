import importlib.util
import json
from pathlib import Path
import threading
import http.client
import http.server

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


t = load('isolated_transport', 'adapters/isolated_transport.py')
b = load('isolated_run_bundle', 'scripts/isolated_run_bundle.py')


@pytest.fixture
def config():
    return {'models': {'test-model': {'base': 'https://example.invalid/v1',
        'headers': {'Authorization': 'Bearer PRIVATE'}, 'paths': ['/v1/responses']}},
        'telemetry': 'http://collector:15340/v1/traces'}


def test_route_is_fixed_and_session_local(config):
    url, headers, body = t.resolve_request('/v1/responses',
        b'{"model":"test-model","input":"hello","store":true}', config)
    assert url == 'https://example.invalid/v1/responses'
    assert headers['Authorization'] == 'Bearer PRIVATE'
    assert json.loads(body)['store'] is False


@pytest.mark.parametrize('path', ['https://github.com/x', '//github.com/x',
    '/v1/responses?url=https://github.com', '/v1/../files', '/v1/files', '/'])
def test_no_arbitrary_fetch(config, path):
    with pytest.raises(ValueError):
        t.resolve_request(path, b'{"model":"test-model"}', config)


@pytest.mark.parametrize('payload', [
    {'model': 'other'}, {'model': 'test-model', 'tools': [{'type': 'web_search'}]},
    {'model': 'test-model', 'previous_response_id': 'prior'},
    {'model': 'test-model', 'conversation': 'prior'},
])
def test_no_hosted_tools_or_cross_run_session(config, payload):
    with pytest.raises(ValueError):
        t.resolve_request('/v1/responses', json.dumps(payload).encode(), config)


def test_function_tools_and_trace_ingestion_remain(config):
    t.resolve_request('/v1/responses', json.dumps({'model': 'test-model',
        'tools': [{'type': 'function', 'name': 'code_run'}]}).encode(), config)
    assert t.resolve_request('/v1/traces', b'protobuf', config)[2] == b'protobuf'


@pytest.mark.parametrize('content', [
    {'type': 'input_image', 'image_url': 'https://github.com/image'},
    {'type': 'image', 'source': {'type': 'url', 'url': 'https://github.com'}},
    {'type': 'input_file', 'file_id': 'previous-run-file'},
])
def test_no_remote_media_fetch(config, content):
    with pytest.raises(ValueError):
        t.resolve_request('/v1/responses', json.dumps({'model': 'test-model',
            'input': [{'role': 'user', 'content': [content]}]}).encode(), config)


def test_local_base64_images_remain(config):
    t.resolve_request('/v1/responses', json.dumps({'model': 'test-model',
        'input': [{'role': 'user', 'content': [{'type': 'input_image',
        'image_url': 'data:image/png;base64,AAAA'}]}]}).encode(), config)


def test_stream_and_credentials_are_forwarded_without_url_control(monkeypatch, config):
    captured = {}

    class Response:
        status = 200
        chunks = iter([b'data: first\n\n', b'data: last\n\n', b''])

        def getheader(self, key, default=None):
            return 'text/event-stream' if key == 'Content-Type' else default

        def read1(self, _):
            return next(self.chunks)

    class Connection:
        def __init__(self, host, port, **kwargs):
            captured['host'] = host

        def request(self, method, target, body, headers):
            captured.update(method=method, target=target, body=body, headers=headers)

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr(t.http.client, 'HTTPSConnection', Connection)
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), t.Handler)
    server.mode, server.config = 'gateway', config
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection(*server.server_address)
        conn.request('POST', '/v1/responses', b'{"model":"test-model"}',
                     {'Authorization': 'Bearer attacker', 'Host': 'github.com'})
        response = conn.getresponse()
        assert response.status == 200
        assert response.read() == b'data: first\n\ndata: last\n\n'
        assert captured['host'] == 'example.invalid'
        assert captured['headers']['Authorization'] == 'Bearer PRIVATE'
        assert 'Host' not in captured['headers']
        conn.close()
    finally:
        server.shutdown()
        server.server_close()


def test_bundle_has_no_source_checkout_or_credentials_in_task(tmp_path):
    source = tmp_path / 'src'
    source.mkdir()
    (source / 'agentmain.py').write_text('# fixture')
    (source / 'temp').mkdir()
    (source / 'temp' / 'answer.txt').write_text('OLD ANSWER')
    (source / 'tests').mkdir()
    (source / 'tests' / 'answer.py').write_text('OLD ANSWER')
    (source / 'memory' / 'L4_raw_sessions').mkdir(parents=True)
    (source / 'memory' / 'L4_raw_sessions' / 'answer.txt').write_text('OLD ANSWER')
    (source / 'memory' / 'plan_sop.md').write_text('Generic planning')
    (source / 'mykey.py').write_text(
        "task={'model':'claude-test','apikey':'SECRET1','apibase':'https://example.invalid'}\n"
        "monitor={'model':'test-model','apikey':'SECRET2','apibase':'https://example.invalid'}")
    copied, compose = b.build_bundle(tmp_path / 'bundle', source, tmp_path / 'runtime',
                                     'python', 'task', 'monitor', 15340)
    data = json.loads(compose.read_text())
    assert data['services']['main']['network_mode'] == 'none'
    assert 'ALL' in data['services']['main']['cap_drop']
    assert not (copied / 'temp').exists()
    assert not (copied / 'tests').exists()
    assert not (copied / 'memory' / 'L4_raw_sessions').exists()
    assert (copied / 'memory' / 'plan_sop.md').read_text() == 'Generic planning'
    assert not (copied / 'mykey.py').exists()
    assert 'SECRET' not in (copied / 'mykey.json').read_text()
    assert not any('gateway' in x for x in data['services']['main']['volumes'])
    with pytest.raises(FileExistsError):
        b.build_bundle(tmp_path / 'bundle', source, tmp_path / 'runtime',
                       'python', 'task', 'monitor', 15340)
