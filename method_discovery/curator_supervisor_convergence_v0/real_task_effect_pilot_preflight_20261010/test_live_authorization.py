"""No-network checks for the two live arm-identity gates."""

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010 import (
    pilot_entry, pilot_harbor_hooks, pilot_offline_harbor,
)


SOURCE = Path(pilot_entry.__file__).with_name('FYNE_KITEX_FOUR_ARM_MANIFEST_DRAFT.json')
HEAD = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=Path(pilot_entry.__file__).resolve().parents[3],
                      capture_output=True, text=True, check=True).stdout.strip()


def fixture(tmp_path, *, arms=None, approved=None, code=HEAD):
    tmp_path.mkdir(parents=True, exist_ok=True)
    frozen = copy.deepcopy(json.loads(SOURCE.read_text(encoding='utf-8')))
    if arms is not None:
        frozen['arms'] = arms
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps(frozen), encoding='utf-8')
    manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
    granted = {'execution_authorized': True, 'manifest_sha256': manifest_sha,
               'audited_code_commit': code,
               'approved_arms': copy.deepcopy(frozen['arms'] if approved is None else approved),
               'run_bindings': [dict(row, run_id=f'pilot-bound-{index}',
                                     run_root=str((tmp_path / f'run-{index}').resolve()))
                                for index, row in enumerate(frozen['arms'], start=1)]}
    authorization = tmp_path / 'AUTHORIZATION.json'
    authorization.write_text(json.dumps(granted), encoding='utf-8')
    spec = {'mode': 'authorized_live', 'execution_authorized': True,
            'manifest_path': str(manifest), 'manifest_sha256': manifest_sha,
            'authorization_path': str(authorization),
            'authorization_sha256': hashlib.sha256(authorization.read_bytes()).hexdigest(),
            'audited_code_commit': code,
            'task_id': frozen['arms'][0]['task_id'],
            'condition': frozen['arms'][0]['condition'],
            'run_id': 'pilot-bound-1',
            'control_root': str((tmp_path / 'run-1' / 'control').resolve())}
    return manifest, authorization, spec, frozen


def check_both(manifest, authorization, spec):
    pilot_entry.require_live_authorization(manifest, authorization, spec,
        spec['run_id'], Path(spec['control_root']).parent)
    pilot_harbor_hooks._check_authorized_live_spec(spec)


def test_four_exact_arms_pass_entry_and_harbor_child_check(tmp_path):
    manifest, authorization, spec, frozen = fixture(tmp_path)
    assert [row['order'] for row in frozen['arms']] == [1, 2, 3, 4]
    for row in frozen['arms']:
        spec['task_id'], spec['condition'] = row['task_id'], row['condition']
        spec['run_id'] = f"pilot-bound-{row['order']}"
        spec['control_root'] = str((tmp_path / f"run-{row['order']}" / 'control').resolve())
        check_both(manifest, authorization, spec)


@pytest.mark.parametrize('bad_arm', [
    {'task_id': 'unknown', 'condition': 'T'},
    {'task_id': 'roadmapbench:fyn-2.2.0-roadmap', 'condition': 'unknown'},
])
def test_wrong_identity_rejected_by_both(tmp_path, bad_arm):
    manifest, authorization, spec, _ = fixture(tmp_path)
    spec.update(bad_arm)
    with pytest.raises(RuntimeError):
        check_both(manifest, authorization, spec)
    with pytest.raises(RuntimeError):
        pilot_harbor_hooks._check_authorized_live_spec(spec)


def test_duplicate_identity_rejected_even_when_full_lists_match(tmp_path):
    arms = copy.deepcopy(json.loads(SOURCE.read_text(encoding='utf-8'))['arms'])
    arms[1]['task_id'], arms[1]['condition'] = arms[0]['task_id'], arms[0]['condition']
    manifest, authorization, spec, _ = fixture(tmp_path, arms=arms)
    with pytest.raises(RuntimeError):
        check_both(manifest, authorization, spec)
    with pytest.raises(RuntimeError):
        pilot_harbor_hooks._check_authorized_live_spec(spec)


def test_reorder_rejected_despite_same_members(tmp_path):
    arms = json.loads(SOURCE.read_text(encoding='utf-8'))['arms']
    approved = copy.deepcopy(arms)
    approved[0], approved[1] = approved[1], approved[0]
    manifest, authorization, spec, _ = fixture(tmp_path, approved=approved)
    with pytest.raises(RuntimeError):
        check_both(manifest, authorization, spec)
    with pytest.raises(RuntimeError):
        pilot_harbor_hooks._check_authorized_live_spec(spec)


