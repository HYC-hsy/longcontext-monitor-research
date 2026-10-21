"""One GA/U-PMA trial over one fixed upstream Task, defaulting to preparation.

This is a thin CLI over the existing materializer, controller and Harbor
launcher. It never mints a real authorization. An independently approved,
one-use binding is required for ``run``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

def _write_new(path: Path, value: dict) -> None:
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def prepare_stateful_fake(args: argparse.Namespace) -> dict:
    """Unarmed, local-only candidate plan; no official Task materialization."""
    if not args.fake_only:
        raise RuntimeError('stateful candidate preparation is fake-only')
    root = Path(args.output).resolve(strict=False)
    root.mkdir(parents=True, exist_ok=False)
    plan = {'schema': 'pma-stateful-ga-fake-plan-v1',
            'research_candidate': 'pma_stateful_memory_v1',
            'mode': 'fake-only', 'execution_authorized': False,
            'task': 'synthetic-local-task', 'run_id': 'stateful-' + uuid.uuid4().hex[:16]}
    _write_new(root / 'plan.json', plan)
    return plan


def run_stateful_fake(args: argparse.Namespace) -> dict:
    if not args.fake_only:
        raise RuntimeError('stateful candidate run is fake-only')
    root = Path(args.output).resolve(strict=True)
    plan = json.loads((root / 'plan.json').read_text(encoding='utf-8'))
    if plan.get('schema') != 'pma-stateful-ga-fake-plan-v1' or set(plan) != {
            'schema', 'research_candidate', 'mode', 'execution_authorized',
            'task', 'run_id'} or plan['research_candidate'] != 'pma_stateful_memory_v1' or \
            plan['mode'] != 'fake-only' or plan['execution_authorized'] is not False or \
            plan['task'] != 'synthetic-local-task' or not plan['run_id'].startswith('stateful-'):
        raise RuntimeError('stateful fake plan identity mismatch')
    if (root / 'result.json').exists() or (root / 'fixture').exists():
        raise RuntimeError('stateful fake run already started')
    # Reuse the tested GA synthetic fixture: actual NativeToolClient, GA loop,
    # tool dispatch, core store, and finite role scripts; no Harbor claim.
    repo = Path(__file__).resolve().parents[3]
    ga_root = repo / 'GenericAgent-main'
    if str(ga_root) not in sys.path:
        sys.path.insert(0, str(ga_root))
    from tests.test_stateful_memory_ga_bridge import run_fixture
    facts = run_fixture(root / 'fixture', run_id=plan['run_id'])
    required = (facts['task_posts'] == 3 and facts['role_attempts'] == 9 and
        facts['tool_calls'] == 2 and facts['reminder_counts'] == [0, 1, 1] and
        facts['delivery_attempts'] == 1 and facts['bridge_closed'])
    result = {'schema': 'pma-stateful-ga-fake-result-v1',
        'run_id': plan['run_id'], 'integration_ok': bool(required),
        'task_posts': facts['task_posts'], 'role_attempts': facts['role_attempts'],
        'tool_calls': facts['tool_calls'], 'reminder_counts': facts['reminder_counts'],
        'action_batches': facts['action_batches'],
        'committed_event_seq': facts['committed_event_seq'],
        'pending_kinds': facts['pending_kinds'],
        'bridge_closed': facts['bridge_closed'], 'harbor_tested': False,
        'real_model_calls': 0, 'official_evaluator_calls': 0}
    _write_new(root / 'result.json', result)
    if not required:
        raise RuntimeError('stateful GA fake integration contract failed')
    return result


def prepare(args: argparse.Namespace) -> dict:
    from .export_official_evaluator import COMMIT
    from .prepare_six_task_manifest import prepare as prepare_manifest
    root = Path(args.output).resolve(strict=False)
    root.mkdir(parents=True, exist_ok=False)
    pos = args.condition == 'P'
    plan = {'schema': 'pos-ga-single-plan-v1' if pos else 'pma-ga-single-plan-v1',
            'execution_authorized': False,
            'official_source_git_commit': COMMIT, 'task': args.task,
            'condition': args.condition, 'occurrence': args.occurrence}
    if pos:
        plan.update(method=getattr(args, 'research_candidate', 'PoS'), synthetic_fixture=bool(
            getattr(args, 'synthetic_pos_fixture', False)))
        if getattr(args, 'candidate_profile_fixture', False):
            if (not plan['synthetic_fixture'] or not args.fake_only or
                    plan['method'] not in {'pos_pma_complement_v1',
                                           'pos_pma_shared_view_v1'}):
                raise RuntimeError('candidate profile fixture requires isolated synthetic P')
            plan['candidate_profile_fixture_only'] = True
        if getattr(args, 'task_complete_response', False):
            if plan['synthetic_fixture']:
                raise RuntimeError('synthetic PoS fixture cannot authorize Task response policy')
            plan['task_complete_response_policy'] = 'complete-response-v1'
        if plan['synthetic_fixture'] and not args.fake_only:
            raise RuntimeError('synthetic PoS package is zero-model only')
    candidate = getattr(args, 'research_candidate', 'U')
    if pos and candidate not in {'PoS', 'PoS-citation-fixed',
                                  'pos_pma_complement_v1', 'pos_pma_shared_view_v1'}:
        raise RuntimeError('PoS plan requires explicit fixed method identity')
    if not pos and candidate != 'U':
        plan['schema'] = 'pma-ga-single-plan-v2'
        plan['research_candidate'] = candidate
        if candidate == 'pma_stateful_memory_v1':
            if args.condition != 'B' or not args.task_complete_response:
                raise RuntimeError('stateful candidate requires B carrier and complete response')
            plan['task_complete_response_policy'] = 'complete-response-v1'
            if not getattr(args, 'stateful_uncapped_diagnostic', False):
                raise RuntimeError('stateful live/fake entry requires explicit diagnostic protocol')
            plan['agent_time_protocol'] = 'diagnostic-uncapped-v1'
    _write_new(root / 'plan.json', plan)
    if pos:
        from method_discovery.pos_upstream_ga_v1_20261017.single_manifest import prepare as prepare_pos
        manifest = prepare_pos(plan, Path(args.official_source_git).resolve(strict=True),
                               Path(args.task_profile_file).resolve(strict=True),
                               certification_dir=(Path(args.certification_dir)
                                   if getattr(args, 'certification_dir', None) else None),
                               pma_profile=(Path(args.pma_profile_file)
                                   if getattr(args, 'pma_profile_file', None) else None))
    else:
        manifest = prepare_manifest(Path(args.official_source_git).resolve(strict=True),
            Path(args.task_profile_file).resolve(strict=True),
            Path(args.pma_profile_file).resolve(strict=True),
            evidence=(Path(args.certification_dir).resolve(strict=True)
                      if getattr(args, 'certification_dir', None) else None), plan=plan)
    if args.fake_only and not pos:
        manifest['zero_model_fixture_only'] = True
        if candidate == 'pma_stateful_memory_v1':
            manifest['stateful_fake_replies_sha256'] = hashlib.sha256(
                Path(__file__).with_name('stateful_fixture_replies.json').read_bytes()).hexdigest()
    _write_new(root / 'manifest.json', manifest)
    # Keep Windows Harbor paths below MAX_PATH while retaining a fresh random ID.
    run_id = ('pos-' if pos else 'pma-') + uuid.uuid4().hex[:16]
    identity = {'run_id': run_id, 'run_root': str(root / 'runs' / run_id),
                'output_root': str(root / 'runs'), 'plan_sha256': hashlib.sha256(
                    (root / 'plan.json').read_bytes()).hexdigest(),
                'manifest_sha256': hashlib.sha256(
                    (root / 'manifest.json').read_bytes()).hexdigest(),
                'execution_authorized': False}
    _write_new(root / 'run_identity.json', identity)
    return identity


def run(args: argparse.Namespace) -> dict:
    from .batch_controller import run_batch
    from .six_task_plan import validate_plan
    root = Path(args.output).resolve(strict=True)
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    identity = json.loads((root / 'run_identity.json').read_text(encoding='utf-8'))
    granted = json.loads(Path(args.authorization).read_text(encoding='utf-8'))
    bindings = validate_plan(manifest, granted)
    if (len(bindings) != 1 or bindings[0]['run_id'] != identity['run_id'] or
            bindings[0]['run_root'] != identity['run_root'] or
            granted.get('manifest_sha256') != identity['manifest_sha256'] or
            bool(args.zero_model_fixture) != (manifest.get('zero_model_fixture_only') is True) or
            bool(args.candidate_profile_fixture) !=
                (manifest.get('candidate_profile_fixture_only') is True and
                 granted.get('candidate_profile_fixture_only') is True)):
        raise RuntimeError('single-run identity or fixture mode differs from approval')
    if (manifest.get('schema') == 'pos-ga-single-manifest-v1' or
            manifest.get('config', {}).get('research_candidate') ==
            'pma_stateful_memory_v1'):
        policy = manifest.get('config', {}).get('task_complete_response_policy', 'disabled')
        actual = 'complete-response-v1' if os.environ.get('GA_TASK_COMPLETE_RESPONSE') == '1' else 'disabled'
        if (policy not in {'disabled', 'complete-response-v1'} or
                granted.get('task_complete_response_policy', 'disabled') != policy or
                actual != policy):
            raise RuntimeError('Task response policy differs from frozen PoS authorization')
        if manifest.get('config', {}).get('research_candidate') == 'pma_stateful_memory_v1' and (
                manifest['config'].get('agent_time_protocol') != 'diagnostic-uncapped-v1' or
                granted.get('agent_time_protocol') != 'diagnostic-uncapped-v1'):
            raise RuntimeError('stateful Agent time protocol differs from authorization')
    if (root / 'batch_result.json').exists() or Path(identity['run_root']).exists():
        raise FileExistsError('single-run result or run root already exists')
    options = argparse.Namespace(
        manifest=str(root / 'manifest.json'), authorization=str(args.authorization),
        batch_result=str(root / 'batch_result.json'),
        ga_source=args.ga_source, runtime_root=args.runtime_root,
        task_profile_file=args.task_profile_file,
        pma_profile_file=args.pma_profile_file,
        worker_python=args.worker_python, harbor_python=args.harbor_python,
        bench_root=args.bench_root, official_source_git=args.official_source_git,
        harbor_source_root=args.harbor_source_root, python_home=args.python_home,
        zero_model_fixture=args.zero_model_fixture,
        candidate_profile_fixture=args.candidate_profile_fixture,
        stateful_fake_replies=getattr(args, 'stateful_fake_replies', None))
    result = run_batch(options)
    return {'run_id': identity['run_id'], 'arm': result['arms'][0] if result['arms'] else None,
            'stop_reason': result['stop_reason']}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    stateful_prepared = commands.add_parser('prepare-stateful-fake',
        help='unarmed stateful-memory local GA fake plan; never a live manifest')
    stateful_prepared.add_argument('--output', required=True)
    stateful_prepared.add_argument('--fake-only', action='store_true')
    stateful_run = commands.add_parser('run-stateful-fake',
        help='one bounded actual GA loop with local fake transport')
    stateful_run.add_argument('--output', required=True)
    stateful_run.add_argument('--fake-only', action='store_true')
    prepared = commands.add_parser('prepare', help='fixed-Git asset and image check; no calls')
    prepared.add_argument('--task', required=True)
    prepared.add_argument('--condition', choices=('A', 'B', 'P'), required=True)
    prepared.add_argument('--research-candidate', choices=(
        'U', 'V1', 'D1', 'PoS', 'PoS-citation-fixed',
        'pos_pma_complement_v1', 'pos_pma_shared_view_v1',
        'pma_stateful_memory_v1'), default='U')
    prepared.add_argument('--occurrence', type=int, default=1)
    prepared.add_argument('--output', required=True)
    prepared.add_argument('--official-source-git', required=True)
    prepared.add_argument('--task-profile-file', required=True)
    prepared.add_argument('--pma-profile-file')
    prepared.add_argument('--fake-only', action='store_true')
    prepared.add_argument('--synthetic-pos-fixture', action='store_true')
    prepared.add_argument('--candidate-profile-fixture', action='store_true')
    prepared.add_argument('--task-complete-response', action='store_true',
                          help='bind complete-response-v1 for the Task only')
    prepared.add_argument('--stateful-uncapped-diagnostic', action='store_true',
                          help='bind nonstandard unlimited cumulative Agent time')
    prepared.add_argument('--certification-dir',
                          help='committed A/B Harbor evidence for future authorized use')
    launched = commands.add_parser('run', help='requires an independent one-use approval')
    launched.add_argument('--output', required=True)
    launched.add_argument('--authorization', required=True)
    for name in ('ga-source', 'runtime-root', 'task-profile-file',
                 'worker-python', 'harbor-python', 'bench-root',
                 'official-source-git', 'harbor-source-root'):
        launched.add_argument('--' + name, required=True)
    launched.add_argument('--pma-profile-file')
    launched.add_argument('--python-home', default='cpython-3.12.12-linux-x86_64-gnu')
    launched.add_argument('--zero-model-fixture', action='store_true')
    launched.add_argument('--candidate-profile-fixture', action='store_true')
    launched.add_argument('--stateful-fake-replies',
                          help='finite local host-role script, zero-model fixture only')
    pos_plan = commands.add_parser('prepare-pos', help='unarmed fixed-source PoS serial plan')
    pos_plan.add_argument('--task', action='append', required=True,
                          help='canonical registered task ID, repeat in desired serial order')
    pos_plan.add_argument('--output', required=True)
    pos_plan.add_argument('--official-source-git', required=True)
    pos_plan.add_argument('--frozen-reference-manifest', required=True)
    pos_fake = commands.add_parser('fake-pos', help='one offline Harbor fake-only PoS run')
    pos_fake.add_argument('--output', required=True, help='prepared PoS plan directory')
    pos_fake.add_argument('--task', required=True)
    pos_fake.add_argument('--run-root', required=True)
    pos_fake.add_argument('--run-id', required=True)
    pos_fake.add_argument('--pos-fake-replies', required=True)
    for name in ('ga-source', 'runtime-root', 'task-profile-file',
                 'worker-python', 'harbor-exe', 'bench-root', 'official-source-git'):
        pos_fake.add_argument('--' + name, required=True)
    pos_fake.add_argument('--task-profile', default='native_claude_cc_vibe_opus48')
    pos_fake.add_argument('--python-home', default='cpython-3.12.12-linux-x86_64-gnu')
    pos_fake.add_argument('--timeout-sec', type=int, default=180)
    args = parser.parse_args()
    if args.command == 'prepare-stateful-fake':
        outcome = prepare_stateful_fake(args)
    elif args.command == 'run-stateful-fake':
        outcome = run_stateful_fake(args)
    elif args.command == 'prepare-pos':
        from method_discovery.pos_upstream_ga_v1_20261017.prepare_plan import prepare as prepare_pos
        outcome = prepare_pos(source=args.official_source_git, tasks=args.task,
                              reference=args.frozen_reference_manifest, output=args.output)
    elif args.command == 'fake-pos':
        from .offline_launcher import run_offline
        args.manifest = str(Path(args.output) / 'manifest.json')
        prepared_pos = json.loads(Path(args.manifest).read_text(encoding='utf-8'))
        if prepared_pos.get('synthetic_fixture') is not True:
            raise RuntimeError('fake-pos requires a synthetic Task fixture; '
                               'the four registered tasks are not a fake fixture')
        args.condition = 'P'
        args.execution_authorized = False
        args.multiturn_fixture = False
        outcome = run_offline(args)
    else:
        outcome = prepare(args) if args.command == 'prepare' else run(args)
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    if (args.command == 'run' and
            (outcome['stop_reason'] or not outcome['arm'] or
             outcome['arm'].get('disposition') != 'completed')):
        raise SystemExit(1)
    if args.command == 'fake-pos' and not outcome['integration_ok']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
