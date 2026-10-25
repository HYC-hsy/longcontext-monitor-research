"""Whitelist projection of a frozen maintenance cycle, never a final bank replay."""
from __future__ import annotations

import gzip
import hashlib
import json
import re
from pathlib import Path

ARCHIVE_SHA = '72152913f545ca36a75b68e8796e24a6e24f9f81'
EXECUTED_SHA = '90a4eb7a77ed6c05101fda7a929cd5cf609bf626'
D = Path('method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013')
SAMPLES = {'sqlite': ('01-sqlite-with-gcov-r1', 14,
    'cycle_fbce65422ff14eeb82b3879bc5fd25fa'),
    'html': ('02-filter-js-from-html-r1', 2,
    'cycle_76e8f85e13394b84a2bdea40ec901c2c')}
HEADER = re.compile(r'\n\[([^\s\]]+) ([^\s\]]+) event_order=(\d+) field=([^\]]+)\]\n')


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def require(condition, code):
    if not condition:
        raise ValueError(code)


def load(path, lines=False):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        data = [json.loads(line) for line in stream if line.strip()] if lines else json.load(stream)
    return [row['value'] for row in data] if lines else data['value']


def only(rows, predicate, code):
    found = [row for row in rows if predicate(row)]
    require(len(found) == 1, code)
    return found[0]


def revision(store, rid):
    rev = store['revisions'].get(rid)
    require(isinstance(rev, dict) and rev['revision_id'] == rid, 'missing_revision')
    content = store['blobs'].get(rev['content_sha256'])
    require(isinstance(content, str), 'missing_revision_content')
    require(digest(content) == rev['content_sha256'], 'revision_hash_mismatch')
    return {'memory_id': rev['memory_id'], 'revision_id': rid,
            'category': rev['category'], 'content': content}


def visible_sources(prompt, manifest):
    """Use manifest lengths, not final retained sources or a global regex split.

    Header-like text inside a tool result cannot create an extra evidence source.
    Offsets stay in original source coordinates; only visible slices are retained.
    """
    refs, spans, vis = (manifest[k] for k in
        ('ordered_source_refs', 'visible_spans', 'visibility_refs'))
    require(len(refs) == len(spans) == len(vis), 'manifest_array_mismatch')
    cursor, sources = 0, []
    for sid, ranges, visibility in zip(refs, spans, vis):
        header = HEADER.search(prompt, cursor)
        require(header is not None, 'missing_source_header')
        handle, role, order, field = header.groups()
        identity = json.loads(sid)
        require(identity[1] in ('public', 'memory'), 'unknown_source_kind')
        if identity[1] == 'public':
            require(identity[-1] == field, 'source_field_mismatch')
        cursor = header.end()
        slices = []
        for number, pair in enumerate(ranges):
            require(len(pair) == 2 and all(type(v) is int for v in pair), 'invalid_span')
            start, end = pair
            require(0 <= start < end, 'invalid_span')
            if number:
                require(prompt[cursor:cursor + 14] == '\n[hidden gap]\n', 'hidden_gap_mismatch')
                cursor += 14
            text = prompt[cursor:cursor + end - start]
            require(len(text) == end - start, 'truncated_source')
            slices.append({'start': start, 'end': end, 'text': text})
            cursor += end - start
        sources.append({'source_id': sid, 'handle': handle, 'kind': identity[1],
            'role': role, 'event_order': int(order), 'field_path': field,
            'visibility_ref': visibility, 'slices': slices})
    require(not HEADER.search(prompt, cursor), 'unmapped_source_header')
    return sources


