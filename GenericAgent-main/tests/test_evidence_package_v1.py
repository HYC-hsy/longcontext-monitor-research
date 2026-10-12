"""Zero-network tests of the opt-in evidence-package path."""

import hashlib
import json
from pathlib import Path

import pytest

from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.loop import MonitorLoopError
from monitor_agent_core.evidence_package_v1 import EvidenceFrontier, EvidencePackageIntegrityError
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.runtime import MonitorRuntime, _capture_pilot_payload
from monitor_agent_core.workspace import MonitorWorkspace


class TestPort:
    evidence_test_port = True


def make_monitor(tmp_path, **switches):
    evidence = tmp_path / 'evidence'
    evidence.mkdir(parents=True)
    (evidence / 'original_task.txt').write_text('Keep the public route working.', encoding='utf-8')
    (evidence / 'public_events.jsonl').write_text('', encoding='utf-8')
    task = tmp_path / 'task'
    task.mkdir()
    workspace = MonitorWorkspace(evidence, tmp_path / 'monitor' / 'monitor_private',
                                 task_mounts={'workspace': task})
    config = {'apikey': 'offline-test', 'apibase': 'https://offline.invalid',
              'model': 'claude-opus-4-8', 'provider': 'anthropic', 'max_retries': 0,
              'monitor_adaptive_supervisory_environment': True,
              'monitor_narrow_supervisor_v1': True,
              'monitor_evidence_package_v1': True, **switches}
    client = MonitorProviderClient('offline', config)
    monitor = MonitorAgent(client, workspace)
    monitor.task_budget_state = lambda: (12, 300)
    return monitor, client, workspace


def test_default_off_invalid_combinations_and_port_before_request(tmp_path):
    for value in ('true', 1):
        with pytest.raises(ValueError):
            make_monitor(tmp_path / str(value), monitor_evidence_package_v1=value)
    with pytest.raises(ValueError):
        make_monitor(tmp_path / 'not-narrow', monitor_narrow_supervisor_v1=False)
    monitor, _, _ = make_monitor(tmp_path / 'no-port')
    with pytest.raises(EvidencePackageIntegrityError, match='isolated analysis port'):
        monitor.review('Wake')


def test_shared_task_container_frontier_is_rejected_before_runtime_start(tmp_path):
    """The present pilot bind mount is not a protected host frontier."""
    with pytest.raises(ValueError, match='reachable from the Task container'):
        MonitorRuntime(public_task='Offline public task', task_workspace=tmp_path / 'app',
                       artifact_dir=tmp_path / 'monitor', config_name='offline',
                       model_config={'monitor_evidence_package_v1': True},
                       interrupt_callback=lambda: None, task_id='offline-task',
                       run_id='offline-run', analysis_port_root=tmp_path / 'spool')


def test_frontier_durable_pages_tamper_and_protected_file_tools(tmp_path):
    monitor, _, workspace = make_monitor(tmp_path)
    state = EvidenceFrontier(workspace.private_root)
    ids = []
    for number in range(16):
        row = state.open_case({'task_basis': 'Public route', 'scope': f'route-{number}',
                               'observable_consequence': 'Public response',
                               'leads': ['Read implementation']})
        ids.append(row['case_id'])
    first = state.page(limit=5)
    assert len(first['cases']) == 5 and first['remaining'] == 11
    assert state.page(cursor=first['next_cursor'], limit=20)['remaining'] == 0
    state.revise_case({'case_id': ids[0], 'status': 'blocked', 'reason': 'Fixture unavailable'})
    assert state.page(cursor=first['next_cursor'])['status'] == 'stale_cursor'
    restored = EvidenceFrontier(workspace.private_root)
    assert len(restored.state['cases']) == 16
    with pytest.raises(ValueError):
        restored.revise_case({'case_id': ids[0], 'status': 'observed',
                             'reason': 'No receipt', 'receipt_ids': ['invented']})
    with pytest.raises(ValueError):
        workspace.write_text('monitor/.evidence_package_v1/frontier.json', 'forged')
    state.state_path.write_text('{}', encoding='utf-8')
    with pytest.raises(EvidencePackageIntegrityError):
        restored.verify()


