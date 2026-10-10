"""No-model staging checks for the exact four-arm pilot entry."""

import json
import os
from pathlib import Path
import subprocess
import uuid

import pytest

from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.pilot_entry import (
    prepare_run, require_live_authorization,
)


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'FYNE_KITEX_FOUR_ARM_MANIFEST_DRAFT.json'


def test_unarmed_manifest_cannot_launch(tmp_path):
    authorization = tmp_path / 'AUTHORIZATION.json'
    authorization.write_text(json.dumps({'execution_authorized': False}), encoding='utf-8')
    with pytest.raises(RuntimeError, match='authorization'):
        require_live_authorization(MANIFEST, authorization, {
            'task_id': 'roadmapbench:fyn-2.2.0-roadmap', 'condition': 'T'})


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
