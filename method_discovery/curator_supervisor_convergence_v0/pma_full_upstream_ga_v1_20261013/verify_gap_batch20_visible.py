"""Read back every public batch member and its private-original hash map."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from .export_gap_visible_audit import file_sha, sha


def verify(batch_root: Path, public_root: Path) -> dict:
    batch_root = batch_root.resolve(strict=True)
    public_root = public_root.resolve(strict=True)
    index = json.loads((public_root / 'INDEX.json').read_bytes())
    if index.get('schema') != 'pma-gap-batch20-visible-projection-v1' or len(index['slots']) != 20:
        raise ValueError('public batch identity or slot count differs')
    if file_sha(batch_root / 'selection_result.json') != index['selection_source_sha256']:
        raise ValueError('private selection result changed')
    checked = 0
    for slot in index['slots']:
        dirname = f"{slot['order']:02d}-{slot['task']}-r1"
        directory = public_root / dirname
        run_dirs = list((batch_root / dirname / 'runs').iterdir())
        if len(run_dirs) != 1 or run_dirs[0].name != slot['run_id']:
            raise ValueError('run identity differs')
        run = run_dirs[0].resolve(strict=True)
        identity = directory / 'IDENTITY.json'
        manifest = directory / 'INDEX.json'
        if (file_sha(identity) != slot['identity_sha256'] or
                file_sha(manifest) != slot['index_sha256']):
            raise ValueError('public per-run identity changed')
        detail = json.loads(manifest.read_bytes())
        if detail['run_id'] != slot['run_id'] or len(detail['files']) != slot['files']:
            raise ValueError('per-run member count differs')
        for item in detail['files']:
            source = (run / item['source']).resolve(strict=True)
            target = (directory / item['public']).resolve(strict=True)
            if not source.is_relative_to(run) or not target.is_relative_to(directory):
                raise ValueError('member escaped frozen run/public directory')
            if (file_sha(source) != item['source_sha256'] or
                    source.stat().st_size != item['source_bytes'] or
                    file_sha(target) != item['public_gzip_sha256'] or
                    target.stat().st_size != item['public_gzip_bytes']):
                raise ValueError(f'member source or compressed bytes changed: {item["public"]}')
            digest = hashlib.sha256()
            number = 0
            with gzip.open(target, 'rb') as stream:
                for number, raw in enumerate(stream, 1):
                    digest.update(raw)
                    mapping = item['row_map'][number - 1]
                    shown = json.loads(raw)
                    if (mapping['line'] != number or
                            mapping['public_sha256'] != sha(raw) or
                            shown.get('source_line', number) != number):
                        raise ValueError('public row identity differs')
            if (number != item['rows'] or len(item['row_map']) != number or
                    digest.hexdigest() != item['public_uncompressed_sha256']):
                raise ValueError('public uncompressed stream differs')
            if source.suffix == '.jsonl':
                line_number = 0
                with source.open('rb') as original:
                    for line_number, raw in enumerate(original, 1):
                        if item['row_map'][line_number - 1]['original_sha256'] != sha(raw):
                            raise ValueError('private source row mapping differs')
                if line_number != number:
                    raise ValueError('private source row count differs')
            elif item['row_map'][0]['original_sha256'] != file_sha(source):
                raise ValueError('private object mapping differs')
            checked += 1
    return {'slots': len(index['slots']), 'members': checked}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-root', type=Path, required=True)
    parser.add_argument('--public-root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.batch_root, args.public_root)))


if __name__ == '__main__':
    main()