def test_child_focus_finding_provenance_and_current_objection(tmp_path):
    (tmp_path / 'monitor').mkdir()
    state = EvidenceFrontier(tmp_path / 'monitor' / 'monitor_private')
    parent = state.open_case({'task_basis': 'Original task', 'scope': 'interface-A',
                              'observable_consequence': 'Visible effect', 'leads': ['Trace caller']})['case_id']
    sibling = state.open_case({'task_basis': 'Original task', 'scope': 'interface-B',
                               'observable_consequence': 'Visible effect', 'leads': ['Trace caller']})['case_id']
    child = state.open_case({'task_basis': 'Original task', 'scope': 'implementation-A',
                             'observable_consequence': 'State propagation', 'leads': ['Read state'],
                             'parent_id': parent})['case_id']
    assert state.next_focus(return_parent=True)['focus'] == parent
    assert state.next_focus()['focus'] == sibling
    assert state.next_focus()['focus'] == child
    receipt = state.register_receipt('file_read', {'path': 'task/workspace/source.go'},
                                     {'sha256': 'source-v1', 'status': 'ok'})
    packet = state.packet_ready(handoff={'request_id': 'completion-1', 'generation': 1},
                                task_cursor=3)
    with pytest.raises(ValueError, match='host-issued receipts'):
        state.finding({'packet_id': packet['id'], 'case_id': parent,
                       'scope': 'interface-A', 'task_basis': 'Original task',
                       'receipt_ids': ['made-up'], 'claim': 'not an observation',
                       'kind': 'counterexample'}, handoff=packet['handoff'])
    finding = state.finding({'packet_id': packet['id'], 'case_id': parent,
                             'scope': 'interface-A', 'task_basis': 'Original task',
                             'receipt_ids': [receipt], 'claim': 'bounded source contradiction',
                             'kind': 'counterexample'}, handoff=packet['handoff'])['finding_id']
    with pytest.raises(ValueError, match='concrete objection'):
        state.check_allow(state.state['revision'], handoff=packet['handoff'])
    state.revise_case({'case_id': parent, 'status': 'retracted',
                       'reason': 'Source premise overturned', 'receipt_ids': [receipt]})
    state.check_allow(state.state['revision'], handoff=packet['handoff'])
    with pytest.raises(ValueError):
        state.check_intervention(finding, handoff=packet['handoff'])


def test_incomplete_process_is_not_behavioral_evidence(tmp_path):
    (tmp_path / 'monitor').mkdir()
    state = EvidenceFrontier(tmp_path / 'monitor' / 'monitor_private')
    case = state.open_case({'task_basis': 'Original task', 'scope': 'route',
                            'observable_consequence': 'Response', 'leads': ['Run probe']})['case_id']
    running = state.register_receipt('code_run', {'code': 'go test ./...'},
                                      {'status': 'running', 'session_id': 'session-1'})
    assert state.state['receipts'][running]['behavior_verified'] is False
    packet = state.packet_ready(handoff=None, task_cursor=0)
    with pytest.raises(ValueError, match='incomplete process'):
        state.finding({'packet_id': packet['id'], 'case_id': case,
                       'scope': 'route', 'task_basis': 'Original task',
                       'receipt_ids': [running], 'claim': 'tests passed',
                       'kind': 'counterexample'}, handoff=None)


def test_cited_source_change_stales_only_related_finding(tmp_path):
    monitor, _, workspace = make_monitor(tmp_path)
    task = workspace.task_mounts['workspace']
    (task / 'a.go').write_text('package a\n', encoding='utf-8')
    (task / 'b.go').write_text('package b\n', encoding='utf-8')
    state = EvidenceFrontier(workspace.private_root)
    cases = []
    findings = []
    packet = state.packet_ready(handoff=None, task_cursor=0)
    for name in ('a', 'b'):
        case = state.open_case({'task_basis': 'Task contract', 'scope': name,
                                'observable_consequence': name + ' response',
                                'leads': ['Read source']})['case_id']
        result = workspace.read_text('task/workspace/' + name + '.go')
        receipt = state.register_receipt('file_read', {'path': result['path']}, result)
        finding = state.finding({'packet_id': packet['id'], 'case_id': case,
                                 'scope': name, 'task_basis': 'Task contract',
                                 'receipt_ids': [receipt], 'claim': 'Source-level local claim',
                                 'kind': 'counterexample'}, handoff=None)['finding_id']
        cases.append(case)
        findings.append(finding)
    assert state.reconcile_sources(workspace) == []
    (task / 'a.go').write_text('package changed\n', encoding='utf-8')
    assert len(state.reconcile_sources(workspace)) == 1
    assert state.state['findings'][findings[0]]['status'] == 'stale'
    assert state.state['findings'][findings[1]]['status'] == 'current'
    assert state.state['cases'][cases[1]]['status'] == 'pending'
    state.revise_case({'case_id': cases[1], 'status': 'active',
                       'reason': 'Oracle changed after inspecting setup',
                       'hypothesis': 'A different expected behavior'})
    assert state.state['findings'][findings[1]]['status'] == 'stale'


