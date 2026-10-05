"""One-shot host launcher for the authorized diagnostic baseline."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from method_discovery.uc_root_scope_execute import now, write, terminal_state
from method_discovery.uc_cqs_kitex_baseline_entry import load_authorized_slot
from method_discovery.uc_cqs_kitex_baseline_prepare import REPO, ROOT
from method_discovery.uc_r5_execution_bridge import file_sha


def main() -> int:
    plan = json.loads((ROOT / 'PLAN.json').read_text(encoding='utf-8'))
    if len(plan['slots']) != 1 or plan['run_order'] != [plan['slots'][0]['run_id']]:
        raise RuntimeError('Exactly one frozen Kitex baseline is required')
    slot = plan['slots'][0]
    run_id = slot['run_id']
    auth_path = ROOT / f'AUTH_{run_id}.json'
    _, auth = load_authorized_slot(run_id, auth_path)
    if file_sha(Path(auth['runner_manifest'])) != auth['runner_manifest_sha256']:
        raise RuntimeError('Runner manifest differs from independent authorization')
    campaign = Path(slot['output']['campaign_root'])
    records = campaign / 'host_execution'
    if records.exists() or Path(slot['live_root']).exists() or any(
            (campaign / name / run_id).exists() for name in ('jobs', 'runs', 'bridge')):
        raise RuntimeError('Baseline slot identity or host log already used')
    records.mkdir(parents=True, exist_ok=False)
    item = {'run_id': run_id, 'condition_host_only': slot['condition'],
            'started_at': now(), 'status': 'running'}
    write(records / 'progress.json', [item])
    log_path = records / f'{run_id}.entry.log'
    print(f'START {run_id} {item["started_at"]}', flush=True)
    with log_path.open('wb') as log:
        completed = subprocess.run(
            [sys.executable, '-m', 'method_discovery.uc_cqs_kitex_baseline_entry',
             '--run-id', run_id, '--authorization', str(auth_path.resolve())],
            cwd=REPO, stdout=log, stderr=subprocess.STDOUT)
    item['ended_at'] = now()
    item['entry_exit_code'] = completed.returncode
    item['entry_log'] = str(log_path)
    status, receipts, timeout, result = terminal_state(campaign, run_id, completed.returncode)
    item['status'] = status
    item['receipts_present'] = receipts
    item['explicit_agent_timeout'] = timeout
    item['runner_valid'] = result.get('valid') if isinstance(result, dict) else None
    write(records / 'progress.json', [item])
    print(f'END {run_id} status={status} exit={completed.returncode}', flush=True)
    return 0 if status in {'completed', 'completed_budget'} else 2


if __name__ == '__main__':
    raise SystemExit(main())
