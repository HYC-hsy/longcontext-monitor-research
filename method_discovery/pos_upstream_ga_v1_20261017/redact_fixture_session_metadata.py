"""Remove synthetic client session IDs from an already collected public fixture.

This only redacts request metadata; prompt, tools, result and source hashes stay
in the evidence. The private fixture is never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


PATTERN = re.compile(rb'("user_id"\s*:\s*)"(?:\\.|[^"\\])*"')
REPLACEMENT = rb'\1"[REDACTED_SYNTHETIC_SESSION]"'
TARGETS = ('normal/agent/research_events.jsonl',
           'normal/fake_requests/0001.json',
           'normal/fake_requests/0002.json')


def main(root: Path) -> None:
    index_path = root / 'FILE_HASHES.json'
    index = json.loads(index_path.read_text(encoding='utf-8'))
    indexed = {row['path']: row for row in index['files']}
    total = 0
    for name in TARGETS:
        row = indexed[name]
        target = root / name
        original = target.read_bytes()
        if hashlib.sha256(original).hexdigest() != row['sha256']:
            raise RuntimeError('collected public fixture changed: ' + name)
        updated, count = PATTERN.subn(REPLACEMENT, original)
        if count < 1:
            raise RuntimeError('expected synthetic metadata missing: ' + name)
        # Confirm the resulting JSON/JSONL is still parseable before writing.
        if target.suffix == '.jsonl':
            for line in updated.decode('utf-8').splitlines():
                if line.strip():
                    json.loads(line)
        else:
            json.loads(updated)
        target.write_bytes(updated)
        row.update(bytes=len(updated), sha256=hashlib.sha256(updated).hexdigest(),
                   redactions=row['redactions'] + count)
        total += count
    index['additional_public_redaction'] = {
        'field': 'metadata.user_id', 'reason': 'synthetic client session identity',
        'occurrences': total, 'private_fixture_unchanged': True}
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n',
                          encoding='utf-8', newline='\n')
    print(json.dumps({'status': 'redacted', 'occurrences': total}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    main(parser.parse_args().root)
