"""Synthetic data only; no real trajectory excerpts or expected real verdicts."""
from pma_evidence_review.inputs import digest


def bundle():
    text = 'The tool ran and the output is green.'
    sources = [('task_instruction', 'initial_user_content', 'Build the tool.'),
               ('tool_command', 'commands/0', 'export PATH=/tool:$PATH; tool'),
               ('tool_observation', 'observation/stdout', 'green'),
               ('memory_derived', 'content', 'Need to check the tool.')]
    import json
    refs, spans, visibility, parts = [], [], [], []
    for i, (role, field, content) in enumerate(sources):
        identity = ['ns', 'memory', 'old'] if role == 'memory_derived' else ['ns', 'public', 'e%d' % i, field]
        refs.append(json.dumps(identity, separators=(',', ':')))
        spans.append([[0, len(content)]])
        visibility.append(None)
        handle = 'm1' if role == 'memory_derived' else 's' + digest(refs[-1])[:12]
        parts.append('\n[%s %s event_order=%d field=%s]\n%s' % (handle, role, i, field, content))
    prompt = ''.join(parts)
    visibility = [digest(json.dumps(['c1', digest(prompt), sid, ranges],
        ensure_ascii=False, separators=(',', ':'))) for sid, ranges in zip(refs, spans)]
    manifest = {'cycle_id': 'c1', 'request_sha256': digest(prompt),
        'ordered_source_refs': refs, 'visible_spans': spans, 'visibility_refs': visibility,
        'pre_cycle_revision_refs': ['old']}
    old = 'Need to check the tool.'
    bank = {'gap_evidence': {'manifests': {'c1': manifest}, 'revisions': {
        'old': {'revision_id': 'old', 'memory_id': 'm1', 'category': 'status',
                'content_sha256': digest(old)},
        'new': {'revision_id': 'new', 'memory_id': 'm1', 'category': 'status',
                'content_sha256': digest(text), 'previous_revision_id': 'old', 'receipt_id': 'r1'}},
        'blobs': {digest(old): old, digest(text): text},
        'receipts': {'r1': {'cycle_id': 'c1', 'op_index': 0}}, 'tombstones': {},
        'active_revisions': {'m1': 'future'}, 'sources': {}, 'status': 'FUTURE'}}
    payload = [{'phase': 'maintenance', 'cycle_step': 1, 'call_sequence': 1, 'prompt': prompt}]
    operations = [{'action': 'update_status', 'memory_id': 'm1', 'content': text, 'success': True}]
    trajectory = {'steps': [{'step_id': 1, 'operations': operations,
        'raw_response_phase2': 'FUTURE', 'should_inject': True, 'context_for_action': 'FUTURE'}]}
    cycles = [{'step': 1, 'sequence': 1, 'evidence_report': {'operations': [
        {'index': 0, 'success': True, 'revision_id': 'new', 'binding_status': 'exact_unique'}]},
        'report': {'actual_phase2_prompt': 'FUTURE'}}]
    return payload, trajectory, cycles, bank


def packet():
    from pma_evidence_review.inputs import build_from_data
    return build_from_data(*bundle(), step=1, cycle_id='c1')


def extraction(two=False):
    import json
    texts = ['The tool ran', 'the output is green'] if two else ['The tool ran']
    return json.dumps({'claims': [{'claim': t, 'original_text':
        'The tool ran and the output is green.', 'op_index': 0, 'kind': 'fact',
        'conditions': ['in this command'], 'dependencies': ['PATH exported']} for t in texts],
        'coverage': [{'op_index': 0, 'status': 'complete', 'reason': 'synthetic mock'}]})


def result(verdict='NOT_ENOUGH_INFO', evidence=None, **kwargs):
    import json
    return json.dumps(dict(verdict=verdict, evidence=evidence or [],
                           explanation='Synthetic mock; no semantic evaluation.', **kwargs))
