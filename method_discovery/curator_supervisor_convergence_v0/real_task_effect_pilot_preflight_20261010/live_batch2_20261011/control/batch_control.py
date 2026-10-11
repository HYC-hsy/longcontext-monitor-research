"""One-shot Fyne/Kitex pilot controller; never alters an arm after launch."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(r'E:\pilot_live_batch2_20261011_8cfc4ef2')
REPO = Path(r'E:\longcontext-cqs-v0-20261005')
BASE = REPO / 'method_discovery/curator_supervisor_convergence_v0/real_task_effect_pilot_preflight_20261010/FYNE_KITEX_FOUR_ARM_MANIFEST_DRAFT.json'
CODE = '8cfc4ef2aac99c2378d98a0489fc0cad45511573'
MANIFEST = ROOT / 'FYNE_KITEX_FOUR_ARM_MANIFEST_BATCH2.json'
AUTH = ROOT / 'AUTHORIZATION.json'
BINDINGS = [
    ('pilot2-fyne-t-20261011-r1', r'E:\pilot_live2_fyne_t_20261011_8cfc4ef2'),
    ('pilot2-fyne-s-20261011-r1', r'E:\pilot_live2_fyne_s_20261011_8cfc4ef2'),
    ('pilot2-kitex-s-20261011-r1', r'E:\pilot_live2_kitex_s_20261011_8cfc4ef2'),
    ('pilot2-kitex-t-20261011-r1', r'E:\pilot_live2_kitex_t_20261011_8cfc4ef2'),
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    with path.open('xb') as stream:
        stream.write(data)


def head():
    result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                            capture_output=True, text=True, check=True)
    return result.stdout.strip()


def prepare():
    if head() != CODE or MANIFEST.exists() or AUTH.exists():
        raise RuntimeError('Code identity or fresh authorization path mismatch')
    if any(Path(path).exists() for _, path in BINDINGS):
        raise RuntimeError('At least one frozen run root already exists')
    source = json.loads(BASE.read_text(encoding='utf-8'))
    frozen = copy.deepcopy(source)
    frozen['batch_identity'] = {
        'schema': 'fyne-kitex-live-batch2-v1',
        'reviewed_baseline_commit': '2b3e2f85d8962cf3805460a202fcc6b57c932d06',
        'subtraction_repair_commit': 'f205f4b903600a1c8df7017d56039ddd6a5bcf87',
        'run_code_commit': CODE,
        'source_manifest_file_sha256': sha(BASE),
        'runtime_scratch_content_statistics': 'disabled',
        'supervisor_incomplete_stream_recovery_v1': True,
    }
    frozen['run_policy']['supervisor_incomplete_stream_recovery_v1'] = {
        'enabled': True, 'total_attempts_including_first': 3,
        'backoff_seconds': [2, 5], 'shared_deadline': True,
        'scope': 'incomplete_uncommitted_stream_only',
    }
    frozen['run_policy']['runtime_scratch_content_statistics'] = 'disabled'
    frozen['execution_authorized'] = False
    if frozen['arms'] != source['arms'] or frozen['task_assets'] != source['task_assets']:
        raise RuntimeError('Frozen task identities changed')
    write_new(MANIFEST, frozen)
    bindings = [dict(arm, run_id=run_id, run_root=run_root)
                for arm, (run_id, run_root) in zip(frozen['arms'], BINDINGS)]
    authorization = {
        'execution_authorized': True,
        'authorization_source': 'User-transmitted second Fyne/Kitex four-arm execution instruction',
        'reviewed_baseline_commit': frozen['batch_identity']['reviewed_baseline_commit'],
        'limited_wiring_diff': 'pilot_profile.py incomplete_stream_recovery_v1 opt-in and public identity',
        'manifest_sha256': sha(MANIFEST),
        'audited_code_commit': CODE,
        'approved_arms': frozen['arms'],
        'run_bindings': bindings,
    }
    write_new(AUTH, authorization)
    write_new(ROOT / 'PRELAUNCH_IDENTITY.json', {
        'manifest_sha256': sha(MANIFEST), 'authorization_sha256': sha(AUTH),
        'control_script_sha256': sha(__file__), 'source_manifest_sha256': sha(BASE),
        'run_code_commit': CODE, 'bindings': bindings,
    })
    print(json.dumps({'prepared': True, 'manifest_sha256': sha(MANIFEST),
                      'authorization_sha256': sha(AUTH), 'code': CODE}, indent=2), flush=True)


def arm_command(binding):
    return [sys.executable, '-m',
            'method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.pilot_entry',
            '--live', '--authorization', str(AUTH),
            '--harbor-python', r'E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe',
            '--manifest', str(MANIFEST), '--task-id', binding['task_id'],
            '--condition', binding['condition'], '--run-id', binding['run_id'],
            '--run-root', binding['run_root'],
            '--source-root', r'E:\LongContext\long_context_bench\.cache\m12_roadmap_tasks',
            '--ga-source', str(REPO / 'GenericAgent-main'),
            '--runtime-root', r'E:\LongContext\bench_runtime\m2\linux',
            '--task-profile-file', r'E:\LongContext\GenericAgent-main\mykey.py',
            '--monitor-profile-file', r'E:\LongContext\monitor_config\models.local.json',
            '--python-home', 'cpython-3.12.12-linux-x86_64-gnu']


def check_finished(binding, returncode):
    root = Path(binding['run_root'])
    result_path = root / 'archive/pilot_result.json'
    frozen_path = root / 'archive/agent_end_frozen.json'
    sidecar_path = root / 'control/sidecar_stopped.json'
    if not (result_path.is_file() and frozen_path.is_file() and sidecar_path.is_file()):
        return {'continue': False, 'reason': 'terminal_or_cleanup_evidence_missing',
                'entry_returncode': returncode}
    result = json.loads(result_path.read_text(encoding='utf-8'))
    frozen = json.loads(frozen_path.read_text(encoding='utf-8'))
    sidecar = json.loads(sidecar_path.read_text(encoding='utf-8'))
    clean = (not result.get('timed_out') and not result.get('spool_errors') and
             frozen.get('run_id') == binding['run_id'] and
             frozen.get('writers_stopped') is True and
             frozen.get('sidecar_clean') is True and
             sidecar == {'run_id': binding['run_id'], 'clean': True})
    return {'continue': clean, 'reason': 'verified_clean' if clean else 'cleanup_or_identity_uncertain',
            'entry_returncode': returncode, 'harbor_returncode': result.get('returncode'),
            'legal_agent_end': frozen.get('legal_agent_end'),
            'native_verifier_released': result.get('harbor_verifier_released')}


def run():
    pre = json.loads((ROOT / 'PRELAUNCH_IDENTITY.json').read_text(encoding='utf-8'))
    granted = json.loads(AUTH.read_text(encoding='utf-8'))
    frozen = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if (head() != CODE or pre['control_script_sha256'] != sha(__file__) or
            pre['manifest_sha256'] != sha(MANIFEST) or
            pre['authorization_sha256'] != sha(AUTH) or
            granted['manifest_sha256'] != sha(MANIFEST) or
            granted['approved_arms'] != frozen['arms'] or
            any(Path(row['run_root']).exists() for row in granted['run_bindings'])):
        raise RuntimeError('Frozen prelaunch identity or fresh output root failed')
    status = {'code_commit': CODE, 'manifest_sha256': sha(MANIFEST),
              'authorization_sha256': sha(AUTH), 'started_at_epoch': time.time(),
              'slots': [dict(row, status='not_started') for row in granted['run_bindings']]}
    write_new(ROOT / 'BATCH_STATUS_INITIAL.json', status)
    for slot in status['slots']:
        if head() != CODE:
            slot.update(status='not_started_code_drift')
            break
        slot.update(status='running', started_at_epoch=time.time())
        (ROOT / 'BATCH_STATUS.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
        command = arm_command(slot)
        with (ROOT / f"{slot['order']:02d}_entry_stdout.log").open('xb') as out, \
             (ROOT / f"{slot['order']:02d}_entry_stderr.log").open('xb') as err:
            completed = subprocess.run(command, cwd=REPO, stdout=out, stderr=err)
        slot.update(status='finished', ended_at_epoch=time.time(),
                    **check_finished(slot, completed.returncode))
        (ROOT / 'BATCH_STATUS.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
        print(f"slot {slot['order']} {slot['task_id']} {slot['condition']}: "
              f"{slot['reason']}; continue={slot['continue']}", flush=True)
        if not slot['continue']:
            break
    status['ended_at_epoch'] = time.time()
    (ROOT / 'BATCH_STATUS.json').write_text(json.dumps(status, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'run'])
    args = parser.parse_args()
    prepare() if args.action == 'prepare' else run()
