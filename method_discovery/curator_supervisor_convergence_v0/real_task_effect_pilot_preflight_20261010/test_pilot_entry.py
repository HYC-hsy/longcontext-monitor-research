"""No-model staging checks for the exact four-arm pilot entry."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import uuid

import pytest

from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.pilot_entry import (
    _ordinary_source_tree_sha256, main, prepare_run, require_live_authorization, sha_file,
)
from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.pilot_fake_gateway import _sse
from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.pilot_offline_harbor import _stage_native_tests
from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.pilot_harbor_hooks import PilotTrialHooks


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'FYNE_KITEX_FOUR_ARM_MANIFEST_DRAFT.json'


def test_unarmed_manifest_cannot_launch(tmp_path):
    authorization = tmp_path / 'AUTHORIZATION.json'
    authorization.write_text(json.dumps({'execution_authorized': False}), encoding='utf-8')
    with pytest.raises(RuntimeError, match='authorization'):
        require_live_authorization(MANIFEST, authorization, {
            'task_id': 'roadmapbench:fyn-2.2.0-roadmap', 'condition': 'T'})


def test_authorization_must_pin_audited_code_commit(tmp_path):
    frozen = json.loads(MANIFEST.read_text(encoding='utf-8'))
    authorization = tmp_path / 'AUTHORIZATION.json'
    authorization.write_text(json.dumps({
        'execution_authorized': True, 'manifest_sha256': sha_file(MANIFEST),
        'approved_arms': frozen['arms'],
        'audited_code_commit': '0' * 40,
    }), encoding='utf-8')
    with pytest.raises(RuntimeError, match='authorization'):
        require_live_authorization(MANIFEST, authorization, frozen['arms'][0])


def test_live_cli_rejects_missing_authorization_before_staging(tmp_path, monkeypatch):
    run_root = tmp_path / 'not-created'
    monkeypatch.setattr(sys, 'argv', ['pilot_entry', '--live',
        '--manifest', str(MANIFEST), '--task-id', 'roadmapbench:fyn-2.2.0-roadmap',
        '--condition', 'T', '--run-id', 'offline-auth-gate',
        '--run-root', str(run_root), '--source-root', str(tmp_path),
        '--ga-source', str(tmp_path), '--runtime-root', str(tmp_path),
        '--task-profile-file', str(tmp_path / 'absent'),
        '--monitor-profile-file', str(tmp_path / 'absent'),
        '--python-home', 'not-used'])
    with pytest.raises(RuntimeError, match='authorization'):
        main()
    assert not run_root.exists()


@pytest.mark.parametrize('task_id,short', [
    ('roadmapbench:fyn-2.2.0-roadmap', 'fyn-2.2.0-roadmap'),
    ('roadmapbench:ktx-0.13.0-roadmap', 'ktx-0.13.0-roadmap'),
])
def test_current_source_bytes_match_separate_draft_identity(task_id, short):
    source = Path(os.environ['PILOT_TASK_SOURCE_ROOT']) / short
    actual, count = _ordinary_source_tree_sha256(source)
    expected = json.loads(MANIFEST.read_text())['task_assets'][task_id]
    assert actual == expected['current_cache_non_git_tree_sha256']
    assert count > 0
    assert actual != expected['task_tree_sha256']  # historical identity uses another codec


def test_evaluator_gate_rejects_nonterminal_or_unstopped_product(tmp_path):
    control, archive, tests = (tmp_path / name for name in ('control', 'archive', 'tests'))
    for path in (control, archive, tests):
        path.mkdir()
    script = tests / 'test.sh'
    script.write_bytes(b'#!/bin/sh\nexit 0\n')
    digest = hashlib.sha256(script.read_bytes()).hexdigest()
    trial = SimpleNamespace(task=SimpleNamespace(paths=SimpleNamespace(tests_dir=tests)))
    hook = PilotTrialHooks(trial, {
        'run_id': 'offline-test', 'mode': 'offline_fake', 'fake_evaluator': True,
        'fake_evaluator_sha256': digest,
        'control_root': str(control), 'archive_root': str(archive),
    })
    hook.container_id = 'fixed-container'
    hook.product_sha256 = 'fixed-product'
    frozen = {'run_id': 'offline-test', 'container_id': hook.container_id,
              'tar_sha256': hook.product_sha256, 'writers_stopped': True,
              'sidecar_clean': True, 'legal_agent_end': False}
    freeze_path = archive / 'agent_end_frozen.json'
    freeze_path.write_text(json.dumps(frozen), encoding='utf-8')
    with pytest.raises(RuntimeError, match='frozen, stopped'):
        asyncio.run(hook.verification_start(None))
    assert not (archive / 'verification_released.json').exists()
    frozen['legal_agent_end'] = True
    frozen['sidecar_clean'] = False
    freeze_path.write_text(json.dumps(frozen), encoding='utf-8')
    with pytest.raises(RuntimeError, match='frozen, stopped'):
        asyncio.run(hook.verification_start(None))
    assert not (archive / 'verification_released.json').exists()


def test_fake_multiblock_sse_uses_native_monitor_parser():
    from monitor_agent_core.provider import MonitorProviderClient
    client = MonitorProviderClient.__new__(MonitorProviderClient)
    payload = _sse(1, 'wait', '', {'after_turns': 1})
    blocks, usage = client._parse_anthropic(payload.decode().splitlines())
    assert [block['type'] for block in blocks] == ['text', 'tool_use']
    assert blocks[1]['input'] == {'after_turns': 1}
    assert client.last_response_metadata['stream_complete'] is True
    assert usage['output_tokens'] == 1


@pytest.mark.parametrize('task_id', [
    'roadmapbench:fyn-2.2.0-roadmap',
    'roadmapbench:ktx-0.13.0-roadmap',
])
def test_native_verifier_source_is_pinned_but_not_staged_for_agent(tmp_path, task_id):
    tests = tmp_path / 'public_agent_task' / 'tests'
    tests.mkdir(parents=True)
    assert list(tests.iterdir()) == []
    tree, script = _stage_native_tests(MANIFEST, task_id,
        Path(os.environ['PILOT_TASK_SOURCE_ROOT']), tmp_path)
    expected = json.loads(MANIFEST.read_text())['task_assets'][task_id]
    assert tree == expected['native_tests_tree_sha256']
    assert script == expected['native_test_sh_sha256']
    assert (tests / 'test.sh').is_file()
    with pytest.raises(RuntimeError, match='not empty'):
        _stage_native_tests(MANIFEST, task_id,
            Path(os.environ['PILOT_TASK_SOURCE_ROOT']), tmp_path)


@pytest.mark.parametrize('task_id,condition', [
    ('roadmapbench:fyn-2.2.0-roadmap', 'T'),
    ('roadmapbench:ktx-0.13.0-roadmap', 'S'),
])
def test_staged_harbor_package_and_mount_contract_are_arm_specific(tmp_path, task_id, condition):
    run_id = 'offline-' + uuid.uuid4().hex[:18]
    volume = 'lc-pilot-' + run_id
    try:
        receipt = prepare_run(
            manifest=MANIFEST, task_id=task_id, condition=condition, run_id=run_id,
            run_root=tmp_path / 'run',
            source_root=Path(os.environ['PILOT_TASK_SOURCE_ROOT']),
            ga_source=Path(os.environ['PILOT_GA_SOURCE']),
            runtime_root=Path(os.environ['PILOT_RUNTIME_ROOT']),
            task_profile_file=Path(os.environ['PILOT_TASK_PROFILE_FILE']),
            monitor_profile_file=Path(os.environ['PILOT_MONITOR_PROFILE_FILE']),
            python_home=os.environ['PILOT_PYTHON_HOME'],
        )
        assert receipt['model_or_evaluator_calls'] == 0
        assert receipt['launch_authorized'] is False
        compose = json.loads((tmp_path / 'run/bundle/isolation.compose.json').read_text())
        mounts = compose['services']['main']['volumes']
        app = [item for item in mounts if isinstance(item, dict) and item.get('target') == '/app']
        assert len(app) == 1 and app[0]['source'] == volume and app[0]['read_only'] is False
        spool = [item for item in mounts if isinstance(item, dict) and
                 item.get('target', '').startswith('/logs/agent/monitor_bridge')]
        assert len(spool) == (3 if condition == 'S' else 0)
        if condition == 'S':
            assert sorted(item['read_only'] for item in spool) == [False, True, True]
            assert receipt['profile_public']['monitor_history_projection'] == 'root_records_v1'
            native_monitor = [item for item in mounts if isinstance(item, dict) and
                              item.get('target') == '/logs/agent/monitor']
            assert len(native_monitor) == 1 and native_monitor[0]['read_only'] is False
            assert list((tmp_path / 'run/monitor').iterdir()) == []
        else:
            assert receipt['profile_public'] is None
        assert not list((tmp_path / 'run/public_agent_task/tests').iterdir())
        assert not (tmp_path / 'run/public_agent_task/solution').exists()
        archive = (tmp_path / 'run/archive/offline_preparation.json').read_text()
        assert 'apikey' not in archive.lower() and 'apibase' not in archive.lower()
    finally:
        existing = subprocess.run(['docker', 'volume', 'inspect', volume],
                                  capture_output=True, timeout=30)
        if existing.returncode == 0:
            removed = subprocess.run(['docker', 'volume', 'rm', volume],
                                     capture_output=True, timeout=30)
            assert removed.returncode == 0, removed.stderr.decode(errors='replace')
