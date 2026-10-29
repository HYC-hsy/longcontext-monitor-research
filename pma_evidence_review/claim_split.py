"""Opt-in atomic reviews of one operation with one frozen submitted evidence set.

RAG ClaimExtractor/_to_claim_objects and indexed verification flow adapted here;
MIT source/license details: claim_split_delivery/REUSE.md. No retrieval or writes.
"""
from copy import deepcopy
from dataclasses import asdict
import json

from .citation_inputs import identity
from .citation_review import SYSTEM as DIRECT_SYSTEM
from .inputs import require
from .prompt_strategy import SUPPORT_SENTENCE
from .review import json_value
from .transport import ResponseProtocolError
from .vendor.rag_models import Claim, Span, VerificationResult
from .vendor.rag_span_union import merge_overlapping_spans
from .vendor.rag_prompts import (format_claim_verification_batch_prompt,
    CLAIM_VERIFICATION_BATCH_SYSTEM)

STRATEGY = 'claim-split-same-evidence-v2'
# Reuse closed-source discipline, replacing only the direct output contract.
BOUNDARY = DIRECT_SYSTEM.split('Return only one JSON object with exactly')[0]
SPLIT_SYSTEM = BOUNDARY + '''\nSplit the ORIGINAL OPERATION, not the evidence, into separately verifiable
claims. Do not let missing evidence decide what to extract. Preserve EVERY commitment,
including requirements as requirements, observations as observations, plans, hypotheses,
open questions, negation, quantifiers, timing, conditions, dependencies, and completion
or gap-resolution assertions. Never convert a requirement/question into an accomplished
fact, or a completion assertion into a report that someone claimed completion.
Split independent assertions joined by 'and'. Retain shared conditions in every claim
that needs them. No kind taxonomy. Include relational/overall commitments, not just local
accomplishments. Full original A is target context, never a source. B is fixed by host.
For each claim copy an exact original_text substring. The host locates it if unique.
Only if repeated, supply BOTH start (inclusive) / end (exclusive) Python Unicode character
offsets to disambiguate; otherwise omit both. Overlapping spans and distinct
claims from the SAME span are allowed. Cover the complete original meaning, including
headings, conditions and completion. Uncovered original characters are recorded verbatim
by the host for the batch preservation check; never assume they are meaningless.
Return exactly {"op_index":0,"claims":[{"claim":"...","original_text":"..."}]}. Optional start/end must be paired. No source IDs, evidence edits, operation edits, or extra fields.
Do not truncate or silently cap claims. An empty/incomplete split blocks publication.'''
VERIFY_SYSTEM = BOUNDARY.replace('support its complete original content',
    'support each identified claim').replace('scope in the original operation.',
    'scope in the identified claim.') + SUPPORT_SENTENCE + '''\nReview ALL listed claims together against exactly the ONE displayed E-numbered
submitted evidence package B. For every claim identify relevant E IDs, compare meaning
and scope, and return its verdict. The analysis/commit unit remains ONE original
operation: do not ask for or initiate a separate call per claim. No cross-operation batch.
Do not retrieve, add, paraphrase or replace evidence. Original A and ALL split claims
are TARGET CONTEXT ONLY, not evidence. Every claim uses the SAME B displayed once.
Also inspect the WHOLE decomposition against A: does it preserve every commitment,
including completion, relationships, modality, negation, timing and shared conditions?
Exact span coverage is only structural: a claim can cover a full span but omit meaning.
Set decomposition_complete=false if anything is dropped, strengthened, weakened, or
transformed from a requirement/question into an accomplished fact. This global judgment
is required even if every listed claim alone is supported. Never trust the splitter's
apparent completeness or a previous review. No extra model phase or per-claim requests.
Return one JSON object with exactly results, decomposition_complete, coverage_explanation.
results must contain exactly one object for EVERY supplied claim_index (no missing,
duplicate, unknown or extra IDs), each with exactly claim_index, verdict, evidence_ids,
explanation. The host attaches the verified original_text for author feedback; do not
re-copy it or count coordinates. Explain unsupported
commitments in the original operation's language and their specific evidence limits;
never require the author to resolve internal claim IDs. Do not call a broad original span
wholly supported just because a narrow proposition is supported. Verdict is supported, contradicted or insufficient; supported/contradicted
require at least one existing E ID. No new quotes, sources or fields. Unsupported is NOT
supported. decomposition_complete is a Boolean. When true, coverage_explanation may
be empty. When false, coverage_explanation must give a specific omission/transformation
in A in original language; the host anchors global feedback to the complete immutable A.
Do not return coverage_original_fragment. No rewritten replacement text.
Inspect uncovered_original_spans without ignoring punctuation, operators, negation,
conditions, chronology or completion. They are diagnostics, not automatically new claims
or proof of incompleteness. Preservation concerns A: B need not be exhaustively copied
into A. Information present only in B is not a missing commitment of A.
Missing or later evidence does not contradict an earlier scoped observation. Preserve
open questions and plans; lack of an answer is not proof the premise is false.
The host requires ALL claims supported AND valid coverage; never average or majority vote.'''


