"""Local citation resolution: source identity precedes textual grounding.

Adapts Sourcecheck's resolve/fetch boundary without its network store or NLI.
Scope is a model judgment, not a deterministic semantic classifier.
"""
import json

from .inputs import require, model_material

POLICY_VERSION = 'source-use-v2'
SCOPES = {
    'execution': {'tool_observation'},
    'attempt': {'tool_command'},
    'static_behavior': {'tool_command', 'tool_observation'},
    'requirement': {'task_instruction'},
    'historical_record': {'memory_derived'},
    'agent_statement': {'agent_report'},
}


def targets(packet):
    return model_material(packet)['operations']


def context(packet):
    material = model_material(packet)
    return {k: material[k] for k in ('original_task', 'memory_before', 'limitations')}


def documents(packet, scope):
    require(scope in SCOPES, 'unknown_evidence_scope')
    registry = []
    for source in model_material(packet)['sources']:
        if source['role'] not in SCOPES[scope]:
            continue
        for piece in source['slices']:
            registry.append({**{k: source[k] for k in
                ('source_id', 'role', 'visibility_ref')}, **piece})
    return registry


def formatted(registry):
    return [{'title': json.dumps({k: v for k, v in doc.items() if k != 'text'},
                                ensure_ascii=False), 'text': doc['text']} for doc in registry]


def bind(row, packet, registry, scope, locator):
    """No fallback search across other identities; never pick a matching role by text."""
    evidence = row['evidence']
    citations = row.get('citations')
    if citations is None:
        # Upstream document_index binds only FIRST quote. Safe only for one quote.
        require(len(evidence) == 1 and type(row.get('document_index')) is int,
                'citation_missing')
        citations = [{'document_index': row['document_index']}]
    require(isinstance(citations, list) and len(citations) == len(evidence),
            'citation_count_mismatch')
    if row.get('document_index') is not None and citations:
        require(isinstance(citations[0], dict) and
                row['document_index'] == citations[0].get('document_index'),
                'citation_first_document_conflict')
    aligned = []
    for quote, citation in zip(evidence, citations):
        require(isinstance(citation, dict), 'citation_shape')
        index = citation.get('document_index')
        require(type(index) is int and 0 <= index < len(registry), 'citation_unknown_document')
        doc = registry[index]
        for key in ('source_id', 'role', 'visibility_ref'):
            require(key not in citation or citation[key] == doc[key], 'citation_wrong_' + key)
        require(doc['role'] in SCOPES[scope], 'citation_use_not_permitted')
        start, end = citation.get('start'), citation.get('end')
        if start is None and end is None:
            require(doc['text'].count(quote) == 1, 'citation_ambiguous_or_unmatched')
            start = doc['start'] + doc['text'].index(quote)
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
