"""Actual MonitorAgent/provider/run_review through a zero-network host session."""

import json
import hashlib
import re

import pytest

from monitor_agent_core.evidence_package_v1 import EvidenceFrontier

from .static_session import STATIC_COMMON_CONTEXT, StaticDiagnosticSession
from .static_host import IMAGE, KITEX_IMAGE


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

    with StaticDiagnosticSession('C02', tmp_path / 'cutoff',
                                 condition='evidence_package_v1', fake_post=sender) as session:
        assert session.cutoff['task_turn'] == 83 and session.cutoff['completion_pending']
        result = session.review(max_turns=12)
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
        for payload in payloads:
            visible = json.dumps(payload, ensure_ascii=False)
            assert 'FUTURE_DIAGNOSTIC_MANIFEST' not in visible
            assert 'STATIC_HOST_REPORT' not in visible
            assert 'evidence_package_v1_20261012' not in visible
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


@pytest.mark.parametrize('image', [IMAGE, KITEX_IMAGE])
def test_native_go_check_uses_monitor_dispatch_and_host_raw_receipt(tmp_path, image):
    def no_network(*_args, **_kwargs):
        raise AssertionError('No model request expected in this tool-path fixture')
    with StaticDiagnosticSession('C02', tmp_path / 'cutoff',
                                 condition='evidence_package_v1', fake_post=no_network,
                                 image=image) as session:
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
                 "'func TestPass(t *testing.T) {}' "
                 "'func TestFail(t *testing.T) { t.Fatal(\"fixture failure\") }' "
                 "'func TestParent(t *testing.T) { t.Run(\"child\", func(t *testing.T) { t.Skip(\"fixture skip\") }) }' >check_test.go\n")
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
        assert check.get('classification') == 'test_passed', check
        assert check['command'].startswith('cd -- /tmp/go_check && go test ')
        assert check['normalized_workdir'] == '/tmp/go_check'
        assert check['tests_run'] == ['TestPass']
        receipt = monitor.evidence_frontier.get('receipt', check['host_receipt_id'])['object']
        assert receipt['kind'] == 'native_go_test'
        assert receipt['result']['raw_sha256'] == check['raw_sha256']
        assert check['private_source_before']['sha256'] == check['private_source_after']['sha256']
        assert any(item[0] == 'check_test.go' for item in
                   check['private_source_before']['identity']['files'])
        for selector, expected in [('TestFail', 'test_failed'),
                                   ('TestParent/child', 'all_skipped')]:
            observed = monitor.dispatch('go_check', {
                'evidence_case_id': case, 'evidence_scope': 'private-fixture',
                'check_id': 'synthetic-' + selector, 'private_workdir': '/tmp/go_check',
                'package': '.', 'test_name': selector, 'timeout': 120,
                'expected_source': 'synthetic private fixture only'}).data
            assert observed.get('classification') == expected, observed
            assert not observed['behavior_verified']
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
        assert session.cutoff['task_turn'] == 61
        result = session.review(max_turns=4)
        assert result['kind'] == 'wait' and result['simulated']
        assert session.public_config['monitor_evidence_package_v1'] is False
        assert session.monitor.intervention_callback is None
        assert len(requests) == 1 and 'temperature' not in requests[0]
        assert requests[0]['model'] == 'claude-opus-4-8'
        assert STATIC_COMMON_CONTEXT in json.dumps(requests[0], ensure_ascii=False)
        assert 'FUTURE_DIAGNOSTIC_MANIFEST' not in json.dumps(requests[0])
        assert not session.monitor.evidence_frontier


@pytest.mark.parametrize('scene,turn,cursor', [('C01', 61, 120), ('C02', 83, 161)])
def test_same_certified_first_input_for_narrow_and_candidate(scene, turn, cursor, tmp_path):
    captured = {}
    for condition in ('N', 'evidence_package_v1'):
        def capture_once(_url, **kwargs):
            captured[condition] = json.loads(json.dumps(kwargs['json']))
            raise RuntimeError('FAKE_FIRST_REQUEST_CAPTURED')
        with StaticDiagnosticSession(scene, tmp_path / condition,
                                     condition=condition, fake_post=capture_once) as session:
            assert session.cutoff['task_turn'] == turn
            assert session.cutoff['public_cursor'] == cursor
            assert session.client.export_history() == []
            with pytest.raises(RuntimeError, match='FAKE_FIRST_REQUEST_CAPTURED'):
                session.review(max_turns=4)
            assert session.request_count == 1
    for condition, payload in captured.items():
        visible = json.dumps(payload, ensure_ascii=False)
        assert 'Original public task:' in visible and 'Current Task Book' in visible
        assert STATIC_COMMON_CONTEXT in visible
        assert f'cursor={cursor}' in visible and f'Task turn={turn}' in visible
        assert payload['model'] == 'claude-opus-4-8' and payload['max_tokens'] == 8192
        assert 'temperature' not in payload
    assert captured['N']['model'] == captured['evidence_package_v1']['model']
    assert captured['N']['max_tokens'] == captured['evidence_package_v1']['max_tokens']
    print({'scene': scene, 'task_turn': turn, 'cursor': cursor,
           'first_request_sha256': {name: hashlib.sha256(json.dumps(value,
               ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
               for name, value in captured.items()}, 'real_provider_calls': 0})


def test_c01_candidate_and_c02_narrow_use_real_tool_result_backfill(tmp_path):
    for scene, condition, sequence in (
            ('C01', 'evidence_package_v1',
             ['frontier_open', 'file_read', 'packet_ready', 'frontier_get', 'wait']),
            ('C02', 'N', ['file_read', 'allow_complete'])):
        sent = []
        def sender(_url, **kwargs):
            payload = json.loads(json.dumps(kwargs['json']))
            sent.append(payload)
            index = len(sent) - 1
            if index >= len(sequence):
                raise AssertionError('Unexpected fake request; real transport is disabled')
            visible = json.dumps(payload['messages'], ensure_ascii=False)
            name = sequence[index]
            if name == 'frontier_open':
                original = visible.split('Original public task:', 1)[1]
                basis = next(line.strip() for line in original.splitlines() if line.strip())[:12]
                args = {'task_basis': basis, 'scope': 'public-source',
                        'observable_consequence': 'Current public task behavior',
                        'leads': ['Read the current source']}
            elif name == 'file_read':
                args = {'path': 'task/workspace/go.mod'}
                if condition != 'N':
                    args.update({'evidence_case_id': re.search(r'case-[0-9a-f]{32}', visible).group(),
                                 'evidence_scope': 'public-source'})
            elif name == 'frontier_get':
                args = {'kind': 'receipt',
                        'id': re.search(r'receipt-[0-9a-f]{32}', visible).group()}
            elif name == 'wait':
                args = {'after_turns': 1, 'mode': 'patrol'}
            else:
                args = {}
            return FakeSSE(name, args, index)
        with StaticDiagnosticSession(scene, tmp_path / scene,
                                     condition=condition, fake_post=sender) as session:
            proposal = session.review(max_turns=8)
            assert proposal['simulated'] and proposal['input_sent'] is False
            assert len(sent) == len(sequence)
            for index in range(1, len(sent)):
                assert f'fake-tool-{index - 1}' in json.dumps(sent[index]['messages'])
            assert session.monitor.intervention_callback is None
            print({'scene': scene, 'condition': condition, 'fake_requests': len(sent),
                   'tool_backfill_verified': True, 'terminal': proposal['kind']})
