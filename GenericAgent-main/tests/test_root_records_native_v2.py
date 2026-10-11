"""Zero-model native root projection and actual pilot capture seam."""

import copy
import json
import threading
import time

import pytest

from monitor_agent_core.agent import MONITOR_TOOLS, MonitorAgent, ProjectionIntegrityError
from monitor_agent_core.actions import MonitorAction, ToolOutcome
from monitor_agent_core.loop import run_review
from monitor_agent_core.provider import (HistoryCapacityError, MonitorProviderClient,
                                          ProviderRecoveryExhausted, _claude_tools)
from monitor_agent_core.root_records_native_v2 import project
from monitor_agent_core.root_records_v1 import canonical, digest
from monitor_agent_core.runtime import _capture_pilot_payload
from test_crs_v0 import fixture


def history():
    return [
        {'role': 'user', 'content': [{'type': 'text', 'text': '原任务 @RECORD'}]},
        {'role': 'assistant', 'content': [
            {'type': 'thinking', 'thinking': 'old claim', 'signature': 'sig'},
            {'type': 'tool_use', 'id': 'a', 'name': 'file_read', 'input': {'path': 'a.go'}},
            {'type': 'tool_use', 'id': 'b', 'name': 'code_run', 'input': {'code': 'echo ok'}}]},
        {'role': 'user', 'content': [
            {'type': 'tool_result', 'tool_use_id': 'b', 'content': 'ok'},
            {'type': 'tool_result', 'tool_use_id': 'a', 'content': 'source'}]},
        {'role': 'assistant', 'content': [{'type': 'text', 'text': 'verified earlier'}]},
    ]


def native_fixture(tmp_path, *, source=None):
    monitor, client, workspace, handoff = fixture(tmp_path, rhr=True, rer=True)
    monitor.history_projection = 'root_records_native_v2'
    client.provider = 'anthropic'
    client.native_projection_acceptance = True
    client.pre_send_capture = lambda request_id, payload: _capture_pilot_payload(
        workspace.private_root, monitor, request_id, payload)
    client.history_transform_callback = monitor._record_native_projection_transform
    client.restore_history(history() if source is None else source)
    monitor._enter_root_frame(handoff)
    monitor._projection_root_input = 'exact current root input'
    monitor._projection_root_system = 'exact system'
    monitor._projection_root_tools = _claude_tools(MONITOR_TOOLS)
    client.system = 'exact system'
    client.history.append({'role': 'user', 'content': [
        {'type': 'text', 'text': monitor._projection_root_input}]})
    return monitor, client, workspace, handoff


def test_native_blocks_parallel_exchange_and_source_round_trip():
    original = history()
    frozen = copy.deepcopy(original)
    projected, manifest, source = project(original)
    assert original == frozen and source == canonical(original)
    assert manifest['tool_pairs'] == 2 and manifest['removed_messages'] == [3]
    assert manifest['removed_blocks'] == 2
    assert projected[1]['content'] == original[1]['content'][1:]
    assert projected[2] == original[2]
    assert 'verified earlier' not in json.dumps(projected)
    assert project(projected)[0] == projected
    assert project(projected)[1]['applied'] is False


@pytest.mark.parametrize('change', ['open', 'duplicate', 'unknown', 'early_result'])
def test_invalid_history_fails_without_mutation(change):
    original = history()
    if change == 'open':
        original[2]['content'].pop()
    elif change == 'duplicate':
        original[1]['content'][2]['id'] = 'a'
    elif change == 'unknown':
        original[2]['content'][0]['is_error'] = False
    else:
        original.insert(1, original.pop(2))
    frozen = copy.deepcopy(original)
    with pytest.raises(ValueError):
        project(original)
    assert original == frozen


