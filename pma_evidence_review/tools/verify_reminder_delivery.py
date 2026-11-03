"""Byte verification of the frozen reminder delivery; standard library only."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DELIVERY = ROOT/'pma_evidence_review/requirement_reminder_delivery_20261103'


def main():
    manifest = json.loads((DELIVERY/'MANIFEST.json').read_bytes())
    identity = json.loads((DELIVERY/'SOURCE_IDENTITY.json').read_bytes())
    failures = []
    for name,expected in {**manifest['files'],**identity['source_files']}.items():
        path = ROOT/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            failures.append(name)
    result = json.loads((DELIVERY/'OFFLINE_RESULTS.json').read_bytes())
    if (result['tests_run']!=167 or not result['successful'] or
            any(result[key] for key in ('errors','failures','skipped'))):
        failures.append('offline result')
    print(json.dumps({'status':'failed' if failures else 'passed','manifest_files':len(manifest['files']),
        'runtime_files':len(identity['source_files']),'failures':sorted(set(failures))}))
    return bool(failures)


if __name__=='__main__':
    raise SystemExit(main())
