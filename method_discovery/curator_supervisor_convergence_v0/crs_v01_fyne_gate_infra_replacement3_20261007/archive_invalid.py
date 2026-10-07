"""Archive the finished invalid CRS trial; no model or verifier execution."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

from method_discovery import uc_path_control_archive as raw


RUN_ID = 'crs-v01-fyne-mechanism-gate-b-only-r1-infra-replacement-3'
CAMPAIGN = Path(r'E:\LongContext\long_context_bench\output\crs_v01_fyne_mechanism_gate')
ROOT = Path(__file__).resolve().parent
DESTINATION = ROOT / 'archive' / 'r1_invalid'
STAGING = Path(r'E:\runs\crs-r3-archive-staging')


def main() -> None:
    if DESTINATION.exists():
        raise RuntimeError('Archive exists; no overwrite')
    manifest = json.loads((CAMPAIGN / 'runs' / RUN_ID / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('run_id') != RUN_ID or manifest.get('valid') is not False:
        raise RuntimeError('Expected this exact invalid trial')
    trials = [p for p in (CAMPAIGN / 'jobs' / RUN_ID).iterdir() if p.is_dir()]
    if len(trials) != 1:
        raise RuntimeError('Expected one trial directory')
    trial = trials[0]
    raw.CAMPAIGN = CAMPAIGN
    raw.RECORDS = STAGING
    generated = STAGING / ('01_' + RUN_ID)
    if STAGING.exists():
        raise RuntimeError('Generated archive target exists')
    summary = raw.record_one({'run_id': RUN_ID, 'position': 1,
                              'condition': 'crs_v01_b_only', 'task': 'fyn-2.2.0-roadmap'})
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    generated.rename(DESTINATION)
    record_path = DESTINATION / 'RAW_FILE_MANIFEST.json'
    records = json.loads(record_path.read_text(encoding='utf-8'))

    def copy(source: Path, relative: str) -> None:
        if not source.is_file():
            records['copied'].append({'source': str(source), 'archive': relative,
                                      'status': 'absent', 'reason': 'source unavailable'})
            return
        target = DESTINATION / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if raw.digest(source) != raw.digest(target):
            raise RuntimeError('Archive copy hash mismatch: ' + relative)
        records['copied'].append({'source': str(source), 'archive': relative,
                                  'status': 'copied', 'bytes': target.stat().st_size,
                                  'sha256': raw.digest(target)})

    private = trial / 'agent/monitor/monitor_private'
    audit = private / 'audit'
    bridge = CAMPAIGN / 'bridge' / RUN_ID
    for source, relative in (
        (trial / 'exception.txt', 'trial/exception.txt'),
        (trial / 'agent/agent_process_return_code.txt', 'agent/agent_process_return_code.txt'),
        (trial / 'agent/isolated_transport.log', 'agent/isolated_transport.log'),
        (trial / 'agent/monitor/completion_incomplete.json', 'monitor/completion_incomplete.json'),
        (trial / 'agent/failure_workspace/report.json', 'agent/failure_workspace/report.json'),
        (CAMPAIGN / 'isolated_bundles' / RUN_ID / 'isolation_identity.json',
         'identity/isolation_identity.json'),
        (private / 'reference.md', 'monitor/private/reference.md'),
    ):
        copy(source, relative)
    for folder in ('cfs_deltas', 'history_transforms', 'continuation_responses'):
        for source in sorted((audit / folder).glob('*.json*')):
            copy(source, 'monitor/audit/' + folder + '/' + source.name)
    for source in sorted((bridge / 'evidence').glob('*')):
        if source.is_file() and source.suffix not in ('.tar', '.zip'):
            copy(source, 'bridge/evidence/' + source.name)
    for source in sorted((trial / 'artifacts').glob('*')):
        if source.is_file():
            copy(source, 'trial/artifacts/' + source.name)
    for source in sorted((trial / 'verifier').glob('*')):
        if source.is_file():
            copy(source, 'verifier/' + source.name)
    local_only = [trial / 'agent/failure_workspace/workspace.tar']
    local_only += sorted((bridge / 'evidence').glob('*.tar'))
    already_recorded = {item['path'] for item in records['local_only_large_artifacts']}
    for source in local_only:
        if source.is_file() and str(source) not in already_recorded:
            records['local_only_large_artifacts'].append({
                'path': str(source), 'bytes': source.stat().st_size,
                'sha256': raw.digest(source)})
    raw.write(record_path, records)
    summary.update({'status': 'monitor_review_incomplete',
                    'archive_path': str(DESTINATION),
                    'native_evaluator_executed': False,
                    'replacement_started': False,
                    'completion_incomplete_reason': 'review_failed'})
    raw.write(DESTINATION / 'MECHANICAL_SUMMARY.json', summary)
    raw.write(DESTINATION / 'TERMINATION.json', {
        'run_id': RUN_ID, 'valid': False,
        'exception_path': 'trial/exception.txt',
        'exception_sha256': raw.digest(DESTINATION / 'trial/exception.txt'),
        'completion_incomplete_path': 'monitor/completion_incomplete.json',
        'completion_incomplete_sha256': raw.digest(DESTINATION / 'monitor/completion_incomplete.json'),
        'actual_isolation_snapshot_sha256': manifest['source_identity']['isolation']['snapshot_sha256'],
        'native_evaluator_executed': False,
        'scientific_interpretation': None,
    })
    gateway = json.loads((CAMPAIGN / 'isolated_bundles' / RUN_ID /
                          'gateway/config.json').read_text(encoding='utf-8'))
    secrets = [value.encode() for route in gateway['models'].values()
               for value in route['headers'].values() if value]
    for path in DESTINATION.rglob('*'):
        if path.is_file() and any(secret in path.read_bytes() for secret in secrets):
            raise RuntimeError('Credential value in archive')
    print(json.dumps({'archive': str(DESTINATION),
                      'records': len(records['copied']),
                      'native_evaluator_executed': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