def test_real_provider_send_two_phase_packet_finding_and_delivery(tmp_path, monkeypatch):
    monitor, client, workspace = make_monitor(tmp_path)
    monitor.analysis = TestPort()
    monitor.intervention_callback = lambda message: {
        'submission_id': 'offline-delivery-1', 'delivery': 'queued',
        'submitted_task_turn': 12, 'submitted_cursor': 0}
    client.pre_send_capture = lambda request_id, payload: _capture_pilot_payload(
        workspace.private_root, monitor, request_id, payload)
    payloads = []
    actions = ['file_write', 'frontier_open', 'packet_ready', 'file_read',
               'frontier_finding', 'intervene']

    class FakeResponse:
        status_code = 200
        headers = {'content-type': 'text/event-stream'}

        def __init__(self, action, arguments):
            self.action, self.arguments = action, arguments

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def iter_lines(self):
            events = [
                {'type': 'message_start', 'message': {'usage': {'input_tokens': 10}}},
                {'type': 'content_block_start', 'content_block': {
                    'type': 'tool_use', 'id': 'offline-tool-' + str(len(payloads)),
                    'name': self.action}},
                {'type': 'content_block_delta', 'delta': {
                    'type': 'input_json_delta', 'partial_json': json.dumps(self.arguments)}},
                {'type': 'content_block_stop'},
                {'type': 'message_delta', 'usage': {'output_tokens': 5}},
                {'type': 'message_stop'},
            ]
            return iter([('data: ' + json.dumps(item)).encode() for item in events])

    def post(_url, **kwargs):
        payload = json.loads(json.dumps(kwargs['json']))
        payloads.append(payload)
        index = len(payloads) - 1
        action = actions[index]
        if action == 'file_write':
            arguments = {'path': 'monitor/reference.md', 'content': 'Public route obligation.'}
        elif action == 'frontier_open':
            arguments = {'task_basis': 'Public route', 'scope': 'route-handler',
                         'observable_consequence': 'Response remains available',
                         'leads': ['Read the route handler']}
        elif action == 'packet_ready':
            arguments = {}
        elif action == 'file_read':
            arguments = {'path': 'task/original_task.txt'}
        elif action == 'frontier_finding':
            state = monitor.evidence_frontier.state
            arguments = {'packet_id': state['packet']['id'],
                         'case_id': state['order'][0], 'task_basis': 'Public route',
                         'scope': 'route-handler', 'receipt_ids': list(state['receipts']),
                         'claim': 'Task basis was inspected; bounded advice remains possible.',
                         'kind': 'investigation_request'}
        else:
            arguments = {'finding_id': next(iter(monitor.evidence_frontier.state['findings'])),
                         'message': 'Please inspect the public route behavior.'}
        return FakeResponse(action, arguments)

    monkeypatch.setattr('monitor_agent_core.provider.requests.post', post)
    action = monitor.review('Current public Task behavior.', max_turns_override=12)
    assert action.kind == 'local_intervened'
    assert len(payloads) == 6
    assert 'Phase A' in payloads[0]['system']
    assert 'Phase B' in payloads[3]['system']
    assert payloads[3]['messages'][0]['role'] == 'user'
    assert not any('offline-tool-1' in json.dumps(message)
                   for message in payloads[3]['messages'])
    assert monitor.evidence_frontier.state['packet']['executed'] is False
    assert monitor.evidence_frontier.state['packet']['input_sent'] is False
    assert monitor.control_echo.pending_submission['submission_id'] == 'offline-delivery-1'
    assert len(list((workspace.private_root / 'audit' / 'provider_pre_send').glob('*.json'))) == 6
    for stage, payload in [('A', payloads[0]), ('B', payloads[3])]:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                         separators=(',', ':')).encode('utf-8')
        print(json.dumps({'fake_request_stage': stage, 'canonical_sha256':
                          hashlib.sha256(raw).hexdigest(), 'byte_count': len(raw),
                          'fields': sorted(payload), 'message_count': len(payload['messages']),
                          'tool_count': len(payload['tools'])}))


