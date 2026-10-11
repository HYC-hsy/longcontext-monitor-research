"""Zero-network tests of the opt-in evidence-package path."""

import json
from pathlib import Path

import pytest

from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.evidence_package_v1 import EvidenceFrontier, EvidencePackageIntegrityError
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.runtime import _capture_pilot_payload
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
        payload = kwargs['json']
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
                         'claim': 'Task basis was inspected; bounded advice remains possible.'}
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

