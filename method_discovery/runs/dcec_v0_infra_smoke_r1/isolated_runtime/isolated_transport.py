"""Fixed-endpoint HTTP over a Unix socket; no generic forward-proxy interface.

Gateway runs outside the network-less task. Local mode exposes only loopback
HTTP inside it, keeping both providers and all tool subprocesses network-less.
"""
import argparse
import http.client
import http.server
import json
import os
import re
import socket
import socketserver
import ssl
import sys
import threading
import time
from urllib.parse import urlsplit


MAX_BODY = 32 * 1024 * 1024
PATHS = {'/v1/messages', '/v1/messages?beta=true', '/v1/responses',
         '/v1/chat/completions', '/v1/traces'}
FORWARD_HEADERS = {'content-type', 'accept', 'anthropic-version', 'anthropic-beta',
                   'content-encoding', 'user-agent', 'x-model-route'}


def create_tls_context(route):
    """Reproduce the frozen production profile's certificate-verification semantics."""
    tls = route.get('tls') or {}
    enabled = tls.get('verification_enabled')
    if enabled is True:
        ca_file = tls.get('ca_file')
        if not isinstance(ca_file, str) or not ca_file:
            raise ValueError('Verified TLS requires an explicit CA bundle')
        return ssl.create_default_context(cafile=ca_file)
    if enabled is False:
        return ssl._create_unverified_context()
    raise ValueError('TLS verification semantics are not configured')


def reject_remote_media(value):
    if isinstance(value, list):
        for item in value:
            reject_remote_media(item)
    elif isinstance(value, dict):
        for key in ('image_url', 'file_url'):
            url = value.get(key)
            if isinstance(url, dict):
                url = url.get('url')
            if isinstance(url, str) and not url.startswith('data:'):
                raise ValueError('Remote media fetch is unavailable')
        if isinstance(value.get('source'), dict) and value['source'].get('type') == 'url':
            raise ValueError('Remote media fetch is unavailable')
        if value.get('type') == 'input_file' and value.get('file_id'):
            raise ValueError('Remote stored files are unavailable')
        for item in value.values():
            reject_remote_media(item)


def provider_url(base, operation):
    """Mirror monitor_agent_core.provider._url without importing the Monitor runtime."""
    base, operation = base.rstrip('/'), operation.strip('/')
    if base.endswith('$'):
        return base[:-1].rstrip('/')
    if base.endswith(operation):
        return base
    return f'{base}/{operation}' if re.search(r'/v\d+(/|$)', base) else f'{base}/v1/{operation}'


def _resolve_request(path, body, config, route_id=None):
    if path not in PATHS:
        raise ValueError('Only fixed inference endpoints and trace ingestion are available')
    if path == '/v1/traces':
        return config['telemetry'], {}, body, None
    payload = json.loads(body)
    reject_remote_media(payload.get('input', payload.get('messages', [])))
    model = payload.get('model')
    route = config['models'].get(route_id or model)
    if not route or path.split('?')[0] not in route['paths']:
        raise ValueError('Model/endpoint is not configured for this run')
    if route.get('model', model) != model:
        raise ValueError('Model does not match the configured route')
    # Providers must not obtain external data through hosted search/fetch tools.
    if any(t.get('type', 'function') != 'function' for t in payload.get('tools', [])):
        raise ValueError('Only client-executed function tools are permitted')
    if payload.get('previous_response_id') or payload.get('conversation'):
        raise ValueError('Remote session reuse is not permitted')
    if 'input' in payload:
        payload['store'] = False
    requested = urlsplit(path)
    operation = requested.path.rstrip('/').rsplit('/', 1)[-1]
    url = provider_url(route['base'], operation)
    if requested.query:
        # Production request builders append their fixed query after _url().
        url += '?' + requested.query
    return url, route['headers'], json.dumps(payload).encode(), route


def resolve_request(path, body, config, route_id=None):
    """Compatibility wrapper used by existing callers and tests."""
    return _resolve_request(path, body, config, route_id)[:3]