def build_from_data(payloads, trajectory, cycles, bank, *, step, cycle_id,
                    allow_redacted=False):
    payload = only(payloads, lambda x: x.get('phase') == 'maintenance'
                   and x.get('cycle_step') == step, 'maintenance_missing_or_ambiguous')
    recorded = only(trajectory['steps'], lambda x: x.get('step_id') == step,
                    'trajectory_step_missing_or_ambiguous')
    cycle = only(cycles, lambda x: x.get('step') == step, 'cycle_missing_or_ambiguous')
    require(cycle['sequence'] == payload['call_sequence'], 'sequence_mismatch')
    store = bank['gap_evidence']
    manifest = store['manifests'].get(cycle_id)
    require(manifest is not None and manifest['cycle_id'] == cycle_id, 'missing_manifest')
    prompt = payload['prompt']
    exact = digest(prompt) == manifest['request_sha256']
    limitations = []
    if not exact:
        require(allow_redacted, 'request_hash_mismatch_replay_refused')
        limitations.append('redacted_or_changed_replay_not_original_equivalent')
    if '[REDACTED]' in prompt:
        limitations.append('public_input_contains_redactions')
    if re.search(r'\[(?:hidden gap|omitted|truncated)[^\]]*\]|<omitted>', prompt, re.I):
        limitations.append('original_prompt_contains_explicit_omission_markers')
    sources = visible_sources(prompt, manifest) if exact else []
    if not exact:
        limitations.append('source_coordinates_unavailable_after_hash_mismatch')
    before = [revision(store, rid) for rid in manifest['pre_cycle_revision_refs']]
    # Cross-check identities, never consult active_revisions or final status.
    for old in before:
        require(old['content'] in prompt, 'historical_memory_not_fully_visible')
    allowed_before = {x['revision_id'] for x in before}
    operations = []
    evidence_ops = cycle['evidence_report']['operations']
    require(len(evidence_ops) == len(recorded['operations']), 'operation_count_mismatch')
    for index, raw in enumerate(recorded['operations']):
        aligned = only(evidence_ops, lambda x: x.get('index') == index,
                       'operation_alignment_missing')
        require(raw['success'] == aligned['success'], 'operation_success_mismatch')
        item = {k: raw[k] for k in ('action', 'memory_id', 'content', 'success')}
        item.update(op_index=index, revision_id=None, before=None,
                    binding_status=aligned.get('binding_status', 'not_applicable'))
        if not raw['success']:
            limitations.append('failed_operation_%s' % index)
        elif raw['action'].startswith('delete_'):
            tomb = only(store['tombstones'].values(), lambda x:
                x['cycle_id'] == cycle_id and x['op_index'] == index
                and x['memory_id'] == raw['memory_id'], 'missing_deletion_tombstone')
            require(tomb['revision_id'] in allowed_before, 'deletion_not_visible_before')
            item['before'] = revision(store, tomb['revision_id'])
            item['revision_id'] = tomb['revision_id']
            item['content'] = item['before']['content']
            item['review_scope'] = 'justification_for_deleting_this_item_not_asserting_it_true'
        else:
            rid = aligned.get('revision_id')
            after = revision(store, rid)
            require(after['memory_id'] == raw['memory_id'] and
                    after['content'] == raw['content'], 'operation_revision_mismatch')
            receipt_id = store['revisions'][rid].get('receipt_id')
            if receipt_id:
                receipt = store['receipts'][receipt_id]
                require(receipt['cycle_id'] == cycle_id and receipt['op_index'] == index,
                        'receipt_cycle_mismatch')
            else:
                association = bank['gap_alignment']['alignments'][rid]
                require(association['cycle_id'] == cycle_id and
                        association['revision_id'] == rid, 'alignment_cycle_mismatch')
            previous = store['revisions'][rid].get('previous_revision_id')
            if previous:
                require(previous in allowed_before, 'previous_revision_not_visible')
                item['before'] = revision(store, previous)
            item.update(revision_id=rid, review_scope='written_content')
        operations.append(item)
    task_sources = [s for s in sources if s['role'] == 'task_instruction']
    require(task_sources or not exact, 'original_task_missing')
    packet = {'schema': 'pma-evidence-review-input-v1', 'cycle_id': cycle_id,
        'step': step, 'call_sequence': payload['call_sequence'],
        'original_task': '\n'.join(p['text'] for s in task_sources for p in s['slices']),
        'maintenance_prompt': prompt, 'request_sha256': digest(prompt),
        'manifest': {k: manifest[k] for k in ('cycle_id', 'request_sha256',
            'ordered_source_refs', 'visible_spans', 'visibility_refs', 'pre_cycle_revision_refs')},
        'original_request_sha256': manifest['request_sha256'],
        'replay_status': 'exact_public_prompt' if exact else 'degraded_replay',
        'memory_before': before, 'operations': operations, 'sources': sources,
        'limitations': limitations, 'truncation': 'none_added_by_builder'}
    validate(packet)
    return packet


