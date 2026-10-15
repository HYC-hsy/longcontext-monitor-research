"""Index Git-delivered and Windows worktree bytes without conflating them."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
CHECKOUT = Path(subprocess.check_output(
    ['git', 'rev-parse', '--show-toplevel'], cwd=HERE, text=True).strip())
PREFIX = HERE.relative_to(CHECKOUT).as_posix() + '/'
OUTPUT = HERE / 'FILE_HASHES_ALL.json'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    listed = subprocess.check_output(['git', 'ls-files', '-z', '--', PREFIX], cwd=CHECKOUT)
    entries = []
    for raw in listed.split(b'\0'):
        if not raw:
            continue
        name = raw.decode('utf-8').replace('\\', '/')
        if not name.startswith(PREFIX) or name == PREFIX + OUTPUT.name:
            continue
        worktree = (CHECKOUT / name).read_bytes()
        blob = subprocess.run(['git', 'show', f'HEAD:{name}'], cwd=CHECKOUT,
                              capture_output=True, check=False)
        entries.append({'path': name[len(PREFIX):], 'worktree_bytes': len(worktree),
                        'worktree_sha256': sha(worktree),
                        'git_blob_bytes': len(blob.stdout) if blob.returncode == 0 else None,
                        'git_blob_sha256': sha(blob.stdout) if blob.returncode == 0 else None,
                        'git_blob_equals_worktree': blob.returncode == 0 and
                            blob.stdout == worktree})
    OUTPUT.write_text(json.dumps({'schema': 'pma-ga-delivery-index-v1',
                                  'index_excluded': OUTPUT.name,
                                  'files': entries}, indent=2, ensure_ascii=False) + '\n',
                      encoding='utf-8', newline='\n')
    print(json.dumps({'files': len(entries), 'byte_equal': sum(
        row['git_blob_equals_worktree'] for row in entries)}))


if __name__ == '__main__':
    main()
