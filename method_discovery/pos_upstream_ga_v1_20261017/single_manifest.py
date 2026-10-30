"""One-slot PoS identity using the existing single-run controller, not an executor."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import runpy
from tempfile import TemporaryDirectory

from long_context_bench.scripts.isolated_run_bundle import digest_tree
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.export_official_evaluator import COMMIT, export_task
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.offline_launcher import image_identity
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.six_task_assets import descriptor, materialize_public
from .worker import (ROLE_JSON_CONTRACT_VERSION, ROLE_INPUT_CONTRACT_VERSION,
                     ROLE_OBJECT_INSTRUCTION, ROLE_UPDATE_FIELDS_INSTRUCTION,
                     ROLE_MAX_TOKENS, ROLE_TEMPERATURE, ROLE_THINKING_TYPE)

ROOT = Path(__file__).resolve().parent
CHECKOUT = ROOT.parents[1]
PMA_VENDOR = CHECKOUT / 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/vendor/pma_89e5c0d'
UPSTREAM = '6818cfa6434dbc91fcf67f0b3eb12a91db47433f'
SYNTHETIC_ID = 'pos-synthetic-file-http'
FOUR = ('nginx-request-logging', 'adaptive-rejection-sampler',
        'sqlite-with-gcov', 'write-compressor')
SOURCE_FILES = (
    'GenericAgent-main/agent_loop.py', 'GenericAgent-main/agentmain.py',
    'GenericAgent-main/ga.py', 'GenericAgent-main/llmcore.py',
    'GenericAgent-main/research_runtime.py',
    'GenericAgent-main/pos_bridge.py',
    'experiment_runner/runtime_policy.py',
    'experiment_runner/methods.py',
    'method_discovery/pos_upstream_ga_v1_20261017/episode.py',
    'method_discovery/pos_upstream_ga_v1_20261017/citation_fix.py',
    'method_discovery/pos_pma_complement_v1_20261019/candidate.py',
    'method_discovery/pos_pma_complement_v1_20261019/memory_adapter.py',
    'method_discovery/pos_pma_complement_v1_20261019/synthetic_replies.json',
    'method_discovery/pos_pma_complement_v1_20261019/test_fake_host_entry.py',
    'method_discovery/pos_upstream_ga_v1_20261017/worker.py',
    'method_discovery/curator_supervisor_convergence_v0/'
    'pma_full_upstream_ga_v1_20261013/event_spool.py',
    'method_discovery/curator_supervisor_convergence_v0/'
    'pma_full_upstream_ga_v1_20261013/candidate_transport_worker.py',
    'method_discovery/pos_upstream_ga_v1_20261017/provider_capture.py',
    'method_discovery/pos_upstream_ga_v1_20261017/compatibility_probe.py',
    'method_discovery/pos_upstream_ga_v1_20261017/serial_live.py',
    'method_discovery/curator_supervisor_convergence_v0/'
    'pma_full_upstream_ga_v1_20261013/single_run.py',
    'method_discovery/curator_supervisor_convergence_v0/'
    'pma_full_upstream_ga_v1_20261013/single_run_fixture.py',
    'method_discovery/curator_supervisor_convergence_v0/'
    'pma_full_upstream_ga_v1_20261013/batch_controller.py',
    'method_discovery/curator_supervisor_convergence_v0/'
    'pma_full_upstream_ga_v1_20261013/live_launcher.py',
    'method_discovery/curator_supervisor_convergence_v0/'
    'pma_full_upstream_ga_v1_20261013/offline_launcher.py',
    'method_discovery/curator_supervisor_convergence_v0/'
    'pma_full_upstream_ga_v1_20261013/harbor_adapter.py',
    'method_discovery/curator_supervisor_convergence_v0/'
    'pma_full_upstream_ga_v1_20261013/pma_harbor_hooks.py',
    'method_discovery/curator_supervisor_convergence_v0/'
    'pma_full_upstream_ga_v1_20261013/native_shared_verifier.py',
    'method_discovery/curator_supervisor_convergence_v0/'
    'pma_full_upstream_ga_v1_20261013/six_task_plan.py',
    'method_discovery/pos_upstream_ga_v1_20261017/single_manifest.py',
    'method_discovery/pos_upstream_ga_v1_20261017/certification.py',
    'method_discovery/pos_upstream_ga_v1_20261017/collect_native_shared.py',
    'method_discovery/curator_supervisor_convergence_v0/'
    'real_task_effect_pilot_preflight_20261010/pilot_fake_gateway.py',
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


SHARED_SOURCE_FILE = 'method_discovery/pos_pma_complement_v1_20261019/shared_view.py'


def source_hashes(*, include_shared=False) -> dict:
    names = (*SOURCE_FILES, SHARED_SOURCE_FILE) if include_shared else SOURCE_FILES
    return {name: sha(CHECKOUT / name) for name in names}


def vendor_hashes() -> dict:
    return {p.relative_to(ROOT / 'vendor').as_posix(): sha(p)
            for p in sorted((ROOT / 'vendor').rglob('*')) if p.is_file()
            and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def pma_vendor_hashes() -> dict:
    return {p.relative_to(PMA_VENDOR).as_posix(): sha(p)
            for p in sorted(PMA_VENDOR.rglob('*')) if p.is_file() and
            (p.name == 'LICENSE' or 'src' in p.relative_to(PMA_VENDOR).parts) and
            '__pycache__' not in p.parts and p.suffix != '.pyc'}


def synthetic_members() -> dict:
    base = ROOT / 'synthetic_task'
    return {p.relative_to(base).as_posix(): sha(p) for p in sorted(base.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}


def prepare(plan: dict, source: Path, task_profile: Path,
            certification_dir: Path | None = None,
            pma_profile: Path | None = None) -> dict:
    if (plan.get('schema') != 'pos-ga-single-plan-v1' or
            plan.get('execution_authorized') is not False or
            plan.get('official_source_git_commit') != COMMIT or
            plan.get('condition') != 'P' or plan.get('method') not in
                {'PoS', 'PoS-citation-fixed', 'pos_pma_complement_v1',
                 'pos_pma_shared_view_v1'} or
            type(plan.get('occurrence')) is not int or plan['occurrence'] < 1):
        raise RuntimeError('PoS single-run plan identity invalid')
    task = plan['task']
    synthetic = plan.get('synthetic_fixture') is True
    candidate_profile_fixture = plan.get('candidate_profile_fixture_only') is True
    if candidate_profile_fixture and (not synthetic or
            plan['method'] not in {'pos_pma_complement_v1', 'pos_pma_shared_view_v1'}):
        raise RuntimeError('candidate profile fixture identity invalid')
    policy = plan.get('task_complete_response_policy', 'disabled')
    if policy not in {'disabled', 'complete-response-v1'} or (synthetic and policy != 'disabled'):
        raise RuntimeError('PoS Task response policy invalid')
    if plan['method'] == 'pos_pma_shared_view_v1' and not synthetic and (
            policy != 'complete-response-v1'):
        raise RuntimeError('shared-view formal Task requires complete-response-v1')
    if synthetic != (task == SYNTHETIC_ID) or (not synthetic and task not in FOUR):
        raise RuntimeError('PoS task not in frozen four or synthetic fixture')
    profile = runpy.run_path(str(task_profile))['native_claude_cc_vibe_opus48']
    if profile.get('model') != 'claude-opus-4-8':
        raise RuntimeError('PoS Task profile model changed')
    if synthetic:
        image_tag = 'alexgshaw/db-wal-recovery:20251031'
        with TemporaryDirectory(prefix='pos-synthetic-public-') as tmp:
            import shutil
            public = Path(tmp) / 'public'
            shutil.copytree(ROOT / 'synthetic_task', public,
                            ignore=shutil.ignore_patterns('tests', 'pos_replies.json',
                                                          '__pycache__'))
            (public / 'tests').mkdir()
            (public / 'solution').mkdir()
            public_sha = digest_tree(public)
        script = ROOT / 'synthetic_task/tests/test.sh'
        asset = {'task': task, 'image_tag': image_tag, 'public_members': [],
                 'public_task_tree_sha256': public_sha,
                 'official_evaluator_members': [],
                 'native_tests_tree_sha256': digest_tree(script.parent),
                 'native_test_sh_sha256': sha(script),
                 'expected_native_reports': [], 'native_agent_seconds': 180,
                 'native_verifier_seconds': 120, 'synthetic_package_files': synthetic_members()}
    else:
        asset = descriptor(source, task, registered=True)
        with TemporaryDirectory(prefix='pos-public-check-') as tmp:
            public = Path(tmp) / 'public'
            materialize_public(source, task, public, asset['public_members'], registered=True)
            (public / 'tests').mkdir()
            (public / 'solution').mkdir()
            asset['public_task_tree_sha256'] = digest_tree(public)
            tests = Path(tmp) / 'tests'
            tests.mkdir()
            export_task(source, task, tests, registered=True)
            asset['native_tests_tree_sha256'] = digest_tree(tests)
            asset['native_test_sh_sha256'] = sha(tests / 'test.sh')
    image = image_identity(asset['image_tag'])
    repo = asset['image_tag'].rsplit(':', 1)[0]
    matches = [v for v in image['repo_digests'] if v.startswith(repo + '@sha256:')]
    if len(matches) != 1:
        raise RuntimeError('PoS fixed image digest missing or ambiguous')
    asset.update(image_id=image['image_id'], repo_digest=matches[0],
                 platform=image['platform'])
    row = {'order': 1, 'task': task, 'repeat': plan['occurrence'],
           'condition': 'P', 'research_candidate': plan['method']}
    method_name = {
        'PoS': 'released-core PoS-on-GA transfer',
        'PoS-citation-fixed': 'released-core PoS-on-GA transfer + decoded citation fix',
        'pos_pma_complement_v1': 'pos_pma_complement_v1',
        'pos_pma_shared_view_v1': 'pos_pma_shared_view_v1',
    }[plan['method']]
    method = {'name': method_name,
              'citation_mode': ('released_core' if plan['method'] == 'PoS' else
                                'visible_tool_fields_v2'),
              'upstream_commit': UPSTREAM, 'task_turns_max': 2 if synthetic else 300,
              'agent_wall_seconds': 180 if synthetic else 14400,
              'harbor_whole_trial_retries': 0,
              'task_profile_name': 'native_claude_cc_vibe_opus48',
              'pos_roles': ('belief', 'consistency', 'progress'),
              'role_max_tokens': ROLE_MAX_TOKENS,
              'role_thinking_type': ROLE_THINKING_TYPE,
              'role_temperature': ROLE_TEMPERATURE,
              'role_json_contract': ROLE_JSON_CONTRACT_VERSION,
              'role_input_contract': ROLE_INPUT_CONTRACT_VERSION,
              'role_object_instruction': ROLE_OBJECT_INSTRUCTION,
              'role_update_fields_instruction': ROLE_UPDATE_FIELDS_INSTRUCTION,
              'role_transport_retries': 0, 'synthetic_fixture': synthetic}
    if plan['method'] == 'pos_pma_complement_v1':
        method['pma_trigger'] = {'interval': 1, 'first_step': True,
                                 'sliding_window_size': 8,
                                 'actor_step_mapping': 'actor_attempt_plus_one'}
        method['candidate_limits'] = {'task_panel_chars': 16000,
            'phase2_advisory_chars': 16000, 'revision_chars': 12000,
            'history_events': 4, 'history_event_chars': 2000,
            'related_records': 8, 'complete_request_bytes': 90000,
            'byte_budget_basis': 'conservative_engineering_cap_not_token_context',
            'output_reserve': 'existing_frozen_max_tokens_per_role'}
        method['candidate_profile_status'] = 'host_pinned_pma_transport_v1_bound_to_run'
    elif plan['method'] == 'pos_pma_shared_view_v1':
        method['pma_trigger'] = {'interval': 1, 'first_step': True,
                                 'sliding_window_size': 8,
                                 'actor_step_mapping': 'actor_attempt_plus_one'}
        method['shared_view_contract'] = 'pma-history-before-pos-single-ga-view-v1'
        method['candidate_profile_status'] = 'host_pinned_pma_transport_v1_bound_to_run'
    if 'task_complete_response_policy' in plan:
        method['task_complete_response_policy'] = policy
    if 'runtime_policy' in plan:
        from experiment_runner.runtime_policy import resolve_policy
        resolved = resolve_policy(plan['runtime_policy'], asset, method)
        method.update(runtime_policy=resolved,
                      task_turns_max=resolved['effective_task_turns'],
                      agent_wall_seconds=resolved['effective_agent_seconds'])
    config_sha = hashlib.sha256(json.dumps(method, sort_keys=True,
        separators=(',', ':')).encode('utf-8')).hexdigest()
    certification = None
    if certification_dir is not None:
        if synthetic:
            raise RuntimeError('synthetic fixture does not accept live certification')
        from .certification import verify_evidence
        evidence = certification_dir.resolve(strict=True)
        verified = verify_evidence(evidence, require_committed=True,
                                   research_candidate=plan['method'])
        index = evidence / 'FILE_HASHES.json'
        certification = {'relative_path': index.relative_to(CHECKOUT).as_posix(),
                         'committed_evidence_sha256': sha(index),
                         'result': verified}
    pma_profile_sha256 = None
    if plan['method'] in {'pos_pma_complement_v1', 'pos_pma_shared_view_v1'} and (not synthetic or
            candidate_profile_fixture):
        if pma_profile is None:
            raise RuntimeError('candidate requires existing private PMA profile identity')
        profile_path = pma_profile.resolve(strict=True)
        private_profile = json.loads(profile_path.read_text(encoding='utf-8'))[
            'claude_monitor_opus48']
        if (private_profile.get('provider'), private_profile.get('api_mode'),
                private_profile.get('model'), private_profile.get('thinking_type')) != (
                'anthropic', 'messages', 'claude-opus-4-8', 'adaptive'):
            raise RuntimeError('candidate PMA profile route differs from pinned U route')
        if candidate_profile_fixture and (private_profile.get('apibase') !=
                'https://fake.invalid/no-network' or private_profile.get('apikey') !=
                'SYNTHETIC_TEST_ONLY'):
            raise RuntimeError('candidate fixture profile is not the isolated test profile')
        pma_profile_sha256 = sha(profile_path)
        method['pma_transport'] = {'kind': 'pinned_host_litellm_spool_v1',
            'profile_sha256': pma_profile_sha256,
            'max_tokens': private_profile['max_tokens'],
            'read_timeout': private_profile['read_timeout'],
            'temperature': private_profile['temperature'],
            'retry_policy': 'pinned_litellm_up_to_3_total_attempts'}
        config_sha = hashlib.sha256(json.dumps(method, sort_keys=True,
            separators=(',', ':')).encode('utf-8')).hexdigest()
    return {'schema': 'pos-ga-single-manifest-v1', 'status': 'prepared_not_executed',
            'execution_authorized': False, 'zero_model_fixture_only': synthetic,
            'candidate_profile_fixture_only': candidate_profile_fixture,
            'official_source_git_commit': COMMIT, 'upstream_commit': UPSTREAM,
            'task_profile_sha256': sha(task_profile),
            'pma_profile_sha256': pma_profile_sha256,
            'profile_identity_status': 'private_bytes_hashed_not_exported',
            'resolved_models_public': {'task': {key: profile.get(key) for key in
                ('model', 'max_tokens', 'temperature', 'max_retries')}},
            'source_files_sha256': source_hashes(
                include_shared=plan['method'] == 'pos_pma_shared_view_v1'),
            'vendor_files_sha256': vendor_hashes(),
            'pma_vendor_files_sha256': pma_vendor_hashes(),
            'config': method, 'config_sha256': config_sha,
            'planned_order': [row], 'assets': {task: asset},
            'native_shared_certification': certification}
