"""Two independent Docker sentinel negatives using only the already-present image."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

TESTS = Path(__file__).resolve().parent / 'synthetic_task/tests'
IMAGE = 'alexgshaw/db-wal-recovery:20251031'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    for name, command in (
        ('missing_file', '/tests/test.sh'),
        ('missing_service', 'printf POS_FILE_OK > /app/pos-fixture-marker.txt; /tests/test.sh')):
        argv = ['docker', 'run', '--rm', '--pull', 'never', '--network', 'none',
                '--entrypoint', '/bin/sh', '-v', f'{TESTS}:/tests:ro',
                '-v', f'{args.runtime_root.resolve(strict=True)}:/opt/m4-runtime:ro',
                IMAGE, '-c', command]
        result = subprocess.run(argv, capture_output=True, check=False)
        (args.output / f'{name}.stdout.txt').write_bytes(result.stdout)
        (args.output / f'{name}.stderr.txt').write_bytes(result.stderr)
        rows.append({'name': name, 'argv': argv, 'exit_code': result.returncode,
                     'stdout_sha256': hashlib.sha256(result.stdout).hexdigest(),
                     'stderr_sha256': hashlib.sha256(result.stderr).hexdigest()})
    (args.output / 'results.json').write_text(json.dumps(rows, indent=2) + '\n',
                                             encoding='utf-8', newline='\n')
    print(json.dumps(rows))
    if any(row['exit_code'] != 1 for row in rows):
        raise SystemExit('synthetic sentinel failed to reject a missing condition')


if __name__ == '__main__':
    main()
