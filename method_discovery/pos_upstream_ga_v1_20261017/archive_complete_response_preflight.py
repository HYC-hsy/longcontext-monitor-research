"""Archive the two-task pre-Harbor and Task fake-HTTP checks without secrets."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from .collect_native_shared import secrets_from_profile
from .single_manifest import CHECKOUT, source_hashes, vendor_hashes


TESTS = (
    'method_discovery.pos_upstream_ga_v1_20261017.test_complete_response_startup',
    'GenericAgent-main.tests.test_task_complete_response.CompleteResponseTests.'
    'test_retry_same_payload_one_history_commit',
    'GenericAgent-main.tests.test_task_complete_response.CompleteResponseTests.'
    'test_pos_decision_view_occurs_once_across_retry',
    'GenericAgent-main.tests.test_task_complete_response.CompleteResponseTests.'
    'test_default_off_and_auxiliary_unaffected',
    'GenericAgent-main.tests.test_task_complete_response.CompleteResponseTests.'
    'test_five_attempts_shared_budget',
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(boundary: Path, target: Path, profile: Path, certification: Path) -> None:
    target.mkdir(parents=True, exist_ok=False)
    rows = []
    def copy(source: Path, relative: str) -> None:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        rows.append({'path': relative, 'bytes': destination.stat().st_size,
                     'sha256': sha(destination), 'source_sha256': sha(source)})

    result = json.loads((boundary / 'boundary_result.json').read_text(encoding='utf-8'))
    if (result.get('status') != 'pass' or len(result.get('runs', [])) != 2 or
            [row['task'] for row in result['runs']] !=
            ['adaptive-rejection-sampler', 'write-compressor'] or
            any(row['harbor_started'] or row['provider_calls'] or
                row['official_evaluator_calls'] for row in result['runs'])):
        raise RuntimeError('pre-Harbor result is not the fixed two-task check')
    copy(boundary / 'boundary_result.json', 'boundary_result.json')
    for number, row in enumerate(result['runs'], 1):
        source = boundary / f"{number:02d}_{row['task']}"
        identity = json.loads((source / 'run_identity.json').read_text(encoding='utf-8'))
        run = Path(identity['run_root']).resolve(strict=True)
        if not run.is_relative_to(source.resolve(strict=True)):
            raise RuntimeError('pre-Harbor run root outside prepared directory')
        for name in ('plan.json', 'manifest.json', 'run_identity.json'):
            copy(source / name, f"{number:02d}/{name}")
        for name in ('control/harbor_spec.json', 'archive/live_command_public.json'):
            copy(run / name, f"{number:02d}/{name}")
    command = [sys.executable, '-B', '-m', 'unittest', '-v', *TESTS]
    completed = subprocess.run(command, cwd=CHECKOUT, capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError('Task/serial zero-model tests failed')
    for name, data in [('tests.stdout.txt', completed.stdout),
                       ('tests.stderr.txt', completed.stderr)]:
        path = target / name
        path.write_bytes(data)
        rows.append({'path': name, 'bytes': len(data),
                     'sha256': hashlib.sha256(data).hexdigest(),
                     'source_sha256': hashlib.sha256(data).hexdigest()})
    sensitive = [value.encode() for value in secrets_from_profile(profile)]
    if any(value in (target / row['path']).read_bytes()
           for value in sensitive for row in rows):
        raise RuntimeError('private profile value found in preflight archive')
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=CHECKOUT,
                          capture_output=True, text=True, check=True).stdout.strip()
    index = {'schema': 'pos-ga-complete-response-preflight-v1',
             'status': 'pass', 'code_commit': head,
             'boundary_source_commit': result['source_commit'],
             'task_complete_response_policy': 'complete-response-v1',
             'certification_index_sha256': sha(certification / 'FILE_HASHES.json'),
             'source_files_sha256': source_hashes(),
             'vendor_files_sha256': vendor_hashes(),
             'test_command': command, 'test_return_code': completed.returncode,
             'real_model_calls': 0, 'official_evaluator_calls': 0,
             'files': rows}
    (target / 'FILE_HASHES.json').write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8', newline='\n')
    print(json.dumps({'status': 'pass', 'files': len(rows),
                      'tests': len(TESTS), 'real_model_calls': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--boundary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--task-profile-file', type=Path, required=True)
    parser.add_argument('--certification', type=Path, required=True)
    args = parser.parse_args()
    main(args.boundary, args.output, args.task_profile_file, args.certification)
