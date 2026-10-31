"""Three frozen reviewer-only calls; never invokes splitter, Task or evaluator."""
import argparse
import asyncio
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

from pma_evidence_review import claim_split_semantic as reviewer
from pma_evidence_review.citation_inputs import identity
from pma_evidence_review.transport import CapturedTransport, load_profile_client


HERE = Path(__file__).resolve().parent
SOURCE_SHA = '48babf4302563bbe6e8f0d47e8c617d041a392b1'


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n',
                    encoding='utf-8')


def sha_file(path):
    return sha256(path.read_bytes()).hexdigest()


def prepared_cases():
    source = read_json(HERE / 'historical_path_material.json')
    spec = read_json(HERE / 'frozen_replay_cases.json')
    out = []
    for item in spec['cases']:
        material = deepcopy(source['material'])
        if isinstance(item['original_operation'], dict):
            material['original_operation'] = deepcopy(item['original_operation'])
        claims = source['claims'] if isinstance(item['claims'], str) else item['claims']
        before = ({'content': source['material']['original_operation']['existing_gap']}
                  if item['operation_kind'] == 'delete' else item['before_entry'])
        request = {'closed_material': material,
                   'audit_operation_kind': item['operation_kind'],
                   'audit_before_entry': before}
        batch, model_request = reviewer.audit_request(request, claims)
        out.append({'id': item['id'], 'origin': item['origin'],
                    'reference_verdict': item['reference_verdict'],
                    'reference_reason': item['reference_reason'],
                    'material': material, 'claims': claims, 'request': request,
                    'batch_request_id': batch.request_id,
                    'model_request': model_request})
    assert len(out) == 3
    assert len({identity(row['material']['submitted_evidence']) for row in out}) == 1
    return out


async def run(args):
    root = Path(args.repo).resolve()
    output = Path(args.out).resolve()
    if output.exists():
        raise ValueError('output_must_not_exist')
    checkout = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    if checkout == SOURCE_SHA:
        raise ValueError('integration_checkout_is_uncommitted_baseline')
    output.mkdir(parents=True)
    cases = prepared_cases()
    save_json(output / 'frozen_inputs_and_plan.json', [
        {k: v for k, v in row.items() if k not in ('reference_verdict', 'reference_reason')}
        for row in cases])
    save_json(output / 'reference_labels_development_only.json', [
        {k: row[k] for k in ('id', 'origin', 'reference_verdict', 'reference_reason')}
        for row in cases])
    profile = read_json(Path(args.profile))[args.profile_key]
    safe_keys = ('provider', 'api_mode', 'model', 'thinking_type', 'temperature',
                 'reasoning_effort', 'max_tokens', 'read_timeout')
    safe_profile = {key: profile.get(key, 'default/unknown') for key in safe_keys}
    if safe_profile['model'] != 'claude-opus-4-8':
        raise ValueError('unexpected_model_identity')
    save_json(output / 'run_identity.json', {
        'checkout_sha': checkout, 'production_parent_sha': SOURCE_SHA,
        'profile_key': args.profile_key, 'safe_profile_fields': safe_profile,
        'historical_fixture_sha256': sha_file(HERE / 'historical_path_material.json'),
        'frozen_cases_sha256': sha_file(HERE / 'frozen_replay_cases.json'),
        'review_strategy': reviewer.STRATEGY,
        'request_sha256': [row['model_request']['audit_request_sha256'] for row in cases],
        'system_sha256': [sha256(row['model_request']['system'].encode()).hexdigest()
                          for row in cases]})
    client = load_profile_client(root, args.profile, args.profile_key, output / 'private_client',
                                 authorized=True)
    transport = CapturedTransport(client, output)
    results = []
    for row in cases:
        try:
            result = await reviewer.review_stage(row['request'], transport,
                {'engineering_status': 'split_ready', 'claims': row['claims']})
            results.append({'id': row['id'], 'origin': row['origin'],
                            'result': result, 'client_calls_so_far': transport.calls})
            save_json(output / 'results.json', results)
            if result['engineering_status'] != 'ok':
                break
        except Exception as error:
            results.append({'id': row['id'], 'origin': row['origin'],
                            'engineering_status': 'exception',
                            'error_type': type(error).__name__,
                            'client_calls_so_far': transport.calls})
            save_json(output / 'results.json', results)
            break
    save_json(output / 'stop_state.json', {'completed_cases': len(results),
        'expected_cases': len(cases), 'client_calls': transport.calls,
        'unrun_ids': [case['id'] for case in cases[len(results):]],
        'stopped_on_engineering_error': bool(results and
            results[-1].get('engineering_status', results[-1].get('result', {}).get('engineering_status')) != 'ok')})
    return 0 if len(results) == len(cases) and not read_json(output / 'stop_state.json')['stopped_on_engineering_error'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--profile-key', default='claude_monitor_opus48')
    parser.add_argument('--out', required=True)
    sys.exit(asyncio.run(run(parser.parse_args())))