def test_actual_capture_archive_chain_and_tamper(tmp_path):
    monitor, client, workspace, _ = native_fixture(tmp_path)
    _, _, payload = client._anthropic_request(MONITOR_TOOLS)
    _capture_pilot_payload(workspace.private_root, monitor, 'review-1', payload)
    assert monitor._projection_pending_request['request_id'] == 'review-1'
    saved = json.loads((workspace.private_root / 'audit/provider_pre_send/review-1.json').read_text(encoding='utf-8'))
    assert saved['native_projection_lineage']['source_sha256'] == digest(canonical(history()))
    monitor._progress('request_usage', request_id='maintenance', usage={})
    assert monitor._projection_pending_request is not None
    monitor._progress('request_accepted', request_id='maintenance')
    assert monitor._projection_pending_request is not None
    monitor._progress('request_accepted', request_id='review-1', request_sha256='accepted')
    assert monitor._projection_pending_request['verified'] is True
    _capture_pilot_payload(workspace.private_root, monitor, 'review-2', payload)

    (tmp_path / 'tamper').mkdir()
    monitor, client, workspace, _ = native_fixture(tmp_path / 'tamper')
    commit = next((workspace.private_root / 'audit/root_projections').rglob('source.json'))
    commit.write_text('[]', encoding='utf-8')
    _, _, payload = client._anthropic_request(MONITOR_TOOLS)
    with pytest.raises(ProjectionIntegrityError):
        _capture_pilot_payload(workspace.private_root, monitor, 'blocked', payload)
    assert monitor._projection_integrity_failure == 'native_projection_pre_send'
    assert not (workspace.private_root / 'audit/provider_pre_send/blocked.json').exists()


def test_no_pilot_capture_hook_rejected_before_history_mutation(tmp_path):
    monitor, client, _, handoff = fixture(tmp_path, rhr=True, rer=True)
    monitor.history_projection = 'root_records_native_v2'
    client.restore_history(history())
    with pytest.raises(ProjectionIntegrityError):
        monitor._enter_root_frame(handoff)
    assert client.export_history() == history()


def test_existing_exchange_retirement_and_fake_continuation_chain(tmp_path):
    monitor, client, workspace, _ = native_fixture(tmp_path)
    assert 3 in client._exchange_boundaries()  # native parallel tool batch is a safe cut
    _, _, first_payload = client._anthropic_request(MONITOR_TOOLS)
    _capture_pilot_payload(workspace.private_root, monitor, 'first-review', first_payload)
    monitor._progress('request_accepted', request_id='first-review', request_sha256='first')
    client.history.extend([
        {'role': 'assistant', 'content': [
            {'type': 'tool_use', 'id': 'new', 'name': 'file_read', 'input': {'path': 'big'}}]},
        {'role': 'user', 'content': [
            {'type': 'tool_result', 'tool_use_id': 'new', 'content': 'Z' * 14000}]},
        {'role': 'assistant', 'content': [{'type': 'text', 'text': 'new review text'}]},
    ])
    client.history_char_limit = 2400
    client.history_target_chars = 1968
    client.prepare_continuation = lambda: 'FAKE_CONTINUATION_TEST_ONLY'
    client._relieve_tool_result_pressure()
    assert client.history_transforms[-1]['kind'] == 'monitor_tool_payload_archival'
    client._compact_with_continuation(client.history_measure())
    assert client.history_transforms[-1]['kind'] == 'monitor_history_compaction'
    assert len(monitor._projection_pending_request['transforms']) == 2
    _, _, payload = client._anthropic_request(MONITOR_TOOLS)
    _capture_pilot_payload(workspace.private_root, monitor, 'post-maintenance-review', payload)
    receipt = json.loads((workspace.private_root / 'audit/provider_pre_send/'
                          'post-maintenance-review.json').read_text(encoding='utf-8'))
    assert len(receipt['native_projection_lineage']['transform_receipts']) == 2


