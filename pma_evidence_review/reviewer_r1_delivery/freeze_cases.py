"""One-time mechanical freeze of prior v4 split outputs plus predeclared controls.

The existing result path is an input to this archival step only. Runtime comparison
uses FROZEN_CASES.json and never invokes the splitter.
"""
import argparse
import hashlib
import json
from pathlib import Path

from pma_evidence_review.citation_inputs import identity
from pma_evidence_review.inputs import digest
from pma_evidence_review.split_v4_compare import SPEC


def control(case_id, content, quote, role, label, reason):
    operation = {'op_index': 0, 'action': 'save_knowledge',
                 'memory_id': 'control_' + case_id, 'revision_id': 'control_' + case_id,
                 'content': content, 'content_sha256': digest(content)}
    material = {'original_operation': operation, 'normative_requirements_context': '',
                'submitted_evidence': [{'submitted_quote': quote,
                    'alternative_origins': [{'role': role, 'field_path': 'content',
                        'source_id': 'control_source_' + case_id, 'event_order': 1}],
                    'origin_semantics': 'alternative_locations_not_independent_corroboration',
                    'source_identity_origin': 'host_inferred_not_model_selected'}]}
    return {'case_id': case_id, 'origin': {'kind': 'manual_constructed_control'},
            'material': material, 'claims': [content], 'reference_label': label,
            'reference_reason': reason}


def controls():
    requirement = 'The integration test must write audit.json recording each rejected request.'
    receipt = ('The integration test finished. There were three rejected requests; '
               'audit.json contains all three, verified by matching their request IDs.')
    practical = "Retain the document's footnotes where practical."
    verbatim = 'Retain every footnote verbatim.'
    alpha = ("In container alpha, SERVICE_MODE was set to staging and the client's "
             'health request returned OK.')
    beta = ("In container beta, SERVICE_MODE was printed as staging and the client's "
            'health request returned OK.')
    instruction, observation = 'task_instruction', 'tool_observation'
    return [
        control('r1-requirement', 'The task requires the integration test to record each rejected request in audit.json.', requirement, instruction, 'supported', 'The quoted instruction states the requirement.'),
        control('r1-completion-unverified', 'The integration test has recorded each rejected request in audit.json.', requirement, instruction, 'insufficient', 'An instruction does not establish execution.'),
        control('r1-completion-verified', 'The integration test has recorded each rejected request in audit.json.', receipt, observation, 'supported', 'The receipt covers the three rejected requests by ID.'),
        control('r1-practical', 'The task requests retaining footnotes where practical.', practical, instruction, 'supported', 'The instruction retains the practical qualifier.'),
        control('r1-verbatim-overreach', 'The task requires every footnote to be retained verbatim.', practical, instruction, 'insufficient', 'A practical qualifier does not require every footnote verbatim; no contrary outcome is shown.'),
        control('r1-verbatim-supported', 'The task requires every footnote to be retained verbatim.', verbatim, instruction, 'supported', 'The quoted instruction directly states the stronger requirement.'),
        control('r1-alpha', "The client's health request succeeded in container alpha with SERVICE_MODE set to staging.", alpha, observation, 'supported', 'The receipt records this result in alpha.'),
        control('r1-beta-unverified', "The client's health request succeeded in container beta with SERVICE_MODE set to staging.", alpha, observation, 'insufficient', 'An alpha observation does not establish beta.'),
        control('r1-beta-verified', "The client's health request succeeded in container beta with SERVICE_MODE set to staging.", beta, observation, 'supported', 'The receipt records beta with the specified setting; not all containers.'),
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prior-v4-results', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--baseline-out', required=True)
    args = parser.parse_args()
    old_path = Path(args.prior_v4_results)
    old = json.loads(old_path.read_text(encoding='utf-8'))
    spec = json.loads(SPEC.read_text(encoding='utf-8'))
    assert len(old['results']) == len(spec['cases']) == 13
    frozen = []
    baseline_system = old['results'][0]['split']['request']['batch_system']
    for prior, label in zip(old['results'], spec['cases']):
        assert prior['case_id'] == label['case_id']
        assert prior['engineering_status'] == 'ok' and prior['claims']
        assert prior['split']['request']['batch_system'] == baseline_system
        material = prior['split']['request']['closed_material']
        assert identity(material) == prior['material_sha256']
        frozen.append({'case_id': prior['case_id'], 'origin': label['origin'],
                       'parent_input_sha256': prior['parent_input_sha256'],
                       'material': material, 'claims': prior['claims'],
                       'reference_label': label['reference_label'],
                       'reference_reason': label['reference_reason']})
    frozen += controls()
    assert len(frozen) == 22
    output = {'schema': 'pma-v4-reviewer-r1-frozen-cases-v1',
              'source_code_sha': 'be44ce85fd2ec1ce116e34a8683cbcb7a113f35e',
              'prior_results_file_sha256': hashlib.sha256(old_path.read_bytes()).hexdigest(),
              'source_small_samples_sha256': hashlib.sha256(SPEC.read_bytes()).hexdigest(),
              'cases': frozen}
    with Path(args.out).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(output, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    Path(args.baseline_out).write_text(baseline_system, encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
