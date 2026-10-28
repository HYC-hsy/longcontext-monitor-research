"""Closed A+B direct/split comparison, offline by default; never a Task runner."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import re

from . import citation_inputs as ci, citation_review as cr, claim_split as cs
from .__main__ import write
from .inputs import require
from .live_citations import assess
from .prompt_strategy import ONE_SENTENCE, apply_strategy
from .review import json_value
from .transport import CapturedTransport, FakeClient, load_profile_client


def read(path):
    return json_value(Path(path).read_text(encoding='utf-8'))


def materials(input_path=None, trace_fixture=None):
    if input_path is not None:
        packet = ci.validate(read(input_path))
        return [{'op_index': row['operation']['op_index'], 'preparation': row['preparation'],
                 'material': cr.projection(packet, row) if row['preparation']['status'] == 'ready' else None}
                for row in packet['operations']], packet['citation_input_sha256']
    root = Path(__file__).parent / 'claim_split_delivery'
    provenance = read(root / 'PROVENANCE.json')
    path = root / 'TRACE_FIXTURES.json'
    require(hashlib.sha256(path.read_bytes()).hexdigest() ==
            provenance['fixture_file']['sha256_verified'], 'trace_fixture_file_hash')
    fixture = next((r for r in read(path)['fixtures'] if r['fixture_id'] == trace_fixture), None)
    mapping = next((r for r in provenance['fixture_mappings'] if r['fixture_id'] == trace_fixture), None)
    require(fixture is not None and mapping is not None, 'unknown_trace_fixture')
    material = fixture['material']  # NEVER use historical outputs, expectations or wider history.
    require(ci.identity(material) == mapping['material_sha256_canonical'], 'trace_material_hash')
    return [{'op_index': material['original_operation']['op_index'], 'material': material,
             'preparation': {'status': 'ready', 'origin': 'published_sanitized_trace_projection'}}], ci.identity(material)


def initial_request(material, strategy):
    index = material['original_operation']['op_index']
    if strategy == cs.STRATEGY:
        return cs.split_request(material, index)
    require(strategy == ONE_SENTENCE, 'invalid_review_strategy')
    return apply_strategy(cr.request_from_material(material, index), ONE_SENTENCE)


class ConservativeFixture:
    """Dynamic canned responses, not evidence inference or a model effectiveness test."""
    async def call(self, *, prompt, system, tools=None):
        if prompt.startswith('CLOSED MATERIAL'):
            material = json.loads(prompt.split('\n', 1)[1]); op = material['original_operation']
            value = {'op_index': op['op_index'], 'claims': [
                {'claim': op['content'], 'original_text': op['content']}]}
        elif prompt.startswith('TARGET CONTEXT ONLY'):
            target = json.loads(prompt.split('\n', 1)[1].split('\nSUBMITTED EVIDENCE ONLY')[0])
            value = {'results': [{'claim_index': claim['index'], 'verdict': 'insufficient',
                     'evidence_ids': [], 'original_fragment': claim['original_text'],
                     'explanation': 'Canned offline response, not a semantic judgment.'}
                     for claim in target['all_claims']], 'decomposition_complete': True,
                     'coverage_original_fragment': '',
                     'coverage_explanation': 'Canned exact full-content claim for transport testing only.'}
        else:
            target = json.loads(prompt.split('\n', 1)[1].split('\nOUTPUT EXAMPLE')[0])
            value = {'op_index': target['original_operation']['op_index'], 'verdict': 'insufficient',
                     'explanation': 'Canned offline response, not a semantic judgment.'}
        return type('Response', (), {'content': json.dumps(value), 'tool_calls': []})()


async def run(rows, strategy, transport):
    results, stopped = [], False
    for row in rows:
        result = {'op_index': row['op_index'], 'preparation': row['preparation'], 'verdict': None,
                  'engineering_status': 'not_reviewed_preparation'}
        results.append(result)
        if row['material'] is None:
            continue
        if stopped:
            result['engineering_status'] = 'not_run_after_engineering_error'
            continue
        request = initial_request(row['material'], strategy)
        result.update(request=request, **await assess(request, transport))
        stopped = result['engineering_status'] != 'ok'
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('export', 'fake', 'run-profile'))
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--input', help='Existing frozen submitted-citation packet, strictly validated')
    source.add_argument('--trace-fixture', choices=('sqlite_call_19', 'sqlite_call_61'))
    parser.add_argument('--strategy', choices=(ONE_SENTENCE, cs.STRATEGY), default=cs.STRATEGY)
    parser.add_argument('--out', required=True, help='New file for export; new directory for execution')
    parser.add_argument('--responses', help='Fake only: JSON array of exact raw response strings, in call order')
    parser.add_argument('--repo', default='.')
    parser.add_argument('--profile')
    parser.add_argument('--profile-key', default='claude_monitor_opus48')
    parser.add_argument('--execute-authorized-real-model', action='store_true')
    args = parser.parse_args(argv)
    if args.responses and args.command != 'fake':
        parser.error('--responses is only valid with fake')
    if args.command == 'run-profile' and (not args.profile or not args.execute_authorized_real_model):
        parser.error('No request sent. Separate model authorization, profile and explicit flag required.')
    rows, input_sha = materials(args.input, args.trace_fixture)
    plan = {'strategy': args.strategy, 'input_sha256': input_sha,
            'verification_requests': 'one_batch_after_validated_split' if args.strategy == cs.STRATEGY else 'direct_only',
            'initial_requests': [{'op_index': row['op_index'], 'preparation': row['preparation'],
                'request': initial_request(row['material'], args.strategy) if row['material'] else None} for row in rows]}
    if args.command == 'export':
        write(args.out, plan)
        return
    responses = read(args.responses) if args.responses else None
    if responses is not None:
        require(isinstance(responses, list) and all(isinstance(r, str) for r in responses), 'fake_responses_schema')
    out = Path(args.out); out.mkdir(parents=True, exist_ok=False, mode=0o700)
    write(out / 'initial-plan.json', plan)
    if args.command == 'fake':
        client = FakeClient(responses) if responses is not None else ConservativeFixture()
    else:
        client = load_profile_client(args.repo, args.profile, args.profile_key,
                                     out / 'private_client', authorized=True)
    transport = CapturedTransport(client, out, fake=args.command == 'fake')
    results = asyncio.run(run(rows, args.strategy, transport))
    report = {'strategy': args.strategy, 'input_sha256': input_sha, 'results': results,
              'client_calls': transport.calls, 'fake': transport.fake, 'memory_mutated': False,
              'semantic_effectiveness': 'not_evaluated',
              'network_calls': 0 if transport.fake else 'not_measured_at_client_boundary'}
    if responses is not None and len(responses) != transport.calls:
        report['response_count_mismatch'] = True
    write(out / 'report.json', report)
    print(json.dumps({'report': str(out / 'report.json'), 'client_calls': transport.calls}))
    if report.get('response_count_mismatch') or any(row['engineering_status'] not in
            ('ok', 'not_reviewed_preparation') for row in results):
        raise SystemExit('Review engineering failure; raw captures/report retained. No retry or publication.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        code = str(error) if isinstance(error, ValueError) and re.fullmatch(r'[a-z0-9_]+', str(error)) else type(error).__name__
        raise SystemExit('Closed review failed (' + code + '); inspect private validated inputs/captures.')
