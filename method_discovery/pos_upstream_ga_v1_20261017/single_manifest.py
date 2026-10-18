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
UPSTREAM = '6818cfa6434dbc91fcf67f0b3eb12a91db47433f'
SYNTHETIC_ID = 'pos-synthetic-file-http'
FOUR = ('nginx-request-logging', 'adaptive-rejection-sampler',
        'sqlite-with-gcov', 'write-compressor')
SOURCE_FILES = (
    'GenericAgent-main/agent_loop.py', 'GenericAgent-main/agentmain.py',
    'GenericAgent-main/ga.py', 'GenericAgent-main/llmcore.py',
    'GenericAgent-main/research_runtime.py',
    'GenericAgent-main/pos_bridge.py',
    'method_discovery/pos_upstream_ga_v1_20261017/episode.py',
    'method_discovery/pos_upstream_ga_v1_20261017/worker.py',
    'method_discovery/pos_upstream_ga_v1_20261017/provider_capture.py',
    'method_discovery/pos_upstream_ga_v1_20261017/compatibility_probe.py',
    'method_discovery/pos_upstream_ga_v1_20261017/serial_live.py',
    'method_discovery/curator_supervisor_convergence_v0/'
    'pma_full_upstream_ga_v1_20261013/single_run.py',
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


def source_hashes() -> dict:
    return {name: sha(CHECKOUT / name) for name in SOURCE_FILES}


def vendor_hashes() -> dict:
    return {p.relative_to(ROOT / 'vendor').as_posix(): sha(p)
            for p in sorted((ROOT / 'vendor').rglob('*')) if p.is_file()
            and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def synthetic_members() -> dict:
    base = ROOT / 'synthetic_task'
    return {p.relative_to(base).as_posix(): sha(p) for p in sorted(base.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}


def prepare(plan: dict, source: Path, task_profile: Path,
            certification_dir: Path | None = None) -> dict:
    if (plan.get('schema') != 'pos-ga-single-plan-v1' or
            plan.get('execution_authorized') is not False or
            plan.get('official_source_git_commit') != COMMIT or
            plan.get('condition') != 'P' or plan.get('method') != 'PoS' or
            type(plan.get('occurrence')) is not int or plan['occurrence'] < 1):
        raise RuntimeError('PoS single-run plan identity invalid')
    task = plan['task']
    synthetic = plan.get('synthetic_fixture') is True
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
           'condition': 'P', 'research_candidate': 'PoS'}
    method = {'name': 'released-core PoS-on-GA transfer',
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
    config_sha = hashlib.sha256(json.dumps(method, sort_keys=True,
        separators=(',', ':')).encode('utf-8')).hexdigest()
    certification = None
    if certification_dir is not None:
        if synthetic:
            raise RuntimeError('synthetic fixture does not accept live certification')
        from .certification import verify_evidence
        evidence = certification_dir.resolve(strict=True)
        verified = verify_evidence(evidence, require_committed=True)
        index = evidence / 'FILE_HASHES.json'
        certification = {'relative_path': index.relative_to(CHECKOUT).as_posix(),
                         'committed_evidence_sha256': sha(index),
                         'result': verified}
    return {'schema': 'pos-ga-single-manifest-v1', 'status': 'prepared_not_executed',
            'execution_authorized': False, 'zero_model_fixture_only': synthetic,
            'official_source_git_commit': COMMIT, 'upstream_commit': UPSTREAM,
            'task_profile_sha256': sha(task_profile),
            'profile_identity_status': 'private_bytes_hashed_not_exported',
            'resolved_models_public': {'task': {key: profile.get(key) for key in
                ('model', 'max_tokens', 'temperature', 'max_retries')}},
            'source_files_sha256': source_hashes(), 'vendor_files_sha256': vendor_hashes(),
            'config': method, 'config_sha256': config_sha,
            'planned_order': [row], 'assets': {task: asset},
            'native_shared_certification': certification}
