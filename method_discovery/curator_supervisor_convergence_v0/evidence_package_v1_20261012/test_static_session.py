"""Actual MonitorAgent/provider/run_review through a zero-network host session."""

import json
import hashlib
import re

from monitor_agent_core.evidence_package_v1 import EvidenceFrontier

from .static_session import STATIC_COMMON_CONTEXT, StaticDiagnosticSession


class FakeSSE:
    status_code = 200
    headers = {'content-type': 'text/event-stream'}

    def __init__(self, name, arguments, sequence):
        self.name, self.arguments, self.sequence = name, arguments, sequence

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def iter_lines(self):
        events = [
            {'type': 'message_start', 'message': {'usage': {'input_tokens': 10}}},
            {'type': 'content_block_start', 'content_block': {
                'type': 'tool_use', 'id': f'fake-tool-{self.sequence}', 'name': self.name}},
            {'type': 'content_block_delta', 'delta': {
                'type': 'input_json_delta', 'partial_json': json.dumps(self.arguments)}},
            {'type': 'content_block_stop'},
            {'type': 'message_delta', 'usage': {'output_tokens': 5}},
            {'type': 'message_stop'},
        ]
        return iter([('data: ' + json.dumps(event)).encode() for event in events])


def test_c02_root_packet_raw_receipt_query_and_simulated_control(tmp_path):
    payloads = []
    sequence = ['frontier_open', 'file_read', 'packet_ready',
                'frontier_get', 'frontier_finding', 'intervene']

    def sender(_url, **kwargs):
        payload = json.loads(json.dumps(kwargs['json']))
        payloads.append(payload)
        index = len(payloads) - 1
        if index >= len(sequence):
            raise AssertionError('Unexpected provider request; no real fallback')
        text = json.dumps(payload, ensure_ascii=False)
        visible_text = '\n'.join(block['text'] for message in payload['messages']
                                 for block in message.get('content', [])
                                 if block.get('type') == 'text')
        name = sequence[index]
        if name == 'frontier_open':
            original = visible_text.split('Original public task:', 1)[1]
            first_line = next(line.strip() for line in original.splitlines() if line.strip())
            args = {'task_basis': first_line[:12], 'scope': 'static-source-path',
                    'observable_consequence': 'Public Task behavior',
                    'leads': ['Read the public task source']}
        elif name == 'file_read':
            args = {'path': 'task/workspace/go.mod',
                    'evidence_case_id': re.search(r'case-[0-9a-f]{32}', text).group(),
                    'evidence_scope': 'static-source-path'}
        elif name == 'packet_ready':
            args = {}
        elif name == 'frontier_get':
            args = {'kind': 'receipt',
                    'id': re.search(r'receipt-[0-9a-f]{32}', text).group()}
        elif name == 'frontier_finding':
            original = '\n'.join(block['text'] for message in payloads[0]['messages']
                                 for block in message.get('content', [])
                                 if block.get('type') == 'text').split('Original public task:', 1)[1]
            args = {'packet_id': re.search(r'packet-[0-9a-f]{32}', text).group(),
                    'case_id': re.search(r'case-[0-9a-f]{32}', text).group(),
                    'scope': 'static-source-path',
                    'task_basis': next(line.strip() for line in original.splitlines()
                                       if line.strip())[:12],
                    'receipt_ids': [re.search(r'receipt-[0-9a-f]{32}', text).group()],
                    'claim': 'Request a bounded investigation; no behavior asserted.',
                    'kind': 'investigation_request'}
        else:
            args = {'finding_id': re.search(r'finding-[0-9a-f]{32}', text).group(),
                    'message': 'Please inspect this bounded public source path.'}
        return FakeSSE(name, args, index)

    handoff = {'request_id': 'static-test-completion-1', 'generation': 1,
               'cursor': 161, 'task_turn': 83}
    with StaticDiagnosticSession('C02', tmp_path / 'cutoff',
                                 condition='evidence_package_v1', fake_post=sender) as session:
        result = session.review('Public static root handoff.', root_handoff=handoff,
                                max_turns=12)
        assert result['simulated'] and result['input_sent'] is False
        assert result['kind'] in {'intervene', 'local_intervened', 'root_intervened'}
        assert session.public_config['monitor_evidence_package_v1'] is True
        assert session.public_config['monitor_history_projection'] == 'off'
        assert payloads[0]['model'] == 'claude-opus-4-8'
        assert payloads[0]['max_tokens'] == 8192
        assert 'temperature' not in payloads[0]
        assert session.monitor.control_echo.pending_submission is None
        assert len(payloads) == 6
        assert 'Original public task:' in json.dumps(payloads[0], ensure_ascii=False)
        assert STATIC_COMMON_CONTEXT in json.dumps(payloads[0], ensure_ascii=False)
        assert 'Host inquiry packet' in json.dumps(payloads[3], ensure_ascii=False)
        assert 'frontier_get' in json.dumps(payloads[3]['tools'])
        assert len(list(session.capture_root.glob('*.json'))) == 6
        assert session.client.export_history() == []
        stages = list((session.monitor.evidence_frontier.root / 'stages').glob('*.json'))
        assert len(stages) == 2
        dialogue = (session.port.cognition / 'audit' / 'dialogue.jsonl').read_bytes()
        assert hashlib.sha256(dialogue).hexdigest() == session.manifest['dialogue_prefix_sha256']
        assert (session.monitor.evidence_host_audit_root / 'dialogue.jsonl').is_file()
        assert all(not (session.port.cognition / 'audit' / 'evidence_package' /
                        'stages' / path.name).exists() for path in stages)
        print({'fake_requests': len(payloads), 'host_only_capture': True,
               'raw_receipt_query': True, 'stage_branches_host_only': len(stages),
               'real_task_controls': 0})