def emit_transport_event(stage, *, status='ok', exception_type=None, http_status=None):
    """Emit only whitelisted transport metadata; never payloads, URLs, or headers."""
    event = {
        'event': 'gateway_transport', 'timestamp': time.time(),
        'thread': threading.get_ident(), 'stage': stage, 'status': status,
    }
    if exception_type:
        event['exception_type'] = exception_type
    if isinstance(http_status, int):
        event['http_status'] = http_status
    print(json.dumps(event, separators=(',', ':')), file=sys.stderr, flush=True)


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path):
        super().__init__('localhost', timeout=1000)
        self.socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *_):
        pass  # Never log payloads, credentials or model output.

    def do_POST(self):
        conn = None
        started = False
        stage = 'resolve'
        try:
            if self.headers.get('Transfer-Encoding'):
                raise ValueError('A fixed Content-Length is required')
            lengths = self.headers.get_all('Content-Length', [])
            if len(lengths) != 1:
                raise ValueError('Exactly one Content-Length is required')
            size = int(lengths[0])
            if not 0 < size <= MAX_BODY:
                raise ValueError('Invalid body length')
            body = self.rfile.read(size)
            if len(body) != size:
                raise ValueError('Incomplete body')
            headers = {k.lower(): v for k, v in self.headers.items()
                       if k.lower() in FORWARD_HEADERS}
            if self.server.mode == 'local':
                if self.path not in PATHS:
                    raise ValueError('Unsupported endpoint')
                conn = UnixHTTPConnection(self.server.socket_path)
                target = self.path
            else:
                # The frozen route header is both an internal route selector and a
                # production application header.  Validate it, but do not consume it.
                route_id = headers.get('x-model-route')
                url, credentials, body, route = _resolve_request(
                    self.path, body, self.server.config, route_id)
                parsed = urlsplit(url)
                headers.update(credentials)
                if parsed.scheme == 'https':
                    conn = http.client.HTTPSConnection(parsed.hostname, parsed.port,
                        timeout=1000, context=create_tls_context(route))
                elif self.path == '/v1/traces' and parsed.scheme == 'http':
                    conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=30)
                else:
                    raise ValueError('Inference requires HTTPS')
                target = parsed.path + ('?' + parsed.query if parsed.query else '')
                emit_transport_event('resolved')
            stage = 'connect'
            conn.connect()
            if self.server.mode == 'gateway':
                emit_transport_event('connected')
            stage = 'request_send'
            conn.request('POST', target, body=body, headers=headers)
            if self.server.mode == 'gateway':
                emit_transport_event('request_sent')
            stage = 'response_headers'
            response = conn.getresponse()
            if self.server.mode == 'gateway':
                emit_transport_event('response_headers_received', http_status=response.status)
            # Redirects must never become a generic external fetch primitive.
            if 300 <= response.status < 400:
                raise ValueError('Upstream redirects are forbidden')
            self.send_response(response.status)
            self.send_header('Content-Type', response.getheader('Content-Type', 'application/json'))
            encoding = response.getheader('Content-Encoding')
            if encoding:
                self.send_header('Content-Encoding', encoding)
            self.send_header('Connection', 'close')
            self.end_headers()
            started = True
            stage = 'response_stream'
            while chunk := response.read1(65536):
                self.wfile.write(chunk)
                self.wfile.flush()
            if self.server.mode == 'gateway':
                emit_transport_event('response_stream_completed', http_status=response.status)
        except (ValueError, KeyError, TypeError) as exc:
            if self.server.mode == 'gateway':
                emit_transport_event(stage, status='error', exception_type=type(exc).__name__)
            if not started:
                self.send_error(400, str(exc))
        except Exception as exc:
            if self.server.mode == 'gateway':
                emit_transport_event(stage, status='error', exception_type=type(exc).__name__)
            if not started:
                self.send_error(502, 'Isolated transport failed')
        finally:
            if conn:
                conn.close()
            self.close_connection = True


class UnixServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    address_family = getattr(socket, 'AF_UNIX', -1)
    daemon_threads = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['gateway', 'local'])
    parser.add_argument('--socket', default='/run/model-channel/gateway.sock')
    parser.add_argument('--config')
    parser.add_argument('--port', type=int, default=18765)
    args = parser.parse_args()
    if not hasattr(socket, 'AF_UNIX'):
        raise RuntimeError('Isolated transport must run inside the Linux containers')
    if args.mode == 'gateway':
        if os.path.lexists(args.socket):
            os.unlink(args.socket)
        server = UnixServer(args.socket, Handler)
        server.config = json.load(open(args.config, encoding='utf-8'))
        os.chmod(args.socket, 0o666)
    else:
        server = http.server.ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.mode = args.mode
    server.socket_path = args.socket
    server.serve_forever()


if __name__ == '__main__':
    main()
