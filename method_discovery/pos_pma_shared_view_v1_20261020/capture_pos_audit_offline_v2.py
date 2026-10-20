"""Capture two bounded offline test commands as raw child-process pipe bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = HERE / 'raw_pos_audit_bounded_repair_v2'
OUT.mkdir(exist_ok=True)
CASES = (
    ('affected', REPO, ['-B', '-m', 'unittest',
        'method_discovery.pos_pma_complement_v1_20261019.test_shared_view',
        'method_discovery.pos_pma_complement_v1_20261019.test_candidate_core',
        'method_discovery.pos_upstream_ga_v1_20261017.test_citation_fix',
        'method_discovery.pos_pma_complement_v1_20261019.test_memory_adapter',
        'method_discovery.pos_pma_complement_v1_20261019.test_candidate_ga_seam']),
    ('pos_legacy', REPO / 'method_discovery/pos_upstream_ga_v1_20261017',
        ['-B', 'test_offline.py']),
)

records = []
for label, cwd, arguments in CASES:
    command = [sys.executable, *arguments]
    result = subprocess.run(command, cwd=cwd, capture_output=True, check=False)
    record = {'label': label, 'command': command, 'cwd': str(cwd),
              'exit_code': result.returncode, 'outputs': {}}
    for stream in ('stdout', 'stderr'):
        data = getattr(result, stream)
        target = OUT / f'{label}.{stream}.bin'
        target.write_bytes(data)
        record['outputs'][stream] = {'path': target.name, 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}
    records.append(record)

(OUT / 'manifest.json').write_text(json.dumps(records, indent=2) + '\n',
                                   encoding='utf-8')
if any(record['exit_code'] for record in records):
    raise SystemExit(1)
