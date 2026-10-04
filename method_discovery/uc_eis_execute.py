"""Serial one-shot execution of the authorized EIS four-slot block."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from method_discovery.uc_root_scope_execute import now, write, terminal_state
from method_discovery.uc_eis_entry import load_authorized_slot
from method_discovery.uc_eis_freeze import PLAN, MANIFEST, ROOT, REPO
from method_discovery.uc_r5_execution_bridge import file_sha


def main():
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    slots = plan['slots']
    if len(slots) != 4 or [row['run_id'] for row in slots] != plan['run_order']:
        raise RuntimeError('Frozen EIS four-slot order mismatch')
    first_auth = json.loads((ROOT / f"AUTH_{slots[0]['run_id']}.json").read_text(encoding='utf-8'))
    if file_sha(MANIFEST) != first_auth['runner_manifest_sha256']:
        raise RuntimeError('Frozen runner manifest changed')
    campaign = Path(slots[0]['output']['campaign_root'])
    records = campaign / 'host_execution'
    if records.exists():
        raise RuntimeError('Host execution directory already used')
    for slot in slots:
        run_id = slot['run_id']
        load_authorized_slot(run_id, ROOT / f'AUTH_{run_id}.json')
        if Path(slot['live_root']).exists() or any((campaign / name / run_id).exists()
            for name in ('jobs', 'runs', 'bridge')):
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
                [sys.executable, '-m', 'method_discovery.uc_eis_entry',
                 '--run-id', run_id, '--authorization',
                 str((ROOT / f'AUTH_{run_id}.json').resolve())],
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
    print('EIS BLOCK COMPLETE: four slots executed once', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
