"""Engineering-only upstream replacement; actual frozen gateway Handler/route.

Runs network=none. No credential discovery or external inference transport.
"""
import http.client
import importlib.util
import json
import os
from pathlib import Path
import threading


def main():
    spec = importlib.util.spec_from_file_location('frozen_transport', '/gateway/transport.py')
    transport = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(transport)
    scripted = [
        dict(type='tool_use', id='read-artifact', name='file_read', input={'path': 'task/original_task.txt'}),
        dict(type='tool_use', id='write-state', name='file_write', input={'path': 'monitor/working.md',
             'content': 'Decision: retain fixture scope. Grounds: original artifact read.\n', 'mode': 'replace'}),
        dict(type='tool_use', id='bash-inspection', name='code_run', input={'type': 'bash',
             'code': 'pwd; command -v bash; test -r /app/go.mod || test -r /app/Cargo.toml', 'wait_seconds': 5, 'timeout': 15}),
        dict(type='tool_use', id='python-inspection', name='code_run', input={'type': 'python',
             'code': 'import os,sys; print(os.getcwd()); print(sys.version)', 'wait_seconds': 5, 'timeout': 15}),
        dict(type='tool_use', id='wait-control', name='wait', input={'after_turns': 1, 'mode': 'follow'}),
        dict(type='text', text='Synthetic transport fixture only.')]
    requests = []
    lock = threading.Lock()

    class Response:
        status = 200
        def __init__(self, block):
            delta = dict(type='input_json_delta', partial_json=json.dumps(block['input'])) if block['type'] == 'tool_use' else dict(type='text_delta', text=block['text'])
            events = [dict(type='message_start', message={'id': 'fake', 'usage': {'input_tokens': 2, 'cache_read_input_tokens': 3}}),
                dict(type='content_block_start', index=0, content_block=block),
                dict(type='content_block_delta', index=0, delta=delta), dict(type='content_block_stop', index=0),
                dict(type='message_delta', delta={'stop_reason': 'tool_use' if block['type'] == 'tool_use' else 'end_turn'}, usage={'output_tokens': 1}), dict(type='message_stop')]
            self.body = ''.join('data: ' + json.dumps(e) + '\n\n' for e in events).encode()
        def getheader(self, name, default=None):
            return 'text/event-stream' if name.lower() == 'content-type' else default
        def read1(self, size):
            result, self.body = self.body[:size], self.body[size:]
            return result

    class FakeHTTPS:
        def __init__(self, host, port=None, **kw):
            if host != 'offline.invalid':
                raise AssertionError('unexpected upstream target')
        def connect(self): pass
        def request(self, method, target, body, headers):
            with lock:
                if method != 'POST' or target != '/v1/messages?beta=true':
                    raise AssertionError('unexpected request')
                block = scripted.pop(0)
                requests.append({'method': method, 'target': target, 'payload': json.loads(body),
                    'scripted_response': block, 'upstream_is_fake': True})
                Path('/gateway-logs/requests.json').write_text(json.dumps(requests, indent=2))
                self.response = Response(block)
        def getresponse(self): return self.response
        def close(self): pass

    http.client.HTTPSConnection = FakeHTTPS
    socket_path = '/run/model-channel/gateway.sock'
    if os.path.lexists(socket_path): os.unlink(socket_path)
    server = transport.UnixServer(socket_path, transport.Handler)
    server.mode, server.socket_path = 'gateway', socket_path
    server.config = json.loads(Path('/gateway/config.json').read_text())
    os.chmod(socket_path, 0o666)
    server.serve_forever()


if __name__ == '__main__': main()
