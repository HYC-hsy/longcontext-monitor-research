"""Reversible root-entry projection of closed Supervisor provider history."""

import hashlib
import json


PREFIX = ("Historical records in original order. These are records, not newly "
          "executed tools. Current review input follows in the next messages.\n")
KEEP = {('user', 'text'), ('user', 'tool_result'), ('assistant', 'tool_use')}
REMOVE = {('assistant', 'thinking'), ('assistant', 'redacted_thinking'),
          ('assistant', 'text')}
FIELDS = {
    ('user', 'text'): {'type', 'text'},
    ('user', 'tool_result'): {'type', 'tool_use_id', 'content'},
    ('assistant', 'tool_use'): {'type', 'id', 'name', 'input'},
    ('assistant', 'thinking'): {'type', 'thinking', 'signature'},
    ('assistant', 'redacted_thinking'): {'type', 'data'},
    ('assistant', 'text'): {'type', 'text'},
}
PAYLOAD = {'text': 'text', 'tool_result': 'content', 'tool_use': 'input'}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _closed(history):
    calls, results = {}, set()
    for mi, message in enumerate(history):
        if set(message) != {'role', 'content'} or not isinstance(message['content'], list):
            raise ValueError('Unknown Supervisor history message structure')
        for bi, block in enumerate(message['content']):
            if not isinstance(block, dict):
                raise ValueError('Unknown Supervisor history block')
            key = (message['role'], block.get('type'))
            if key not in FIELDS or set(block) != FIELDS[key]:
                raise ValueError('Unknown Supervisor history block fields')
            if key == ('assistant', 'tool_use'):
                ident = block['id']
                if not isinstance(ident, str) or not ident or ident in calls or not isinstance(block['input'], dict):
                    raise ValueError('Malformed or duplicate historical tool call')
                calls[ident] = (mi, bi)
            elif key == ('user', 'tool_result'):
                ident = block['tool_use_id']
                if (not isinstance(ident, str) or ident not in calls or ident in results
                        or calls[ident] >= (mi, bi) or not isinstance(block['content'], str)):
                    raise ValueError('Unmatched historical tool result')
                results.add(ident)
            elif key[1] == 'text' and not isinstance(block['text'], str):
                raise ValueError('Malformed historical text')
    if set(calls) != results:
        raise ValueError('Unclosed historical tool exchange')
    return len(calls)


def parse_ledger(text):
    """Decode provider-visible bytes, never the archived source or manifest."""
    raw = text.encode('utf-8')
    if not raw.startswith(PREFIX.encode('utf-8')):
        raise ValueError('Root record prefix mismatch')
    pos, rows = len(PREFIX.encode('utf-8')), []
    while pos < len(raw):
        end = raw.find(b'\n', pos)
        if end < 0:
            raise ValueError('Unterminated root record header')
        parts = raw[pos:end].split(b' ')
        if len(parts) != 3 or parts[0] != b'@RECORD' or not all(x.isdigit() for x in parts[1:]):
            raise ValueError('Ambiguous root record header')
        meta_len, payload_len = map(int, parts[1:])
        start, stop = end + 1, end + 1 + meta_len + payload_len
        if stop > len(raw):
            raise ValueError('Truncated root record')
        meta = json.loads(raw[start:start + meta_len])
        if set(meta) != {'message_index', 'block_index', 'role', 'type', 'payload_key', 'other_fields'}:
            raise ValueError('Root record metadata changed')
        key = meta['payload_key']
        if key != PAYLOAD.get(meta['type']):
            raise ValueError('Root record payload key mismatch')
        payload = raw[start + meta_len:stop]
        value = json.loads(payload) if key == 'input' else payload.decode('utf-8')
        block = dict(meta['other_fields'])
        block[key] = value
        row = (meta['message_index'], meta['block_index'], meta['role'], block)
        if rows and row[:2] <= rows[-1][:2]:
            raise ValueError('Root record order mismatch')
        rows.append(row)
        pos = stop
    return rows


def project(history):
    """Return projected history, mechanical manifest, and exact source bytes."""
    calls = _closed(history)
    source = canonical(history)
    rows, raw = [], bytearray(PREFIX.encode('utf-8'))
    removed = 0
    for mi, message in enumerate(history):
        for bi, block in enumerate(message['content']):
            kind = (message['role'], block['type'])
            row = {'message_index': mi, 'block_index': bi, 'role': message['role'],
                   'type': block['type'], 'source_sha256': digest(canonical(block)),
                   'rule': 'retain' if kind in KEEP else 'remove_early_assistant_text'}
            if kind in REMOVE:
                removed += 1
            else:
                key = PAYLOAD[block['type']]
                payload = canonical(block[key]) if key == 'input' else block[key].encode('utf-8')
                meta = canonical({'message_index': mi, 'block_index': bi,
                                  'role': message['role'], 'type': block['type'],
                                  'payload_key': key,
                                  'other_fields': {k: v for k, v in block.items() if k != key}})
                record = f'@RECORD {len(meta)} {len(payload)}\n'.encode() + meta + payload
                row.update(start=len(raw), length=len(record), sha256=digest(record))
                raw.extend(record)
            rows.append(row)
    manifest = {'source_sha256': digest(source), 'source_items': len(history),
                'tool_pairs': calls, 'removed_blocks': removed, 'rows': rows}
    if not removed:
        manifest.update(applied=False, projected_sha256=digest(source))
        return history, manifest, source
    ledger = raw.decode('utf-8')
    decoded = parse_ledger(ledger)
    retained = [r for r in rows if r['rule'] == 'retain']
    if len(decoded) != len(retained) or any(
            (mi, bi, role) != (r['message_index'], r['block_index'], r['role'])
            or digest(canonical(block)) != r['source_sha256']
            for (mi, bi, role, block), r in zip(decoded, retained)):
        raise ValueError('Root record round-trip mismatch')
    projected = [{'role': 'user', 'content': [{'type': 'text', 'text': ledger}]}]
    manifest.update(applied=True, ledger_sha256=digest(raw),
                    projected_sha256=digest(canonical(projected)),
                    retained_blocks=len(retained))
    return projected, manifest, source
