"""Zero-model tests for exact native Task request assembly at a frozen cut."""

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import llmcore
from task_recheck_actor_state import CONFIG_FIELDS
from task_recheck_branch import (
    FIXED_TEXT, TARGETED_TEXT, branch_messages, load_frozen, restore_native_state,
)

CFG = {'apikey': 'synthetic-only', 'apibase': 'http://127.0.0.1:9/v1',
       'model': 'claude-opus-4-8', 'max_tokens': 64000, 'temperature': 1,
       'thinking_type': 'adaptive', 'stream': True}


def _frozen(tmp_path):
    base = [{'role': 'user', 'content': 'Continue with the extracted CSV',
             'tool_results': [{'tool_use_id': 'call-1', 'content': 'extraction finished'}]}]
    original = copy.deepcopy(base)
    from pma_upstream_bridge import append_reminder
    original[-1] = append_reminder(original[-1], 'Original pending reminder')
    row = {
        'schema': 'task-recheck-actor-state-v1', 'run_id': 'run-fixture',
        'actor_attempt': 9, 'initial_task': 'Extract invoice amounts',
        'messages': original, 'pre_reminder_messages': base,
        'pending_reminder': 'Original pending reminder',
        'tools_schema': [{'type': 'function', 'function': {'name': 'code_run',
            'description': 'Execute code', 'parameters': {'type': 'object', 'properties': {}}}}],
        'backend_history': [{'role': 'user', 'content': [{'type': 'text', 'text': 'task'}]},
            {'role': 'assistant', 'content': [{'type': 'tool_use', 'id': 'call-1',
                'name': 'code_run', 'input': {'code': 'print(1)'}}]}],
        'backend_system': 'Task system', 'pending_tool_ids': ['call-1'],
        'last_tools': 'prior', 'total_cd_tokens': 21, 'role': 'executor',
        'session_ids': {'_session_id': 'session-1', '_account_uuid': 'account-1',
                        '_device_id': 'device-1'},
        'handler_working': {'key_info': 'keep'}, 'handler_history_info': ['prior'],
    }
    backend = llmcore.client_from_config('native_claude_fixture', CFG).backend
    row['effective_model_config'] = {field: getattr(backend, field, None)
                                     for field in CONFIG_FIELDS}
    row['api_base_sha256'] = hashlib.sha256(backend.api_base.encode()).hexdigest()
    path = tmp_path / 'state.json'
    path.write_text(json.dumps(row), encoding='utf-8')
    return load_frozen(path)


def _native_payload(row, arm):
    client = llmcore.client_from_config('native_claude_fixture', CFG)
    handler = SimpleNamespace(working={}, history_info=[])
    restore_native_state(row, client, handler)
    seen = []

    def fake_wire(_sess, _url, _headers, payload, _parse):
        seen.append(copy.deepcopy(payload))
        if False:
            yield None
        return [{'type': 'text', 'text': 'fixture done'}]

    with patch.object(llmcore, '_stream_with_retry', fake_wire):
        gen = client.chat(branch_messages(row, arm), row['tools_schema'])
        try:
            while True:
                next(gen)
        except StopIteration:
            pass
    assert len(seen) == 1
    return seen[0]


def test_three_arms_differ_only_in_current_reminder(tmp_path):
    row = _frozen(tmp_path)
    outputs = {arm: _native_payload(row, arm) for arm in ('none', 'fixed', 'targeted')}
    for arm, prompt in [('fixed', FIXED_TEXT), ('targeted', TARGETED_TEXT)]:
        assert outputs[arm]['messages'][:-1] == outputs['none']['messages'][:-1]
        assert outputs[arm]['system'] == outputs['none']['system']
        assert outputs[arm]['tools'] == outputs['none']['tools']
        assert outputs[arm]['model'] == outputs['none']['model']
        assert outputs[arm]['thinking'] == outputs['none']['thinking']
        no = outputs['none']['messages'][-1]['content']
        yes = outputs[arm]['messages'][-1]['content']
        assert yes[:-1] == no[:-1]
        assert yes[-1]['text'] == no[-1]['text'] + '\n\n' + prompt
        assert {k: v for k, v in yes[-1].items() if k != 'text'} == {
            k: v for k, v in no[-1].items() if k != 'text'}
        assert 'Original pending reminder' not in str(yes)
    assert outputs['none']['messages'][-1]['content'][0]['tool_use_id'] == 'call-1'


def test_corrupt_original_reminder_assembly_is_rejected(tmp_path):
    row = _frozen(tmp_path)
    row['messages'][-1]['content'] = 'changed'
    path = tmp_path / 'corrupt.json'
    path.write_text(json.dumps(row), encoding='utf-8')
    try:
        load_frozen(path)
    except ValueError as exc:
        assert 'assembly' in str(exc)
    else:
        raise AssertionError('corrupt Task checkpoint was accepted')


def test_short_branch_uses_ga_tool_and_receipt_without_model(tmp_path, monkeypatch):
    from agentmain import GenericAgent
    from task_recheck_branch_entry import run

    row = _frozen(tmp_path)
    (tmp_path / 'source_ocr.txt').write_text('Invoice A: amount 12.50', encoding='utf-8')
    (tmp_path / 'extraction.csv').write_text('invoice,amount\nA,12.50\n', encoding='utf-8')
    packet = tmp_path / 'state.json'
    client = llmcore.client_from_config('native_claude_fixture', CFG)

    def install_client(self):
        self.llmclients = [client]
        self.llmclient = client

    call = []

    def fake_wire(_sess, _url, _headers, payload, _parse):
        call.append(copy.deepcopy(payload))
        if False:
            yield None
        if len(call) == 1:
            return [{'type': 'tool_use', 'id': 'branch-tool-1', 'name': 'code_run',
                     'input': {'type': 'python', 'code':
                         "from pathlib import Path; print(Path('source_ocr.txt').read_text()); "
                         "print(Path('extraction.csv').read_text())"}}]
        return [{'type': 'text', 'text': 'Source and CSV both show 12.50.'}]

    monkeypatch.setenv('GA_EXPERIMENT_RUNTIME_POLICY', 'v1')
    monkeypatch.setenv('GA_EXPERIMENT_TASK_TURNS', '4')
    monkeypatch.delenv('GA_TASK_RECHECK_CAPTURE', raising=False)
    with patch.object(GenericAgent, 'load_llm_sessions', install_client), \
            patch.object(llmcore, '_stream_with_retry', fake_wire):
        agent = GenericAgent()
        result = run(packet, 'targeted', tmp_path / 'branch-result.json',
                     agent=agent, workspace=tmp_path)
    assert len(call) == 2
    assert result['max_task_turns'] == 4
    assert '12.50' in json.dumps(result['visible_stream'])
    assert call[0]['messages'][-1]['content'][-1]['text'].endswith(TARGETED_TEXT)
    assert call[1]['messages'][-1]['content'][0]['tool_use_id'] == 'branch-tool-1'