def test_first_review_after_fake_maintenance_keeps_exact_root_input(tmp_path):
    source = history()
    source[2]['content'][1]['content'] = 'Z' * 14000
    monitor, client, workspace, _ = native_fixture(tmp_path, source=source)
    client.history_char_limit = 7000
    client.history_target_chars = 5740
    client.prepare_continuation = lambda: 'FAKE_CONTINUATION_TEST_ONLY'
    client._compact_history()
    _, _, payload = client._anthropic_request(MONITOR_TOOLS)
    _capture_pilot_payload(workspace.private_root, monitor, 'first-after-maintenance', payload)
    assert monitor._projection_pending_request['request_id'] == 'first-after-maintenance'
    assert monitor._projection_pending_request.get('verified') is None


def test_illegal_transform_and_missing_archive_fail_before_send(tmp_path):
    monitor, client, workspace, _ = native_fixture(tmp_path)
    before = client.export_history()
    after = copy.deepcopy(before)
    after[0]['content'][0]['text'] = 'tampered'
    archive = monitor._archive_continuation_history(before)
    with pytest.raises(ProjectionIntegrityError):
        monitor._record_native_projection_transform(
            'monitor_history_compaction', before, after, archive,
            {'cut': 1, 'tail_sha256': 'bad', 'continuation_note_sha256': 'bad'})
    assert monitor._projection_integrity_failure == 'native_projection_transform'


def test_real_request_purpose_switch_and_acceptance_with_fake_sse(tmp_path, monkeypatch):
    monitor, client, workspace, _ = native_fixture(tmp_path)
    events = [
        {'type': 'message_start', 'message': {'usage': {'input_tokens': 4}}},
        {'type': 'content_block_start', 'content_block': {'type': 'text'}},
        {'type': 'content_block_delta', 'delta': {'type': 'text_delta', 'text': 'reviewed'}},
        {'type': 'content_block_stop'},
        {'type': 'message_delta', 'usage': {'output_tokens': 2}},
        {'type': 'message_stop'},
    ]
    sent = []

    class Response:
        status_code = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def iter_lines(self):
            return [("data: " + json.dumps(event)).encode('utf-8') for event in events]

    def post(*args, **kwargs):
        sent.append(kwargs['json'])
        return Response()

    monkeypatch.setattr('monitor_agent_core.provider.requests.post', post)
    client.progress_callback = monitor._progress
    client.request_purpose = 'continuation'
    client.maintenance_prompt = 'FAKE_CONTINUATION_TEST_ONLY'
    client.history.append({'role': 'user', 'content': [
        {'type': 'text', 'text': client.maintenance_prompt}]})
    client._request([])
    assert len(sent) == 1 and monitor._projection_pending_request.get('verified') is None
    client.history.pop()
    client.maintenance_prompt = None
    client.request_purpose = 'review'
    client._request(MONITOR_TOOLS)
    assert len(sent) == 2 and monitor._projection_pending_request['verified'] is True
    captures = list((workspace.private_root / 'audit/provider_pre_send').glob('*.json'))
    assert len(captures) == 2


def test_completed_but_stopped_response_does_not_verify_root(tmp_path, monkeypatch):
    monitor, client, workspace, _ = native_fixture(tmp_path)
    stop = threading.Event()
    client.recovery_stop = stop
    client.recovery_deadline = time.monotonic() + 60
    events = [
        {'type': 'message_start', 'message': {}},
        {'type': 'content_block_start', 'content_block': {'type': 'text'}},
        {'type': 'content_block_delta', 'delta': {'type': 'text_delta', 'text': 'ready'}},
        {'type': 'content_block_stop'}, {'type': 'message_stop'},
    ]

    class Response:
        status_code = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def iter_lines(self):
            for event in events:
                if event['type'] == 'message_stop':
                    stop.set()
                yield ('data: ' + json.dumps(event)).encode('utf-8')

    monkeypatch.setattr('monitor_agent_core.provider.requests.post', lambda *a, **k: Response())
    with pytest.raises(ProviderRecoveryExhausted):
        client._request(MONITOR_TOOLS)
    assert monitor._projection_pending_request is not None
    assert monitor._projection_pending_request.get('verified') is None
    assert len(list((workspace.private_root / 'audit/provider_pre_send').glob('*.json'))) == 1