def test_changed_manifest_or_code_or_missing_authorization_rejected(tmp_path):
    manifest, authorization, spec, _ = fixture(tmp_path)
    manifest.write_text(manifest.read_text(encoding='utf-8') + '\n', encoding='utf-8')
    with pytest.raises(RuntimeError):
        check_both(manifest, authorization, spec)
    with pytest.raises(RuntimeError):
        pilot_harbor_hooks._check_authorized_live_spec(spec)
    manifest, authorization, spec, _ = fixture(tmp_path / 'code', code='0' * 40)
    with pytest.raises(RuntimeError):
        check_both(manifest, authorization, spec)
    with pytest.raises(RuntimeError):
        pilot_harbor_hooks._check_authorized_live_spec(spec)
    manifest, authorization, spec, _ = fixture(tmp_path / 'missing')
    authorization.unlink()
    with pytest.raises(Exception):
        pilot_entry.require_live_authorization(manifest, authorization, spec,
            spec['run_id'], Path(spec['control_root']).parent)
    with pytest.raises(RuntimeError):
        pilot_harbor_hooks._check_authorized_live_spec(spec)


def test_live_cli_selects_authorized_gateway_and_native_verification(tmp_path, monkeypatch):
    manifest, authorization, _, frozen = fixture(tmp_path)
    calls = []

    def no_network(**kwargs):
        calls.append(kwargs)
        return {'authorization_checked_without_network': True}

    monkeypatch.setattr(pilot_offline_harbor, 'run_offline', no_network)
    monkeypatch.setattr(sys, 'argv', ['pilot_entry', '--live',
        '--authorization', str(authorization), '--harbor-python', str(tmp_path / 'harbor'),
        '--manifest', str(manifest), '--task-id', frozen['arms'][0]['task_id'],
        '--condition', frozen['arms'][0]['condition'], '--run-id', 'pilot-bound-1',
        '--run-root', str(tmp_path / 'run-1'), '--source-root', str(tmp_path),
        '--ga-source', str(tmp_path), '--runtime-root', str(tmp_path),
        '--task-profile-file', str(tmp_path / 'profile'),
        '--monitor-profile-file', str(tmp_path / 'monitor-profile'),
        '--python-home', 'pinned-runtime'])
    pilot_entry.main()
    assert len(calls) == 1
    assert calls[0]['execution_mode'] == 'authorized_live'
    assert calls[0]['timeout_seconds'] == 10000
    assert calls[0]['authorization'] == authorization
    assert not (tmp_path / 'run-1').exists()


def test_authorized_launcher_selects_real_gateway_and_native_verifier_argv(tmp_path, monkeypatch):
    manifest, authorization, _, frozen = fixture(tmp_path)
    run_root = tmp_path / 'run-1'
    calls = []

    def staged(**kwargs):
        root = kwargs['run_root']
        for name in ('control', 'archive', 'bundle/source'):
            (root / name).mkdir(parents=True, exist_ok=True)
        (root / 'bundle/isolation.compose.json').write_text('{}', encoding='utf-8')
        (root / 'control/harbor_spec.json').write_text(json.dumps({
            'mode': 'unarmed', 'execution_authorized': False}), encoding='utf-8')
        return {'bundle_source_sha256': 'fixture-source', 'task_volume': 'fixture-volume'}

    def fake_subprocess(argv, **kwargs):
        if argv[:3] == ['git', 'rev-parse', 'HEAD']:
            return SimpleNamespace(returncode=0, stdout=HEAD + '\n')
        calls.append(argv)
        return SimpleNamespace(returncode=0)

    from types import SimpleNamespace
    monkeypatch.setattr(pilot_offline_harbor, 'prepare_run', staged)
    monkeypatch.setattr(pilot_offline_harbor, '_stage_native_tests',
                        lambda *_: ('pinned-native-tree', 'pinned-test-script'))
    monkeypatch.setattr(pilot_offline_harbor, '_offline_gateway',
                        lambda *_: pytest.fail('live branch invoked fake gateway'))
    monkeypatch.setattr(pilot_offline_harbor, '_cleanup_offline_containers', lambda *_: [])
    monkeypatch.setattr(subprocess, 'run', fake_subprocess)
    result = pilot_offline_harbor.run_offline(
        manifest=manifest, task_id=frozen['arms'][0]['task_id'], condition='T',
        run_id='pilot-bound-1', run_root=run_root, source_root=tmp_path,
        ga_source=tmp_path, runtime_root=tmp_path,
        task_profile_file=tmp_path, monitor_profile_file=tmp_path,
        python_home='pinned-runtime', harbor_python=Path(sys.executable),
        timeout_seconds=10000, execution_mode='authorized_live',
        authorization=authorization)
    assert result['returncode'] == 0 and len(calls) == 1
    assert '--enable-verification' in calls[0]
    assert '--disable-verification' not in calls[0]
    assert '--agent-timeout-multiplier' in calls[0]
    spec = json.loads((run_root / 'control/harbor_spec.json').read_text(encoding='utf-8'))
    assert spec['mode'] == 'authorized_live'
    assert spec['native_tests_tree_sha256'] == 'pinned-native-tree'
    assert spec['native_test_sh_sha256'] == 'pinned-test-script'
    assert not (run_root / 'archive/fake_provider_requests').exists()
