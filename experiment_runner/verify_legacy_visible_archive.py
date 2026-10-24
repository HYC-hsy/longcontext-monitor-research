"""Verify already-published redacted legacy archive bytes, not lost originals."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def verify(root: Path) -> dict:
    root = root.resolve(strict=True)
    if (root / 'ARCHIVED_FILE_INDEX.json').is_file():
        index = json.loads((root / 'ARCHIVED_FILE_INDEX.json').read_bytes())
        if not isinstance(index, list):
            raise ValueError('legacy archive index is not a list')
        members = [(root / item['path'], item['archive_bytes'], item['archive_sha256'])
                   for item in index]
    else:
        index = json.loads((root / 'RAW_TRACE_INDEX.json').read_bytes())
        if not isinstance(index, dict):
            raise ValueError('legacy trace index is not a map')
        members = [(root / 'raw' / name, item['archived_bytes'], item['archived_sha256'])
                   for name, item in index.items()]
    for path, length, expected_hash in members:
        path = path.resolve(strict=True)
        if not path.is_relative_to(root):
            raise ValueError('legacy member escaped archive')
        raw = path.read_bytes()
        if len(raw) != length or hashlib.sha256(raw).hexdigest() != expected_hash:
            raise ValueError(f'published legacy member changed: {path.name}')
    return {'members': len(index), 'published_bytes_verified': True,
            'lost_private_originals_verified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.root), sort_keys=True))
