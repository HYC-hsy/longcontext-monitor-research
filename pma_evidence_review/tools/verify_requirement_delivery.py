"""Verify the local prototype delivery with only the Python standard library."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DELIVERY = ROOT/'pma_evidence_review/requirement_attributes_delivery_20261103'


def main():
    manifest = json.loads((DELIVERY/'MANIFEST.json').read_bytes())
    failures = []
    for name,sha in manifest['files'].items():
        path = ROOT/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
            failures.append(name)
    identity = json.loads((DELIVERY/'SOURCE_IDENTITY.json').read_bytes())
    for name,sha in identity['source_files'].items():
        path = ROOT/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
            failures.append(name)
    frozen = json.loads((DELIVERY/'FROZEN_INPUT_CHECK.json').read_bytes())
    for row in frozen['cases']:
        if row['expected_sha256']!=row['actual_sha256']:
            failures.append(row['file'])
    report = json.loads((DELIVERY/'OFFLINE_RESULTS.json').read_bytes())
    if report['tests_run']!=118 or not report['successful'] or any(report[k] for k in ('errors','failures','skipped')):
        failures.append('offline result')
    print(json.dumps({'status':'failed' if failures else 'passed','manifest_files':len(manifest['files']),
        'runtime_files':len(identity['source_files']),'failures':sorted(set(failures)),
        'publication_status':manifest['publication_status']}))
    return bool(failures)


if __name__=='__main__':
    raise SystemExit(main())
