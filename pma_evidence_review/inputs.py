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


def visible_sources(prompt, manifest, *, allow_python_default_source_ids=False):
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
        canonical = json.dumps(identity, ensure_ascii=False, separators=(',', ':'))
        python_default = json.dumps(identity, ensure_ascii=False)
        require(sid == canonical or (allow_python_default_source_ids and sid == python_default),
                'noncanonical_source_id')
        combined = [span for ref, group in zip(refs, spans) if ref == sid for span in group]
        sealed = json.dumps([manifest['cycle_id'], manifest['request_sha256'], canonical, combined],
                            ensure_ascii=False, separators=(',', ':'))
        require(visibility == digest(sealed), 'visibility_ref_mismatch')
        require(identity[1] in ('public', 'memory'), 'unknown_source_kind')
        if identity[1] == 'public':
            require(identity[-1] == field, 'source_field_mismatch')
            require(handle == 's' + digest(canonical)[:12], 'source_handle_mismatch')
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
    current = {x['memory_id']: x for x in before}
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
            require(item['before'] == current.get(raw['memory_id']), 'deletion_not_current')
            item['category'] = item['before']['category']
            current.pop(raw['memory_id'])
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
            require(item['before'] == current.get(raw['memory_id']), 'previous_revision_not_current')
            item.update(revision_id=rid, category=after['category'], review_scope='written_content')
            allowed_before.add(rid)
            current[raw['memory_id']] = after
        item['content_sha256'] = digest(item['content']) if item['success'] else None
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
    packet['review_input_sha256'] = review_input_identity(packet)
    validate(packet)
    return packet


def model_material(packet):
    """Explicit top-level whitelist; no developer labels or unknown fields serialized."""
    def memory(row):
        return {k: row[k] for k in ('memory_id', 'revision_id', 'category', 'content')}
    operations = []
    for op in packet['operations']:
        row = {k: op[k] for k in ('op_index', 'action', 'memory_id', 'revision_id',
            'content', 'content_sha256', 'category', 'success', 'binding_status', 'review_scope') if k in op}
        row['before'] = memory(op['before']) if op.get('before') else None
        operations.append(row)
    sources = []
    for source in packet['sources']:
        row = {k: source[k] for k in ('source_id', 'handle', 'kind', 'role',
            'event_order', 'field_path', 'visibility_ref')}
        row['slices'] = [{k: part[k] for k in ('start', 'end', 'text')}
                         for part in source['slices']]
        sources.append(row)
    return {'original_task': packet['original_task'],
        'maintenance_prompt': packet['maintenance_prompt'],
        'memory_before': [memory(x) for x in packet['memory_before']],
        'operations': operations, 'sources': sources,
        'limitations': packet['limitations'], 'replay_status': packet['replay_status']}


def review_input_identity(packet):
    """Content identity, not a signature or proof of archive authenticity.

    The maintenance hash binds only the old prompt. This identity additionally
    binds the exact whitelisted model material and its cycle/operation provenance.
    Extra developer annotations excluded by model_material cannot enter requests.
    """
    identity = {k: packet[k] for k in ('schema', 'cycle_id', 'step', 'call_sequence',
        'manifest', 'request_sha256', 'original_request_sha256', 'truncation')}
    identity['model_material'] = model_material(packet)
    return digest(json.dumps(identity, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False, allow_nan=False))


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
    require(isinstance(packet.get('manifest'), dict) and
            packet['manifest'].get('cycle_id') == packet.get('cycle_id') and
            packet['manifest'].get('request_sha256') == packet.get('original_request_sha256'),
            'manifest_identity_mismatch')
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
    before_by_id = {row['memory_id']: row for row in packet['memory_before']}
    require(len(before_by_id) == len(packet['memory_before']), 'duplicate_before_memory')
    indices = []
    for op in packet['operations']:
        require(type(op.get('op_index')) is int, 'operation_index')
        indices.append(op['op_index'])
        require(isinstance(op.get('memory_id'), str) and op['memory_id'], 'memory_id_missing')
        require(isinstance(op.get('action'), str), 'action_missing')
        require(type(op.get('success')) is bool, 'success_missing')
        require(not op['success'] or isinstance(op.get('content'), str) and
                bool(op['content']) and bool(op.get('revision_id')), 'operation_content_missing')
        if op['success']:
            require(op.get('content_sha256') == digest(op['content']), 'operation_content_hash')
            expected_before = before_by_id.get(op['memory_id'])
            require((None if op.get('before') is None else
                     {k: op['before'][k] for k in ('memory_id', 'revision_id', 'category', 'content')}) ==
                    (None if expected_before is None else
                     {k: expected_before[k] for k in ('memory_id', 'revision_id', 'category', 'content')}),
                    'operation_before_mismatch')
            if op['action'].startswith('delete_'):
                require(expected_before is not None and
                        op['revision_id'] == expected_before['revision_id'] and
                        op['content'] == expected_before['content'], 'deletion_revision_mismatch')
                before_by_id.pop(op['memory_id'])
            else:
                before_by_id[op['memory_id']] = {k: op[k] for k in
                    ('memory_id', 'revision_id', 'category', 'content')}
    require(indices == list(range(len(indices))), 'operations_not_ordered')
    require(len(set(indices)) == len(indices), 'duplicate_operation')
    require(packet.get('review_input_sha256') == review_input_identity(packet),
            'review_input_hash_mismatch')
    return packet


def load_indexed(path, files, lines=False):
    entry = only(files, lambda x: x['public'] == path.name, 'indexed_file_missing')
    raw = path.read_bytes()
    require(len(raw) == entry['public_gzip_bytes'] and
            hashlib.sha256(raw).hexdigest() == entry['public_gzip_sha256'], 'public_gzip_hash')
    decoded = gzip.decompress(raw)
    require(hashlib.sha256(decoded).hexdigest() == entry['public_uncompressed_sha256'],
            'public_uncompressed_hash')
    data = [json.loads(line) for line in decoded.splitlines() if line.strip()] if lines else json.loads(decoded)
    return [row['value'] for row in data] if lines else data['value']


def build(repo, sample, *, step=None, cycle_id=None, allow_redacted=False):
    slot, default_step, default_cycle = SAMPLES[sample]
    root = Path(repo) / D / 'source_window_two_real_20261025'
    index = json.loads((root / 'INDEX.json').read_text())
    require(index['executed_code_commit'] == EXECUTED_SHA, 'executed_baseline_mismatch')
    selected = only(index['slots'], lambda x: x.get('task') == slot[3:-3], 'sample_not_indexed')
    path = root / slot
    raw_index = (path / 'INDEX.json').read_bytes()
    require(hashlib.sha256(raw_index).hexdigest() == selected['index_sha256'], 'slot_index_hash')
    files = json.loads(raw_index)['files']
    return build_from_data(load_indexed(path / 'memory_payload.jsonl.gz', files, True),
        load_indexed(path / 'trajectory_memory.json.gz', files),
        load_indexed(path / 'gap_cycle.jsonl.gz', files, True),
        load_indexed(path / 'memory.json.gz', files), step=default_step if step is None else step,
        cycle_id=default_cycle if cycle_id is None else cycle_id, allow_redacted=allow_redacted)
