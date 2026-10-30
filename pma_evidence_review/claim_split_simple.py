"""Simple ordered split + one closed batch review; v2 remains unchanged.

Adapts the RAG batch reconstruction using retained MIT model/formatter code.
No retrieval, span matching, model IDs, claim cap, or implicit positive verdict.
"""
from copy import deepcopy
import json

from .citation_inputs import identity
from .citation_review import SYSTEM as DIRECT_SYSTEM
from .claim_split import _call
from .inputs import require
from .review import json_value
from .prompt_strategy import SUPPORT_SENTENCE
from .vendor.rag_models import VerificationResult
from .vendor.rag_prompts import format_documents

STRATEGY = 'claim-split-same-evidence-v3'
BOUNDARY = DIRECT_SYSTEM.split('Return only one JSON object with exactly')[0].replace(
    'Only the E-numbered\nsubmitted quotes', 'Only the submitted quotes')
SPLIT_SYSTEM = BOUNDARY + '''
Split ORIGINAL OPERATION A into an ordered list of complete claim strings.
Preserve all important commitments, including completion, relationships, conditions,
negation, chronology, quantifiers, requirements as requirements and plans as plans.
Do not weaken a completion assertion into a report that completion was claimed.
A is the review target, never evidence. Missing evidence must not change extraction.
Return only a nonempty JSON array of nonempty strings. No IDs, original_text,
character offsets, kind taxonomy or extra fields. Do not silently cap the list.'''
VERIFY_SYSTEM = BOUNDARY + SUPPORT_SENTENCE + '''
Review the ordered claims together in ONE batch using only the displayed submitted B.
Also judge whether B supports the COMPLETE original operation A, not merely the subset
chosen by the splitter. Important omitted completion/relational commitments must not
pass because all listed claims pass. This is a semantic judgment, not a literal
character-coverage check: headings such as Step 1 need not be copied into claims.
A and the claim list are targets, NOT evidence. No retrieval or unquoted neighbors.
Alternative origins are possible locations of ONE submitted quotation, not independent
corroboration. Preserve role differences: a command containing a success string is not
stdout proving success; ambiguous provenance must not be silently promoted to stdout.
Return exactly {"overall":{"verdict":"supported|insufficient|contradicted","reason":"..."},
"results":[{"verdict":"supported|insufficient|contradicted","reason":"..."}]}.
results must have exactly one entry per claim IN THE SAME ORDER. Every reason must be
nonempty and briefly explain the evidence limits or support. No evidence IDs, claim IDs,
claim text echoes, coordinates or extra fields. Overall supported never overrides an
insufficient or contradicted claim. No replacement operation or extra review phase.'''


def projection(packet, row):
    """Closed quote groups with all actual matched provenance, never extra source text."""
    op = row['operation']
    evidence = []
    for item in row['preparation']['citations']:
        origins = []
        for bound in item['candidates']:
            ref = bound['reference']
            origins.append({'role': ref['role'], 'field_path': bound['field_path'],
                            'source_id': ref['source_id'], 'event_order': ref['order']})
        evidence.append({'submitted_quote': item['submitted_quote'],
                         'alternative_origins': origins,
                         'origin_semantics': 'alternative_locations_not_independent_corroboration',
                         'source_identity_origin': 'host_inferred_not_model_selected'})
    return {'original_operation': {k: op[k] for k in
            ('op_index', 'action', 'memory_id', 'revision_id', 'content', 'content_sha256')},
            'submitted_evidence': evidence,
            'normative_requirements_context': packet['normative_context']}


def _request(system, prompt, phase, material, strategy=STRATEGY):
    payload = {'system': system, 'prompt': prompt, 'tools': None}
    return {**payload, 'phase': phase,
            'op_index': material['original_operation']['op_index'],
            'review_strategy': strategy, 'evidence_policy': 'submitted-literal-only-v1',
            'audit_request_sha256': identity(payload)}


def split_request(material, index):
    require(index == material['original_operation']['op_index'], 'operation_identity')
    request = _request(SPLIT_SYSTEM, 'CLOSED MATERIAL (A is not evidence):\n' +
                       json.dumps(material, ensure_ascii=False), 'citation_claim_split', material)
    request['closed_material'] = deepcopy(material)
    return request


def parse_split(raw):
    claims = json_value(raw)
    require(isinstance(claims, list) and bool(claims), 'split_empty_or_shape')
    require(all(isinstance(c, str) and c.strip() for c in claims), 'split_claim_type_or_empty')
    return claims


