"""Zero-network checks for the authority-gated static batch seam."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from .static_live_batch import (CUTOFFS, IMAGE, REQUIRED_SOURCE, REPO, SLOTS,
                                _head, _profile, digest, run_slot, validate_gate)
from .test_static_session import FakeSSE
from .static_session import StaticDiagnosticSession
from monitor_agent_core.evidence_package_v1 import EvidenceFrontier


def fixture_gate(tmp_path):
    profile = tmp_path / 'profile.private.json'
    profile.write_text(json.dumps({'claude_monitor_opus48': {
        'apikey': 'offline-test-only', 'apibase': 'https://offline.invalid',
        'provider': 'anthropic', 'model': 'claude-opus-4-8',
        'max_tokens': 8192, 'thinking_type': 'adaptive',
        'reasoning_effort': 'high', 'temperature': 1}}), encoding='utf-8')
    profiles = {name: _profile(profile, name)[1] for name in ('N', 'E')}
    manifest = {'execution_authorized': False, 'slots': SLOTS, 'cutoffs': CUTOFFS,
        'image_id': IMAGE, 'max_outer_cycles': 100, 'deadline_seconds': 3600,
        'profile_sha256': digest(profile), 'public_profiles': profiles,
        'source_sha256': {name: digest(REPO / name) for name in sorted(REQUIRED_SOURCE)}}
    manifest_path = tmp_path / 'MANIFEST.json'
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    output = tmp_path / 'fresh-run'
    bindings = [dict(slot, run_id=f'zero-model-{slot["order"]:02d}',
        run_root=str(output / f"{slot['order']:02d}-{slot['scene']}-{slot['repeat']}-{slot['condition']}"))
        for slot in SLOTS]
    auth = {'execution_authorized': True, 'manifest_sha256': digest(manifest_path),
        'audited_code_commit': _head(), 'approved_slots': SLOTS,
        'output_root': str(output), 'run_bindings': bindings}
    auth_path = tmp_path / 'AUTHORIZATION.json'
    auth_path.write_text(json.dumps(auth), encoding='utf-8')
    return manifest_path, auth_path, profile, output, bindings


def test_authority_gate_rejects_absent_mismatch_and_stale_identities_before_send(
        tmp_path, monkeypatch):
    manifest, auth, profile, output, _ = fixture_gate(tmp_path)
    def no_network(*_args, **_kwargs):
        raise AssertionError('The live provider must not be reached by a gate test')
    monkeypatch.setattr('requests.post', no_network)
    validate_gate(manifest, auth, profile, output, require_fresh=True)
    with pytest.raises(FileNotFoundError):
        validate_gate(manifest, tmp_path / 'absent.json', profile, output,
                      require_fresh=True)
    original = auth.read_text(encoding='utf-8')
    for change in ({'audited_code_commit': 'wrong'}, {'manifest_sha256': 'wrong'},
                   {'approved_slots': list(reversed(SLOTS))},
                   {'run_bindings': json.loads(original)['run_bindings'][:-1]}):
        edited = json.loads(original)
        edited.update(change)
        auth.write_text(json.dumps(edited), encoding='utf-8')
        with pytest.raises(RuntimeError, match='authorization|bindings'):
            validate_gate(manifest, auth, profile, output, require_fresh=True)
    auth.write_text(original, encoding='utf-8')
    output.mkdir()
    with pytest.raises(RuntimeError, match='authorization'):
        validate_gate(manifest, auth, profile, output, require_fresh=True)
    assert not list(output.iterdir())
    child = subprocess.run([sys.executable, '-m',
        'method_discovery.curator_supervisor_convergence_v0.evidence_package_v1_20261012.static_live_batch',
        '--live', '--manifest', str(manifest), '--authorization', str(tmp_path / 'absent.json'),
        '--profile-file', str(profile), '--output-root', str(tmp_path / 'another-fresh-run')],
        cwd=REPO, capture_output=True, timeout=20)
    assert child.returncode != 0
    assert not (tmp_path / 'another-fresh-run').exists()


def test_authorized_static_slot_uses_native_complete_and_simulated_control_only(
        tmp_path, monkeypatch):
    manifest, auth, profile, output, bindings = fixture_gate(tmp_path)
    validate_gate(manifest, auth, profile, output, require_fresh=True)
    sent = []
    def fake_post(_url, **kwargs):
        sent.append(json.loads(json.dumps(kwargs['json'])))
        assert len(sent) == 1, 'Unexpected second request; no network fallback'
        return FakeSSE('wait', {'after_turns': 1, 'mode': 'patrol'}, 1)
    monkeypatch.setattr('requests.post', fake_post)
    config, public = _profile(profile, 'N')
    record = run_slot(SLOTS[0], bindings[0], config)
    assert record['cleanup_certified'] and not record['stop_batch']
    assert record['outcome']['simulated'] and record['outcome']['input_sent'] is False
    assert record['outcome']['kind'] == 'wait'
    assert record['complete_calls'] == 1 and record['pre_send_attempts'] == 1
    assert sent[0]['model'] == 'claude-opus-4-8' and sent[0]['max_tokens'] == 8192
    assert sent[0]['thinking'] == {'type': 'adaptive'}
    assert 'temperature' not in sent[0]
    assert public['monitor_history_projection'] == 'off'
    path = Path(bindings[0]['run_root'])
    archived = next((path / 'host_requests').glob('0001-*.json'))
    assert hashlib.sha256(archived.read_bytes()).hexdigest() == hashlib.sha256(
        json.dumps(sent[0], ensure_ascii=False, sort_keys=True,
                   separators=(',', ':')).encode()).hexdigest()
    assert (path / 'host_requests' / 'provider_history.json').is_file()
    assert len(list((path / 'host_requests').glob('*.sse.jsonl'))) == 1
    assert (path / 'SLOT_RESULT.json').is_file()
    assert not (path / 'task_queue').exists()


def test_full_compaction_format_repair_near_cycle_limit_keeps_stage_identity(
        tmp_path, monkeypatch):
    profile = tmp_path / 'profile.private.json'
    profile.write_text(json.dumps({'claude_monitor_opus48': {
        'apikey': 'offline-test-only', 'apibase': 'https://offline.invalid',
        'provider': 'anthropic', 'model': 'claude-opus-4-8', 'max_tokens': 8192,
        'thinking_type': 'adaptive', 'reasoning_effort': 'high', 'temperature': 1}}),
        encoding='utf-8')
    config, _ = _profile(profile, 'E')
    sent = []
    class NoteResponse:
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
                block = {'type': 'tool_use', 'id': 'never-execute', 'name': 'wait'}
                delta = {'type': 'input_json_delta', 'partial_json': '{"after_turns":1}'}
            else:
                block = {'type': 'text', 'text': ''}
                delta = {'type': 'text_delta', 'text': 'B phase bounded question remains open.'}
            events = [
                {'type': 'message_start', 'message': {'usage': {}}},
                {'type': 'content_block_start', 'content_block': block},
                {'type': 'content_block_delta', 'delta': delta},
                {'type': 'content_block_stop'}, {'type': 'message_stop'}]
            return iter([('data: ' + json.dumps(item)).encode() for item in events])
    def post(_url, **kwargs):
        sent.append(json.loads(json.dumps(kwargs['json'])))
        if len(sent) > 2:
            raise AssertionError('Unexpected maintenance request; no real fallback')
        return NoteResponse(len(sent))
    monkeypatch.setattr('requests.post', post)
    with StaticDiagnosticSession('C01', tmp_path / 'cutoff',
                                 condition='evidence_package_v1',
                                 _live_config=config) as session:
        monitor, client = session.monitor, session.client
        monitor._evidence_stage = 'B'
        monitor._evidence_limit = 100
        monitor._evidence_model_cycles = 99
        monitor.evidence_frontier = EvidenceFrontier(session.port.workspace.private_root)
        monitor.evidence_frontier.packet_ready(handoff=None, task_cursor=120)
        client.transport_post = post
        client.history = [block for number in range(20) for block in (
            {'role': 'user', 'content': [{'type': 'text', 'text': f'prior public event {number}'}]},
            {'role': 'assistant', 'content': [{'type': 'text',
                'text': f'bounded earlier response {number}'}]})]
        original = client.export_history()
        client.history_char_limit = 1000
        client.history_target_chars = 400
        client.recovery_deadline = time.monotonic() + 30
        client._compact_history()
        assert len(sent) == 2
        assert all(payload['tools'] == [] for payload in sent)
        assert all('evidence phase B' in json.dumps(payload['messages']) for payload in sent)
        assert sent[0]['messages'][-1] != sent[1]['messages'][-1]
        assert monitor._evidence_model_cycles == 99
        assert monitor._evidence_maintenance_calls == 2
        assert client.export_history() != original
        assert client.history_measure()['characters'] <= 1000
        assert monitor.evidence_frontier.state['packet']['task_cursor'] == 120
        assert not monitor._sent_messages


def test_stop_after_complete_response_discards_control_without_retry(tmp_path):
    profile = tmp_path / 'profile.private.json'
    profile.write_text(json.dumps({'claude_monitor_opus48': {
        'apikey': 'offline-test-only', 'apibase': 'https://offline.invalid',
        'provider': 'anthropic', 'model': 'claude-opus-4-8',
        'max_tokens': 8192, 'thinking_type': 'adaptive',
        'reasoning_effort': 'high'}}), encoding='utf-8')
    config, _ = _profile(profile, 'N')
    with StaticDiagnosticSession('C01', tmp_path / 'cutoff', condition='N',
                                 _live_config=config) as session:
        calls = []
        def post(_url, **kwargs):
            calls.append(kwargs['json'])
            session.stop.set()
            return FakeSSE('wait', {'after_turns': 1, 'mode': 'patrol'}, 1)
        session.client.transport_post = post
        with pytest.raises(Exception, match='discarded|stopped|cancelled|exhausted'):
            session.review(max_turns=100)
        assert len(calls) == 1
        assert not (session.destination / 'STATIC_CONTROL_PROPOSAL.json').exists()
        assert all(row['role'] != 'assistant' for row in session.client.export_history())
        events = [json.loads(line) for line in (session.capture_root /
            'provider_events.jsonl').read_text(encoding='utf-8').splitlines()]
        assert any(row.get('event') == 'response_discarded' for row in events)
