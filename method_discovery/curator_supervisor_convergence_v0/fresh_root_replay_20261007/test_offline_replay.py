"""Zero-model fixture and request-boundary regression tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from method_discovery.curator_supervisor_convergence_v0.fresh_root_replay_20261007 import materialize
from method_discovery.curator_supervisor_convergence_v0.fresh_root_replay_20261007 import offline_replay as replay
from monitor_agent_core.provider import ModelResponse, ToolCall


ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / 'FIXTURE_MANIFEST.json').read_text(encoding='utf-8'))


class ScriptedClient:
    """Implements only provider mechanics needed by the existing run_review loop."""

    def __init__(self, actions):
        self.actions = list(actions)
        self.history = []
        self.system = ''
        self.model = replay.MODEL
        self.complete_calls = 0
        self.progress_callback = None

    def export_history(self):
        return json.loads(json.dumps(self.history))

    def history_measure(self):
        encoded = json.dumps(self.history, ensure_ascii=False).encode('utf-8')
        return {'items': len(self.history), 'characters': len(encoded),
                'sha256': hashlib.sha256(encoded).hexdigest()}

    def assembled_request_snapshot(self, tools):
        return {'system': self.system, 'messages': self.export_history(), 'tools': tools,
                'model_parameters': {'model': self.model}}

    def _request_with_recovery(self, tools):
        name, arguments = self.actions.pop(0)
        assert name in [item['function']['name'] for item in tools]
        return ModelResponse('', [ToolCall(f'call-{self.complete_calls}', name,
                                           json.dumps(arguments))], {})

    def complete(self, messages, tools):
        self.complete_calls += 1
        self.system = next(row['content'] for row in messages if row['role'] == 'system')
        self.history.append({'role': 'user', 'content': messages})
        response = self._request_with_recovery(tools)
        self.history.append({'role': 'assistant', 'content': response.tool_calls[0].name})
        return response

    def record_tool_results(self, results):
        self.history.append({'role': 'user', 'content': results})

    def drain_telemetry(self):
        return {'usage': [], 'request_attempts': [], 'history_transforms': []}


def authorization():
    return {'execution_authorized': True, 'model': replay.MODEL,
            'fixture_manifest_sha256': replay.fixture_identity()['manifest_sha256'],
            'code_image': replay.CODE_IMAGE,
            'approved_conditions': ['simple_fresh', 'spec_first_fresh']}


def audit_rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def test_checkpoint_bound_to_exact_pre_evaluator_tar_and_patch():
    assert materialize.digest(materialize.CAPTURE) == materialize.EXPECTED_CAPTURE_SHA256
    assert materialize.digest(materialize.ARCHIVE / 'task_final/tracked_changes.patch') == materialize.EXPECTED_PATCH_SHA256
    recorded = json.loads((materialize.ARCHIVE / 'RAW_FILE_MANIFEST.json').read_text(encoding='utf-8'))
    assert any(row['sha256'] == materialize.EXPECTED_CAPTURE_SHA256
               and row['path'] == str(materialize.CAPTURE)
               for row in recorded['local_only_large_artifacts'])
    assert MANIFEST['checkpoint'] == 'final Task workspace captured before native evaluator'


def test_source_additions_and_workspace_manifest_are_exact():
    identity = replay.fixture_identity()
    assert identity['workspace_tree_sha256'] == MANIFEST['workspace_tree_sha256']
    assert identity['file_count'] == len(MANIFEST['included_paths']) == 2473
    for row in MANIFEST['untracked_implementation_sources']:
        assert replay.sha(replay.FIXTURE / 'workspace' / row['path']) == row['sha256']
        assert row['path'].endswith('.go')
    assert len(MANIFEST['untracked_implementation_sources']) == 5


def test_hidden_history_gold_and_completion_narrative_not_readable():
    included = {row['path'] for row in MANIFEST['included_paths']}
    excluded = {row['path']: row['reason'] for row in MANIFEST['excluded_paths']}
    assert {'IMPLEMENTATION_COMPLETE.md', 'IMPLEMENTATION_SUMMARY.md'} <= set(excluded)
    assert not any(path in included for path in excluded)
    assert not any(path.startswith(('.git/', 'monitor/', 'monitor_private/', 'verifier/',
                                    'solution/', '.monitor_original_task_')) for path in included)
    assert not any('public_events' in path or 'provider_history' in path or
                   'CRS_TRACE' in path or 'reward' in path for path in included)
    assert MANIFEST['native_evaluator_or_history_in_review_view'] is False


def test_spec_phase_task_only_and_no_workspace_access(tmp_path):
    client = ScriptedClient([])
    session = replay.ReplaySession('spec_first_fresh', client, replay.FIXTURE, tmp_path / 'B')
    system, user = replay.phase_input('specification', 'PUBLIC_TASK_SENTINEL')
    assert 'PUBLIC_TASK_SENTINEL' in user and 'workspace' not in user.lower()
    assert [tool['function']['name'] for tool in replay.review_tools('specification')] == [
        'file_read', 'commit_review_basis']
    assert replay.review_tools('specification')[0]['function']['parameters']['properties']['path']['enum'] == [
        'task/original_task.txt']
    assert 'workspace' not in json.dumps(replay.review_tools('specification')).lower()
    refused = session._dispatch('specification', 'file_read', {'path': 'task/workspace/app.go'})
    assert refused.data['status'] == 'error'
    assert session._dispatch('specification', 'code_run', {'command': 'find .'}).data['status'] == 'error'
    assert session._dispatch('specification', 'file_read', {'path': 'task/original_task.txt'}).data['sha256'] == MANIFEST['public_task_sha256']


def test_final_tool_schema_equal_and_basis_non_evidence():
    a = replay.review_tools('review')
    b = replay.review_tools('review')
    assert a == b
    assert [tool['function']['name'] for tool in a] == ['file_read', 'code_run', 'finish_review']
    assert a[-1]['function']['parameters']['required'] == ['outcome', 'conclusion']
    assert a[-1]['function']['parameters']['properties']['outcome']['enum'] == ['release', 'block', 'unresolved']
    system_a, user_a = replay.phase_input('review', 'TASK')
    system_b, user_b = replay.phase_input('review', 'TASK', 'BASIS_SENTINEL')
    assert system_a == system_b == replay.SIMPLE_SYSTEM
    assert 'BASIS_SENTINEL' not in user_a
    assert 'model-authored, revisable, not an oracle and not evidence' in user_b
    assert 'BASIS_SENTINEL' in user_b
    assert not any(token in system_a + user_a + system_b + user_b for token in
                   ('Control Echo', 'Root Horizon Reset', 'CRS', 'native evaluator'))


def test_both_conditions_start_fresh_and_have_independent_outputs(tmp_path):
    a_client = ScriptedClient([('finish_review', {'outcome': 'unresolved', 'conclusion': 'Public basis.'})])
    b_client = ScriptedClient([
        ('commit_review_basis', {'review_basis': 'BASIS_SENTINEL'}),
        ('finish_review', {'outcome': 'block', 'conclusion': 'Public basis.'}),
    ])
    a = replay.ReplaySession('simple_fresh', a_client, replay.FIXTURE, tmp_path / 'A')
    b = replay.ReplaySession('spec_first_fresh', b_client, replay.FIXTURE, tmp_path / 'B')
    assert a_client.export_history() == b_client.export_history() == []
    assert a.workspace_path != b.workspace_path
    ar, br = a.run(authorization()), b.run(authorization())
    assert (ar['outcome'], ar['model_turns']) == ('unresolved', 1)
    assert (br['outcome'], br['model_turns']) == ('block', 2)
    assert br['review_basis'] == {'text': 'BASIS_SENTINEL', 'model_authored': True,
                                  'revisable': True, 'oracle': False, 'evidence': False}
    assert ar['review_basis'] is None
    b_inputs = [row for row in audit_rows(b.audit_path) if row['event'] == 'model_input']
    assert len(b_inputs) == 2
    assert 'task/workspace/' not in json.dumps(b_inputs[0]['messages'])
    assert 'BASIS_SENTINEL' in json.dumps(b_inputs[1]['messages'])
    assert not any(x in json.dumps(b_inputs) for x in ('native evaluator', 'CRS_TRACE_INDEX'))
    assert replay.review_tools('review') == replay.review_tools('review')
    assert replay.source_tree(a.workspace_path)[0] == replay.source_tree(b.workspace_path)[0]
    assert any(row['event'] == 'exact_provider_request_pre_send' for row in audit_rows(a.audit_path))
    assert any(row['event'] == 'exact_provider_request_pre_send' for row in audit_rows(b.audit_path))


def test_disposable_workspace_mutation_does_not_cross_conditions(tmp_path):
    a = replay.ReplaySession('simple_fresh', ScriptedClient([]), replay.FIXTURE, tmp_path / 'A')
    b = replay.ReplaySession('spec_first_fresh', ScriptedClient([]), replay.FIXTURE, tmp_path / 'B')
    target = a.workspace_path / 'app.go'
    before = replay.sha(b.workspace_path / 'app.go')
    target.write_bytes(target.read_bytes() + b'\n// PROTOCOL_TEST_MUTATION\n')
    assert replay.sha(b.workspace_path / 'app.go') == before
    assert replay.sha(replay.FIXTURE / 'workspace/app.go') == before
    assert a._workspace_result()['implementation_mutation_protocol_violation'] is True
    assert b._workspace_result()['implementation_mutation_protocol_violation'] is False


def test_code_run_command_is_no_network_and_disposable(monkeypatch, tmp_path):
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, b'public\n', b'')

    monkeypatch.setattr(replay.subprocess, 'run', fake_run)
    result = replay.DockerCodeRunner(workspace, tmp_path)({'command': 'grep public app.go'})
    argv = calls[0][0]
    assert argv[argv.index('--network') + 1] == 'none'
    assert replay.CODE_IMAGE in argv
    assert str(workspace.resolve()) in ' '.join(argv)
    assert not any('verifier' in item or 'solution' in item for item in argv)
    assert result['stdout'] == 'public\n' and result['network_mode'] == 'none'


def test_sanitized_tool_image_go_smoke_without_model(tmp_path):
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    result = replay.DockerCodeRunner(workspace, tmp_path)({'command': 'go version',
                                                             'timeout_seconds': 30})
    assert result['status'] == 'completed' and result['exit_code'] == 0
    assert 'go version go1.22.12 linux/amd64' in result['stdout']
    assert result['network_mode'] == 'none'


def test_no_countdown_no_evaluator_and_authorization_absent(tmp_path):
    assert replay.MODEL_TURN_CEILING == 300
    assert '300' not in replay.SIMPLE_SYSTEM + replay.SPEC_ONLY_SYSTEM
    assert not (ROOT / 'AUTHORIZATION.json').exists()
    assert not (replay.FIXTURE / 'AUTHORIZATION.json').exists()
    config = json.loads((ROOT / 'PROTOCOL.json').read_text(encoding='utf-8'))
    assert config['posthoc_scoring_side_only'] and not config['online_evaluator_access']
    session = replay.ReplaySession('simple_fresh', ScriptedClient([]), replay.FIXTURE, tmp_path / 'A')
    with pytest.raises(RuntimeError, match='authorization'):
        session.run({})
    assert session.client.complete_calls == 0


def test_nonfresh_provider_history_rejected_before_output(tmp_path):
    client = ScriptedClient([])
    client.history.append({'role': 'assistant', 'content': 'old narrative'})
    with pytest.raises(RuntimeError, match='history'):
        replay.ReplaySession('simple_fresh', client, replay.FIXTURE, tmp_path / 'A')
    assert not (tmp_path / 'A').exists()