def validate(packet):
    require(packet.get('schema') == 'pma-evidence-review-input-v1', 'input_schema')
    require(isinstance(packet.get('maintenance_prompt'), str) and
            bool(packet['maintenance_prompt']), 'maintenance_prompt_empty')
    require(digest(packet['maintenance_prompt']) == packet.get('request_sha256'), 'input_hash')
    require(packet.get('replay_status') in ('exact_public_prompt', 'degraded_replay'), 'replay_status')
    require(isinstance(packet.get('limitations'), list), 'limitations_missing')
    require(isinstance(packet.get('sources'), list), 'sources_missing')
    require(isinstance(packet.get('memory_before'), list), 'memory_before_missing')
    require(isinstance(packet.get('original_task'), str), 'original_task_missing')
    if packet['replay_status'] == 'exact_public_prompt':
        manifest = packet.get('manifest')
        require(isinstance(manifest, dict) and manifest.get('request_sha256') ==
                packet['request_sha256'], 'manifest_hash')
        require(visible_sources(packet['maintenance_prompt'], manifest) == packet['sources'],
                'sources_not_from_visible_prompt')
        require([r['revision_id'] for r in packet['memory_before']] ==
                manifest['pre_cycle_revision_refs'], 'before_revision_manifest_mismatch')
        expected_task = '\n'.join(part['text'] for source in packet['sources']
            if source['role'] == 'task_instruction' for part in source['slices'])
        require(packet['original_task'] == expected_task and bool(expected_task), 'task_not_visible')
        for old in packet['memory_before']:
            matching = [source for source in packet['sources'] if source['kind'] == 'memory'
                        and json.loads(source['source_id'])[-1] == old['revision_id']]
            require(len(matching) == 1 and matching[0]['slices'] == [
                {'start': 0, 'end': len(old['content']), 'text': old['content']}],
                'historical_memory_not_fully_visible')
    else:
        require(packet['limitations'] and not packet['sources'], 'degraded_sources_untrusted')
    require(isinstance(packet.get('operations'), list) and packet['operations'], 'operations_empty')
    indices = []
    for op in packet['operations']:
        require(type(op.get('op_index')) is int, 'operation_index')
        indices.append(op['op_index'])
        require(isinstance(op.get('memory_id'), str) and op['memory_id'], 'memory_id_missing')
        require(isinstance(op.get('action'), str), 'action_missing')
        require(type(op.get('success')) is bool, 'success_missing')
        require(not op['success'] or isinstance(op.get('content'), str) and
                bool(op['content']) and bool(op.get('revision_id')), 'operation_content_missing')
    require(len(set(indices)) == len(indices), 'duplicate_operation')
    return packet


def build(repo, sample, *, step=None, cycle_id=None, allow_redacted=False):
    slot, default_step, default_cycle = SAMPLES[sample]
    root = Path(repo) / D / 'source_window_two_real_20261025'
    index = json.loads((root / 'INDEX.json').read_text())
    require(index['executed_code_commit'] == EXECUTED_SHA, 'executed_baseline_mismatch')
    require(any(x.get('task') == slot[3:-3] for x in index['slots']), 'sample_not_indexed')
    path = root / slot
    return build_from_data(load(path / 'memory_payload.jsonl.gz', True),
        load(path / 'trajectory_memory.json.gz'), load(path / 'gap_cycle.jsonl.gz', True),
        load(path / 'memory.json.gz'), step=default_step if step is None else step,
        cycle_id=default_cycle if cycle_id is None else cycle_id, allow_redacted=allow_redacted)
