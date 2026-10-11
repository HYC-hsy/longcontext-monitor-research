"""Exercise the unarmed pilot preparation and its copied runtime identity."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010 import pilot_entry


HERE = Path(__file__).resolve().parent
PILOT = HERE.parent / 'real_task_effect_pilot_preflight_20261010'
ASSETS = Path('E:/LongContext/long_context_bench/.cache/m12_roadmap_tasks')
RUNTIME = Path('E:/LongContext/bench_runtime/m2/linux')
GA = HERE.parents[2] / 'GenericAgent-main'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize('task_id', [
    'roadmapbench:fyn-2.2.0-roadmap', 'roadmapbench:ktx-0.13.0-roadmap'])
def test_real_unarmed_bundle_contains_candidate_and_readable_profile(tmp_path, monkeypatch,
                                                                       task_id):
    if not ASSETS.exists() or not RUNTIME.exists():
        pytest.skip('Pinned Fyne/Kitex local assets unavailable')
    manifest = json.loads((PILOT / 'FYNE_KITEX_FOUR_ARM_MANIFEST_DRAFT.json').read_text(
        encoding='utf-8'))
    manifest['supervisor_variant'] = 'evidence_package_v1'
    task_profile = tmp_path / 'mykey.py'
    task_profile.write_text("native_claude_cc_vibe_opus48 = {'model': 'claude-opus-4-8', "
                            "'apikey': 'offline', 'apibase': 'https://offline.invalid'}\n",
                            encoding='utf-8')
    supervisor_profile = tmp_path / 'monitor.json'
    supervisor_profile.write_text(json.dumps({'claude_monitor_opus48': {
        'model': 'claude-opus-4-8', 'max_tokens': 8192,
        'thinking_type': 'adaptive', 'reasoning_effort': 'high',
        'apikey': 'offline', 'apibase': 'https://offline.invalid'}}), encoding='utf-8')
    manifest['private_profile_file_sha256_only'] = {
        'task': sha(task_profile), 'supervisor': sha(supervisor_profile)}
    draft = tmp_path / 'manifest.json'
    draft.write_text(json.dumps(manifest), encoding='utf-8')
    row = manifest['task_assets'][task_id]
    monkeypatch.setattr(pilot_entry, '_image_identity', lambda image: {
        'image_id': image, 'repo_digests': row['repo_digests']})

    def volume(command, **_):
        assert command[:3] == ['docker', 'volume', 'create']
        return SimpleNamespace(returncode=0, stdout=command[3] + '\n')

    monkeypatch.setattr(pilot_entry.subprocess, 'run', volume)
    receipt = pilot_entry.prepare_run(
        manifest=draft, task_id=task_id, condition='S',
        run_id='offline-evidence-' + ('fyne' if ':fyn-' in task_id else 'kitex'),
        run_root=tmp_path / 'run', source_root=ASSETS, ga_source=GA,
        runtime_root=RUNTIME, task_profile_file=task_profile,
        monitor_profile_file=supervisor_profile,
        python_home='cpython-3.12.12-linux-x86_64-gnu',
        supervisor_variant='evidence_package_v1')
    bundle = tmp_path / 'run' / 'bundle' / 'source' / 'monitor_agent_core'
    assert (bundle / 'evidence_package_v1.py').is_file()
    profile = json.loads((bundle / 'models.local.json').read_text(
        encoding='utf-8'))['claude_monitor_opus48']
    assert profile['monitor_evidence_package_v1'] is True
    assert profile['monitor_narrow_supervisor_v1'] is True
    assert profile['monitor_history_projection'] == 'off'
    assert receipt['profile_public']['monitor_evidence_package_v1'] is True
    from monitor_agent_core.provider import MonitorProviderClient
    from monitor_agent_core.agent import MonitorAgent
    from monitor_agent_core.workspace import MonitorWorkspace
    evidence = tmp_path / 'test-evidence'
    evidence.mkdir()
    (evidence / 'original_task.txt').write_text('Offline public task.', encoding='utf-8')
    client = MonitorProviderClient('claude_monitor_opus48', profile)
    agent = MonitorAgent(client, MonitorWorkspace(evidence, tmp_path / 'test-private'))
    assert client.config['monitor_evidence_package_v1'] is True
    assert agent.evidence_package_v1 and agent.narrow_supervisor_v1

