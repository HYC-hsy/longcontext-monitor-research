"""Archive the actually executed ASE discovery prefix, including infrastructure failures."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

from method_discovery import uc_path_control_archive as raw
from method_discovery.uc_ase_freeze import ROOT, PLAN, CAMPAIGN


RECORDS = ROOT / 'records'


def main():
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    host = json.loads((CAMPAIGN / 'host_execution/progress.json').read_text(encoding='utf-8'))
    if not host or [row['run_id'] for row in host] != plan['run_order'][:len(host)]:
        raise RuntimeError('Actual host prefix does not match the frozen order')
    if any(row['status'] == 'running' for row in host):
        raise RuntimeError('Cannot archive a running slot')
    if RECORDS.exists():
        raise RuntimeError('Archive records already exist; no overwrite')
    raw.PLAN = PLAN
    raw.PLAN_ROOT = ROOT
    raw.CAMPAIGN = CAMPAIGN
    raw.RECORDS = RECORDS
    summaries = []
    for host_row in host:
        slot = next(row for row in plan['slots'] if row['run_id'] == host_row['run_id'])
        summary = raw.record_one(slot)
        destination = RECORDS / f"{slot['position']:02d}_{slot['run_id']}"
        trial = Path(summary['trial_dir'])
        extra = []

        def copy(source, relative):
            if not source.is_file():
                extra.append({'source': str(source), 'archive': relative, 'status': 'missing'})
                return
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            extra.append({'source': str(source), 'archive': relative, 'status': 'copied',
                          'bytes': target.stat().st_size, 'sha256': raw.digest(target)})

        for name in ('exception.txt', 'config.json', 'lock.json'):
            copy(trial / name, 'trial/' + name)
        for name in ('completion_incomplete.json',):
            copy(trial / 'agent/monitor' / name, 'monitor/' + name)
        for name in ('agent_process_return_code.txt', 'isolated_transport.log'):
            copy(trial / 'agent' / name, 'agent/' + name)
        for name in ('result.json', 'job.log', 'launcher_stdout.log', 'launcher_stderr.log'):
            copy(CAMPAIGN / 'jobs' / slot['run_id'] / name, 'job/' + name)
        copy(CAMPAIGN / 'host_execution' / f"{slot['run_id']}.entry.log", 'host/entry.log')
        for name in ('report.json',):
            copy(trial / 'agent/failure_workspace' / name, 'agent/failure_workspace/' + name)
        for source in sorted((trial / 'agent/monitor/monitor_private/audit').rglob('*')):
            if source.is_file() and source.suffix != '.tar':
                copy(source, 'monitor/audit/' + str(source.relative_to(
                    trial / 'agent/monitor/monitor_private/audit')).replace('\\', '/'))
        local_only = []
        for source in (trial / 'agent/failure_workspace/workspace.tar',):
            if source.is_file():
                local_only.append({'path': str(source), 'bytes': source.stat().st_size,
                                   'sha256': raw.digest(source)})
        manifest = json.loads((destination / 'RAW_FILE_MANIFEST.json').read_text(encoding='utf-8'))
        manifest['copied'].extend(extra)
        manifest['local_only_large_artifacts'].extend(local_only)
        raw.write(destination / 'RAW_FILE_MANIFEST.json', manifest)
        summary.update(host_status=host_row['status'], entry_exit_code=host_row['entry_exit_code'],
                       stop_reason='infrastructure_review' if host_row['status'] not in
                       {'completed', 'completed_budget'} else None,
                       ase_reference_present=(trial / 'agent/monitor/monitor_private/reference.md').is_file(),
                       ase_initialization_pending_count=0,
                       ase_initialization_ready_count=0)
        raw.write(destination / 'MECHANICAL_SUMMARY.json', summary)
        summaries.append(summary)
    copy_host = RECORDS / 'host_execution'
    copy_host.mkdir(parents=True, exist_ok=False)
    shutil.copy2(CAMPAIGN / 'host_execution/progress.json', copy_host / 'progress.json')
    raw.write(ROOT / 'DISCOVERY_MECHANICAL_SUMMARY.json', {
        'executed_run_ids': [row['run_id'] for row in host],
        'not_started_run_ids': plan['run_order'][len(host):],
        'records': summaries,
        'scientific_interpretation': None,
    })
    print(json.dumps({'executed': [row['run_id'] for row in host],
                      'not_started': plan['run_order'][len(host):]}, indent=2))


if __name__ == '__main__':
    main()
