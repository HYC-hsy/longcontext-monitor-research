"""Exercise the real unarmed preparation/bundle path with non-secret fake profiles."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from . import pilot_entry


HERE = Path(__file__).resolve().parent
SOURCE = Path('E:/LongContext/long_context_bench/.cache/m12_roadmap_tasks')
RUNTIME = Path('E:/LongContext/bench_runtime/m2/linux')
GA = Path(__file__).resolve().parents[3] / 'GenericAgent-main'
TASK_ID = 'roadmapbench:fyn-2.2.0-roadmap'


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_prepare_bundle_narrow_and_task_only(tmp_path, monkeypatch):
    if not SOURCE.exists() or not RUNTIME.exists():
        pytest.skip('Pinned local pilot assets unavailable')
    original = json.loads((HERE / 'FYNE_KITEX_FOUR_ARM_MANIFEST_DRAFT.json').read_text())
    original['supervisor_variant'] = 'narrow_v1'
    task_profile = tmp_path / 'mykey.py'
    task_profile.write_text(
        "native_claude_cc_vibe_opus48 = {'model': 'claude-opus-4-8', "
        "'apikey': 'offline-test-key', 'apibase': 'https://offline.invalid'}\n",
        encoding='utf-8')
    monitor_profile = tmp_path / 'monitor.json'
    monitor_profile.write_text(json.dumps({'claude_monitor_opus48': {
        'model': 'claude-opus-4-8', 'max_tokens': 8192, 'thinking_type': 'adaptive',
        'reasoning_effort': 'high', 'apikey': 'offline-test-key',
        'apibase': 'https://offline.invalid'}}), encoding='utf-8')
    original['private_profile_file_sha256_only'] = {
        'task': _sha(task_profile), 'supervisor': _sha(monitor_profile)}
    manifest = tmp_path / 'draft.json'
    manifest.write_text(json.dumps(original), encoding='utf-8')
    image_row = original['task_assets'][TASK_ID]
    monkeypatch.setattr(pilot_entry, '_image_identity', lambda image: {
        'image_id': image, 'repo_digests': image_row['repo_digests']})

    def no_docker(command, **_):
        assert command[:3] == ['docker', 'volume', 'create']
        return SimpleNamespace(returncode=0, stdout=command[3] + '\n')

    monkeypatch.setattr(pilot_entry.subprocess, 'run', no_docker)
    receipts = {}
    for condition in ('T', 'S'):
        root = tmp_path / condition
        receipts[condition] = pilot_entry.prepare_run(
            manifest=manifest, task_id=TASK_ID, condition=condition,
            run_id=f'offline-narrow-{condition.lower()}-001', run_root=root,
            source_root=SOURCE, ga_source=GA, runtime_root=RUNTIME,
            task_profile_file=task_profile, monitor_profile_file=monitor_profile,
            python_home='cpython-3.12.12-linux-x86_64-gnu',
            supervisor_variant='narrow_v1' if condition == 'S' else 'legacy')
    t = tmp_path / 'T/bundle/source'
    s = tmp_path / 'S/bundle/source'
    task_t = json.loads((t / 'mykey.json').read_text())
    task_s = json.loads((s / 'mykey.json').read_text())
    assert task_t == task_s
    assert not (t / 'monitor_agent_core/models.local.json').exists()
    assert (s / 'monitor_agent_core/narrow_supervisor_v1.py').is_file()
    monitor = json.loads((s / 'monitor_agent_core/models.local.json').read_text())[
        'claude_monitor_opus48']
    assert monitor['monitor_narrow_supervisor_v1'] is True
    assert monitor['monitor_history_projection'] == 'off'
    assert all(monitor[key] is False for key in (
        'monitor_contrastive_release_state', 'monitor_receding_horizon_release',
        'monitor_root_epistemic_reestimation'))
    assert receipts['T']['profile_public'] is None
    assert receipts['S']['profile_public']['monitor_narrow_supervisor_v1'] is True
    for name in ('instruction.md', 'task.toml'):
        assert _sha(tmp_path / 'T/public_agent_task' / name) == _sha(
            tmp_path / 'S/public_agent_task' / name)
    print('PREPARED_BUNDLE_EVIDENCE=' + json.dumps({condition: {
        'bundle_source_sha256': receipts[condition]['bundle_source_sha256'],
        'compose_sha256': receipts[condition]['compose_sha256'],
        'public_task_instruction_sha256': receipts[condition]['public_package']['included']['instruction.md'],
        'profile_public': receipts[condition]['profile_public'],
    } for condition in ('T', 'S')}, sort_keys=True))
