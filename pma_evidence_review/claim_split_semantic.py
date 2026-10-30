"""Opt-in v4: meaning-preserving decomposition and closed submitted-evidence review.

The host retains B across the split call. No retrieval, semantic acceptance rule,
or extra model role is introduced here.
"""
from copy import deepcopy
from dataclasses import asdict
import json

from . import claim_split_simple as v3
from .citation_inputs import identity
from . import citation_inputs as ci
from .inputs import require

STRATEGY = 'claim-split-same-evidence-v4'

SPLIT_SYSTEM = '''Split the complete original memory operation into an ordered JSON array of
nonempty claim strings. You are decomposing meaning, NOT reviewing evidence or
predicting whether claims can be supported. You will not see evidence.
Split only independently judgeable commitments. Keep tightly related clauses
together when separating them would change their meaning. Carry a shared condition
into every claim it governs. Preserve requirements as requirements, plans as plans,
questions as questions, negation, chronology, quantifiers, scope, causation,
comparison, completion, and the reason for a proposed gap deletion. Do not turn
"if A then B" into "A happened" or "B happened". Do not turn "X happened,
therefore X caused Y" into two unrelated events.

Examples (illustrative, not evidence or answers to the current operation):
Input: "The task requires a report; the report was written."
Output: ["The task requires a report.", "The report was written."]
Input: "If the flag is enabled, the parser rejects empty input."
Output: ["If the flag is enabled, the parser rejects empty input."]
Input: "The patch ran before installation, and that patch caused installation to succeed."
Output: ["The patch ran before installation.", "The patch caused installation to succeed."]
Input: "Some files were copied, so every file is now present."
Output: ["Some files were copied.", "Every file is now present as a result of that copying."]

Return only a nonempty JSON array of nonempty strings, in original order. No IDs,
coordinates, evidence judgments, labels, or extra fields.'''

VERIFY_SYSTEM = v3.BOUNDARY + v3.SUPPORT_SENTENCE + '''
Compare each original claim against the submitted evidence, then give its verdict.
The complete original operation A is also a target: the overall judgment must
detect an omitted or altered commitment, even if every listed claim passes.
Task instructions can establish what was required; an assertion that work was
actually completed needs execution evidence. Preserve condition, time, scope,
negation, quantity, causal and comparison direction. A command or success string
in source code is not its execution receipt. An old gap is target context, not
evidence that it has been resolved. For deletion, judge whether the NEW submitted
evidence supports retiring that specific old gap, not whether it once existed.
Candidate source locations of one quote are alternatives, not independent votes.
A and the claims are targets, never evidence. Use only submitted B; do not retrieve.
Return exactly {"overall":{"verdict":"supported|insufficient|contradicted","reason":"..."},
"results":[{"verdict":"supported|insufficient|contradicted","reason":"..."}]}.
Results must have exactly one entry per claim in the same order. Reasons must be
nonempty. No evidence IDs, claim IDs, coordinates, or extra fields.'''


def split_request(material, index):
    require(index == material['original_operation']['op_index'], 'operation_identity')
    # This is the entire model-visible splitter payload: B is not serialized.
    target = {'original_operation': material['original_operation'],
              'normative_requirements_context': material['normative_requirements_context']}
    request = v3._request(SPLIT_SYSTEM, 'TARGET TO DECOMPOSE (not evidence):\n' +
                          json.dumps(target, ensure_ascii=False),
                          'citation_claim_split', material, STRATEGY)
    request['closed_material'] = deepcopy(material)  # host-only, never sent by transport
    request['batch_system'] = VERIFY_SYSTEM         # host-only, used for second request
    return request


async def split_stage(request, transport):
    return await v3.split_stage(request, transport)


async def review_stage(request, transport, result):
    return await v3.review_stage(request, transport, result)


async def assess(request, transport):
    return await review_stage(request, transport, await split_stage(request, transport))


def deletion_candidate(memory, parts, args, index, *, run_id):
    """Freeze the live gap version and only literal submitted citations.

    Existing gap text is target context, never evidence. Non-exact or malformed
    submissions are not silently upgraded to model insufficiency.
    """
    from gap_evidence_alignment import align_evidence
    from .live_citations import visible_snapshot

    key = args['memory_id']
    kind, old_content = memory._content(key)
    require(kind == 'gap', 'delete_target_not_gap')
    revision = memory.active_revisions.get(key)
    require(isinstance(revision, str) and revision, 'delete_target_revision_missing')
    reason = args['reason']
    alignment = align_evidence(args['evidence'], parts.catalog)
    parent, records = visible_snapshot(parts)
    op = {'op_index': index, 'action': 'delete_gap', 'memory_id': key,
          'revision_id': revision, 'content': reason,
          'content_sha256': ci.old.digest(reason), 'existing_gap': old_content,
          'target_revision_id': revision}
    rows = []
    issues = []
    for item in alignment.items:
        origins = []
        if item.status not in ('exact_unique', 'exact_multiple') or not item.candidates:
            issues.append('binding_' + item.status)
        for ref in item.candidates:
            bound = ci.candidate(asdict(ref), parent, records)
            if bound['original_excerpt'] != item.quote:
                issues.append('quote_differs_from_visible_excerpt')
            origins.append({'role': ref.role, 'field_path': bound['field_path'],
                            'source_id': ref.source_id, 'event_order': ref.order})
        rows.append({'submitted_quote': item.quote, 'alternative_origins': origins,
                     'origin_semantics': 'alternative_locations_not_independent_corroboration',
                     'source_identity_origin': 'host_inferred_not_model_selected'})
    if not rows:
        issues.append('no_evidence')
    material = {'original_operation': op, 'submitted_evidence': rows,
                'normative_requirements_context': ''}
    envelope = {'schema': 'pma-live-gap-deletion-candidate-v1', 'run_id': run_id,
                'cycle_id': parts.manifest.cycle_id,
                'maintenance_request_sha256': parts.manifest.request_sha256,
                'operation': op, 'preparation': {'status': 'ready' if not issues else
                 'citation_set_not_eligible', 'issues': issues, 'citations': rows},
                'host_provenance_sha256': identity(parent),
                'submitted_evidence_sha256': identity(rows)}
    envelope['live_input_sha256'] = identity(envelope)
    request = split_request(material, index) if not issues else None
    return envelope, request
