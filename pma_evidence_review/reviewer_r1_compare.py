"""Frozen reviewer-only v4 prompt comparison; no splitting, Task, or evaluation.

Export is offline. A later real run needs an explicit execution flag and profile.
Reference labels are read only by score, never by export or run-profile.
"""
import argparse
import asyncio
import hashlib
import inspect
import json
from pathlib import Path
import re
import subprocess

from . import claim_split_semantic as v4, claim_split_simple as v3
from .citation_inputs import identity
from .split_v4_compare import write
from .transport import CapturedTransport, load_profile_client

ROOT = Path(__file__).parent / 'reviewer_r1_delivery'
FROZEN = ROOT / 'FROZEN_CASES.json'
BASELINE = ROOT / 'BASELINE_VERIFY_SYSTEM.txt'
ARMS = ('baseline', 'v4-reviewer-r1')


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def system(arm):
    if arm == 'baseline':
        return BASELINE.read_text(encoding='utf-8')
    if arm == 'v4-reviewer-r1':
        return v4.VERIFY_SYSTEM
    raise ValueError('unknown_arm')


def cases():
    return json.loads(FROZEN.read_text(encoding='utf-8'))['cases']


def plan(arm):
    prompt = system(arm)
    rows = []
    for row in cases():
        material, claims = row['material'], row['claims']
        request = v3.verification_request(material, claims, system=prompt,
                                          strategy=v4.STRATEGY)
        rows.append({'case_id': row['case_id'], 'origin_kind': row['origin']['kind'],
                     'material_sha256': identity(material), 'claims_sha256': identity(claims),
                     'request': request})
    result = {'schema': 'pma-v4-reviewer-only-plan-v1', 'arm': arm,
              'code_baseline_sha': 'be44ce85fd2ec1ce116e34a8683cbcb7a113f35e',
              'review_system_sha256': sha(prompt), 'entries': rows}
    result['plan_sha256'] = identity(result)
    return result


def _public_value(value, *, numeric=False):
    if numeric:
        return value if type(value) in (int, float) and value >= 0 else 'default/unknown'
    return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9._/-]+', value) else 'default/unknown'


def runtime_config(repo, frozen, client):
    """Whitelist actual initialized client/call-wrapper values, never a profile dump."""
    checkout = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'],
                              capture_output=True, text=True, check=True).stdout.strip()
    if not re.fullmatch(r'[0-9a-f]{40}', checkout):
        raise ValueError('checkout_identity_unavailable')
    call = getattr(client, 'call', None)
    closure = inspect.getclosurevars(call).nonlocals if inspect.isfunction(call) else {}
    bound = closure.get('memory_profile')
    bound = bound if isinstance(bound, dict) else {}
    return {'schema': 'pma-v4-reviewer-r1-runtime-config-v1', 'arm': frozen['arm'],
            'checkout_sha': checkout, 'model_id': _public_value(getattr(client, '_model_name', None)),
            'generation_parameters': {
                'temperature': _public_value(getattr(client, '_temperature', None), numeric=True),
                'reasoning_effort': _public_value(getattr(client, '_reasoning_effort', None)),
                'max_tokens': _public_value(bound.get('max_tokens'), numeric=True),
                'thinking_type': _public_value(bound.get('thinking_type')),
                'read_timeout': _public_value(bound.get('read_timeout'), numeric=True),
                'top_p': 'default/unknown', 'seed': 'default/unknown'},
            'parameter_scope': 'initialized client and bound call arguments; provider-side defaults or dropped parameters unknown',
            'review_system_sha256': frozen['review_system_sha256'],
            'plan_sha256': frozen['plan_sha256'],
            'audit_request_sha256': [row['request']['audit_request_sha256'] for row in frozen['entries']]}