def test_root_packet_reference_guard_and_no_objection_path(tmp_path, monkeypatch):
    monitor, client, workspace = make_monitor(tmp_path)
    monitor.analysis = TestPort()
    handoff = {'generation': 1, 'request_id': 'completion-1', 'cursor': 1}
    monitor.completion_state = lambda: handoff
    (workspace.evidence_root / 'public_events.jsonl').write_text(json.dumps({
        'archive_sequence': 1, 'task_turn': 12, 'boundary': 'completion',
        'text': 'Task says done.', 'tool_calls': [], 'tool_results': []}) + '\n',
        encoding='utf-8')
    client.pre_send_capture = lambda request_id, payload: _capture_pilot_payload(
        workspace.private_root, monitor, request_id, payload)
    checkpoint_requests = []
    client.request_assembly_callback = lambda snapshot: (
        checkpoint_requests.append(snapshot) or True)
    sent = []
    actions = ['packet_ready', 'wait', 'allow_complete', 'file_write', 'allow_complete']

    class Response:
        status_code = 200
        headers = {'content-type': 'text/event-stream'}

        def __init__(self, name, arguments):
            self.name, self.arguments = name, arguments

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def iter_lines(self):
            events = [
                {'type': 'message_start', 'message': {'usage': {}}},
                {'type': 'content_block_start', 'content_block': {
                    'type': 'tool_use', 'id': 'root-tool-' + str(len(sent)),
                    'name': self.name}},
                {'type': 'content_block_delta', 'delta': {
                    'type': 'input_json_delta', 'partial_json': json.dumps(self.arguments)}},
                {'type': 'content_block_stop'},
                {'type': 'message_stop'},
            ]
            return iter([('data: ' + json.dumps(item)).encode() for item in events])

    def post(_url, **kwargs):
        sent.append(json.loads(json.dumps(kwargs['json'])))
        index = len(sent) - 1
        name = actions[index]
        if name == 'allow_complete':
            arguments = {'frontier_revision': monitor.evidence_frontier.state['revision']}
        elif name == 'wait':
            arguments = {'after_turns': 1, 'mode': 'follow'}
        elif name == 'file_write':
            arguments = {'path': 'monitor/reference.md', 'content': 'Public route contract.'}
        else:
            arguments = {}
        return Response(name, arguments)

    monkeypatch.setattr('monitor_agent_core.provider.requests.post', post)
    action = monitor.review('Task completion handoff.', completion_pending=True,
                            root_handoff=handoff, max_turns_override=8)
    assert action.kind == 'allow_complete'
    assert len(sent) == 5
    assert monitor.evidence_frontier.state['packet']['handoff'] == handoff
    assert checkpoint_requests and checkpoint_requests[0]['root_handoff'] == handoff
    assert 'Phase A' in sent[0]['system'] and 'Phase B' in sent[1]['system']
    first_input = json.dumps(sent[0]['messages'], ensure_ascii=False)
    second_input = json.dumps(sent[1]['messages'], ensure_ascii=False)
    assert 'Task completion handoff.' in first_input
    assert 'Keep the public route working.' in first_input
    assert 'Host inquiry frontier' in first_input
    assert monitor.evidence_frontier.state['packet']['id'] in second_input
    assert 'Host inquiry packet' in second_input
    assert 'Keep the public route working.' in second_input
    dialogue = (workspace.private_root / 'audit' / 'dialogue.jsonl').read_text(
        encoding='utf-8')
    assert 'reference_invalid' in dialogue
    assert 'handoff_pending' in dialogue
    assert not any(row.get('event') == 'ase_reconsideration_boundary'
                   for row in map(json.loads, dialogue.splitlines()))


