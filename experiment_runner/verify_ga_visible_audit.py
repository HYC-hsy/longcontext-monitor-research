"""Read back GA-only source/public identities without contacting any provider."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def verify(run_root: Path, public_root: Path) -> dict:
    root = run_root.resolve(strict=True)
    public = public_root.resolve(strict=True)
    index = json.loads((public / 'INDEX.json').read_bytes())
    if index['schema'] != 'ga-visible-readonly-audit-v1' or root.name != index['run_id']:
        raise ValueError('run or schema identity mismatch')
    originals = index['private_originals']
    for item in originals.values():
        path = (root / item['relative_path']).resolve(strict=True)
        if not path.is_relative_to(root) or digest(path.read_bytes()) != item['sha256']:
            raise ValueError('private original identity changed')
    rows = 0
    for item in index['public_files']:
        path = (public / item['file']).resolve(strict=True)
        if not path.is_relative_to(public):
            raise ValueError('public member escaped package')
        raw = path.read_bytes()
        lines = raw.splitlines(keepends=True)
        if digest(raw) != item['sha256'] or len(raw) != item['bytes'] or len(lines) != item['lines']:
            raise ValueError(f'public file identity changed: {item["file"]}')
        if len(lines) != len(item['line_map']):
            raise ValueError('public line map size differs')
        for number, (line, mapping) in enumerate(zip(lines, item['line_map']), 1):
            if number != mapping['public_line'] or digest(line) != mapping['sha256'] or len(line) != mapping['bytes']:
                raise ValueError(f'public line changed: {item["file"]}:{number}')
            json.loads(line)
        rows += len(lines)
    events_path = root / originals['research_events']['relative_path']
    with events_path.open('rb') as stream:
        source_lines = list(stream)
    event_map = index['public_files'][0]['line_map']
    if len(source_lines) != len(event_map):
        raise ValueError('source event count differs')
    for number, (raw, mapping) in enumerate(zip(source_lines, event_map), 1):
        if mapping['source_line'] != number or mapping['source_sha256'] != digest(raw):
            raise ValueError(f'private event line changed: {number}')
    return {'run_id': index['run_id'], 'public_rows': rows,
            'task_turns': index['counts']['task_turns']}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--public-root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.run_root, args.public_root), sort_keys=True))


if __name__ == '__main__':
    main()
