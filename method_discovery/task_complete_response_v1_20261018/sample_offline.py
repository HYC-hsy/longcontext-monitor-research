"""Produce a small, synthetic local-HTTP Task request/integrity example."""
import hashlib
import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import time
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'GenericAgent-main'))
spec = importlib.util.spec_from_file_location(
    'task_complete_test', ROOT / 'GenericAgent-main/tests/test_task_complete_response.py')
test = importlib.util.module_from_spec(spec)
spec.loader.exec_module(test)
import llmcore

events = []
def emit(kind, payload, **kwargs):
    if kind in ('provider_request_ready', 'provider_request_attempt',
                'task_response_integrity', 'provider_response'):
        events.append({'event': kind, 'call_id': kwargs.get('llm_call_id'),
                       'attempt': payload.get('attempt'),
                       'category': payload.get('category'),
                       'outcome': payload.get('outcome'),
                       'end_reason': payload.get('end_reason'),
                       'event_counts': payload.get('event_counts'),
                       'unclosed_blocks': payload.get('unclosed_blocks'),
                       'stop_reason': payload.get('stop_reason'),
                       'message_stop': payload.get('message_stop')})
    return {'event_id': 'synthetic-event-' + str(len(events))}

with mock.patch.dict(os.environ, {
        'GA_TASK_COMPLETE_RESPONSE': '1',
        'GA_TASK_DEADLINE_EPOCH': str(time.time() + 120)}), \
     mock.patch.object(llmcore, '_research_emit', side_effect=emit), \
     test.ScriptedServer([
        test.stream(text='uncommitted', stop=None, message_stop=False),
        test.stream(tools=['touch'])]) as server:
    client = test.CompleteResponseTests().client(server.url, retries=1)
    with contextlib.redirect_stdout(io.StringIO()):
        _, response = test.exhaust(client.chat(
            messages=[{'role': 'system', 'content': 'synthetic system'},
                      {'role': 'user', 'content': 'synthetic task'}],
            tools=client.backend.tools))
    payloads = [json.loads(raw) for raw in server.payloads]
    public = {
        'schema': 'synthetic-task-complete-response-example-v1',
        'real_model_calls': 0,
        'local_fake_http_posts': len(payloads),
        'requests_byte_equal': server.payloads[0] == server.payloads[1],
        'request_sha256': [hashlib.sha256(raw).hexdigest() for raw in server.payloads],
        'request_payload': payloads[0],
        'events': events,
        'committed_public_content': response.content,
        'committed_tool_names': [x.function.name for x in response.tool_calls],
        'assistant_history_entries': sum(x['role'] == 'assistant'
                                         for x in client.backend.history),
    }
    assert public['requests_byte_equal']
    assert public['committed_tool_names'] == ['touch']
    assert public['assistant_history_entries'] == 1
    rendered = json.dumps(public, ensure_ascii=False, indent=2) + '\n'
    if len(sys.argv) == 2:
        Path(sys.argv[1]).write_bytes(rendered.encode('utf-8'))
    else:
        print(rendered, end='')
