"""Offline-only rehydration of authenticated v1 ledgers; never a live restore path."""

import json
from pathlib import Path

from monitor_agent_core.root_records_v1 import PREFIX, _closed, canonical, digest, parse_ledger, project


def _catalog(root):
    entries = {}
    for directory in sorted(Path(root).iterdir()):
        if not directory.is_dir():
            continue
        source = json.loads((directory / 'source.json').read_text(encoding='utf-8'))
        projected = json.loads((directory / 'projected_history.json').read_text(encoding='utf-8'))
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        commit = json.loads((directory / 'committed.json').read_text(encoding='utf-8'))
        locator = manifest['source_locator']
        expected, check, _ = project(source, source_locator=locator)
        check.update(request_id=manifest['request_id'], generation=manifest['generation'])
        if (expected != projected or check != manifest or
                commit['source_sha256'] != digest(canonical(source)) or
                commit['projected_sha256'] != digest(canonical(projected)) or
                commit['source_locator'] != locator or
                locator != 'monitor/audit/root_projections/' + directory.name + '/source.json'):
            raise ValueError('Unauthenticated v1 root projection: ' + directory.name)
        if len(projected) != 1 or len(projected[0]['content']) != 1:
            raise ValueError('Unexpected v1 projected shape')
        ledger = projected[0]['content'][0]['text']
        key = digest(ledger.encode('utf-8'))
        if key in entries:
            raise ValueError('Duplicate archived v1 ledger')
        entries[key] = (ledger, manifest, directory.name)
    return entries


def rehydrate(history, root):
    """Decode only exact, manifest-backed ledgers present in the supplied history."""
    entries = _catalog(root)
    visited, lineage = set(), []

    def expand(messages):
        result = []
        for message in messages:
            blocks = message['content']
            candidate = (blocks[0].get('text') if message['role'] == 'user'
                         and len(blocks) == 1 and blocks[0].get('type') == 'text' else None)
            if isinstance(candidate, str) and candidate.startswith(PREFIX):
                key = digest(candidate.encode('utf-8'))
                if key not in entries or entries[key][0] != candidate:
                    raise ValueError('Unproven ledger-like historical text')
                if key in visited:
                    raise ValueError('Duplicate or cyclic v1 ledger reference')
                visited.add(key)
                ledger, manifest, directory = entries[key]
                rows = parse_ledger(ledger)
                retained = [row for row in manifest['rows'] if row['rule'] == 'retain']
                if len(rows) != len(retained):
                    raise ValueError('v1 retained row count mismatch')
                rebuilt = []
                for (mi, bi, role, block), row in zip(rows, retained):
                    if ((mi, bi, role) != (row['message_index'], row['block_index'], row['role'])
                            or digest(canonical(block)) != row['source_sha256']):
                        raise ValueError('v1 retained record identity mismatch')
                    if not rebuilt or rebuilt[-1][0] != mi:
                        rebuilt.append((mi, {'role': role, 'content': []}))
                    rebuilt[-1][1]['content'].append(block)
                nested = expand([item for _, item in rebuilt])
                _closed(nested)
                lineage.append({'directory': directory, 'ledger_sha256': key,
                                'retained_blocks': len(rows),
                                'source_sha256': manifest['source_sha256']})
                result.extend(nested)
            else:
                if any(block.get('type') == 'text' and isinstance(block.get('text'), str)
                       and block['text'].startswith(PREFIX) for block in blocks):
                    raise ValueError('Ambiguous embedded ledger-like text')
                result.append(message)
        return result

    restored = expand(history)
    pairs = _closed(restored)
    return restored, {'lineage': lineage, 'tool_pairs': pairs,
                      'source_history_sha256': digest(canonical(history)),
                      'restored_history_sha256': digest(canonical(restored))}
