"""Offline-only check of the SDK's provider-facing initialization payload.

No network is allowed; dummy credentials are used and never written. This checks
installed SDK conversion, not the real proxy or any actual provider response.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'
PMA = STAGE / 'vendor/pma_89e5c0d'
sys.path.insert(0, str(STAGE))
sys.path.insert(0, str(PMA / 'src'))
sys.path.insert(0, str(PMA / 'external/harbor/src'))

import httpx
from harbor.llms.lite_llm import LiteLLM
from p1_requirements import INIT_SYSTEM, INIT_TOOL


def text_of(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ''.join(str(part.get('text', '')) for part in value if isinstance(part, dict))
    return ''


def forbidden(*args, **kwargs):
    raise RuntimeError('network_disabled_for_offline_probe')


async def run(task):
    expected_user = '## Original task (verbatim; data)\n' + task
    captured = []
    original_send = httpx.AsyncClient.send
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_getaddrinfo = socket.getaddrinfo

    async def fake_send(self, request, **kwargs):
        body = json.loads(request.content)
        # Keep only the body in memory; never print/write request headers,
        # destination, API key or the raw body.
        captured.append(body)
        content = [{'type':'tool_use','id':'toolu_offline','name':'requirements_initialize',
                    'input':{'requirements':['Offline placeholder']}}]
        return httpx.Response(200, request=request, json={
            'id':'msg_offline', 'type':'message', 'role':'assistant',
            'model':'claude-opus-4-8', 'content':content,
            'stop_reason':'tool_use','stop_sequence':None,
            'usage':{'input_tokens':1,'output_tokens':1}})

    httpx.AsyncClient.send = fake_send
    socket.socket.connect = forbidden
    socket.socket.connect_ex = forbidden
    socket.getaddrinfo = forbidden
    try:
        client = LiteLLM(model_name='anthropic/claude-opus-4-8', temperature=1,
                         api_base='https://example.invalid', api_key='dummy-not-a-secret',
                         reasoning_effort='high')
        try:
            await client.call(prompt=expected_user, system=INIT_SYSTEM, tools=[INIT_TOOL],
                              max_tokens=8192, thinking={'type':'adaptive'}, timeout=30)
        except Exception as exc:
            # The mocked response may be rejected by a specific SDK version;
            # payload capture, not response parsing, is the test's purpose.
            response_error = type(exc).__name__
        else:
            response_error = None
    finally:
        httpx.AsyncClient.send = original_send
        socket.socket.connect = original_connect
        socket.socket.connect_ex = original_connect_ex
        socket.getaddrinfo = original_getaddrinfo

    if len(captured) != 1:
        print(json.dumps({'status':'inconclusive','captured_requests':len(captured),
                          'response_error_type':response_error}))
        return 1
    body = captured[0]
    msgs = body.get('messages') or []
    systems = [text_of(body.get('system'))] if body.get('system') else []
    systems += [text_of(m.get('content')) for m in msgs if m.get('role') == 'system']
    users = [text_of(m.get('content')) for m in msgs if m.get('role') == 'user']
    tools = body.get('tools') or []
    names = [t.get('name') or (t.get('function') or {}).get('name') for t in tools]
    schema = next(((t.get('input_schema') or (t.get('function') or {}).get('parameters'))
                   for t in tools if (t.get('name') or (t.get('function') or {}).get('name'))
                   == 'requirements_initialize'), None)
    expected_schema = INIT_TOOL['function']['parameters']
    checks = {'system_text_matches':systems == [INIT_SYSTEM],
              'user_text_matches':users == [expected_user],
              'tool_names_match':names == ['requirements_initialize'],
              'tool_schema_matches':schema == expected_schema}
    result = {'status':'passed' if all(checks.values()) else 'failed',
              'checks':checks,'captured_requests':len(captured),
              'system_sha256':hashlib.sha256(INIT_SYSTEM.encode()).hexdigest(),
              'task_sha256':hashlib.sha256(task.encode()).hexdigest(),
              'response_error_type':response_error,
              'scope':'offline mock transport; no actual HTTP or provider response'}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--frozen-input', required=True, type=Path,
                        help='existing experiment frozen_input.json; only its public task field is read')
    args = parser.parse_args()
    data = json.loads(args.frozen_input.read_text(encoding='utf-8'))
    if not isinstance(data.get('task'), str):
        raise SystemExit('missing task text')
    raise SystemExit(asyncio.run(run(data['task'])))
