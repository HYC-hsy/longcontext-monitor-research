"""Finite no-model checks and raw receipt capture; no scientific entry point."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--supervisor-source', required=True)
    args = parser.parse_args()
    env = dict(os.environ, M1_FROZEN_SOURCE=str(Path(args.supervisor_source).resolve(strict=True)))
    command = [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', str(HERE / 'test_launch_preparation.py')]
    result = subprocess.run(command, env=env, capture_output=True)
    receipts = HERE / 'offline_receipts'; receipts.mkdir(exist_ok=True)
    (receipts / 'pytest.stdout.txt').write_bytes(result.stdout)
    (receipts / 'pytest.stderr.txt').write_bytes(result.stderr)
    (receipts / 'command.json').write_text(json.dumps({'command': command,
        'source_argument': env['M1_FROZEN_SOURCE'], 'exit_code': result.returncode,
        'purpose': 'no-model engineering checks; not pilot execution'}, indent=2), encoding='utf-8')
    sys.stdout.buffer.write(result.stdout); sys.stderr.buffer.write(result.stderr)
    raise SystemExit(result.returncode)
