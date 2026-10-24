"""Verify a generic historical visible package against unchanged private sources."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def verify(run_root: Path, public_root: Path) -> dict:
    root = run_root.resolve(strict=True)
    public = public_root.resolve(strict=True)
    index = json.loads((public / 'INDEX.json').read_bytes())
    if index['schema'] != 'historical-visible-sources-v1' or index['run_id'] != root.name:
        raise ValueError('run/schema identity mismatch')
    for item in index['files']:
        source = (root / item['source']).resolve(strict=True)
        shown = (public / item['public']).resolve(strict=True)
        if not source.is_relative_to(root) or not shown.is_relative_to(public):
            raise ValueError('source or public path escaped selected root')
        private_bytes = source.read_bytes()
        gzip_bytes = shown.read_bytes()
        if (sha(private_bytes) != item['source_sha256'] or
                len(private_bytes) != item['source_bytes'] or
                sha(gzip_bytes) != item['public_gzip_sha256'] or
                len(gzip_bytes) != item['public_gzip_bytes']):
            raise ValueError(f'source/public file changed: {item["public"]}')
        with gzip.open(shown, 'rb') as stream:
            public_bytes = stream.read()
        lines = public_bytes.splitlines(keepends=True)
        if sha(public_bytes) != item['public_uncompressed_sha256'] or len(lines) != item['rows']:
            raise ValueError('uncompressed stream changed')
        originals = private_bytes.splitlines(keepends=True) if source.suffix == '.jsonl' else [private_bytes]
        if len(originals) != len(lines) or len(item['row_map']) != len(lines):
            raise ValueError('row mapping count differs')
        for number, (raw, line, mapping) in enumerate(zip(originals, lines, item['row_map']), 1):
            if (mapping['line'] != number or mapping['original_sha256'] != sha(raw) or
                    mapping['public_sha256'] != sha(line)):
                raise ValueError(f'row mapping differs: {item["public"]}:{number}')
            json.loads(line)
    derived = index.get('derived_reminder_links')
    if derived:
        path = (public / derived['public']).resolve(strict=True)
        if not path.is_relative_to(public) or sha(path.read_bytes()) != derived['public_sha256']:
            raise ValueError('derived reminder file changed')
        with gzip.open(path, 'rb') as stream:
            lines = list(stream)
        if len(lines) != derived['rows'] or len(lines) != len(derived['line_map']):
            raise ValueError('derived reminder row count differs')
        for number, (line, mapping) in enumerate(zip(lines, derived['line_map']), 1):
            if mapping['line'] != number or sha(line) != mapping['public_sha256']:
                raise ValueError(f'derived reminder line changed: {number}')
            json.loads(line)
        for name, key in (('host_private/archive/trajectory_memory.json',
                           'trajectory_original_sha256'),):
            if sha((root / name).read_bytes()) != derived[key]:
                raise ValueError('derived reminder trajectory original changed')
        paths = list((root / 'jobs').glob('*/*/agent/research_events.jsonl'))
        if len(paths) != 1 or sha(paths[0].read_bytes()) != derived['task_events_original_sha256']:
            raise ValueError('derived reminder Task event original changed')
    return {'run_id': index['run_id'], 'source_files': len(index['files'])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--public-root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.run_root, args.public_root), sort_keys=True))


if __name__ == '__main__':
    main()
