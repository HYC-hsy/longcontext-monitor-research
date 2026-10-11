"""Mechanical root projection retaining native, closed tool exchanges.

This codec makes no judgment about the usefulness or truth of old content.
The source is returned separately for durable archival before commit.
"""

import copy

from .root_records_v1 import REMOVE, _closed, canonical, digest


def project(history):
    """Return (projected history, source/position manifest, exact source bytes)."""
    pairs = _closed(history)
    source = canonical(history)
    projected, rows, removed_messages = [], [], []
    removed = 0
    for mi, message in enumerate(history):
        kept = []
        projected_index = len(projected)
        for bi, block in enumerate(message['content']):
            drop = (message['role'], block['type']) in REMOVE
            row = {
                'source_message': mi, 'source_block': bi,
                'source_sha256': digest(canonical(block)),
                'rule': 'remove_early_assistant_text' if drop else 'retain_native',
                'projected_message': None if drop else projected_index,
                'projected_block': None if drop else len(kept),
            }
            rows.append(row)
            if drop:
                removed += 1
            else:
                kept.append(copy.deepcopy(block))
        if kept:
            projected.append({'role': message['role'], 'content': kept})
        elif message['role'] == 'assistant':
            removed_messages.append(mi)
        else:
            raise ValueError('Empty non-assistant historical message')
    _closed(projected)
    for row in rows:
        if row['rule'] == 'retain_native':
            target = projected[row['projected_message']]['content'][row['projected_block']]
            if digest(canonical(target)) != row['source_sha256']:
                raise ValueError('Native root record round-trip mismatch')
    projected_raw = canonical(projected)
    return projected, {
        'codec': 'root_records_native_v2', 'source_sha256': digest(source),
        'projected_sha256': digest(projected_raw), 'source_items': len(history),
        'projected_items': len(projected), 'tool_pairs': pairs,
        'removed_blocks': removed, 'removed_messages': removed_messages,
        'applied': bool(removed), 'rows': rows,
    }, source


def _closed_exchange_cuts(history):
    cuts, outstanding = [], set()
    for index, message in enumerate(history):
        blocks = message['content']
        if message['role'] == 'assistant':
            calls = [block['id'] for block in blocks if block['type'] == 'tool_use']
            outstanding.update(calls)
            if not calls and not outstanding:
                cuts.append(index + 1)
        else:
            results = [block for block in blocks if block['type'] == 'tool_result']
            for block in results:
                outstanding.discard(block['tool_use_id'])
            if results and not outstanding:
                cuts.append(index + 1)
    return cuts


def validate_transform(kind, before, after, archive, details):
    """Check that an existing provider transform did only its documented operation."""
    _closed(before)
    _closed(after)
    if kind == 'monitor_tool_payload_archival':
        if len(before) != len(after):
            raise ValueError('Payload archival changed message count')
        changed = 0
        for mi, (old_message, new_message) in enumerate(zip(before, after)):
            if old_message['role'] != new_message['role'] or len(old_message['content']) != len(new_message['content']):
                raise ValueError('Payload archival changed message shape')
            for bi, (old, new) in enumerate(zip(old_message['content'], new_message['content'])):
                if old == new:
                    continue
                if old_message['role'] != 'user' or old['type'] != 'tool_result':
                    raise ValueError('Payload archival changed non-result block')
                value = old['content']
                expected = dict(old, content=(
                    'Large tool result: only beginning/end excerpts are in this context, not the full evidence. '
                    'Use file_read/code_run to inspect the full JSON string at ' + archive
                    + f', JSON location [{mi}].content[{bi}].content (zero-based). '
                    'The omitted middle may contain relevant evidence; excerpts alone cannot establish absence.\n'
                    + value[:2000] + '\n[Middle archived, not shown]\n' + value[-2000:]))
                if len(value.encode('utf-8')) <= 12000 or new != expected:
                    raise ValueError('Payload archival changed invalid result')
                changed += 1
        if changed != details['results_archived']:
            raise ValueError('Payload archival changed count mismatch')
        return
    if kind != 'monitor_history_compaction':
        raise ValueError('Unknown native history transform')
    cut = details.get('cut')
    if type(cut) is not int or cut not in _closed_exchange_cuts(before)[:-1]:
        raise ValueError('Compaction cut splits a tool exchange')
    if len(after) != len(before) - cut + 1 or after[1:] != before[cut:]:
        raise ValueError('Compaction altered retained tail')
    carried = after[0]
    if carried.get('role') != 'user' or len(carried.get('content', [])) != 1:
        raise ValueError('Compaction continuation shape changed')
    text = carried['content'][0].get('text')
    prefix = ('Current working understanding, written after reviewing the retained dialogue below. '
              'It is revisable, not a new task instruction. Full pre-compaction history: '
              + archive + '\n')
    if not isinstance(text, str) or not text.startswith(prefix):
        raise ValueError('Compaction continuation identity changed')
    if digest((text[len(prefix):]).encode('utf-8')) != details['continuation_note_sha256']:
        raise ValueError('Compaction continuation note mismatch')
    if digest(canonical(before[cut:])) != details['tail_sha256']:
        raise ValueError('Compaction tail identity mismatch')
