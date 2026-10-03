"""Serial host-only execution of the frozen four root-scope slots."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

from method_discovery.uc_root_scope_entry import (
    MANIFEST, PLAN, PLAN_ROOT, REPO, load_authorized_slot,
)
from method_discovery.uc_r5_execution_bridge import file_sha


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def terminal_state(campaign, run_id, exit_code):
    evidence = campaign / 'bridge' / run_id / 'evidence'
    required = ('agent_start_identity', 'pre_verification_capture',
                'verification_release', 'trial_end_binding', 'inference_send_accounting')
    receipts = {name: (evidence / f'{name}.json').is_file() for name in required}
    manifest = campaign / 'runs' / run_id / 'manifest.json'
    timeout = False
    result = None
    if manifest.is_file():
        row = json.loads(manifest.read_text(encoding='utf-8'))
        result_path = Path(row.get('trial_result') or '')
        if result_path.is_file():
            result = json.loads(result_path.read_text(encoding='utf-8'))
            exception = result.get('exception_info') or {}
            errors = row.get('validation_errors') or []
            timeout = (exception.get('exception_type') == 'AgentTimeoutError'
                       and not any(any(term in str(error).lower() for term in (
                           'model identity', 'source mismatch', 'checker', 'isolation'))
                           for error in errors))
    status = ('completed' if exit_code == 0 and all(receipts.values()) else
              'completed_budget' if timeout and all(receipts.values()) else
              'paused_for_infrastructure_review')
    return status, receipts, timeout, result


def main():
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    slots = plan['slots']
    if len(slots) != 4 or [row['run_id'] for row in slots] != plan['run_order']:
        raise RuntimeError('Frozen four-slot order mismatch')
    if file_sha(MANIFEST) != json.loads((PLAN_ROOT / f"AUTH_{slots[0]['run_id']}.json"
                                       ).read_text(encoding='utf-8'))['runner_manifest_sha256']:
        raise RuntimeError('Frozen runner manifest changed')
    campaign = Path(slots[0]['output']['campaign_root'])
    records = campaign / 'host_execution'
    if records.exists():
        raise RuntimeError('Host execution directory already used')
    for slot in slots:
        run_id = slot['run_id']
        load_authorized_slot(run_id, PLAN_ROOT / f'AUTH_{run_id}.json')
        if Path(slot['live_root']).exists() or any(
                (campaign / name / run_id).exists() for name in ('jobs', 'runs', 'bridge')):
            raise RuntimeError(f'Slot identity already used: {run_id}')
    records.mkdir(parents=True, exist_ok=False)
    progress = []
    for slot in slots:
        run_id = slot['run_id']
        item = {'run_id': run_id, 'condition_host_only': slot['condition'],
                'started_at': now(), 'status': 'running'}
        progress.append(item)
        write(records / 'progress.json', progress)
        log_path = records / f'{run_id}.entry.log'
        print(f"START {run_id} {item['started_at']}", flush=True)
        with log_path.open('wb') as log:
            completed = subprocess.run(
                [sys.executable, '-m', 'method_discovery.uc_root_scope_entry',
                 '--run-id', run_id, '--authorization',
                 str((PLAN_ROOT / f'AUTH_{run_id}.json').resolve())],
                cwd=REPO, stdout=log, stderr=subprocess.STDOUT)
        item['ended_at'] = now()
        item['entry_exit_code'] = completed.returncode
        item['entry_log'] = str(log_path)
        status, receipts, timeout, result = terminal_state(campaign, run_id, completed.returncode)
        item['status'] = status
        item['receipts_present'] = receipts
        item['explicit_agent_timeout'] = timeout
        item['runner_valid'] = result.get('valid') if isinstance(result, dict) else None
        write(records / 'progress.json', progress)
        print(f"END {run_id} status={status} exit={completed.returncode}", flush=True)
        if status not in {'completed', 'completed_budget'}:
            print('BATCH STOP: preserve this slot; no skip or rerun', flush=True)
            return 2
    print('ROOT-SCOPE BLOCK COMPLETE: four slots executed once', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
