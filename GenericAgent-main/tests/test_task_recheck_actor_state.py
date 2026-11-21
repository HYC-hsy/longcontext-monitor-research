"""No-model regression of default-off Task pre-request state capture."""

import copy
import json
from pathlib import Path
from types import SimpleNamespace

from task_recheck_actor_state import capture_pre_request


def test_disabled_or_initial_does_not_write(tmp_path, monkeypatch):
    monkeypatch.delenv('GA_TASK_RECHECK_CAPTURE', raising=False)
    backend = SimpleNamespace(history=[{'role': 'user', 'content': [{'type': 'text', 'text': 'old'}]}])
    client = SimpleNamespace(backend=backend, last_tools='existing', total_cd_tokens=3)
    handler = SimpleNamespace(working={'key_info': 'keep'}, history_info=[])
    args = dict(turn=5, client=client, messages=[{'role': 'user', 'content': 'next'}],
                pre_reminder_messages=[{'role': 'user', 'content': 'next'}], reminder=None,
                initial_task='task fixture',
                tools_schema=[{'name': 'file_read'}], handler=handler, directory=tmp_path)
    assert capture_pre_request(**args) is None
    monkeypatch.setenv('GA_TASK_RECHECK_CAPTURE', '1')
    monkeypatch.setenv('GA_BENCH_RUN_ID', 'run-a')
    assert capture_pre_request(**{**args, 'turn': 1}) is None
    assert list(tmp_path.iterdir()) == []


def test_captures_precise_history_once_without_mutation(tmp_path, monkeypatch):
    monkeypatch.setenv('GA_TASK_RECHECK_CAPTURE', '1')
    monkeypatch.setenv('GA_BENCH_RUN_ID', 'run-a')
    monkeypatch.setenv('GA_BENCH_TASK_ID', 'financial-document-processor')
    monkeypatch.setenv('GA_PMA_BATCH_ROUNDS', '4')
    history = [{'role': 'assistant', 'content': [
        {'type': 'tool_use', 'id': 'call-1', 'name': 'file_read', 'input': {'path': '/app/a'}},
        {'type': 'thinking', 'thinking': 'private-fixture', 'signature': 'signed-fixture'}]}]
    messages = [{'role': 'system', 'content': 'fixed'},
                {'role': 'user', 'content': 'continuation', 'tool_results': [
                    {'tool_use_id': 'call-1', 'content': 'receipt'}]}]
    tools = [{'name': 'file_read', 'parameters': {'type': 'object'}}]
    backend = SimpleNamespace(history=copy.deepcopy(history), system='fixed',
                              _session_id='session-1', _account_uuid='account-1',
                              _device_id='device-1')
    client = SimpleNamespace(backend=backend, _pending_tool_ids=['call-1'],
                             last_tools='tools-json', total_cd_tokens=10, role='executor')
    handler = SimpleNamespace(working={'key_info': 'prior memory'}, history_info=['prior'])
    before = copy.deepcopy((history, messages, tools, handler.working))
    result = capture_pre_request(turn=5, client=client, messages=messages,
                                 pre_reminder_messages=messages, reminder=None,
                                 initial_task='task fixture',
                                 tools_schema=tools, handler=handler, directory=tmp_path)
    row = json.loads((tmp_path / 'task_recheck_before_actor_0005.json').read_text(encoding='utf-8'))
    assert row['backend_history'] == history
    assert row['messages'] == messages
    assert row['tools_schema'] == tools
    assert row['pending_tool_ids'] == ['call-1']
    assert row['session_ids']['_session_id'] == 'session-1'
    assert row['backend_history'][0]['content'][1]['signature'] == 'signed-fixture'
    assert (history, messages, tools, handler.working) == before
    assert result['sha256']
    try:
        capture_pre_request(turn=5, client=client, messages=messages,
                            pre_reminder_messages=messages, reminder=None,
                            initial_task='task fixture',
                            tools_schema=tools, handler=handler, directory=tmp_path)
    except RuntimeError as exc:
        assert 'already exists' in str(exc)
    else:
        raise AssertionError('duplicate capture unexpectedly overwrote original')
