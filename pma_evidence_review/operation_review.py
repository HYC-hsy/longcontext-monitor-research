"""Direct operation audit: no model extraction, rewriting, or target classification."""
import json

from . import evidence_policy as policy
from .inputs import validate, require, digest
from .review import SYSTEM as LEGACY_SYSTEM, json_value, VERDICTS
from .transport import ResponseProtocolError
from .vendor.rag_models import EvidenceSpan
from .vendor.rag_prompts import format_documents

SYSTEM = LEGACY_SYSTEM.replace(
    'You audit evidence support of proposed memory changes, not task completion.',
    'You audit evidence support of complete memory operations, including every task '
    'completion assertion in their content. You do not replace Task execution or '
    'official evaluation.')
STRATEGY = 'direct-operation-v4.1'
SCHEMA = 'pma-operation-review-report-v2'
ACTIONS = {'save_knowledge', 'save_procedural', 'save_gap', 'update_status',
           'delete_knowledge', 'delete_procedural', 'delete_gap', 'delete_status'}
DELETE_QUESTION = 'Is there sufficient visible evidence to justify deleting this exact entry?'
WRITE_QUESTION = 'Is the complete content of this memory operation supported by the visible evidence?'
CONTRACT = '''
OPERATION AUDIT INSTRUCTIONS
Use evidence-first reasoning: first identify relevant verbatim source passages,
then compare them against the complete operation, then decide its verdict.
Audit the complete original operation, not a selected fragment or a rewritten claim.
SUPPORTED requires support for ALL judgments requiring evidence in that operation.
If only part is supported, identify the unsupported portion in explanation and return
NOT_ENOUGH_INFO; if a material assertion is contradicted, return CONTRADICTED and
identify it. Do not let a correct subfact establish the entire operation.
For deletion the fixed question is whether deleting the exact before/target is justified.
The old entry is the object being deleted, not a factual claim to verify. Evidence that
an old gap once existed is NOT a reason to delete it. Resolution, valid replacement or
redundancy or obsolescence may justify deletion only when visible evidence establishes that reason.
Do not invent task requirements or demand unrelated proof.
Plans, questions and hypotheses are not automatically false. Explain any nonfactual
parts and audit their factual premises without inventing a classification field. If no
factual judgment can be substantiated, return NOT_ENOUGH_INFO and explain this limit.
Source Documents are the only citable sources. Targets/context are not independent
proof. Task instructions establish requirements, commands establish attempts or narrow
static code behavior, receipts establish observations, and old memory/self-reports
establish what was recorded/claimed. Interpret receipts with original command arguments,
session conditions, PATH exports and visible event identities. Do not turn file creation
into complete functionality or a local success into cross-session success.
Return one JSON object with exactly op_index, verdict, explanation, evidence.
verdict: SUPPORTED, CONTRADICTED or NOT_ENOUGH_INFO. explanation: specific reasons.
evidence: an array of objects, each containing document_index and quote. Use the
displayed one-based Document N and one contiguous verbatim passage. Never stitch or
paraphrase passages. Multiple quotes use multiple entries. Only for repeated text in
that document, optionally give exact original-source start/end together. No invented
source IDs or additional top-level fields.
No evidence means NOT_ENOUGH_INFO. Do not execute commands or modify memories.
'''


def disposition(op):
    if not op['success']:
        return 'not_reviewed_failed_operation'
    if op['action'] not in ACTIONS:
        return 'not_reviewed_unknown_action'
    return None


def target(op):
    return {'question': DELETE_QUESTION if op['action'].startswith('delete_') else WRITE_QUESTION,
            'original_operation': op}


def operation_requests(packet):
    """Stable one-to-one targets; skipped operations stay explicit in exported plans."""
    validate(packet)
    registry = policy.documents(packet)
    docs = policy.formatted(registry)
    budget = max(sum(len(doc['text']) for doc in docs), 1)
    plans = []
    for op in policy.targets(packet):
        plan = {'op_index': op['op_index'], 'target': target(op),
                'engineering_status': disposition(op) or 'ready', 'request': None}
        if disposition(op) is None:
            prompt = CONTRACT + '\nSource Documents:\n'
            prompt += format_documents(docs, max_total_chars=budget, max_chars_per_doc=budget)
            prompt += '\nOPERATION TARGET (not evidence):\n'
            prompt += json.dumps(plan['target'], ensure_ascii=False)
            prompt += '\nINTERPRETIVE CONTEXT (not independent proof):\n'
            prompt += json.dumps(policy.context(packet, include_sources=True), ensure_ascii=False)
            example = {'op_index': op['op_index'], 'verdict': 'NOT_ENOUGH_INFO',
                'explanation': 'Explain the specific unsupported portions or missing evidence.',
                'evidence': []}
            prompt += ('\nOUTPUT EXAMPLE (shape only; decide the verdict from evidence):\n' +
                       json.dumps(example, ensure_ascii=False))
            payload = {'system': SYSTEM, 'prompt': prompt, 'tools': None}
            identity = digest(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                         separators=(',', ':')))
            plan['request'] = {'phase': 'verify_operation', **payload,
                'audit_request_sha256': identity, 'evidence_policy': policy.POLICY_VERSION,
                'review_strategy': STRATEGY, 'op_index': op['op_index'],
                'citation_registry': registry}
        plans.append(plan)
    return plans