def _request(system, prompt, phase, index):
    payload = {'system': system, 'prompt': prompt, 'tools': None}
    return {**payload, 'phase': phase, 'op_index': index, 'review_strategy': STRATEGY,
            'evidence_policy': 'submitted-literal-only-v1',
            'audit_request_sha256': identity(payload)}


def split_request(material, index):
    system = SPLIT_SYSTEM.replace('"op_index":0', '"op_index":' + str(index))
    request = _request(system, 'CLOSED MATERIAL (A is not evidence):\n' +
                       json.dumps(material, ensure_ascii=False), 'citation_claim_split', index)
    request['closed_material'] = deepcopy(material)
    return request


def parse_split(raw, index, content):
    """Adapt RAG _to_claim_objects, but reject ambiguity, duplicates and omissions."""
    data = json_value(raw)
    require(isinstance(data, dict) and set(data) == {'op_index', 'claims'}, 'split_schema')
    require(type(data['op_index']) is int and data['op_index'] == index, 'unknown_operation_index')
    require(isinstance(data['claims'], list) and data['claims'], 'split_empty')
    claims, identities, covered = [], set(), set()
    offset_corrections = []
    for i, item in enumerate(data['claims']):
        require(isinstance(item, dict) and {'claim', 'original_text'} <= set(item)
                and set(item) <= {'claim', 'original_text', 'start', 'end'}, 'split_claim_schema')
        text, original = item['claim'], item['original_text']
        require(isinstance(text, str) and text.strip() and isinstance(original, str)
                and original.strip(), 'split_empty_claim')
        require(('start' in item) == ('end' in item), 'split_offset_pair')
        first = content.find(original)
        require(first >= 0, 'split_invalid_span')
        unique = content.find(original, first + 1) < 0
        if 'start' in item:
            require(type(item['start']) is int and type(item['end']) is int, 'split_invalid_span')
        if unique:
            start, end = first, first + len(original)
            if 'start' in item and (item['start'], item['end']) != (start, end):
                offset_corrections.append({'claim_index': i + 1,
                    'supplied': [item['start'], item['end']], 'resolved': [start, end],
                    'method': 'unique_exact_original_text'})
        else:
            require('start' in item, 'split_ambiguous_span')
            start, end = item['start'], item['end']
        require(0 <= start < end <= len(content) and content[start:end] == original,
                'split_invalid_span')
        key = (text.strip(), start, end)
        require(key not in identities, 'split_duplicate_claim')
        identities.add(key)
        claims.append(Claim(text=text, index=i + 1, original_text=original, span=Span(start, end)))
        covered.update(range(start, end))
    required = {i for i, char in enumerate(content) if not char.isspace()}
    require(required, 'split_empty')
    diagnostic = coverage_diagnostic(claims, content)
    diagnostic['offset_corrections'] = offset_corrections
    return claims, diagnostic


def coverage_diagnostic(claims, content):
    union = merge_overlapping_spans([(c.span.start, c.span.end) for c in claims], max_gap=0)
    gaps = []
    cursor = 0
    for start, end in union + [(len(content), len(content))]:
        if cursor < start:
            gaps.append({'start': cursor, 'end': start, 'text': content[cursor:start]})
        cursor = end
    required = sum(not c.isspace() for c in content)
    missing = sum(not c.isspace() for g in gaps for c in g['text'])
    return {'status': 'structural_full' if missing == 0 else 'structural_gaps',
            'required_characters': required, 'covered_required_characters': required - missing,
            'uncovered_original_spans': gaps,
            'limitation': 'Exact anchors and character diagnostics do not prove semantic completeness.'}


