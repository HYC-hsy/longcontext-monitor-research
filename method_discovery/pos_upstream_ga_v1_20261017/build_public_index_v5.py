"""Hash exact staged Git blob bytes for this handoff; index excludes itself."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TARGET = Path(__file__).resolve().parent / 'PUBLIC_FILE_SHA256_V5.json'


def git(*args: str) -> bytes:
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True,
                          check=True).stdout


def main() -> None:
    names = [item.decode('utf-8') for item in
             git('diff', '--cached', '--name-only', '-z').split(b'\0') if item]
    rows = []
    for name in names:
        if name == TARGET.relative_to(ROOT).as_posix():
            continue
        content = git('show', ':' + name)
        rows.append({'path': name, 'bytes': len(content),
                     'sha256': hashlib.sha256(content).hexdigest()})
    TARGET.write_text(json.dumps({'schema': 'pos-ga-public-git-blob-index-v1',
        'files': rows}, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8', newline='\n')
    print(json.dumps({'files': len(rows), 'index_sha256':
        hashlib.sha256(TARGET.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
