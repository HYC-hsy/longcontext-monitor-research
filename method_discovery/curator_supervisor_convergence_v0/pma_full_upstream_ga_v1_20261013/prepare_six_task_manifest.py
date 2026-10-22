"""Generate an unarmed six-task draft from fixed Git blobs and local images.

This is a host-only preparation command. It never creates an authorization,
imports a model client, starts Harbor, or executes an official verifier.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
from tempfile import TemporaryDirectory
from experiment_runner.methods import candidate_names

from long_context_bench.scripts.isolated_run_bundle import digest_tree

from .export_official_evaluator import export_task
from .offline_launcher import image_identity
from .six_task_assets import descriptor, materialize_public
from .six_task_plan import ORDER
from .export_official_evaluator import SIX_TASKS

STAGE = Path(__file__).resolve().parent
SOURCE_FILES = (
    'experiment_runner/__init__.py',
    'experiment_runner/methods.py',
    'experiment_runner/__main__.py',
    'experiment_runner/runtime_policy.py',
    'long_context_bench/adapters/harbor_ga_agent.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'archive_six_task_native_base.py',
    'long_context_bench/scripts/isolated_run_bundle.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'batch_controller.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'export_official_evaluator.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'harbor_adapter.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'live_launcher.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'native_shared_verifier.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'networked_transport_setup.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'offline_launcher.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'pma_harbor_hooks.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'worker_main.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'six_task_assets.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'six_task_plan.py',
)
V3_SOURCE_FILES = SOURCE_FILES + (
    'GenericAgent-main/agent_loop.py',
    'GenericAgent-main/agentmain.py',
    'GenericAgent-main/llmcore.py',
    'GenericAgent-main/pma_upstream_bridge.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'prepare_six_task_manifest.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'two_task_certification.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'archive_two_task_native_base.py',
)
EVIDENCE_FILES = (
    'FILE_HASHES.json', 'image_checks.json', 'request_comparison.json',
    'unittest.stderr.txt',
    'fixtures/02/archive/fixture_result.json',
    'fixtures/03/archive/fixture_result.json',
    'fixtures/04/archive/fixture_result.json',
    'fixtures/08/archive/fixture_result.json',
    'fixtures/09/archive/fixture_result.json',
    'fixtures/10/archive/fixture_result.json',
    'fixtures/11/archive/fixture_result.json',
    'fixtures/13/archive/fixture_result.json',
    'fixtures/16/archive/fixture_result.json',
    'controller_entry/batch.json',
    'controller_entry/run-1/archive/live_result.json',
    'controller_entry/run-1/archive/agent_start_identity.json',
)

def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _committed_source_sha(checkout: Path, name: str) -> str:
    unchanged = subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', name],
                               cwd=checkout, check=False)
    if unchanged.returncode:
        raise RuntimeError(f'pilot source differs from HEAD: {name}')
    blob = subprocess.run(['git', 'show', f'HEAD:{name}'], cwd=checkout,
                          capture_output=True, check=True).stdout
    return hashlib.sha256(blob).hexdigest()


def prepare(source: Path, task_profile: Path, pma_profile: Path,
            evidence: Path | None = None, plan: dict | None = None) -> dict:
    single = plan is not None and plan.get('schema') in {
        'pma-ga-single-plan-v1', 'pma-ga-single-plan-v2'}
    candidate = plan.get('research_candidate', 'U') if single else 'U'
    stateful = candidate == 'pma_stateful_memory_v1'
    if stateful:
        from .stateful_runtime_policy import policies
        runtime_policies = policies(plan)
    if plan is None:
        slots = [dict(order=o, task=t, repeat=r, condition=c)
                 for o, t, r, c in ORDER]
        schema = 'pma-ga-live-manifest-v2'
    elif single:
        versioned = plan['schema'] == 'pma-ga-single-plan-v2'
        required = {'schema', 'execution_authorized',
                    'official_source_git_commit', 'task', 'condition', 'occurrence'}
        if versioned:
            required.add('research_candidate')
        if stateful:
            required.add('task_complete_response_policy')
            required.add('agent_time_protocol')
            required.update(key for key in runtime_policies if key in plan)
        if 'runtime_policy' in plan:
            required.add('runtime_policy')
        if (set(plan) != required or
                plan['execution_authorized'] is not False or
                plan['official_source_git_commit'] !=
                '2fd12b88aafdd04a52c298e3940bcb189f9766d6' or
                not isinstance(plan['task'], str) or
                plan['condition'] not in {'A', 'B'} or
                candidate not in (candidate_names(plan['condition'])
                                  if versioned else {'U'}) or
                (stateful and (plan['condition'] != 'B' or
                 plan.get('task_complete_response_policy') != 'complete-response-v1')) or
                (stateful and plan.get('agent_time_protocol') !=
                 ('runtime-policy-v1' if 'runtime_policy' in plan else 'diagnostic-uncapped-v1')) or
                (plan['condition'] == 'A' and candidate != 'U') or
                type(plan['occurrence']) is not int or plan['occurrence'] < 1):
            raise RuntimeError('single-run plan schema mismatch')
        slot = dict(order=1, task=plan['task'],
                    repeat=plan['occurrence'], condition=plan['condition'])
        if versioned:
            slot['research_candidate'] = candidate
        slots = [slot]
        schema = 'pma-ga-live-manifest-v5' if versioned else 'pma-ga-live-manifest-v4'
    else:
        if (plan.get('schema') != 'pma-ga-live-plan-v3' or
                plan.get('execution_authorized') is not False or
                plan.get('official_source_git_commit') !=
                '2fd12b88aafdd04a52c298e3940bcb189f9766d6' or
                set(plan) != {'schema', 'execution_authorized',
                              'official_source_git_commit', 'planned_order'}):
            raise RuntimeError('V3 plan schema mismatch')
        slots = plan.get('planned_order')
        if not isinstance(slots, list) or not slots:
            raise RuntimeError('V3 plan is empty')
        seen = set()
        for number, row in enumerate(slots, 1):
            if (not isinstance(row, dict) or
                    set(row) != {'order', 'task', 'repeat', 'condition'} or
                    row['order'] != number or row['task'] not in SIX_TASKS or
                    type(row['repeat']) is not int or row['repeat'] < 1 or
                    row['condition'] not in {'A', 'B'} or
                    (row['task'], row['repeat'], row['condition']) in seen):
                raise RuntimeError('V3 slot identity invalid')
            seen.add((row['task'], row['repeat'], row['condition']))
        schema = 'pma-ga-live-manifest-v3'
    task_settings = runpy.run_path(str(task_profile))[
        'native_claude_cc_vibe_opus48']
    pma_settings = json.loads(pma_profile.read_text(encoding='utf-8'))[
        'claude_monitor_opus48']
    if (task_settings.get('model') != 'claude-opus-4-8' or
            pma_settings.get('model') != 'claude-opus-4-8'):
        raise RuntimeError('frozen Task/PMA models are not Opus 4.8')
    tasks = tuple(dict.fromkeys(row['task'] for row in slots))
    assets = {}
    for task in tasks:
        desc = descriptor(source, task, registered=single)
        with TemporaryDirectory(prefix='pma-public-check-') as temporary:
            base = Path(temporary)
            public = base / 'public'
            materialize_public(source, task, public, desc['public_members'], registered=single)
            (public / 'tests').mkdir(exist_ok=True)
            (public / 'solution').mkdir(exist_ok=True)
            public_hash = digest_tree(public)
            tests = base / 'tests'
            tests.mkdir()
            export_task(source, task, tests, registered=single)
            tests_hash = digest_tree(tests)
            test_sh_hash = _sha(tests / 'test.sh')
        image = image_identity(desc['image_tag'])
        repo = desc['image_tag'].rsplit(':', 1)[0]
        matching_digests = [value for value in image['repo_digests']
                            if value.startswith(repo + '@sha256:')]
        if len(matching_digests) != 1:
            raise RuntimeError(f'{task}: no unique matching local official RepoDigest')
        assets[task] = {**desc, 'image_id': image['image_id'],
                        'repo_digest': matching_digests[0],
                        'platform': image['platform'],
                        'public_task_tree_sha256': public_hash,
                        'official_evaluator_members': desc['evaluator_members'],
                        'native_tests_tree_sha256': tests_hash,
                        'native_test_sh_sha256': test_sh_hash,
                        'agent_timeout_multiplier': (1 if stateful else
                            14400 / desc['native_agent_seconds']),
                        'verifier_timeout_multiplier': 1}
    method = {'conditions': {'A': 'GA_only', 'B': 'GA_plus_fixed_upstream_PMA'},
              'task_turns_max': 300, 'agent_wall_seconds': 14400,
              'harbor_whole_trial_retries': 0,
              'task_profile_name': 'native_claude_cc_vibe_opus48',
              'pma_profile_name': 'claude_monitor_opus48',
              'network': 'official_task_network_with_host_credential_gateway',
              'evaluation': 'native_Harbor_SHARED_pending_lifecycle_certification'}
    if schema == 'pma-ga-live-manifest-v5':
        method['research_candidate'] = candidate
        if candidate == 'pma_stateful_memory_v1':
            guard_window = task_settings.get('context_win')
            if runtime_policies['native_context_policy'] == 'off':
                guard_window, guard_basis = None, 'disabled_by_frozen_policy'
            elif guard_window is None:
                guard_window = 1000000
                guard_basis = ('Anthropic_Claude_Opus_4_8_official_1M_context;'
                               'private_proxy_limit_unknown_fail_on_provider_rejection')
            elif type(guard_window) is int and 0 < guard_window <= 1000000:
                guard_basis = 'smaller_existing_task_profile_context_win'
            else:
                raise RuntimeError('stateful native window cannot be bound')
            method.update(conditions={'B': 'GA_plus_stateful_proactive_memory_v1'},
                task_turns_max=None, agent_wall_seconds=None,
                research_cumulative_calls=None, research_cumulative_tokens=None,
                research_cumulative_cost=None,
                task_complete_response_policy='complete-response-v1',
                agent_time_protocol=plan['agent_time_protocol'],
                auxiliary_provider_retries=0, task_provider_retries=0,
                native_context_guard_window_tokens=guard_window,
                native_context_guard_basis=guard_basis, **runtime_policies)
    if single and 'runtime_policy' in plan:
        from experiment_runner.runtime_policy import resolve_policy
        policy = resolve_policy(plan['runtime_policy'], assets[plan['task']], method)
        method['runtime_policy'] = policy
        method['task_turns_max'] = policy['effective_task_turns']
        method['agent_wall_seconds'] = policy['effective_agent_seconds']
        assets[plan['task']]['agent_timeout_multiplier'] = 1
    config_hash = hashlib.sha256(json.dumps(method, sort_keys=True,
        separators=(',', ':')).encode('utf-8')).hexdigest()
    certification = None
    if evidence is not None and schema == 'pma-ga-live-manifest-v2':
        if evidence != STAGE / 'six_task_native_base_20261014_v3':
            raise RuntimeError('unexpected native-base evidence namespace')
        checkout = STAGE.parents[2]
        certification = {
            'source_files': {name: _committed_source_sha(checkout, name)
                             for name in SOURCE_FILES},
            'source_identity_kind': 'HEAD_Git_blob_bytes_SHA256_with_clean_worktree',
            'evidence_files': {name: _sha(evidence / name) for name in EVIDENCE_FILES},
            'harbor_commit': '459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc'}
    elif evidence is not None and schema == 'pma-ga-live-manifest-v3':
        if evidence != STAGE / 'two_task_live_20261015' / 'zero_model_certification':
            raise RuntimeError('unexpected V3 evidence namespace')
        from .two_task_certification import verify_evidence
        checkout = STAGE.parents[2]
        certification = {
            'source_files': {name: _committed_source_sha(checkout, name)
                             for name in V3_SOURCE_FILES},
            'source_identity_kind': 'HEAD_Git_blob_bytes_SHA256_with_clean_worktree',
            'evidence': verify_evidence(evidence, checkout, slots),
            'harbor_commit': '459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc'}
    elif evidence is not None and schema in {'pma-ga-live-manifest-v4',
                                             'pma-ga-live-manifest-v5'}:
        if stateful:
            from .stateful_certification import (HARBOR_COMMIT, source_identity,
                                                 verify_evidence)
        else:
            from .single_run_certification import (HARBOR_COMMIT, source_identity,
                                                   verify_evidence)
        checkout = STAGE.parents[2]
        evidence = evidence.resolve(strict=True)
        if not evidence.is_relative_to(checkout):
            raise RuntimeError('single-run certification must be committed in repository')
        research = candidate if schema == 'pma-ga-live-manifest-v5' else None
        conditions = (('A',) if single and plan['condition'] == 'A' and
                      not (evidence / 'B').exists() else ('A', 'B'))
        certification = {'source_files': (source_identity(checkout) if stateful else
                             source_identity(checkout, candidate=research is not None,
                                 gap=research == 'pma_gap_memory_v0')),
                         'evidence_path': evidence.relative_to(checkout).as_posix(),
                         'evidence': (verify_evidence(evidence) if stateful else
                             verify_evidence(evidence, research_candidate=research,
                                             conditions=conditions)),
                         **({'conditions': list(conditions)} if not stateful else {}),
                         'harbor_commit': HARBOR_COMMIT}
    return {'schema': schema,
            'status': ('prepared_not_executed' if certification else
                       'prepared_assets_lifecycle_blocked'),
            'execution_authorized': False,
            'official_source_git_commit': '2fd12b88aafdd04a52c298e3940bcb189f9766d6',
            'pma_vendor_commit': '89e5c0d6aadfe531a1aee42fd290d48be89973dd',
            'task_profile_sha256': _sha(task_profile),
            'pma_profile_sha256': _sha(pma_profile),
            'profile_identity_status': 'private_bytes_hashed_not_exported',
            'resolved_models_public': {
                'task': {key: task_settings.get(key) for key in
                         ('model', 'max_tokens', 'temperature', 'max_retries')},
                'pma': {key: pma_settings.get(key) for key in
                        ('model', 'max_tokens', 'temperature', 'max_retries',
                         'provider', 'api_mode', 'thinking_type', 'reasoning_effort',
                         'connect_timeout', 'read_timeout')}},
            'config': method, 'config_sha256': config_hash,
            'native_shared_certification': certification,
            'assets': assets,
            'planned_order': slots,
            'technical_replacements_before_first_model_request_only':
                ['headless-terminal', 'cancel-async-tasks'] if plan is None else []}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--official-source-git', type=Path, required=True)
    parser.add_argument('--task-profile-file', type=Path, required=True)
    parser.add_argument('--pma-profile-file', type=Path, required=True)
    parser.add_argument('--evidence-dir', type=Path)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    plan = json.loads(args.plan.read_text(encoding='utf-8')) if args.plan else None
    manifest = prepare(args.official_source_git.resolve(strict=True),
                       args.task_profile_file.resolve(strict=True),
                       args.pma_profile_file.resolve(strict=True),
                       args.evidence_dir.resolve(strict=True) if args.evidence_dir else None,
                       plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                           encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'tasks': len(manifest['assets']),
                      'slots': len(manifest['planned_order']),
                      'execution_authorized': False,
                      'sha256': _sha(args.output)}))


if __name__ == '__main__':
    main()