def test_mid_phase_root_cutover_preserves_budget_and_parent_history(tmp_path, monkeypatch):
    monitor, client, workspace = make_monitor(tmp_path)
    monitor.analysis = TestPort()
    client.pre_send_capture = lambda *_: None
    parent = [{'role': 'user', 'content': [{'type': 'text', 'text': 'prior context'}]}]
    client.restore_history(parent)
    current = {'generation': 2, 'request_id': 'completion-2', 'cursor': 1}
    state = {'handoff': None, 'calls': 0}
    monitor.completion_state = lambda: state['handoff']

    def first(_tools):
        state['calls'] += 1
        assert state['calls'] == 1
        state['handoff'] = current
        return [{'type': 'text', 'text': 'Inspecting.'}], {}

    monkeypatch.setattr(client, '_request_once', first)
    action = monitor.review('Ordinary wake.', max_turns_override=5)
    assert action.kind == 'root_route'
    assert action.payload['prior_model_turns'] == 1
    assert client.export_history() == parent
    assert monitor.evidence_frontier.state['packet'] is None


def test_shared_outer_budget_exhaustion_is_not_wait(tmp_path, monkeypatch):
    monitor, client, _ = make_monitor(tmp_path)
    monitor.analysis = TestPort()
    client.pre_send_capture = lambda *_: None
    calls = []

    def fake(_tools):
        calls.append(monitor._evidence_stage)
        if monitor._evidence_stage == 'A':
            return [{'type': 'tool_use', 'id': 'packet', 'name': 'packet_ready',
                     'input': {}}], {}
        return [{'type': 'text', 'text': 'Need more investigation.'}], {}

    monkeypatch.setattr(client, '_request_once', fake)
    with pytest.raises(MonitorLoopError):
        monitor.review('Wake.', max_turns_override=2)
    assert calls == ['A', 'B']
    assert monitor.evidence_frontier.state['packet']['executed'] is False
    assert monitor._evidence_stage is None


def test_real_maintenance_format_repair_does_not_execute_or_finish_packet(tmp_path, monkeypatch):
    monitor, client, workspace = make_monitor(tmp_path)
    monitor.analysis = TestPort()
    monitor.evidence_frontier = EvidenceFrontier(workspace.private_root)
    packet = monitor.evidence_frontier.packet_ready(handoff=None, task_cursor=0)
    monitor._evidence_stage = 'B'
    monitor._evidence_limit = 8
    sent = []
    client.pre_send_capture = lambda request_id, payload: _capture_pilot_payload(
        workspace.private_root, monitor, request_id, payload)

    class Response:
        status_code = 200
        headers = {'content-type': 'text/event-stream'}

        def __init__(self, number):
            self.number = number

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def iter_lines(self):
            if self.number == 1:
                block = {'type': 'tool_use', 'id': 'unexecuted', 'name': 'wait'}
                delta = {'type': 'input_json_delta', 'partial_json': '{"after_turns":1}'}
            else:
                block = {'type': 'text', 'text': ''}
                delta = {'type': 'text_delta', 'text': 'Keep the bounded question open.'}
            events = [
                {'type': 'message_start', 'message': {'usage': {}}},
                {'type': 'content_block_start', 'content_block': block},
                {'type': 'content_block_delta', 'delta': delta},
                {'type': 'content_block_stop'},
                {'type': 'message_stop'},
            ]
            return iter([('data: ' + json.dumps(item)).encode() for item in events])

    def post(_url, **kwargs):
        sent.append(json.loads(json.dumps(kwargs['json'])))
        return Response(len(sent))

    monkeypatch.setattr('monitor_agent_core.provider.requests.post', post)
    before = client.export_history()
    note = monitor._prepare_continuation()
    assert note == 'Keep the bounded question open.'
    assert len(sent) == 2 and all(row['tools'] == [] for row in sent)
    assert sent[0]['messages'][-1] != sent[1]['messages'][-1]
    assert client.export_history() == before
    assert getattr(client, 'request_purpose', 'review') == 'review'
    assert monitor.evidence_frontier.state['packet'] == packet
    assert monitor._evidence_maintenance_calls == 2
    assert not monitor._sent_messages

