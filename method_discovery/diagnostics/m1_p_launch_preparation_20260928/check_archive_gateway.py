"""Synthetic Task + Monitor upstream only. Run in a network=none gateway."""
import http.client
import importlib.util
import json
import os
from pathlib import Path
import threading


def main():
    spec = importlib.util.spec_from_file_location('transport', '/gateway/transport.py')
    transport = importlib.util.module_from_spec(spec); spec.loader.exec_module(transport)
    records = []
    lock = threading.Lock()
    task_count = 0
    monitor_count = 0

    class Response:
        status = 200
        def __init__(self, block):
            delta = (dict(type='input_json_delta', partial_json=json.dumps(block['input']))
                     if block['type'] == 'tool_use' else dict(type='text_delta', text=block['text']))
            events = [dict(type='message_start', message={'id': 'fake', 'usage': {'input_tokens': 2}}),
                      dict(type='content_block_start', index=0, content_block=block),
                      dict(type='content_block_delta', index=0, delta=delta),
                      dict(type='content_block_stop', index=0),
                      dict(type='message_delta', delta={'stop_reason': 'tool_use' if block['type'] == 'tool_use' else 'end_turn'}, usage={'output_tokens': 1}),
                      dict(type='message_stop')]
            self.body = ''.join('data: ' + json.dumps(e) + '\n\n' for e in events).encode()
        def getheader(self, name, default=None):
            return 'text/event-stream' if name.lower() == 'content-type' else default
        def read1(self, size):
            result, self.body = self.body[:size], self.body[size:]; return result

    class FakeHTTPS:
        def __init__(self, host, port=None, **kwargs):
            if host != 'offline.invalid': raise AssertionError('external upstream forbidden')
        def connect(self): pass
        def request(self, method, target, body, headers):
            nonlocal task_count, monitor_count
            with lock:
                payload = json.loads(body)
                monitor = any(t.get('name') == 'allow_complete' for t in payload.get('tools', []))
                if monitor:
                    monitor_count += 1
                    serialized = json.dumps(payload['messages'])
                    if 'handoff_pending' in serialized or 'completion-1' in serialized:
                        name, inp = 'allow_complete', {}
                    elif monitor_count == 1:
                        name, inp = 'file_read', {'path': 'task/original_task.txt'}
                    elif monitor_count == 2:
                        name, inp = 'file_write', {'path': 'monitor/working.md', 'content': 'Decision: synthetic completion. Grounds: fixture original read.\n', 'mode': 'replace'}
                    else:
                        name, inp = 'wait', {'after_turns': 1, 'mode': 'follow'}
                    block = dict(type='tool_use', id='fake-monitor-' + str(monitor_count), name=name, input=inp)
                else:
                    task_count += 1
                    if task_count == 1:
                        block = dict(type='tool_use', id='fake-task-env', name='code_run', input={
                            'type': 'python', 'script': "import os,json,pathlib; data={k:os.environ.get(k) for k in ['GA_MAX_TURNS','GA_LLM_CONFIG_NAME','GA_MONITOR_ENABLED','GA_MONITOR_CONFIG','GA_MONITOR_ARTIFACT_DIR','GA_BASELINE_CONDITION']}; pathlib.Path('/logs/agent/engineering_env.json').write_text(json.dumps(data)); print('ENGINEERING_ENV='+json.dumps(data))" +
                            ("; import time; time.sleep(180)" if os.environ.get('ENGINEERING_TIMEOUT') == '1' else '')})
                    else:
                        block = dict(type='text', text='Engineering synthetic task complete.')
                records.append(dict(role='supervisor' if monitor else 'task', payload=payload,
                                    scripted_response=block, fake_usage=True, actual_external_requests=0))
                Path('/gateway-logs/requests.json').write_text(json.dumps(records, indent=2))
                self.response = Response(block)
        def getresponse(self): return self.response
        def close(self): pass

    http.client.HTTPSConnection = FakeHTTPS
    path = '/run/model-channel/gateway.sock'
    if os.path.lexists(path): os.unlink(path)
    server = transport.UnixServer(path, transport.Handler)
    server.mode, server.socket_path = 'gateway', path
    server.config = json.loads(Path('/gateway/config.json').read_text())
    os.chmod(path, 0o666)
    server.serve_forever()


if __name__ == '__main__': main()
