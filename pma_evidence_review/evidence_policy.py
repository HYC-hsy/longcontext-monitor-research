"""Local citation resolution: source identity precedes textual grounding.

Adapts Sourcecheck's resolve/fetch boundary without its network store or NLI.
Scope is a model judgment, not a deterministic semantic classifier.
"""
import json

from .inputs import require, model_material

POLICY_VERSION = 'source-use-v3'
# Legacy extraction labels are descriptive metadata, never source eligibility gates.
SCOPES = ('execution', 'attempt', 'static_behavior', 'requirement',
          'historical_record', 'agent_statement')


def targets(packet):
    return model_material(packet)['operations']


def context(packet, *, include_sources=False):
    material = model_material(packet)
    result = {k: material[k] for k in ('original_task', 'memory_before', 'limitations')}
    if include_sources:
        # Preserve original event identities/order/field paths and visible slices.
        # No inferred command-result pairing or extra history is introduced.
        result['visible_source_context_not_independent_evidence'] = material['sources']
    return result


def documents(packet, scope=None):
    # scope is accepted only for older callers; never consulted.
    registry = []
    ids = [s['source_id'] for s in packet['sources']]
    require(len(ids) == len(set(ids)), 'citation_duplicate_source_id')
    for source in model_material(packet)['sources']:
        for piece in source['slices']:
            registry.append({**{k: source[k] for k in
                ('source_id', 'role', 'visibility_ref')}, **piece})
    identities = [(d['source_id'], d['start'], d['end']) for d in registry]
    require(len(identities) == len(set(identities)), 'citation_duplicate_document')
    return registry


def formatted(registry):
    return [{'title': json.dumps({k: v for k, v in doc.items() if k != 'text'},
                                ensure_ascii=False), 'text': doc['text']} for doc in registry]


def bind(row, packet, registry, scope=None, locator=None):
    """No fallback search across other identities; never pick a matching role by text."""
    evidence = row['evidence']
    citations = row.get('citations')
    require(isinstance(citations, list) and len(citations) == len(evidence),
            'citation_count_mismatch')
    aligned = []
    for quote, citation in zip(evidence, citations):
        require(isinstance(citation, dict), 'citation_shape')
        index = citation.get('document_index')
        require(type(index) is int and 1 <= index <= len(registry), 'citation_unknown_document')
        doc = registry[index - 1]
        for key in ('source_id', 'role', 'visibility_ref'):
            require(key not in citation or citation[key] == doc[key], 'citation_wrong_' + key)
        start, end = citation.get('start'), citation.get('end')
        if 'start' in citation or 'end' in citation:
            require(type(start) is int and type(end) is int, 'citation_outside_visible_range')
        else:
            position = doc['text'].find(quote)
            require(position >= 0 and doc['text'].find(quote, position + 1) < 0,
                    'citation_ambiguous_or_unmatched')
            start = doc['start'] + position
            end = start + len(quote)
        require(type(start) is int and type(end) is int and
                doc['start'] <= start < end <= doc['end'], 'citation_outside_visible_range')
        require(doc['text'][start-doc['start']:end-doc['start']] == quote,
                'citation_text_mismatch')
        require(locator is not None, 'locator_unavailable')
        source = next(s for s in packet['sources'] if s['source_id'] == doc['source_id'])
        restricted = {**packet, 'sources': [{**source, 'slices': [
            {'start': start, 'end': end, 'text': quote}]}]}
        alignment = locator([quote], restricted)
        require(alignment['status'] == 'exact_unique', 'evidence_not_bound')
        aligned.append({'document_index': index, 'source_id': doc['source_id'],
            'role': doc['role'], 'visibility_ref': doc['visibility_ref'],
            'start': start, 'end': end, 'quote': quote, 'alignment': alignment})
    return {'status': 'exact_unique', 'citations': aligned, 'semantic_proof': False}