def test_native_go_check_uses_monitor_dispatch_and_host_raw_receipt(tmp_path):
    def no_network(*_args, **_kwargs):
        raise AssertionError('No model request expected in this tool-path fixture')
    with StaticDiagnosticSession('C02', tmp_path / 'cutoff',
                                 condition='evidence_package_v1', fake_post=no_network) as session:
        monitor = session.monitor
        monitor.evidence_frontier = EvidenceFrontier(session.port.workspace.private_root)
        monitor._evidence_stage = 'B'
        case = monitor.evidence_frontier.open_case({
            'task_basis': 'public task', 'scope': 'private-fixture',
            'observable_consequence': 'synthetic test result',
            'leads': ['Run one named Go test']})['case_id']
        setup = ('mkdir -p /tmp/go_check\ncd /tmp/go_check\n'
                 "printf '%s\\n' 'module offlinecheck' '' 'go 1.18' >go.mod\n"
                 "printf '%s\\n' 'package check' 'import \"testing\"' "
                 "'func TestPass(t *testing.T) {}' >check_test.go\n")
        result = monitor.dispatch('code_run', {'code': setup, 'type': 'bash',
            'timeout': 60, 'wait_seconds': 5, 'evidence_case_id': case,
            'evidence_scope': 'private-fixture'}).data
        for _ in range(20):
            if result['status'] != 'running':
                break
            result = monitor.dispatch('code_run', {'session_id': result['session_id'],
                'wait_seconds': 5, 'evidence_case_id': case,
                'evidence_scope': 'private-fixture'}).data
        assert result['status'] == 'success', result
        check = monitor.dispatch('go_check', {
            'evidence_case_id': case, 'evidence_scope': 'private-fixture',
            'check_id': 'synthetic-pass-1', 'private_workdir': '/tmp/go_check',
            'package': '.', 'test_name': 'TestPass', 'timeout': 120,
            'expected_source': 'synthetic private fixture only'}).data
        assert check['classification'] == 'test_passed'
        assert check['tests_run'] == ['TestPass']
        receipt = monitor.evidence_frontier.get('receipt', check['host_receipt_id'])['object']
        assert receipt['kind'] == 'native_go_test'
        assert receipt['result']['raw_sha256'] == check['raw_sha256']
        assert session.request_count == 0
        monitor._evidence_stage = None


def test_c01_narrow_baseline_uses_same_static_host_and_no_task_delivery(tmp_path):
    requests = []
    def sender(_url, **kwargs):
        payload = json.loads(json.dumps(kwargs['json']))
        requests.append(payload)
        if len(requests) != 1:
            raise AssertionError('Unexpected static baseline request')
        return FakeSSE('wait', {'after_turns': 1, 'mode': 'patrol'}, 0)
    with StaticDiagnosticSession('C01', tmp_path / 'cutoff',
                                 condition='N', fake_post=sender) as session:
        result = session.review('Inspect only the certified public cutoff.', max_turns=4)
        assert result['kind'] == 'wait' and result['simulated']
        assert session.public_config['monitor_evidence_package_v1'] is False
        assert session.monitor.intervention_callback is None
        assert len(requests) == 1 and 'temperature' not in requests[0]
        assert requests[0]['model'] == 'claude-opus-4-8'
        assert STATIC_COMMON_CONTEXT in json.dumps(requests[0], ensure_ascii=False)
        assert not session.monitor.evidence_frontier