def verification_request(material, claims):
    context = {key: deepcopy(value) for key, value in material.items() if key != 'submitted_evidence'}
    context.update(all_claims=[asdict(c) for c in claims],
        uncovered_original_spans=coverage_diagnostic(claims, material['original_operation']['content'])['uncovered_original_spans'])
    documents = [{'title': item['evidence_id'], 'text': json.dumps(item, ensure_ascii=False)}
                 for item in material['submitted_evidence']]
    budget = max(1, sum(len(doc['text']) for doc in documents))
    # Execute upstream indexed batch/document formatter, but replace its incompatible
    # factual-only/quote-output contract, not append a second competing schema.
    formatted = format_claim_verification_batch_prompt(
        [(c.index, json.dumps(c.text, ensure_ascii=False)) for c in claims], documents,
        max_chars_per_doc=budget, max_docs_chars=budget)
    prefix = CLAIM_VERIFICATION_BATCH_SYSTEM + '\n\n'
    suffix = '\n\nReturn a JSON array with one object per claim.'
    require(formatted.startswith(prefix) and formatted.endswith(suffix), 'batch_template_contract')
    body = formatted[len(prefix):-len(suffix)]
    marker = '\nClaims to verify:\n'
    require(body.count(marker) == 1, 'batch_target_section')
    body = body.replace(marker, '\nTARGET CLAIMS TO VERIFY (not evidence):\n', 1)
    prompt = 'TARGET CONTEXT ONLY (not evidence):\n' + json.dumps(context, ensure_ascii=False)
    prompt += '\nSUBMITTED EVIDENCE ONLY (unchanged B):\n' + body
    example = {'results': [{'claim_index': c.index, 'verdict': 'insufficient',
               'evidence_ids': [],
               'explanation': 'Explain this original portion and its specific evidence limits.'} for c in claims],
               'decomposition_complete': False, 'coverage_explanation': 'Identify what was omitted or changed in A.'}
    prompt += '\nOUTPUT EXAMPLE (shape and IDs only):\n' + json.dumps(example)
    request = _request(VERIFY_SYSTEM, prompt, 'citation_claim_verify_batch', material['original_operation']['op_index'])
    request.update(submitted_evidence_sha256=identity(material['submitted_evidence']))
    return request


def parse_batch(raw, claims, evidence, original_content):
    """RAG _single_batch_verify indexed reconstruction, strict before dict mapping."""
    data = json_value(raw)
    require(isinstance(data, dict) and {'results', 'decomposition_complete', 'coverage_explanation'} <= set(data)
            and set(data) <= {'results', 'decomposition_complete', 'coverage_explanation', 'coverage_original_fragment'}, 'batch_result_schema')
    require(type(data['decomposition_complete']) is bool, 'decomposition_complete_type')
    require(isinstance(data['coverage_explanation'], str) and
            (data['decomposition_complete'] or data['coverage_explanation'].strip()),
            'missing_coverage_explanation')
    # Legacy redundant echoes are never authoritative identity or semantic evidence.
    supplied = data.get('coverage_original_fragment', '')
    require(isinstance(supplied, str), 'invalid_coverage_fragment')
    fragment = '' if data['decomposition_complete'] else original_content
    if not data['decomposition_complete'] and supplied.strip() and supplied in original_content:
        fragment = supplied
    rows = data['results']
    require(isinstance(rows, list), 'batch_results_shape')
    expected = {c.index for c in claims}
    ids = [row.get('claim_index') if isinstance(row, dict) else None for row in rows]
    require(all(type(i) is int and i in expected for i in ids), 'unknown_claim_index')
    require(len(ids) == len(set(ids)), 'duplicate_claim_index')
    require(set(ids) == expected, 'missing_claim_result')
    parsed = {row['claim_index']: row for row in rows}
    available = {item['evidence_id'] for item in evidence}
    results = []
    for claim in claims:
        row = parsed[claim.index]
        require({'claim_index', 'verdict', 'evidence_ids', 'explanation'} <= set(row) and
                set(row) <= {'claim_index', 'verdict', 'evidence_ids', 'explanation', 'original_fragment'}, 'claim_result_schema')
        require(row['verdict'] in ('supported', 'contradicted', 'insufficient'), 'invalid_verdict')
        refs = row['evidence_ids']
        require(isinstance(refs, list) and all(isinstance(i, str) and i in available for i in refs),
                'unknown_evidence_id')
        require(len(refs) == len(set(refs)), 'duplicate_evidence_id')
        require(row['verdict'] == 'insufficient' or refs, 'decisive_verdict_without_evidence')
        require(isinstance(row['explanation'], str) and row['explanation'].strip(), 'missing_explanation')
        supplied = row.get('original_fragment', '')
        require(isinstance(supplied, str), 'invalid_feedback_fragment')
        fragment_for_claim = supplied if supplied.strip() and supplied in claim.original_text else claim.original_text
        result = VerificationResult(claim=claim.text, claim_index=claim.index,
            verdict=row['verdict'], confidence=0, explanation=row['explanation'])
        results.append({'claim_index': result.claim_index, 'verdict': result.verdict,
                        'explanation': result.explanation, 'original_fragment': fragment_for_claim,
                        'evidence_ids': refs, 'engineering_status': 'ok'})
    return results, {'decomposition_complete': data['decomposition_complete'],
                     'coverage_explanation': data['coverage_explanation'], 'coverage_original_fragment': fragment}


