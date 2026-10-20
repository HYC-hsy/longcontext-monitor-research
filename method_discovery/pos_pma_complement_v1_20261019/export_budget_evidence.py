"""Redact the stopped long-output synthetic run, explicitly indexing unsafe logs.

This is archive-only code: it does not change the frozen run or certification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.archive_live_six_task import (
    UnsafePublicProjection, redact)
from method_discovery.pos_upstream_ga_v1_20261017.collect_native_shared import (
    mapping_for, secrets_from_profile)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--task-profile-file', type=Path, required=True)
    args = parser.parse_args()
    target = args.output.resolve(strict=False)
    target.mkdir(parents=True, exist_ok=False)
    secrets = secrets_from_profile(args.task_profile_file)
    files, omissions = [], []
    for name, path in sorted(mapping_for(args.source).items()):
        original = path.read_bytes()
        try:
            public, redactions = redact(original, secrets)
        except UnsafePublicProjection:
            if name != 'agent/agent_stdout.log':
                raise
            omissions.append({'path': 'normal/' + name,
                              'private_source_bytes': len(original),
                              'private_source_sha256': sha(original),
                              'reason': 'non-JSON stdout not safely projectable'})
            continue
        destination = target / 'normal' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            stream.write(public)
        if destination.read_bytes() != public:
            raise RuntimeError('public evidence readback differs')
        files.append({'path': 'normal/' + name, 'bytes': len(public),
                      'sha256': sha(public),
                      'private_source_bytes': len(original),
                      'private_source_sha256': sha(original),
                      'redactions': redactions})
    index = {'schema': 'pos-ga-native-shared-evidence-v1',
             'source_kind': 'redacted_copies_of_existing_run_records',
             'files': files, 'omissions': omissions,
             'new_real_model_calls': 0, 'official_evaluator_calls': 0}
    (target / 'FILE_HASHES.json').write_text(json.dumps(index, ensure_ascii=False,
        indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'files': len(files), 'omissions': len(omissions),
                      'redactions': sum(row['redactions'] for row in files)}))


if __name__ == '__main__':
    main()
