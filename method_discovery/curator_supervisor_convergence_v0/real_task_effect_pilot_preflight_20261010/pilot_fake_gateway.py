"""Deterministic local Unix-socket provider used only by offline Harbor tests."""

from __future__ import annotations

import http.server
import json
import os
from pathlib import Path
import re
import socket
import socketserver
import threading


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.sequence = 0
        self.task_responses = 0
        self.reference_written = False
        self.intervened = False
        self.root_code_returned = False
        self.contrast = None

    def next(self, route, body):
        with self.lock:
            self.sequence += 1
            sequence = self.sequence
            if route != 'monitor':
                self.task_responses += 1
                return sequence, None, ('<summary>Offline fixture.</summary> '
                                        'Offline Task completion.'), {}
            if not self.reference_written:
                self.reference_written = True
                return sequence, 'file_write', '', {
                    'path': 'monitor/reference.md',
                    'content': 'Offline fixture Task Book; task authority remains original_task.txt.\n',
                    'mode': 'replace',
                }
            root = any(tool.get('name') == 'allow_complete' and
                       'release_blocking_state' in
                       tool.get('input_schema', {}).get('properties', {})
                       for tool in body.get('tools', []))
            if not root:
                return sequence, 'wait', '', {'after_turns': 1}
            if not self.intervened:
                self.intervened = True
                return sequence, 'intervene', '', {
                    'message': 'Offline fixture correction for delivery wiring only.'}
            if not self.root_code_returned:
                self.root_code_returned = True
                return sequence, 'code_run', '', {'code': 'head -n 1 /app/go.mod',
                                                 'type': 'bash', 'timeout': 60}
            if self.contrast is None:
                serialized = json.dumps(body, ensure_ascii=False)
                found = re.search(r'monitor/audit/commands/[a-zA-Z0-9-]+/output\.log', serialized)
                if not found:
                    return sequence, 'wait', '', {'after_turns': 1}
                self.contrast = {
                    'release_blocking_state': 'Offline fixture blocking state.',
                    'grounding': 'Offline fixture grounding.',
                    'ground_refs': ['task/original_task.txt'],
                    'exclusion_reason': 'Offline fixture exclusion.',
                    'observation_refs': [found.group(0)],
                }
            return sequence, 'allow_complete', '', self.contrast


STATE = State()


def _sse(sequence, name, text, args):
    def event(kind, payload):
        return ('event: ' + kind + '\ndata: ' + json.dumps(payload, ensure_ascii=False,
                                                           separators=(',', ':')) + '\n\n').encode()
    response = [event('message_start', {
        'type': 'message_start', 'message': {'id': f'msg_offline_{sequence}',
        'type': 'message', 'role': 'assistant', 'content': [], 'model': 'claude-opus-4-8',
        'stop_reason': None, 'usage': {'input_tokens': 1, 'output_tokens': 0}}})]
    if name is None:
        response.append(event('content_block_start', {'type': 'content_block_start',
                        'index': 0, 'content_block': {'type': 'text', 'text': ''}}))
        response.append(event('content_block_delta', {'type': 'content_block_delta',
                        'index': 0, 'delta': {'type': 'text_delta', 'text': text}}))
    else:
        response.append(event('content_block_start', {'type': 'content_block_start',
                        'index': 0, 'content_block': {'type': 'text', 'text': ''}}))
        response.append(event('content_block_delta', {'type': 'content_block_delta',
                        'index': 0, 'delta': {'type': 'text_delta',
                        'text': 'Offline fixture narrative.'}}))
        response.append(event('content_block_stop', {'type': 'content_block_stop', 'index': 0}))
        response.append(event('content_block_start', {'type': 'content_block_start',
                        'index': 1, 'content_block': {'type': 'tool_use',
                        'id': f'toolu_offline_{sequence}', 'name': name, 'input': {}}}))
        response.append(event('content_block_delta', {'type': 'content_block_delta',
                        'index': 1, 'delta': {'type': 'input_json_delta',
                        'partial_json': json.dumps(args, ensure_ascii=False)}}))
    response.append(event('content_block_stop', {'type': 'content_block_stop',
                    'index': 0 if name is None else 1}))
    response.append(event('message_delta', {'type': 'message_delta',
                    'delta': {'stop_reason': 'end_turn' if name is None else 'tool_use'},
                    'usage': {'output_tokens': 1}}))
    response.append(event('message_stop', {'type': 'message_stop'}))
    return b''.join(response)


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *_args):
        pass

    def do_POST(self):
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= 32 * 1024 * 1024 or self.path.split('?')[0] != '/v1/messages':
            self.send_error(400)
            return
        raw = self.rfile.read(length)
        body = json.loads(raw)
        route = self.headers.get('x-model-route', 'task')
        sequence, name, text, args = STATE.next(route, body)
        capture = Path('/fake_capture') / f'{sequence:04d}.json'
        capture.write_bytes(json.dumps({'route': route, 'path': self.path, 'body': body},
                                       ensure_ascii=False).encode())
        payload = _sse(sequence, name, text, args)
        capture.with_suffix('.sse').write_bytes(payload)
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(payload)
        self.close_connection = True


class UnixServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    address_family = getattr(socket, 'AF_UNIX', None)
    daemon_threads = True


def main():
    if UnixServer.address_family is None:
        raise RuntimeError('Offline fake gateway requires Linux Unix sockets')
    path = '/run/model-channel/gateway.sock'
    if os.path.lexists(path):
        os.unlink(path)
    server = UnixServer(path, Handler)
    os.chmod(path, 0o666)
    server.serve_forever()


if __name__ == '__main__':
    main()
