"""Assemble a complete uploadable, credential-free host-static TXT audit."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess


BASE = 'ce332b5968b0dc020d8051c2e41887a19a67dc3a'
ROOT = Path(__file__).resolve().parents[3]
REL = Path('method_discovery/curator_supervisor_convergence_v0/evidence_package_v1_20261012')
SECTIONS = ('STATIC_HOST_REPORT.md', 'REUSE_MANIFEST.json', 'SOURCE_LOCK.json',
            'FUTURE_DIAGNOSTIC_MANIFEST_DRAFT.json')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def section(head, relative):
    name = relative.as_posix()
    raw = git('show', head + ':' + name)
    blob = git('rev-parse', head + ':' + name).decode().strip()
    label = (f'\n===== {name} =====\n'
             f'git_blob={blob}\nbytes={len(raw)}\n'
             f'raw_sha256={hashlib.sha256(raw).hexdigest()}\n').encode()
    return label + raw + b'\n'


def main():
    head = git('rev-parse', 'HEAD').decode().strip()
    if git('branch', '--show-current').decode().strip() != 'crs-v0-20261007':
        raise RuntimeError('Unexpected research branch')
    destination = ROOT / REL / 'STATIC_HOST_AUDIT.txt'
    if destination.exists():
        raise RuntimeError('Existing static audit packet must not be overwritten')
    names = git('ls-tree', '-r', '--name-only', head,
                (REL / 'STATIC_OFFLINE_RAW_RESULTS').as_posix(),
                (REL / 'STATIC_OFFLINE_FOLLOWUP_RESULTS').as_posix())
    raw_files = [Path(line) for line in names.decode().splitlines() if line]
    if len(raw_files) != 18:
        raise RuntimeError('Expected five original and one follow-up complete command records')
    parts = [f'EVIDENCE_PACKAGE_V1 HOST-STATIC ZERO-MODEL AUDIT\n'
             f'base={BASE}\ncontent_commit={head}\n'.encode()]
    for name in SECTIONS:
        parts.append(section(head, REL / name))
    for path in raw_files:
        parts.append(section(head, path))
    patch = git('diff', '--binary', BASE + '..' + head)
    parts.extend((b'\n===== COMPLETE BASE-TO-CONTENT-COMMIT DIFF =====\n', patch))
    destination.write_bytes(b''.join(parts))
    print('content_commit=' + head)
    print('raw_files=' + str(len(raw_files)))
    print('diff_sha256=' + hashlib.sha256(patch).hexdigest())
    print('audit_bytes=' + str(destination.stat().st_size))
    print('audit_sha256=' + hashlib.sha256(destination.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