def parse_operation(data, op_index):
    """Strict v3 verdict/evidence parsing adapted to operation identity, without Claim."""
    require(isinstance(data, dict), 'result_shape')
    require(type(data.get('op_index')) is int and data['op_index'] == op_index,
            'unknown_operation_index')
    require(set(data) == {'op_index', 'verdict', 'explanation', 'evidence'}, 'operation_result_fields')
    verdict = data['verdict']
    require(isinstance(verdict, str) and verdict.lower() in VERDICTS, 'invalid_verdict')
    evidence = data['evidence']
    require(isinstance(evidence, list) and all(isinstance(q, dict) and
        isinstance(q.get('quote'), str) and q['quote'].strip() and
        type(q.get('document_index')) is int and
        set(q) <= {'quote', 'document_index', 'start', 'end'} for q in evidence), 'invalid_evidence')
    require(isinstance(data['explanation'], str) and data['explanation'].strip(), 'missing_explanation')
    require(VERDICTS[verdict.lower()] == 'insufficient' or evidence,
            'decisive_verdict_without_evidence')
    return {'verdict': VERDICTS[verdict.lower()], 'explanation': data['explanation'],
            'evidence': [q['quote'] for q in evidence],
            'citations': [{k: v for k, v in q.items() if k != 'quote'} for q in evidence]}


async def review(packet, transport, *, locator=None):
    plans = operation_requests(packet)
    report = {'schema': SCHEMA, 'review_strategy': STRATEGY,
        'evidence_policy': policy.POLICY_VERSION, 'cycle_id': packet['cycle_id'],
        'request_sha256': packet['request_sha256'],
        'review_input_sha256': packet['review_input_sha256'], 'results': [],
        'audit_request_sha256s': [], 'limitations': packet['limitations'],
        'semantic_effectiveness': 'not_evaluated', 'memory_mutated': False}
    for plan in plans:
        op = plan['target']['original_operation']
        row = {k: op.get(k) for k in ('op_index', 'memory_id', 'revision_id', 'action', 'content_sha256')}
        row.update(target=plan['target'], verdict=None, model_verdict=None,
                   raw_response=None, engineering_status=plan['engineering_status'])
        report['results'].append(row)
        req = plan['request']
        if req is None:
            continue
        row['audit_request_sha256'] = req['audit_request_sha256']
        report['audit_request_sha256s'].append(req['audit_request_sha256'])
        await execute_request(packet, transport, req, row, locator)
    return report


async def execute_request(packet, transport, req, row, locator):
    """Shared parsing/binding/capture for one host-bound target; mutates only row."""
    try:
        row['raw_response'] = await transport.send(req)
    except ResponseProtocolError as error:
        row.update(engineering_status='protocol_error', reason=error.code,
                   raw_response=error.raw_response, error_type=type(error).__name__)
        try:
            data = json_value(error.raw_response)
            if isinstance(data, dict):
                row['model_verdict'] = data.get('verdict')
        except (ValueError, TypeError):
            pass
        return
    except Exception as error:
        row.update(engineering_status='call_error', error_type=type(error).__name__)
        return
    try:
        data = json_value(row['raw_response'])
        if isinstance(data, dict):
            row['model_verdict'] = data.get('verdict')
        row.update(parse_operation(data, row['op_index']))
    except (ValueError, TypeError, KeyError) as error:
        row.update(engineering_status='parse_failure', reason=str(error), verdict=None)
        return
    try:
        if row['evidence']:
            row['alignment'] = policy.bind(row, packet, req['citation_registry'], locator=locator)
            # Reuse upstream EvidenceSpan with its zero-based internal index, then
            # explicitly translate to v3's one-based public protocol.
            spans = []
            for citation in row['alignment']['citations']:
                span = EvidenceSpan(citation['quote'], citation['start'], citation['end'],
                                    citation['document_index'] - 1).to_dict()
                span['document_index'] += 1
                spans.append(span)
            row['evidence_spans'] = spans
        row['engineering_status'] = 'ok'
    except Exception as error:
        row.update(verdict=None, engineering_status=str(error) if isinstance(error, ValueError)
                   else 'alignment_error', error_type=type(error).__name__)
