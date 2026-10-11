"""Mechanically assemble the credential-free source and test audit TXT."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


BASE = 'cea43088039154505a162514880af99acfc1c0c1'
ROOT = Path(__file__).resolve().parents[3]
RELATIVE = Path('method_discovery/curator_supervisor_convergence_v0/evidence_package_v1_20261012')
SECTIONS = ('REPORT.md', 'REUSE_MANIFEST.json', 'SOURCE_LOCK.json',
            'FUTURE_DIAGNOSTIC_MANIFEST_DRAFT.json')


def git(*args: str) -> bytes:
    return subprocess.check_output(['git', *args], cwd=ROOT)


def main() -> None:
    head = git('rev-parse', 'HEAD').decode().strip()
    if git('branch', '--show-current').decode().strip() != 'crs-v0-20261007':
        raise RuntimeError('Unexpected branch')
    changed = git('diff', '--name-only', BASE + '..' + head).decode().splitlines()
    allowed = ('GenericAgent-main/monitor_agent_core/', 'GenericAgent-main/tests/',
               'method_discovery/curator_supervisor_convergence_v0/')
    if not changed or any(not path.startswith(allowed) for path in changed):
        raise RuntimeError('Diff includes an out-of-scope file')
    chunks = [f'EVIDENCE_PACKAGE_V1 ZERO-MODEL AUDIT\nbase={BASE}\ncode_commit={head}\n'
              .encode('utf-8')]
    for name in SECTIONS:
        path = RELATIVE / name
        raw = git('show', head + ':' + path.as_posix())
        label = (f'\n===== {path.as_posix()} =====\n'
                 f'git_blob={git("rev-parse", head + ":" + path.as_posix()).decode().strip()}\n'
                 f'blob_bytes_sha256={hashlib.sha256(raw).hexdigest()}\n'
                 f'byte_count={len(raw)}\n').encode('utf-8')
        chunks.extend((label, raw, b'\n'))
    patch = git('diff', '--binary', BASE + '..' + head)
    chunks.extend((b'\n===== FULL BASE-TO-CODE-COMMIT DIFF =====\n', patch))
    destination = ROOT / RELATIVE / 'AUDIT_PACKET.txt'
    destination.write_bytes(b''.join(chunks))
    print(f'code_commit={head}')
    print(f'changed_files={len(changed)}')
    print(f'diff_sha256={hashlib.sha256(patch).hexdigest()}')
    print(f'audit_txt_sha256={hashlib.sha256(destination.read_bytes()).hexdigest()}')
    print(f'audit_txt_bytes={destination.stat().st_size}')


if __name__ == '__main__':
    main()
