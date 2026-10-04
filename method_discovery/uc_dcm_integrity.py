"""Read-only hash and private-header scan of the DCM raw archive."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from method_discovery.uc_dcm_freeze import ROOT, CAMPAIGN, PLAN
from method_discovery.uc_path_control_archive import write


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    records = []
    all_secrets = []
    for slot in plan['slots']:
        run_id = slot['run_id']
        archive = ROOT / 'records' / f"{slot['position']:02d}_{run_id}"
        manifest = json.loads((archive / 'RAW_FILE_MANIFEST.json').read_text(encoding='utf-8'))
        gateway = json.loads((CAMPAIGN / 'isolated_bundles' / run_id /
                              'gateway/config.json').read_text(encoding='utf-8'))
        secrets = [value.encode() for route in gateway['models'].values()
                   for value in route['headers'].values() if value]
        all_secrets.extend(secrets)
        copied = [row for row in manifest['copied'] if row.get('status') == 'copied']
        missing = [row['archive'] for row in manifest['copied'] if row.get('status') == 'missing']
        mismatch, exposed = [], []
        for row in copied:
            path = archive / row['archive']
            if not path.is_file() or path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
                mismatch.append(row['archive'])
                continue
            payload = path.read_bytes()
            if any(secret in payload for secret in secrets):
                exposed.append(row['archive'])
        local = []
        for row in manifest['local_only_large_artifacts']:
            path = Path(row['path'])
            ok = path.is_file() and path.stat().st_size == row['bytes'] and sha(path) == row['sha256']
            local.append({'path': row['path'], 'bytes': row['bytes'], 'sha256': row['sha256'],
                          'verified': ok})
        records.append({'run_id': run_id, 'copied_files': len(copied),
                        'missing_optional_paths': missing, 'hash_mismatches': mismatch,
                        'private_header_exposure_paths': exposed,
                        'local_only_large_artifacts': local,
                        'raw_manifest_sha256': sha(archive / 'RAW_FILE_MANIFEST.json')})
    archive_exposures = []
    archive_files = sorted(path for path in ROOT.rglob('*') if path.is_file())
    for path in archive_files:
        if any(secret in path.read_bytes() for secret in all_secrets):
            archive_exposures.append(path.relative_to(ROOT).as_posix())
    result = {'records': records,
              'all_copied_hashes_match': all(not r['hash_mismatches'] for r in records),
              'archive_files_scanned_for_private_headers': len(archive_files),
              'archive_private_header_exposure_paths': archive_exposures,
              'no_private_header_exposure': not archive_exposures and
                  all(not r['private_header_exposure_paths'] for r in records),
              'all_local_large_artifacts_match': all(all(a['verified'] for a in r['local_only_large_artifacts'])
                                                    for r in records)}
    write(ROOT / 'ARCHIVE_INTEGRITY.json', result)
    print(json.dumps({'all_copied_hashes_match': result['all_copied_hashes_match'],
                      'no_private_header_exposure': result['no_private_header_exposure'],
                      'all_local_large_artifacts_match': result['all_local_large_artifacts_match'],
                      'copied_file_counts': [r['copied_files'] for r in records],
                      'missing_path_counts': [len(r['missing_optional_paths']) for r in records]}, indent=2))
    if not all((result['all_copied_hashes_match'], result['no_private_header_exposure'],
                result['all_local_large_artifacts_match'])):
        raise RuntimeError('Archive integrity check failed')


if __name__ == '__main__':
    main()