def verification_request(material, claims, *, system=VERIFY_SYSTEM, strategy=STRATEGY):
    documents = [json.dumps(e, ensure_ascii=False) for e in material['submitted_evidence']]
    # Execute the retained upstream formatter with a complete-corpus budget: no cuts.
    budget = sum(map(len, documents)) + 1
    body = format_documents(documents, max_chars_per_doc=budget, max_total_chars=budget)
    context = {'original_operation': material['original_operation'], 'claims': claims,
               'normative_requirements_context': material['normative_requirements_context']}
    request = _request(system, 'TARGET CONTEXT ONLY (not evidence):\n' +
        json.dumps(context, ensure_ascii=False) + '\nSUBMITTED EVIDENCE ONLY (unchanged B):\n' +
        body, 'citation_claim_verify_batch', material, strategy)
    request['submitted_evidence_sha256'] = identity(material['submitted_evidence'])
    return request


def _verdict(row):
    require(isinstance(row, dict) and set(row) == {'verdict', 'reason'}, 'verdict_schema')
    require(isinstance(row['verdict'], str) and
            row['verdict'] in ('supported', 'insufficient', 'contradicted'), 'invalid_verdict')
    require(isinstance(row['reason'], str) and row['reason'].strip(), 'missing_reason')
    return row


def parse_batch(raw, claims):
    data = json_value(raw)
    require(isinstance(data, dict) and set(data) == {'overall', 'results'}, 'batch_schema')
    overall = _verdict(data['overall'])
    rows = data['results']
    require(isinstance(rows, list) and len(rows) == len(claims), 'batch_cardinality')
    reviews = []
    for index, (claim, row) in enumerate(zip(claims, rows)):
        _verdict(row)
        # Retained RAG result container, reconstructed only after exact cardinality.
        result = VerificationResult(claim=claim, claim_index=index, verdict=row['verdict'],
                                    confidence=0, explanation=row['reason'])
        reviews.append({'claim': result.claim, 'verdict': result.verdict,
                        'reason': result.explanation})
    verdicts = [overall['verdict']] + [r['verdict'] for r in reviews]
    verdict = ('contradicted' if 'contradicted' in verdicts else
               'insufficient' if 'insufficient' in verdicts else 'supported')
    return reviews, overall, verdict


async def split_stage(request, transport):
    result = {'verdict': None, 'model_verdict': None, 'claims': [], 'claim_reviews': []}
    split = await _call(request, transport)
    result.update(split=split, raw_response=split['raw_response'],
                  engineering_status=split['engineering_status'])
    if split['engineering_status'] != 'received':
        return result
    try:
        result['claims'] = parse_split(split['raw_response'])
        split['engineering_status'] = 'ok'
        result['engineering_status'] = 'split_ready'
    except (ValueError, TypeError, KeyError) as error:
        split.update(engineering_status='parse_failure', reason=str(error))
        result.update(engineering_status='parse_failure', reason=str(error))
    return result


async def review_stage(request, transport, result):
    if result['engineering_status'] != 'split_ready':
        return result
    material = deepcopy(request['closed_material'])
    batch = await _call(verification_request(material, result['claims'],
        system=request.get('batch_system', VERIFY_SYSTEM),
        strategy=request.get('review_strategy', STRATEGY)), transport)
    result['batch'] = batch
    if batch['engineering_status'] != 'received':
        result.update(engineering_status=batch['engineering_status'],
                      reason=batch.get('reason', batch.get('error_type')))
        return result
    try:
        reviews, overall, verdict = parse_batch(batch['raw_response'], result['claims'])
        batch['engineering_status'] = 'ok'
        feedback = {'original_operation': material['original_operation'], 'claims': reviews,
                    'overall': overall, 'submitted_evidence': material['submitted_evidence']}
        result.update(claim_reviews=reviews, overall=overall, verdict=verdict,
                      model_verdict=overall['verdict'], engineering_status='ok',
                      explanation=overall['reason'], repair_feedback=feedback)
    except (ValueError, TypeError, KeyError) as error:
        batch.update(engineering_status='parse_failure', reason=str(error))
        result.update(engineering_status='parse_failure', reason=str(error))
    return result


async def assess(request, transport):
    return await review_stage(request, transport, await split_stage(request, transport))