def test_payload_mismatch_blocks_actual_transport(tmp_path, monkeypatch):
    monitor, client, _, _ = native_fixture(tmp_path)
    client.history[0]['content'][0]['text'] = 'unarchived mutation'
    sent = []
    monkeypatch.setattr('monitor_agent_core.provider.requests.post',
                        lambda *a, **k: sent.append(k))
    client._progress_request_id = 'blocked-review'
    with pytest.raises(ProjectionIntegrityError):
        client._request_once(MONITOR_TOOLS)
    assert sent == []


def test_historical_native_tool_calls_are_not_execution_queue(tmp_path, monkeypatch):
    monitor, client, _, _ = native_fixture(tmp_path)
    calls = []
    monkeypatch.setattr(client, '_request_once', lambda tools: ([
        {'type': 'tool_use', 'id': 'fresh', 'name': 'wait', 'input': {'after_turns': 1}}], {}))

    def dispatch(name, arguments):
        calls.append((name, arguments))
        return ToolOutcome({'status': 'accepted'}, False, MonitorAction('wait', {'after_turns': 1}))

    action = run_review(client, 'system', 'root input', MONITOR_TOOLS, dispatch, max_turns=1)
    assert action.kind == 'wait'
    assert calls == [('wait', {'after_turns': 1})]


def test_second_handoff_reprojects_without_ledger_or_old_analysis(tmp_path):
    monitor, client, workspace, _ = native_fixture(tmp_path)
    client.history.append({'role': 'assistant', 'content': [
        {'type': 'text', 'text': 'new removable analysis'}]})
    next_handoff = {'request_id': 'completion-2', 'generation': 2, 'cursor': 2}
    monitor.completion_state = lambda: next_handoff
    monitor._enter_root_frame(next_handoff)
    current = client.export_history()
    assert 'new removable analysis' not in json.dumps(current)
    assert not any('Historical records in original order' in str(block)
                   for message in current for block in message['content'])
    assert len(list((workspace.private_root / 'audit/root_projections').glob('*/committed.json'))) == 2


def test_rer_branch_reset_and_parent_restore_do_not_replay_old_tools(tmp_path):
    monitor, client, _, handoff = native_fixture(tmp_path)
    client.history.extend([
        {'role': 'assistant', 'content': [
            {'type': 'tool_use', 'id': 'reestimate', 'name': 'allow_complete', 'input': {}}]},
        {'role': 'user', 'content': [
            {'type': 'tool_result', 'tool_use_id': 'reestimate', 'content': '{"status":"accepted"}'}]},
    ])
    parent = client.export_history()
    monitor.crs.root_reorientation = {'root_horizon_digest': 'horizon'}
    action = MonitorAction('root_reestimate', dict(
        request_id=handoff['request_id'], generation=handoff['generation'],
        root_horizon_digest='horizon'))
    monitor.enter_root_reestimate(handoff, action)
    assert client.export_history() == [] and monitor._projection_pending_request is None
    monitor.restore_rer_parent('root_intervened')
    assert client.export_history() == parent
    assert monitor._projection_pending_request is None


