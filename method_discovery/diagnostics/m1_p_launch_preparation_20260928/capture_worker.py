"""Fresh host child through COPIED GA adapter -> exact native runtime._worker.

Not a Linux container receipt, not a scientific task. Real frozen worker,
real file/control tools, synthetic public event, scripted HTTP send boundary.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import queue
import socket
import sys
import threading
import platform
from importlib.metadata import version, PackageNotFoundError
from types import SimpleNamespace


def main():
    def dependency_version(name):
        try:
            return version(name)
        except PackageNotFoundError:
            return 'not installed (inactive path not exercised)'
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    base = Path(args.bundle).resolve()
    source = base / 'source'
    fixture = base / 'engineering-fixture'
    task, private = fixture / 'task', fixture / 'monitor'
    (task / 'workspace').mkdir(parents=True)
    private.mkdir(parents=True)
    (task / 'original_task.txt').write_text('Engineering fixture: inspect a local text artifact; no benchmark meaning.', encoding='utf-8')
    (task / 'synopsis.jsonl').write_text('', encoding='utf-8')
    (task / 'public_events.jsonl').write_text('', encoding='utf-8')
    (private / 'working.md').write_text('Decision: inspect the current fixture.\n', encoding='utf-8')
    os.environ.update(PILOT_BUDGET_PATH=str(base / 'budget.json'), PILOT_RECORD_ID='engineering-fixture',
        MONITOR_CONFIG_FILE=str(base / 'virtual_monitor_profiles.json'))
    network = {'external_http_attempts': 0, 'socket_attempts': 0}
    import requests

    def deny_http(*a, **kw):
        network['external_http_attempts'] += 1
        raise AssertionError('external HTTP denied')
    def deny_socket(*a, **kw):
        network['socket_attempts'] += 1
        raise AssertionError('network socket denied')
    requests.sessions.Session.request = deny_http
    socket.socket.connect = deny_socket
    socket.create_connection = deny_socket
    socket.socket.connect_ex = deny_socket
    scripted = [
        {'type': 'tool_use', 'id': 'read-artifact', 'name': 'file_read', 'input': {'path': 'task/original_task.txt'}},
        {'type': 'tool_use', 'id': 'write-state', 'name': 'file_write', 'input': {'path': 'monitor/working.md', 'content': 'Decision: retain fixture scope. Grounds: original artifact read.\n', 'mode': 'replace'}},
        {'type': 'tool_use', 'id': 'wait-control', 'name': 'wait', 'input': {'after_turns': 1, 'mode': 'follow'}}]
    captures, responses = [], []

    class Fake:
        status_code = 200
        def __init__(self, block): self.block = block
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def close(self): pass
        def iter_lines(self):
            b = self.block
            delta = ({'type': 'input_json_delta', 'partial_json': json.dumps(b['input'])}
                if b['type'] == 'tool_use' else {'type': 'text_delta', 'text': b['text']})
            events = [dict(type='message_start', message={'id': 'fake', 'usage': {'input_tokens': 2, 'cache_read_input_tokens': 3}}),
                dict(type='content_block_start', index=0, content_block=b),
                dict(type='content_block_delta', index=0, delta=delta),
                dict(type='content_block_stop', index=0),
                dict(type='message_delta', delta={'stop_reason': 'tool_use' if b['type'] == 'tool_use' else 'end_turn'}, usage={'output_tokens': 1}),
                dict(type='message_stop')]
            for event in events:
                yield ('data: ' + json.dumps(event)).encode()
                yield b''

    def post(url, **kw):
        if url != 'http://127.0.0.1:18765/v1/messages?beta=true':
            network['external_http_attempts'] += 1
            raise AssertionError('uncovered HTTP target denied at fake boundary')
        captures.append({'url': url, 'headers': copy.deepcopy(kw['headers']),
            'transport_options': {k: kw.get(k) for k in ('stream', 'timeout', 'verify', 'proxies')},
            'payload': copy.deepcopy(kw['json']),
            'payload_sha256': hashlib.sha256(json.dumps(kw['json'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()})
        b = scripted.pop(0); responses.append(copy.deepcopy(b))
        return Fake(b)
    requests.post = post
    sys.path.insert(0, str(source))
    import ga_monitor_adapter  # ACTUAL copied prelude applies before native imports
    from monitor_agent_core.runtime import _worker
    commands, outputs = queue.Queue(), queue.Queue()
    commands.put({'kind': 'close'})
    cfg = ga_monitor_adapter.monitor_profile('claude_monitor_opus48')
    class Value:
        value = 0
        def get_lock(self): return threading.Lock()
    # _worker itself performs native construction; no direct mock MonitorAgent.
    _worker(dict(config_name='claude_monitor_opus48', model_config=cfg,
        evidence_root=str(task), private_root=str(private), task_workspace=str(task / 'workspace'),
        task_id='engineering-fixture', max_review_turns=20, stop_event=threading.Event(),
        active_completion=Value(), completion_cursor=Value(),
        completion_receipts=queue.Queue(), wake_receipts=None), commands, outputs)
    outcome = list(outputs.queue)
    if not any(x['kind'] == 'ready' for x in outcome) or any(x['kind'] == 'failure' for x in outcome):
        raise AssertionError(outcome)
    modules = {k: str(Path(m.__file__).resolve()) for k, m in sys.modules.items()
        if (k == 'monitor_agent_core' or k.startswith('monitor_agent_core.')) and getattr(m, '__file__', None)}
    assert all(Path(p).is_relative_to(source / 'monitor_agent_core') for p in modules.values())
    assert network == {'external_http_attempts': 0, 'socket_attempts': 0}
    assert len(captures) == 3 and not scripted
    assert 'original artifact read' in json.dumps(captures[-1]['payload'])
    assert 'read-artifact' in json.dumps(captures[1]['payload'])
    # Fixed Task source's actual native transport/parser, synthetic prompt only.
    # No agentmain execution or benchmark. Exercise the same installed budget hook.
    scripted.append({'type': 'text', 'text': 'Synthetic transport fixture only.'})
    from pilot_bootstrap import install_task
    install_task(source)
    import llmcore
    task_config = json.loads((source / 'mykey.json').read_text())['native_claude_cc_vibe_opus48']
    session = llmcore.NativeClaudeSession(task_config)
    session._session_id, session._device_id, session._account_uuid = 'engineering-session', 'engineering-device', ''
    session.tools = []  # This transport fixture has no Task tool execution.
    list(session.raw_ask([{'role': 'user', 'content': [{'type': 'text', 'text': 'Synthetic transport fixture only.'}]}]))
    assert len(captures) == 4 and not scripted
    artifacts = {p.relative_to(private).as_posix(): p.read_text(encoding='utf-8') for p in private.rglob('*') if p.is_file()}
    record = dict(engineering_fixture=True, container_started=False, requests=captures[:3],
        platform={'os': platform.platform(), 'python': platform.python_version(), 'requests': requests.__version__,
            'dependencies': {name: dependency_version(name) for name in ('requests', 'shortuuid', 'urllib3', 'certifi')},
            'shell': 'frozen Windows Monitor schema; no analysis command executed'},
        task_transport_requests=captures[3:], task_agentmain_executed=False,
        task_imports={name: {'path': str(Path(sys.modules[name].__file__).resolve()),
            'runtime_sha256': hashlib.sha256(Path(sys.modules[name].__file__).read_bytes()).hexdigest()}
            for name in ('llmcore', 'research_runtime', 'ga_monitor_adapter')},
        scripted_responses=responses, synthetic_usage=True, actual_model_requests=0,
        network=network, modules=modules, worker_outputs=outcome, effective_config=cfg,
        private_artifacts=artifacts, budget=json.loads((base / 'budget.json').read_text()),
        final_working=(private / 'working.md').read_text())
    Path(args.output).write_text(json.dumps(record, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
