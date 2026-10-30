"""Small frozen development A/B over submitted quotations; never runs a Task.

Export is offline. run-profile requires a separate future real-model authorization.
The program does not choose samples or alter reference labels after a response.
"""
import argparse
import asyncio
import json
from pathlib import Path

from .benchmark import core
from .citation_inputs import identity
from .inputs import digest
from .claim_split_cli import materials as trace_materials
from . import claim_split_simple as v3, claim_split_semantic as v4
from .transport import CapturedTransport, load_profile_client

MANIFEST_SHA256 = 'dcadeb1fabe2c2518307e8763ea5f6118688027394e514b575ce07d4fe482928'
SPEC = Path(__file__).parent / 'split_v4_delivery' / 'SMALL_SAMPLES.json'
STRATEGIES = {v3.STRATEGY: v3, v4.STRATEGY: v4}


def _material(value):
    material = value['material']
    evidence = []
    for row in material['submitted_evidence']:
        if 'alternative_origins' in row:
            evidence.append(row)
        else:
            evidence.append({'submitted_quote': row['submitted_quote'],
                'alternative_origins': [{'role': row['role'],
                    'field_path': row['field_path'], 'source_id': row['source_id'],
                    'event_order': row['event_order']}],
                'origin_semantics': 'alternative_locations_not_independent_corroboration',
                'source_identity_origin': 'host_inferred_not_model_selected'})
    operation = dict(material['original_operation'])
    operation.setdefault('content_sha256', digest(operation['content']))
    return {'original_operation': operation,
            'submitted_evidence': evidence,
            'normative_requirements_context': material['normative_requirements_context']}


def cases(dataset):
    spec = json.loads(SPEC.read_text(encoding='utf-8'))
    frozen = {c['sample_id']: c for c in
              core.load_dataset(dataset, MANIFEST_SHA256)['cases.json']}
    result = []
    for row in spec['cases']:
        origin = row['origin']
        if origin['kind'] == 'frozen_29':
            source = frozen[origin['sample_id']]
            material = _material(source)
            parent = source['benchmark_input_sha256']
        elif origin['kind'] == 'historical_trace_fixture':
            trace, parent = trace_materials(trace_fixture=origin['fixture_id'])
            material = _material(trace[0])
        else:
            material = _material(row)
            parent = identity(material)
        result.append({'case_id': row['case_id'], 'origin': origin,
                       'parent_input_sha256': parent, 'material': material})
    return result


def plan(dataset, strategy):
    module = STRATEGIES[strategy]
    entries = []
    for row in cases(dataset):
        material = row['material']
        delete_na = strategy == v3.STRATEGY and material['original_operation']['action']=='delete_gap'
        request = None if delete_na else module.split_request(material, material['original_operation']['op_index'])
        # Request metadata holds frozen B for the host's second call; the splitter
        # client receives only prompt/system/tools, which omit B in v4.
        entries.append({'case_id': row['case_id'], 'origin': row['origin'],
                        'parent_input_sha256': row['parent_input_sha256'],
                        'material_sha256': identity(material), 'initial_request': request,
                        'preparation': 'not_applicable_delete_v3' if delete_na else 'ready'})
    value = {'schema': 'pma-split-small-comparison-plan-v1', 'strategy': strategy,
             'dataset_manifest_sha256': MANIFEST_SHA256, 'entries': entries}
    value['plan_sha256'] = identity(value)
    return value


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        file.write('\n')


async def run(value, transport):
    module = STRATEGIES[value['strategy']]
    results = []
    stopped = False
    for entry in value['entries']:
        row = {'case_id': entry['case_id'], 'parent_input_sha256': entry['parent_input_sha256'],
               'material_sha256': entry['material_sha256'], 'strategy': value['strategy'],
               'plan_sha256': value['plan_sha256']}
        if entry['preparation'] == 'not_applicable_delete_v3':
            row.update(engineering_status='not_applicable_delete_v3', verdict=None)
        elif stopped:
            row.update(engineering_status='not_run_after_engineering_error', verdict=None)
        else:
            result = await module.assess(entry['initial_request'], transport)
            row.update(result)
            stopped = result['engineering_status'] != 'ok'
        results.append(row)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('export', 'run-profile', 'score'))
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--strategy', choices=tuple(STRATEGIES), required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--repo', default='.')
    parser.add_argument('--profile')
    parser.add_argument('--profile-key', default='claude_monitor_opus48')
    parser.add_argument('--results')
    parser.add_argument('--execute-authorized-real-model', action='store_true')
    args = parser.parse_args()
    frozen = plan(args.dataset, args.strategy)
    if args.command == 'export':
        write(args.out, frozen)
        return
    if args.command == 'score':
        report = json.loads(Path(args.results).read_text(encoding='utf-8'))
        labels = {r['case_id']: r for r in json.loads(SPEC.read_text(encoding='utf-8'))['cases']}
        entries = {r['case_id']: r for r in frozen['entries']}
        if report['plan_sha256'] != frozen['plan_sha256']:
            raise ValueError('plan_identity_mismatch')
        scored = []
        for row in report['results']:
            entry = entries[row['case_id']]
            if (row['parent_input_sha256'], row['material_sha256']) != (
                    entry['parent_input_sha256'], entry['material_sha256']):
                raise ValueError('case_identity_mismatch')
            scored.append({'case_id': row['case_id'], 'reference_label': labels[row['case_id']]['reference_label'],
                           'reference_reason': labels[row['case_id']]['reference_reason'],
                           'model_verdict': row.get('model_verdict'), 'formal_verdict': row.get('verdict'),
                           'engineering_status': row['engineering_status'],
                           'agreement': (None if row['engineering_status']=='not_applicable_delete_v3'
                                         else row['engineering_status']=='ok' and
                                         row.get('verdict')==labels[row['case_id']]['reference_label'])})
        write(args.out, {'schema':'pma-split-small-comparison-score-v1',
                         'strategy':args.strategy,'plan_sha256':frozen['plan_sha256'],
                         'development_only':True,'results':scored})
        return
    if not args.execute_authorized_real_model or not args.profile:
        raise ValueError('explicit_real_model_authorization_and_profile_required')
    out = Path(args.out); out.mkdir(parents=True, exist_ok=False)
    write(out / 'plan.json', frozen)
    client = load_profile_client(args.repo,args.profile,args.profile_key,
                                 out / 'private_client',authorized=True)
    transport = CapturedTransport(client,out,fake=False)
    results = asyncio.run(run(frozen,transport))
    write(out / 'results.json', {'schema':'pma-split-small-comparison-results-v1',
        'strategy':args.strategy,'plan_sha256':frozen['plan_sha256'], 'results':results})
    if any(row['engineering_status'] not in ('ok','not_applicable_delete_v3') for row in results):
        raise SystemExit('Engineering failure; preserve captured records, do not rerun automatically.')


if __name__ == '__main__':
    main()
