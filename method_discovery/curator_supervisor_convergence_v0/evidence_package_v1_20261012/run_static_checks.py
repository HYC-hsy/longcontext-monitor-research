"""Run only zero-model acceptance paths and persist complete raw command output."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUTPUT = Path(os.environ.get('STATIC_CHECK_OUTPUT',
                             str(HERE / 'STATIC_OFFLINE_RAW_RESULTS')))
CORE = 'GenericAgent-main/tests/'
RESEARCH = ('method_discovery/curator_supervisor_convergence_v0/'
            'evidence_package_v1_20261012/')
CHECKS = [
    ('core', [CORE + name for name in ('test_evidence_package_v1.py',
        'test_narrow_supervisor_v1.py', 'test_monitor_agent.py',
        'test_monitor_provider.py')]),
    ('profile_bundle', [RESEARCH + name for name in ('test_profile.py',
        'test_bundle.py')]),
    ('static_host_session', [RESEARCH + name for name in ('test_static_host.py',
        'test_static_session.py')]),
    ('static_live_gate', [RESEARCH + 'test_static_live_batch.py']),
    ('native_go', [RESEARCH + 'test_go_checks.py']),
    ('existing_docker_candidate', [RESEARCH + 'test_docker_candidate.py']),
]


def main():
    if OUTPUT.exists():
        raise RuntimeError('Existing raw results must not be overwritten')
    OUTPUT.mkdir()
    env = dict(os.environ)
    env['PYTHONPATH'] = str(ROOT / 'GenericAgent-main')
    for label, paths in CHECKS:
        selected = os.environ.get('STATIC_CHECK_ONLY')
        if selected and label != selected:
            continue
        command = [sys.executable, '-m', 'pytest', '--import-mode=importlib',
                   *paths, '-q', '-s', '--tb=short']
        started = time.time()
        try:
            result = subprocess.run(command, cwd=ROOT, env=env,
                                    capture_output=True, timeout=600)
            stdout, stderr, status = result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, status = exc.stdout or b'', exc.stderr or b'', 'timeout'
        directory = OUTPUT / label
        directory.mkdir()
        (directory / 'stdout.txt').write_bytes(stdout)
        (directory / 'stderr.txt').write_bytes(stderr)
        record = {'command': command, 'cwd': str(ROOT), 'exit_code': status,
                  'started_unix': started, 'duration_seconds': time.time() - started,
                  'stdout_sha256': hashlib.sha256(stdout).hexdigest(),
                  'stderr_sha256': hashlib.sha256(stderr).hexdigest(),
                  'stdout_bytes': len(stdout), 'stderr_bytes': len(stderr),
                  'transport_evidence': 'see test fake_post counters and offline.invalid configuration; '
                                        'this runner does not measure external calls'}
        (directory / 'result.json').write_text(json.dumps(record, ensure_ascii=False,
            sort_keys=True, indent=2) + '\n', encoding='utf-8')
        print(label, status, round(record['duration_seconds'], 2),
              record['stdout_sha256'], flush=True)


if __name__ == '__main__':
    main()