def test_wrong_handoff_and_transform_receipt_tamper_block_capture(tmp_path):
    monitor, client, workspace, _ = native_fixture(tmp_path)
    next_handoff = {'request_id': 'other', 'generation': 2, 'cursor': 2}
    monitor.completion_state = lambda: next_handoff
    _, _, payload = client._anthropic_request(MONITOR_TOOLS)
    with pytest.raises(ProjectionIntegrityError):
        _capture_pilot_payload(workspace.private_root, monitor, 'wrong-handoff', payload)
    assert not (workspace.private_root / 'audit/provider_pre_send/wrong-handoff.json').exists()

    (tmp_path / 'receipt').mkdir()
    monitor, client, workspace, _ = native_fixture(tmp_path / 'receipt')
    client.history.extend([
        {'role': 'assistant', 'content': [
            {'type': 'tool_use', 'id': 'big', 'name': 'file_read', 'input': {'path': 'big'}}]},
        {'role': 'user', 'content': [
            {'type': 'tool_result', 'tool_use_id': 'big', 'content': 'Z' * 14000}]},
    ])
    client.history_target_chars = 1000
    client._relieve_tool_result_pressure()
    receipt = monitor._projection_pending_request['transforms'][0]['receipt']
    path = workspace.private_root / receipt[len('monitor/'):]
    path.write_text('{}', encoding='utf-8')
    _, _, payload = client._anthropic_request(MONITOR_TOOLS)
    with pytest.raises(ProjectionIntegrityError):
        _capture_pilot_payload(workspace.private_root, monitor, 'tampered-transform', payload)


def test_replaced_prior_capture_blocks_subsequent_send(tmp_path):
    monitor, client, workspace, _ = native_fixture(tmp_path)
    _, _, payload = client._anthropic_request(MONITOR_TOOLS)
    _capture_pilot_payload(workspace.private_root, monitor, 'first', payload)
    path = workspace.private_root / 'audit/provider_pre_send/first.json'
    path.write_text('{}', encoding='utf-8')
    with pytest.raises(ProjectionIntegrityError):
        _capture_pilot_payload(workspace.private_root, monitor, 'second', payload)


def test_coherently_replaced_projection_archive_cannot_change_committed_source(tmp_path):
    monitor, client, workspace, handoff = native_fixture(tmp_path)
    base = (workspace.private_root / monitor._projection_pending_request[
        'commit_locator'][len('monitor/'):]).parent
    changed = history()
    changed[0]['content'][0]['text'] = 'substituted history'
    projected, manifest, source = project(changed)
    manifest.update(request_id=handoff['request_id'], generation=handoff['generation'])
    commit = {'request_id': handoff['request_id'], 'generation': handoff['generation'],
              'source_sha256': manifest['source_sha256'],
              'projected_sha256': manifest['projected_sha256'],
              'applied': manifest['applied'],
              'source_locator': 'monitor/audit/root_projections/' + base.name + '/source.json'}
    for name, value in (('source.json', source),
                        ('projected_history.json', canonical(projected)),
                        ('manifest.json', canonical(manifest)),
                        ('committed.json', canonical(commit))):
        (base / name).write_bytes(value)
    client.restore_history(projected + [
        {'role': 'user', 'content': [{'type': 'text', 'text': monitor._projection_root_input}]}])
    _, _, payload = client._anthropic_request(MONITOR_TOOLS)
    with pytest.raises(ProjectionIntegrityError):
        _capture_pilot_payload(workspace.private_root, monitor, 'forged', payload)


def test_no_safe_cut_keeps_oversized_history_and_fails_closed(tmp_path):
    monitor, client, _, _ = native_fixture(tmp_path)
    client.restore_history([{'role': 'user', 'content': [
        {'type': 'text', 'text': 'X' * 9000}]}])
    frozen = client.export_history()
    client.history_char_limit = 1000
    client.history_target_chars = 820
    client.prepare_continuation = lambda: 'FAKE_CONTINUATION_TEST_ONLY'
    with pytest.raises(HistoryCapacityError, match='remains over capacity'):
        client._compact_history()
    assert client.export_history() == frozen


def test_default_and_v1_configuration_unchanged(tmp_path):
    monitor, client, workspace, _ = fixture(tmp_path, rhr=True, rer=True)
    assert monitor.history_projection == 'off'
    assert MonitorAgent(MonitorProviderClient('anthropic', dict(
        client.config, monitor_history_projection='root_records_v1')), workspace).history_projection == 'root_records_v1'
    assert MonitorAgent(MonitorProviderClient('anthropic', dict(
        client.config, monitor_history_projection='root_records_native_v2')), workspace
        ).history_projection == 'root_records_native_v2'