async def run(frozen, transport):
    results = []
    stopped = False
    by_id = {row['case_id']: row for row in cases()}
    for entry in frozen['entries']:
        result = {'case_id': entry['case_id'], 'material_sha256': entry['material_sha256'],
                  'claims_sha256': entry['claims_sha256'],
                  'audit_request_sha256': entry['request']['audit_request_sha256'],
                  'model_verdict': None, 'verdict': None}
        if stopped:
            result['engineering_status'] = 'not_run_after_engineering_error'
        else:
            try:
                raw = await transport.send(entry['request'])
            except Exception as error:
                result.update(engineering_status='call_or_protocol_error',
                              error_type=type(error).__name__)
                stopped = True
            else:
                result['raw_response'] = raw
                try:
                    reviews, overall, verdict = v3.parse_batch(raw, by_id[entry['case_id']]['claims'])
                except (ValueError, TypeError, KeyError) as error:
                    result.update(engineering_status='parse_failure', reason=str(error))
                    stopped = True
                else:
                    result.update(engineering_status='ok', model_verdict=overall['verdict'],
                                  verdict=verdict, overall=overall, claim_reviews=reviews)
        results.append(result)
    return results


def score(report, frozen):
    if report['plan_sha256'] != frozen['plan_sha256']:
        raise ValueError('plan_identity_mismatch')
    entries = frozen['entries']
    if len(report['results']) != len(entries):
        raise ValueError('result_cardinality')
    refs = {row['case_id']: row for row in cases()}
    scored = []
    for actual, entry in zip(report['results'], entries):
        for key in ('case_id', 'material_sha256', 'claims_sha256', 'audit_request_sha256'):
            expected = entry['request'][key] if key == 'audit_request_sha256' else entry[key]
            if actual[key] != expected:
                raise ValueError('result_identity_mismatch')
        label = refs[actual['case_id']]['reference_label']
        status = actual['engineering_status']
        scored.append({'case_id': actual['case_id'], 'origin_kind': entry['origin_kind'],
                       'delete': refs[actual['case_id']]['material']['original_operation']['action'] == 'delete_gap',
                       'reference_label': label,
                       'reference_reason': refs[actual['case_id']]['reference_reason'],
                       'model_verdict': actual['model_verdict'], 'formal_verdict': actual['verdict'],
                       'engineering_status': status,
                       'three_state_agreement': actual['verdict'] == label if status == 'ok' else None,
                       'acceptance_agreement': (actual['verdict'] == 'supported') ==
                           (label == 'supported') if status == 'ok' else None})
    return {'schema': 'pma-v4-reviewer-only-score-v1', 'arm': frozen['arm'],
            'development_only': True, 'results': scored}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('export', 'run-profile', 'score'))
    parser.add_argument('--arm', choices=ARMS, required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--repo', default='.')
    parser.add_argument('--profile')
    parser.add_argument('--profile-key', default='claude_monitor_opus48')
    parser.add_argument('--results')
    parser.add_argument('--execute-authorized-real-model', action='store_true')
    args = parser.parse_args()
    frozen = plan(args.arm)
    if args.command == 'export':
        write(args.out, frozen)
    elif args.command == 'score':
        if not args.results:
            raise ValueError('results_required')
        write(args.out, score(json.loads(Path(args.results).read_text(encoding='utf-8')), frozen))
    else:
        if not args.execute_authorized_real_model or not args.profile:
            raise ValueError('explicit_real_model_authorization_and_profile_required')
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=False)
        write(out / 'plan.json', frozen)
        client = load_profile_client(args.repo, args.profile, args.profile_key,
                                     out / 'private_client', authorized=True)
        write(out / 'run-config.json', runtime_config(args.repo, frozen, client))
        transport = CapturedTransport(client, out, fake=False)
        results = asyncio.run(run(frozen, transport))
        write(out / 'results.json', {'schema': 'pma-v4-reviewer-only-results-v1',
            'arm': args.arm, 'plan_sha256': frozen['plan_sha256'], 'results': results})
        if any(row['engineering_status'] != 'ok' for row in results):
            raise SystemExit('Engineering failure; preserve captured records; no automatic rerun.')


if __name__ == '__main__':
    main()
