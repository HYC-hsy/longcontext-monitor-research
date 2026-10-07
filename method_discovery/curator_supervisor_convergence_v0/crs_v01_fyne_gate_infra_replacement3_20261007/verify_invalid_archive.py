"""Verify byte integrity and private-data boundary for the invalid CRS run."""

from __future__ import annotations

import json
from pathlib import Path
import runpy

from method_discovery import uc_path_control_archive as raw
from method_discovery.curator_supervisor_convergence_v0.crs_v01_fyne_gate_infra_replacement3_20261007 import archive_invalid


def check() -> dict:
    root = archive_invalid.DESTINATION
    manifest = json.loads((root / 'RAW_FILE_MANIFEST.json').read_text(encoding='utf-8'))
    verified, absent = 0, []
    for record in manifest['copied']:
        path = root / record['archive']
        if record.get('status') != 'copied':
            absent.append(record['archive'])
            continue
        if not path.is_file() or path.stat().st_size != record['bytes']:
            raise RuntimeError('Archive size mismatch: ' + record['archive'])
        if raw.digest(path) != record['sha256']:
            raise RuntimeError('Archive hash mismatch: ' + record['archive'])
        verified += 1
    for record in manifest['local_only_large_artifacts']:
        path = Path(record['path'])
        if not path.is_file() or path.stat().st_size != record['bytes']:
            raise RuntimeError('Local-only artifact missing or resized')
        if raw.digest(path) != record['sha256']:
            raise RuntimeError('Local-only artifact hash mismatch')
    gateway = json.loads((archive_invalid.CAMPAIGN / 'isolated_bundles' /
                          archive_invalid.RUN_ID / 'gateway/config.json').read_text(encoding='utf-8'))
    secrets = [value.encode() for route in gateway['models'].values()
               for value in route['headers'].values() if value]
    private = Path(r'E:\crs_fyne_gate_private_20261007')
    monitor_profile = json.loads((private / 'monitor_config/models.local.json').read_text(
        encoding='utf-8'))['claude_monitor_opus48']
    task_profile = runpy.run_path(str(private / 'GenericAgent-main/mykey.py'))[
        'native_claude_cc_vibe_opus48']
    endpoints = [value.encode() for value in (monitor_profile.get('apibase'),
                                               task_profile.get('apibase')) if value]
    for path in root.rglob('*'):
        if path.is_file():
            content = path.read_bytes()
            if any(secret in content for secret in secrets):
                raise RuntimeError('Private gateway credential in archive')
            if any(endpoint in content for endpoint in endpoints):
                raise RuntimeError('Private upstream endpoint in archive')
    termination = json.loads((root / 'TERMINATION.json').read_text(encoding='utf-8'))
    if termination['native_evaluator_executed'] or termination['valid']:
        raise RuntimeError('Invalid trial marked valid/evaluated')
    for name, sha_name in (('exception_path', 'exception_sha256'),
                           ('completion_incomplete_path', 'completion_incomplete_sha256')):
        if raw.digest(root / termination[name]) != termination[sha_name]:
            raise RuntimeError('Terminal record changed')
    return {'schema': 'crs-v01-invalid-archive-integrity/1',
            'run_id': archive_invalid.RUN_ID,
            'copied_records_verified': verified,
            'absent_records': sorted(set(absent)),
            'local_only_records_verified': len(manifest['local_only_large_artifacts']),
            'gateway_credential_scan': 'passed',
            'private_endpoint_scan': 'passed',
            'trial_valid': False,
            'native_evaluator_executed': False}


if __name__ == '__main__':
    result = check()
    raw.write(archive_invalid.DESTINATION / 'ARCHIVE_INTEGRITY.json', result)
    print(json.dumps(result, ensure_ascii=False))