def aggregate(claims, coverage, reviews, preservation):
    """Exact cardinality and unanimous support, never a score or majority."""
    require(claims and coverage.get('status') in ('structural_full', 'structural_gaps'), 'aggregate_coverage')
    require([r.get('claim_index') for r in reviews] == [c.index for c in claims], 'aggregate_claim_alignment')
    require(all(r.get('engineering_status') == 'ok' for r in reviews), 'aggregate_review_failure')
    complete = preservation['decomposition_complete'] is True
    supported = all(r['verdict'] == 'supported' for r in reviews)
    verdict = 'supported' if complete and supported else ('contradicted' if complete and
        any(r['verdict'] == 'contradicted' for r in reviews) else 'insufficient')
    issues = [f"Original text “{r['original_fragment']}”: {r['explanation']}" for r in reviews if r['verdict'] != 'supported']
    if not complete:
        issues.append('Original text “' + preservation['coverage_original_fragment'] + '”: ' +
                      preservation['coverage_explanation'])
    return {'engineering_status': 'ok', 'verdict': verdict,
            'explanation': '; '.join(issues) if issues else 'Every claim supported; exact anchors valid and batch semantic preservation confirmed (fallible model judgment).'}


async def _call(request, transport):
    row = {'request': deepcopy(request), 'raw_response': None, 'engineering_status': 'received'}
    try:
        row['raw_response'] = await transport.send(deepcopy(request))
    except ResponseProtocolError as error:
        row.update(engineering_status='protocol_error', reason=error.code, raw_response=error.raw_response)
    except Exception as error:
        row.update(engineering_status='call_error', error_type=type(error).__name__)
    return row


async def assess(request, transport):
    material = deepcopy(request['closed_material'])
    result = {'verdict': None, 'model_verdict': None, 'claims': [], 'claim_reviews': []}
    split = await _call(request, transport)
    result.update(split=split, raw_response=split['raw_response'], engineering_status=split['engineering_status'])
    if split['engineering_status'] != 'received':
        return result
    try:
        claims, coverage = parse_split(split['raw_response'], request['op_index'], material['original_operation']['content'])
        split['engineering_status'] = 'ok'
        result.update(claims=[asdict(c) for c in claims], coverage=coverage)
    except (ValueError, TypeError, KeyError) as error:
        split.update(engineering_status='parse_failure', reason=str(error))
        result.update(engineering_status='parse_failure', reason=str(error))
        return result
    batch = await _call(verification_request(material, claims), transport)
    result['batch'] = batch
    if batch['engineering_status'] != 'received':
        result.update(engineering_status=batch['engineering_status'], reason=batch.get('reason', batch.get('error_type')))
        return result
    try:
        reviews, preservation = parse_batch(batch['raw_response'], claims, material['submitted_evidence'],
                                             material['original_operation']['content'])
        batch['engineering_status'] = 'ok'
        result.update(claim_reviews=reviews, preservation=preservation)
        result.update(aggregate(claims, coverage, reviews, preservation))
    except (ValueError, TypeError, KeyError) as error:
        batch.update(engineering_status='parse_failure', reason=str(error))
        result.update(engineering_status='parse_failure', reason=str(error))
    return result


def validate_attempt(attempt):
    """Offline certificate replay. Rebuild exact requests; never trust saved pass flags."""
    from .citation_review import projection
    envelope = attempt['input']
    material = projection(envelope, {'operation': envelope['operation'], 'preparation': envelope['preparation']})
    request = split_request(material, envelope['operation']['op_index'])
    require(attempt['request'] == request == attempt['split']['request'], 'split_request_identity')
    require(attempt['split']['engineering_status'] == 'ok', 'split_saved_status')
    require(attempt['raw_response'] == attempt['split']['raw_response'], 'split_saved_raw')
    claims, coverage = parse_split(attempt['split']['raw_response'], request['op_index'], material['original_operation']['content'])
    require(attempt['claims'] == [asdict(c) for c in claims] and attempt['coverage'] == coverage, 'split_saved_claims')
    batch = attempt['batch']
    require(batch['engineering_status'] == 'ok', 'batch_saved_status')
    require(batch['request'] == verification_request(material, claims), 'batch_request_identity')
    reviews, preservation = parse_batch(batch['raw_response'], claims, material['submitted_evidence'],
                                             material['original_operation']['content'])
    require(reviews == attempt['claim_reviews'] and preservation == attempt['preservation'], 'batch_saved_result')
    expected = aggregate(claims, coverage, reviews, preservation)
    require(all(attempt.get(key) == value for key, value in expected.items()), 'split_saved_aggregate')
    return expected


def audit_calls(attempt):
    """Exactly split then ONE batch call per original operation, after strict replay."""
    validate_attempt(attempt)
    return [(row['request'], row['raw_response']) for row in (attempt['split'], attempt['batch'])]
