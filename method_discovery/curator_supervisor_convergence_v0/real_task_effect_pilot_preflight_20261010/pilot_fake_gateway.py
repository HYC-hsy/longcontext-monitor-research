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
        self.pos_role_responses = 0
        self.reference_written = False
        self.intervened = False
        self.root_code_returned = False
        self.contrast = None

    def next(self, route, body):
        with self.lock:
            self.sequence += 1
            sequence = self.sequence
            if route == 'pos-role':
                self.pos_role_responses += 1
                position = self.pos_role_responses - 1
                schedule = (('belief', 4096, 0), ('consistency', 512, 0),
                            ('belief', 4096, 1), ('consistency', 512, 1),
                            ('progress', 512, 0))
                if position >= len(schedule) or body.get('max_tokens') != schedule[position][1]:
                    raise ValueError('unmatched synthetic PoS role request')
                replies = json.loads(Path('/pos_role_replies.json').read_text(encoding='utf-8'))
                role, _, index = schedule[position]
                return sequence, None, replies[role][index], {}
            if route != 'monitor':
                self.task_responses += 1
                if os.environ.get('POS_SYNTHETIC_FIXTURE') == '1' and self.task_responses == 1:
                    long_output = ('; /opt/m4-runtime/python/'
                        'cpython-3.12.12-linux-x86_64-gnu/bin/python3.12 '
                        '-c "print(\'SYNTHETIC_LONG_OUTPUT_\' + \'X\' * 12000)"'
                        if os.environ.get('POS_SYNTHETIC_LONG_OUTPUT') == '1' else '')
                    return sequence, 'code_run', '<summary>Creating synthetic file and service.</summary>', {
                        'script': ('printf "POS_FILE_OK\\n" > /app/pos-fixture-marker.txt; '
                                   'setsid /opt/m4-runtime/python/'
                                   'cpython-3.12.12-linux-x86_64-gnu/bin/python3.12 '
                                   '-m http.server 19173 --bind 127.0.0.1 '
                                   '>/tmp/pos_fixture_http.log 2>&1 </dev/null & '
                                   'sleep 1; test "$(cat /app/pos-fixture-marker.txt)" = POS_FILE_OK; '
                                   '/opt/m4-runtime/python/'
                                   'cpython-3.12.12-linux-x86_64-gnu/bin/python3.12 '
                                   "-c 'import urllib.request; "
                                   'assert urllib.request.build_opener('
                                   'urllib.request.ProxyHandler({})).open('
                                   '"http://127.0.0.1:19173/", timeout=3).status == 200\''
                                   + long_output),
                        'type': 'bash', 'timeout': 60}
                if os.environ.get('PMA_MULTITURN_FIXTURE') == '1' and self.task_responses == 1:
                    if os.environ.get('PMA_SERVICE_FIXTURE') == '1':
                        return sequence, 'code_run', 'Start a harmless local test service.', {
                            'script': ('setsid /opt/m4-runtime/python/'
                                       'cpython-3.12.12-linux-x86_64-gnu/bin/python3.12 '
                                       '-m http.server 19173 --bind 127.0.0.1 '
                                       '>/tmp/pma_service_fixture.log 2>&1 </dev/null & '
                                       'sleep 1; /opt/m4-runtime/python/'
                                       'cpython-3.12.12-linux-x86_64-gnu/bin/python3.12 '
                                       '-c "import urllib.request; '
                                       'urllib.request.build_opener('
                                       'urllib.request.ProxyHandler({})).open('
                                       '\'http://127.0.0.1:19173/\', '
                                       'timeout=3).close()" && '
                                       'printf "PMA_SERVICE_STARTED\\nPMA_OFFLINE_TOOL_OK\\n"'),
                            'type': 'bash', 'timeout': 60,
                        }
                    return sequence, 'code_run', 'Inspecting the public workspace.', {
                        'script': "printf 'PMA_OFFLINE_TOOL_OK\\n'",
                        'type': 'bash', 'timeout': 60,
                    }
                return sequence, None, ('<summary>Offline fixture.</summary> '
                                        'Offline Task completion.'), {}
            if not self.reference_written:
                self.reference_written = True
                return sequence, 'file_write', '', {
                    'path': 'monitor/reference.md',
                    'content': 'Offline fixture Task Book; task authority remains original_task.txt.\n',
                    'mode': 'replace',
                }
            if 'You supervise the Task\'s current behavior against the public task' in str(
                    body.get('system', '')):
                if 'Root decision input for the current pending handoff.' in json.dumps(
                        body.get('messages', []), ensure_ascii=False):
                    return sequence, 'allow_complete', '', {}
                return sequence, 'wait', '', {'after_turns': 1, 'mode': 'patrol'}
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
                        'text': text or 'Offline fixture narrative.'}}))
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
        if os.environ.get('POS_CANDIDATE_PROFILE_FIXTURE') == '1':
            if (body.get('thinking') == {'type': 'disabled'} and
                    body.get('temperature') == 0):
                route = 'pos-role'
            elif route != 'monitor' and (body.get('thinking') == {'type': 'disabled'} or
                    body.get('temperature') == 0):
                self.send_error(400, 'unmatched synthetic auxiliary role')
                return
        try:
            sequence, name, text, args = STATE.next(route, body)
        except (ValueError, KeyError, IndexError):
            self.send_error(400, 'unmatched synthetic request')
            return
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
