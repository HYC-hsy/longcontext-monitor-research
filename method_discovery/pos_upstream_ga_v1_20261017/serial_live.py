"""Thin prepare/run loop over the existing single_run entry and one-use bindings."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from .single_manifest import CHECKOUT, FOUR, source_hashes, vendor_hashes
from .worker import (ROLE_JSON_CONTRACT_VERSION, ROLE_INPUT_CONTRACT_VERSION,
                     ROLE_OBJECT_INSTRUCTION, ROLE_UPDATE_FIELDS_INSTRUCTION,
                     ROLE_MAX_TOKENS, ROLE_TEMPERATURE, ROLE_THINKING_TYPE)

ENTRY = ('method_discovery.curator_supervisor_convergence_v0.'
         'pma_full_upstream_ga_v1_20261013.single_run')
HISTORICAL_PROBE = Path(__file__).resolve().parent / 'raw_compat_v3/probe'
HISTORICAL_PROBE_HASHES = {
    'result.json': 'e4f4ce0426fc25d119369e2f855ca9cb0bf2601de93cb3226d34fedad5c3549c',
    'role_events.jsonl': 'c54968cdb60f86fc3c0a3181c75c06fe59636e41363c7d616086c4263906d781',
    'http_attempts.json': '94be22e76da39c547fddf300e2b5f157efd2c9e00a0a63d610e86d8cbd09834d',
}
HISTORICAL_SCOPE_SHA256 = 'f1294c085f7cb5d945180e0326280e5380c9568d14340bbab766d08a940931ea'
INFRA_BASELINE_COMMIT = 'cfc06c5e0a8a14631ffd65fcddf9cba742e1dbbf'
INFRA_PATH = ('method_discovery/curator_supervisor_convergence_v0/'
              'pma_full_upstream_ga_v1_20261013/live_launcher.py')
INFRA_BEFORE_SHA256 = 'b415b93d70a163bd261bf5aab2a429e953562fea614aa2de30c54c396dedf184'
INFRA_AFTER_SHA256 = '58f091cd4a83c90c693e5ae2742bfdd8c1365e449b6a78b1d8fbfe6e9300e81c'
INFRA_DIFF_SHA256 = '00d2924654f799bf91fef8e031469ff228b008c30f900a01b52df6f18e3bf755'
CAPTURE_BASELINE_COMMIT = 'db2d10c5d439c61b456dd6b9015076afd4ed664e'
CAPTURE_PATH = 'method_discovery/pos_upstream_ga_v1_20261017/worker.py'
HISTORICAL_WORKER_SHA256 = 'c49d1ffd712cce1e84ada7490c2aaee90bfdc777af11b6827518276b6c45378d'
CAPTURE_BEFORE_SHA256 = '09c0ef92d4a76a64d016f647f112ead3459dd61ef1d207b442678fbe0162ab1f'
CAPTURE_AFTER_SHA256 = '75ae2e1f1c072ab5e3cd46b6e732403630c58657a69eef75f5170e6bfbca30e0'
CAPTURE_DIFF_SHA256 = '166862bffd8dd4873d22f266ee9913fbe1980c62473f4c8e6ade0e18aeeae58e'
REVIEW_BASELINE_COMMIT = CAPTURE_BASELINE_COMMIT
REVIEWED_SOURCE_CHANGES = {
    'GenericAgent-main/research_runtime.py': ('b2372a50f1c8d7498c47e0555dc299d85e5986905ae5409982ec058a5a6daeba', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
    'method_discovery/pos_upstream_ga_v1_20261017/provider_capture.py': ('5ee9ab377c98d7a7059404d14a3c69b4a4466c46553b0cce990e5ebb8294f36a', '5887f32b0aa782654a4f073b5de6c22c3e7d7f0704c18238a217cd692064cc86'),
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/offline_launcher.py': ('b1201866b460d182124f0dbeca141f8eaf95be03b48df7237b8029c9e8633e7a', '54da093ecf7c2305b4bb3b19f9cc7eee2444d0cf020117b17d9816bd0dea7c05'),
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/pma_harbor_hooks.py': ('30c571b862767b1949ebae742d8b5b86fb570de2868d9a79c232975c6d788005', '20013d876e774173bddbbbd0ae34642c454d1cb12b91f20d87be6e536f80a997'),
    'method_discovery/pos_upstream_ga_v1_20261017/single_manifest.py': ('0b13b0b20efa45c0455bbde69a06bacf795a21f5912658e7cf1b6cd712e55b20', '8b4e0e73ad0847a449aac868249525ba965e06b433f12dfc24bfd88923eb875f'),
    'method_discovery/pos_upstream_ga_v1_20261017/certification.py': ('ce89d06ea419b2b260200a245b3bb7326471c147c1439ac06390f4e57b37a190', '195ba28bef94a5bf356cadedff8fd7ca5b717bbe7087c1e98eeb98e2658aa039'),
    'method_discovery/pos_upstream_ga_v1_20261017/collect_native_shared.py': ('cb318a59652379127becd8ea80bedff7f751d922d5317fddae0e687b901b8bd6', '4e29bb6d82a9af82416573b17c89c498950e5adde37df37a6d2bced393e77603'),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def base_arguments(parser):
    for name in ('task-profile-file', 'official-source-git', 'ga-source',
                 'runtime-root', 'worker-python', 'harbor-python', 'bench-root',
                 'harbor-source-root'):
        parser.add_argument('--' + name, required=True)


def common(args):
    return ['--task-profile-file', args.task_profile_file,
            '--official-source-git', args.official_source_git,
            '--ga-source', args.ga_source, '--runtime-root', args.runtime_root,
            '--worker-python', args.worker_python,
            '--harbor-python', args.harbor_python,
            '--bench-root', args.bench_root,
            '--harbor-source-root', args.harbor_source_root]


def _ancestor(commit):
    return subprocess.run(['git', 'merge-base', '--is-ancestor', commit, 'HEAD'],
                          cwd=CHECKOUT, check=False).returncode == 0


def _reviewed_infrastructure_diff():
    if not _ancestor(INFRA_BASELINE_COMMIT):
        raise RuntimeError('reviewed infrastructure baseline not in history')
    previous = subprocess.run(['git', 'show', INFRA_BASELINE_COMMIT + ':' + INFRA_PATH],
        cwd=CHECKOUT, capture_output=True, check=True).stdout
    delta = subprocess.run(['git', 'diff', '--no-ext-diff', '--binary',
        INFRA_BASELINE_COMMIT, 'HEAD', '--', INFRA_PATH],
        cwd=CHECKOUT, capture_output=True, check=True).stdout
    before = hashlib.sha256(previous).hexdigest()
    after = sha(CHECKOUT / INFRA_PATH)
    diff_sha = hashlib.sha256(delta).hexdigest()
    if (before != INFRA_BEFORE_SHA256 or after != INFRA_AFTER_SHA256 or
            diff_sha != INFRA_DIFF_SHA256):
        raise RuntimeError('shared launcher change differs from reviewed exact diff')
    return {'baseline_commit': INFRA_BASELINE_COMMIT, 'path': INFRA_PATH,
        'before_sha256': before, 'after_sha256': after, 'diff_sha256': diff_sha}


def _reviewed_capture_diff():
    if not _ancestor(CAPTURE_BASELINE_COMMIT):
        raise RuntimeError('reviewed PoS capture baseline not in history')
    previous = subprocess.run(['git', 'show',
        CAPTURE_BASELINE_COMMIT + ':' + CAPTURE_PATH], cwd=CHECKOUT,
        capture_output=True, check=True).stdout
    delta = subprocess.run(['git', 'diff', '--no-ext-diff', '--binary',
        CAPTURE_BASELINE_COMMIT, 'HEAD', '--', CAPTURE_PATH], cwd=CHECKOUT,
        capture_output=True, check=True).stdout
    before = hashlib.sha256(previous).hexdigest()
    after = sha(CHECKOUT / CAPTURE_PATH)
    diff_sha = hashlib.sha256(delta).hexdigest()
    if (before != CAPTURE_BEFORE_SHA256 or after != CAPTURE_AFTER_SHA256 or
            diff_sha != CAPTURE_DIFF_SHA256):
        raise RuntimeError('PoS worker capture repair differs from reviewed exact diff')
    return {'baseline_commit': CAPTURE_BASELINE_COMMIT, 'path': CAPTURE_PATH,
        'before_sha256': before, 'after_sha256': after, 'diff_sha256': diff_sha}


def _reviewed_source_changes():
    if not _ancestor(REVIEW_BASELINE_COMMIT):
        raise RuntimeError('provider capture review baseline not in history')
    rows = []
    for path, (expected_after, expected_diff) in REVIEWED_SOURCE_CHANGES.items():
        delta = subprocess.run(['git','diff','--no-ext-diff','--binary',
            REVIEW_BASELINE_COMMIT,'HEAD','--',path],cwd=CHECKOUT,
            capture_output=True,check=True).stdout
        after = sha(CHECKOUT/path)
        diff_sha = hashlib.sha256(delta).hexdigest()
        if after != expected_after or diff_sha != expected_diff:
            raise RuntimeError('provider capture infrastructure differs: '+path)
        rows.append({'path':path,'after_sha256':after,'diff_sha256':diff_sha})
    return rows


def native_unscored_review(scope_path, certification, profile_path, continuity_path):
    """Bind one *historical failure* to a new source-exact discovery scope."""
    from .certification import verify_evidence
    scope_path = Path(scope_path).resolve(strict=True)
    certification = Path(certification).resolve(strict=True)
    profile_path = Path(profile_path).resolve(strict=True)
    continuity_path = Path(continuity_path).resolve(strict=True)
    if verify_evidence(certification, require_committed=True).get('status') != 'pass':
        raise RuntimeError('current source-bound synthetic certification failed')
    scope = json.loads(scope_path.read_text(encoding='utf-8'))
    old_scope = HISTORICAL_PROBE.parent / 'preparation/authorized_serial_scope.json'
    if sha(old_scope) != HISTORICAL_SCOPE_SHA256 or any(
            sha(HISTORICAL_PROBE / name) != expected
            for name, expected in HISTORICAL_PROBE_HASHES.items()):
        raise RuntimeError('fixed historical v3 probe identity changed')
    old = json.loads((HISTORICAL_PROBE / 'result.json').read_text(encoding='utf-8'))
    events = [json.loads(line) for line in
        (HISTORICAL_PROBE / 'role_events.jsonl').read_text(encoding='utf-8').splitlines()]
    checks = (old.get('compatibility_checks') or {}).get('checks') or {}
    if (old.get('status') != 'failed' or old.get('schema') !=
            'pos-ga-live-compatibility-result-v3' or
            checks != {'initial_original_parse_committed': True,
                       'update_original_parse_resolved': True,
                       'sentinel_final_audit_resolved': True,
                       'final_textualization': True,
                       'valid_nonterminal_progress': False,
                       'applicable_work_finished': True,
                       'role_and_transport_protocol': True} or
            old.get('task_logical_calls') != 0 or
            old.get('task_tools_executed') != 0 or
            old.get('official_evaluator_calls') != 0 or
            old.get('pos_logical_calls') != 9 or old.get('http_attempts') != 9):
        raise RuntimeError('historical failure is outside the reviewed scope')
    for step, expected in ((-1, 1), (0, 2)):
        for event, count in (('belief_sentinel_audit_submitted', expected),
                             ('belief_sentinel_audit_completed', expected),
                             ('belief_sentinel_audit_failed', 0)):
            if sum(row.get('event') == event and row.get('step') == step
                   for row in events) != count:
                raise RuntimeError('initial or update Sentinel outcome differs')
    for event, step in (('belief_state_initialized', -1),
                        ('belief_state_updated', 0),
                        ('belief_candidate_repaired', 0),
                        ('belief_text_updated', -1),
                        ('belief_text_updated', 0),
                        ('belief_sentinel_progress_failed', 0)):
        if sum(row.get('event') == event and row.get('step') == step
               for row in events) != 1:
            raise RuntimeError('reviewed stage completion/failure differs')
    if any(row.get('event') in {'belief_model_parse_error',
            'belief_model_schema_error', 'belief_candidate_schema_error',
            'belief_candidate_rejected', 'belief_sentinel_model_parse_error',
            'belief_sentinel_progress_model_parse_error'} for row in events):
        raise RuntimeError('unreviewed original parser or audit failure')
    progress_response = [row for row in events if row.get('event') ==
                         'belief_sentinel_progress_model_response']
    progress_input = [row for row in events if row.get('event') ==
                      'belief_sentinel_progress_model_input']
    if len(progress_response) != 1 or len(progress_input) != 1:
        raise RuntimeError('historical progress identity differs')
    payload = json.loads(progress_response[0]['raw_response'])
    before_after = json.loads(progress_input[0]['messages'][1]['content'].splitlines()[0])
    before = before_after['belief_before']['world']
    after = before_after['belief_after']['world']
    transition = (old.get('partial_pos_result') or {}).get('health_transitions') or []
    if (payload.get('affected_record_ids') != ['e1', 's1'] or
            before['entities'].get('e1') != after['entities'].get('e1') or
            's1' in before['states'] or 's1' not in after['states'] or
            len(transition) != 1 or
            any(transition[0].get(key) is not None for key in
                ('progress', 'score', 'scoring_method')) or
            (old.get('partial_pos_result') or {}).get('scored_transitions') != 0):
        raise RuntimeError('unscored native progress is not the reviewed e1 case')
    continuity = json.loads(continuity_path.read_text(encoding='utf-8'))
    if (continuity.get('schema') != 'pos-native-unscored-continuity-v1' or
            continuity.get('model_calls') != 0 or
            continuity.get('archived_probe_status') != 'failed' or
            continuity.get('archived_role_events_sha256') !=
                HISTORICAL_PROBE_HASHES['role_events.jsonl'] or
            continuity.get('first_progress') is not None or
            continuity.get('first_score') is not None or
            continuity.get('first_scoring_method') is not None or
            continuity.get('first_update_status') != 'repaired' or
            continuity.get('first_progress_failed') is not True or
            continuity.get('first_window_ready') is not False or
            continuity.get('second_progress') != 1 or
            continuity.get('second_affected_record_ids') != ['s2'] or
            continuity.get('second_scored_transitions') != 1 or
            continuity.get('second_window_ready') is not False or
            continuity.get('recovery') is not None or
            continuity.get('next_decision_view_generated') is not True):
        raise RuntimeError('zero-model native continuity evidence is incomplete')
    old_identity = old['identity']
    current_sources = source_hashes()
    previous_sources = old_identity['source_files_sha256']
    changed = [name for name in current_sources if
               current_sources[name] != previous_sources.get(name)]
    infra = _reviewed_infrastructure_diff()
    capture = _reviewed_capture_diff()
    source_changes = _reviewed_source_changes()
    if (changed != ['GenericAgent-main/research_runtime.py', CAPTURE_PATH,
                    'method_discovery/pos_upstream_ga_v1_20261017/provider_capture.py',
                    'method_discovery/pos_upstream_ga_v1_20261017/serial_live.py',
                    INFRA_PATH,
                    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/offline_launcher.py',
                    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/pma_harbor_hooks.py',
                    'method_discovery/pos_upstream_ga_v1_20261017/single_manifest.py',
                    'method_discovery/pos_upstream_ga_v1_20261017/certification.py',
                    'method_discovery/pos_upstream_ga_v1_20261017/collect_native_shared.py'] or
            previous_sources.get(CAPTURE_PATH) != HISTORICAL_WORKER_SHA256 or
            current_sources[CAPTURE_PATH] != CAPTURE_AFTER_SHA256 or
            previous_sources.get(INFRA_PATH) != INFRA_BEFORE_SHA256 or
            current_sources[INFRA_PATH] != INFRA_AFTER_SHA256 or
            scope.get('schema') != 'pos-ga-user-authorized-serial-scope-v1' or
            not _ancestor(scope.get('code_commit', '')) or
            scope.get('source_files_sha256') != current_sources or
            scope.get('vendor_files_sha256') != vendor_hashes() or
            scope.get('vendor_files_sha256') != old_identity['vendor_files_sha256'] or
            scope.get('role_generation') != old_identity['role_generation'] or
            scope.get('certification_sha256') != sha(certification / 'FILE_HASHES.json') or
            scope.get('task_turns_max') != 300 or
            scope.get('agent_wall_seconds') != 14400 or
            scope.get('formal_runs_started') != 0 or
            tuple(row.get('task') for row in scope.get('prepared', [])) != FOUR or
            [row.get('order') for row in scope['prepared']] != [1, 2, 3, 4] or
            old_identity.get('profile_sha256') != sha(profile_path)):
        raise RuntimeError('current method/source/profile/asset scope differs')
    if len({row['run_id'] for row in scope['prepared']}) != 4 or len({
            row['run_root'] for row in scope['prepared']}) != 4:
        raise RuntimeError('prepared run identities are not independent')
    for row in scope['prepared']:
        directory = Path(row['directory']).resolve(strict=True)
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        identity = json.loads((directory / 'run_identity.json').read_text(encoding='utf-8'))
        if (directory.parent != scope_path.parent or
                sha(directory / 'manifest.json') != row['manifest_sha256'] or
                manifest.get('task_profile_sha256') != sha(profile_path) or
                manifest.get('config_sha256') != row['config_sha256'] or
                manifest.get('source_files_sha256') != current_sources or
                manifest.get('vendor_files_sha256') != vendor_hashes() or
                manifest.get('assets', {}).get(row['task'], {}).get('image_id') !=
                    row['image_id'] or
                manifest.get('assets', {}).get(row['task'], {}).get(
                    'native_tests_tree_sha256') != row['native_tests_tree_sha256'] or
                manifest.get('execution_authorized') is not False or
                identity.get('run_id') != row['run_id'] or
                identity.get('run_root') != row['run_root'] or
                Path(row['run_root']).exists() or
                (directory / 'authorization.json').exists() or
                (directory / 'batch_result.json').exists()):
            raise RuntimeError('prepared task/image/evaluator/output binding differs')
    note = scope['role_generation']
    return {'schema': 'pos-ga-native-unscored-review-v1',
        'decision': 'fixed_native_unscored_fallback_accepted_for_discovery',
        'historical_status': 'failed',
        'accepted_failure': 'progress_affected_record_ids_unchanged_e1_only',
        'historical_probe_sha256': HISTORICAL_PROBE_HASHES,
        'historical_scope_sha256': HISTORICAL_SCOPE_SHA256,
        'historical_code_commit': old_identity['code_commit'],
        'initial_audit': 'completed_once', 'update_audit': 'completed_twice_repaired',
        'progress': 'invalid_unscored_not_zero',
        'continuity_sha256': sha(continuity_path),
        'continuity_test_sha256': sha(Path(__file__).with_name(
            'test_unscored_continuity.py')),
        'current_scope_sha256': sha(scope_path),
        'current_code_commit': scope['code_commit'],
        'current_source_files_sha256': current_sources,
        'reviewed_infrastructure_diff': infra,
        'reviewed_capture_diff': capture,
        'reviewed_provider_capture_sources': source_changes,
        'current_vendor_files_sha256': vendor_hashes(),
        'input_contract_version': note['role_input_contract'],
        'object_instruction': note['role_object_instruction'],
        'object_instruction_sha256': hashlib.sha256(note[
            'role_object_instruction'].encode('utf-8')).hexdigest(),
        'update_instruction': note['role_update_fields_instruction'],
        'update_instruction_sha256': hashlib.sha256(note[
            'role_update_fields_instruction'].encode('utf-8')).hexdigest(),
        'profile_sha256': sha(profile_path),
        'certification_sha256': scope['certification_sha256'],
        'role_generation': note, 'prepared': scope['prepared'],
        'output_root': str(scope_path.parent),
        'task_turns_max': 300, 'agent_wall_seconds': 14400,
        'formal_runs_started_at_review': 0}


def prepare(args):
    root = Path(args.output).resolve(strict=False)
    root.mkdir(parents=True, exist_ok=False)
    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    tasks = tuple(row['task'] for row in plan['planned_order'])
    if (plan.get('schema') != 'pos-ga-serial-plan-v1' or
            plan.get('execution_authorized') is not False or tasks != FOUR or
            [row.get('order') for row in plan['planned_order']] != [1, 2, 3, 4]):
        raise RuntimeError('four-task historical order/identity differs')
    from .certification import verify_evidence
    certified = verify_evidence(Path(args.certification))
    if certified.get('status') != 'pass':
        raise RuntimeError('committed PoS synthetic certification failed')
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=CHECKOUT,
        capture_output=True, text=True, check=True).stdout.strip()
    prepared = []
    role_generation = {'role_max_tokens': ROLE_MAX_TOKENS,
        'role_thinking_type': ROLE_THINKING_TYPE,
        'role_temperature': ROLE_TEMPERATURE,
        'role_json_contract': ROLE_JSON_CONTRACT_VERSION,
        'role_input_contract': ROLE_INPUT_CONTRACT_VERSION,
        'role_object_instruction': ROLE_OBJECT_INSTRUCTION,
        'role_update_fields_instruction': ROLE_UPDATE_FIELDS_INSTRUCTION,
        'role_transport_retries': 0}
    for order, task in enumerate(tasks, 1):
        directory = root / f'{order:02d}_{task}'
        command = [sys.executable, '-B', '-m', ENTRY, 'prepare',
                   '--condition', 'P', '--research-candidate', 'PoS',
                   '--task', task, '--output', str(directory),
                   '--certification-dir', str(Path(args.certification).resolve()),
                   '--official-source-git', args.official_source_git,
                   '--task-profile-file', args.task_profile_file]
        completed = subprocess.run(command, cwd=CHECKOUT, capture_output=True,
                                   text=True, check=False)
        write_new(root / f'prepare_{order:02d}.json', {
            'task': task, 'command_public': command, 'return_code': completed.returncode,
            'stdout': completed.stdout, 'stderr': completed.stderr})
        if completed.returncode:
            raise RuntimeError('PoS prepare failed for order ' + str(order))
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        identity = json.loads((directory / 'run_identity.json').read_text(encoding='utf-8'))
        if (manifest['config']['task_turns_max'] != 300 or
                manifest['config']['agent_wall_seconds'] != 14400 or
                any(manifest['config'].get(key) != value
                    for key, value in role_generation.items()) or
                manifest['source_files_sha256'] != source_hashes() or
                manifest['vendor_files_sha256'] != vendor_hashes() or
                manifest.get('zero_model_fixture_only') is not False):
            raise RuntimeError('prepared PoS profile/source/budget differs')
        prepared.append({'order': order, 'task': task, 'directory': str(directory),
            'run_id': identity['run_id'], 'run_root': identity['run_root'],
            'manifest_sha256': sha(directory / 'manifest.json'),
            'profile_sha256': manifest['task_profile_sha256'],
            'config_sha256': manifest['config_sha256'],
            'image_id': manifest['assets'][task]['image_id'],
            'native_tests_tree_sha256': manifest['assets'][task]['native_tests_tree_sha256']})
    write_new(root / 'authorized_serial_scope.json', {
        'schema': 'pos-ga-user-authorized-serial-scope-v1',
        'authorization_basis': 'current user instruction; each run still requires a one-use binding',
        'historical_plan_sha256': sha(args.plan),
        'code_commit': head, 'certification_sha256': sha(
            Path(args.certification) / 'FILE_HASHES.json'),
        'source_files_sha256': source_hashes(), 'vendor_files_sha256': vendor_hashes(),
        'role_generation': role_generation,
        'prepared': prepared, 'task_turns_max': 300,
        'agent_wall_seconds': 14400, 'formal_runs_started': 0})
    print(json.dumps({'prepared': len(prepared), 'code_commit': head,
                      'scope': str(root / 'authorized_serial_scope.json')}))


def run(args):
    root = Path(args.output).resolve(strict=True)
    scope_path = root / 'authorized_serial_scope.json'
    scope = json.loads(scope_path.read_text(encoding='utf-8'))
    review_path = getattr(args, 'compatibility_review', None)
    compat_result = getattr(args, 'compatibility_result', None)
    if bool(review_path) == bool(compat_result):
        raise RuntimeError('select exactly one bound compatibility decision')
    if review_path:
        review = json.loads(Path(review_path).resolve(strict=True).read_text(
            encoding='utf-8'))
        expected = native_unscored_review(scope_path, args.certification,
            args.task_profile_file, args.continuity_evidence)
        if review != expected or Path(review_path).resolve(strict=True).parent != root:
            raise RuntimeError('independent native-unscored review identity differs')
    else:
        from .compatibility_probe import compatibility_checks
        compat_path = Path(compat_result).resolve(strict=True)
        compat = json.loads(compat_path.read_text(encoding='utf-8'))
        wire = json.loads((compat_path.parent / 'http_attempts.json').read_text(
            encoding='utf-8'))
        role_events = [json.loads(line) for line in
            (compat_path.parent / 'role_events.jsonl').read_text(
                encoding='utf-8').splitlines()]
        identity = compat.get('identity') or {}
        recomputed = compatibility_checks(role_events, compat.get('pos_result') or {},
            compat.get('initial_context') or {}, compat.get('update_context') or {},
            wire, compat.get('pos_roles') or [],
            work_finished=(compat.get('compatibility_checks') or {}).get('checks', {}).get(
                'applicable_work_finished') is True)
        if (compat.get('schema') != 'pos-ga-live-compatibility-result-v3' or
                compat.get('status') != 'passed' or
                recomputed != compat.get('compatibility_checks') or
                recomputed.get('status') != 'passed' or
                identity.get('schema') != 'pos-ga-live-compatibility-v3' or
                identity.get('scope_sha256') != sha(scope_path) or
                identity.get('code_commit') != scope.get('code_commit') or
                identity.get('source_files_sha256') != scope.get('source_files_sha256') or
                identity.get('vendor_files_sha256') != scope.get('vendor_files_sha256') or
                identity.get('certification_sha256') != scope.get('certification_sha256') or
                identity.get('role_generation') != scope.get('role_generation') or
                identity.get('profile_sha256') != sha(args.task_profile_file) or
                identity.get('probe_sha256') != sha(Path(__file__).with_name(
                    'compatibility_probe.py')) or
                identity.get('serial_sha256') != sha(__file__) or
                compat.get('role_events_sha256') != sha(
                    compat_path.parent / 'role_events.jsonl') or
                compat.get('http_attempts_sha256') != sha(
                    compat_path.parent / 'http_attempts.json') or
                not wire or
                compat.get('http_attempts') != len(wire) or
                compat.get('pos_logical_calls') != len([
                    row for row in role_events if row.get('event') == 'pos_role_request']) or
                not {'belief', 'consistency', 'progress'} <= set(compat.get('pos_roles', [])) or
                not any(row.get('event') == 'belief_model_input' and
                        row.get('operation') == 'textualize' for row in role_events) or
                not compat.get('update_context', {}).get('belief_text') or
                not all(row.get('http_status') == 200 and
                        row.get('returned_model') == 'claude-opus-4-8' for row in wire) or
                compat.get('task_logical_calls') != 0 or
                compat.get('official_evaluator_calls') != 0 or
                compat.get('task_tools_executed') != 0):
            raise RuntimeError('current bound PoS compatibility did not pass')
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=CHECKOUT,
        capture_output=True, text=True, check=True).stdout.strip()
    if (not _ancestor(scope['code_commit']) or
            scope['source_files_sha256'] != source_hashes() or
            scope['vendor_files_sha256'] != vendor_hashes() or
            sha(Path(args.certification) / 'FILE_HASHES.json') !=
            scope['certification_sha256']):
        raise RuntimeError('frozen execution code/certification changed')
    rows = scope['prepared']
    if tuple(row['task'] for row in rows) != FOUR:
        raise RuntimeError('serial order changed')
    for row in rows:
        order, task = row['order'], row['task']
        directory = Path(row['directory'])
        manifest_path = directory / 'manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        identity = json.loads((directory / 'run_identity.json').read_text(encoding='utf-8'))
        if (sha(manifest_path) != row['manifest_sha256'] or
                sha(args.task_profile_file) != row['profile_sha256'] or
                Path(row['run_root']).exists() or (directory / 'batch_result.json').exists()):
            raise RuntimeError('prepared run identity or output root changed')
        arm = manifest['planned_order'][0]
        binding = dict(arm, run_id=row['run_id'], run_root=row['run_root'],
                       batch_id=row['run_id'], config_sha256=row['config_sha256'])
        authorization = {'execution_authorized': True,
            'zero_model_fixture_only': False,
            'manifest_sha256': row['manifest_sha256'],
            'audited_code_commit': head, 'approved_arms': [arm],
            'run_bindings': [binding], 'run_id': row['run_id'],
            'batch_id': row['run_id'], 'config_sha256': row['config_sha256'],
            'output_root': identity['output_root']}
        auth_path = directory / 'authorization.json'
        write_new(auth_path, authorization)
        command = [sys.executable, '-B', '-m', ENTRY, 'run',
            '--output', str(directory), '--authorization', str(auth_path),
            *common(args)]
        record = {'order': order, 'task': task, 'run_id': row['run_id'],
                  'authorization_sha256': sha(auth_path),
                  'command_public': command, 'status': 'started'}
        write_new(directory / 'serial_start.json', record)
        try:
            with (directory / 'serial_stdout.txt').open('xb') as out, (
                    directory / 'serial_stderr.txt').open('xb') as err:
                completed = subprocess.run(command, cwd=CHECKOUT,
                                           stdout=out, stderr=err, check=False)
        finally:
            auth_path.unlink(missing_ok=True)
            write_new(directory / 'authorization_removed.json', {
                'authorization_removed': not auth_path.exists(),
                'authorization_sha256': record['authorization_sha256']})
        status_path = Path(row['run_root']) / 'archive/live_result.json'
        try:
            status = json.loads(status_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            status = None
        terminal_paths = list(Path(row['run_root']).glob('jobs/*/*/agent/task_terminal.json'))
        try:
            terminal = (json.loads(terminal_paths[0].read_text(encoding='utf-8'))
                        if len(terminal_paths) == 1 else None)
        except (OSError, ValueError):
            terminal = None
        from .collect_native_shared import collect_provider_capture, secrets_from_profile
        provider_public = None
        provider_collection_error = None
        try:
            provider_public = collect_provider_capture(
                Path(row['run_root']) / 'control/pos_archive',
                directory / 'provider_public',
                secrets_from_profile(Path(args.task_profile_file)),
                row['run_id'], task, profile_mode=True)
        except (OSError, ValueError, RuntimeError) as error:
            provider_collection_error = type(error).__name__
        summary = {'order': order, 'task': task, 'run_id': row['run_id'],
                   'run_exit': completed.returncode,
                   'status_available': status is not None,
                   'primary_failure': status.get('primary_failure') if status else None,
                   'cleanup_confirmed': status.get('cleanup_confirmed') if status else None,
                   'harbor_return_code': status.get('harbor_return_code') if status else None,
                   'native_result_status': (status.get('native_result') or {}).get('status')
                       if status else None,
                   'native_reward': ((status.get('native_result') or {}).get('rewards') or {})
                       if status else None,
                   'task_terminal_result': terminal.get('result') if terminal else None,
                   'pos_archive_status': status.get('pos_archive_status') if status else None,
                   'provider_collection_error_type':provider_collection_error,
                   'provider_capture':provider_public.get('capture') if provider_public else None}
        safe = bool(status and not status.get('primary_failure') and
            status.get('cleanup_confirmed') is True and
            status.get('remaining_containers') == [] and
            status.get('harbor_return_code') == 0 and
            status.get('frozen_product') is True and
            status.get('evaluation_released') is True and
            (status.get('native_result') or {}).get('status') == 'native_recorded' and
            status.get('native_script_observed') is True and
            len(status.get('native_script_executions') or []) == 1 and
            status.get('native_upload_checked') is True and
            status.get('native_reports_checked') is True and
            (status.get('pos_archive_status') or {}).get('result_bound') is True and
            (status.get('pos_archive_status') or {}).get('close_bound') is True and
            (status.get('pos_archive_status') or {}).get('archive_incomplete') is False and
            provider_collection_error is None and provider_public is not None and
            provider_public['capture']['capture_complete'] is True and
            (status.get('pos_archive_status') or {}).get('close_status') == 'graceful_exit' and
            terminal and terminal.get('run_id') == row['run_id'] and
            terminal.get('task_id') == task and
            terminal.get('result') in {'CURRENT_TASK_DONE', 'MAX_TURNS_EXCEEDED', 'EXITED'})
        summary['continue_safe'] = safe
        write_new(directory / 'serial_result.json', summary)
        print(json.dumps({'order': order, 'task': task,
                          'continue_safe': safe, 'reward': summary['native_reward']},
                         ensure_ascii=False), flush=True)
        if not safe:
            raise RuntimeError('formal run/evaluation/cleanup uncertain; later tasks stopped')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepared = commands.add_parser('prepare')
    base_arguments(prepared)
    prepared.add_argument('--plan', required=True)
    prepared.add_argument('--certification', required=True)
    prepared.add_argument('--output', required=True)
    launched = commands.add_parser('run')
    base_arguments(launched)
    launched.add_argument('--certification', required=True)
    launched.add_argument('--compatibility-result')
    launched.add_argument('--compatibility-review')
    launched.add_argument('--continuity-evidence')
    launched.add_argument('--output', required=True)
    reviewed = commands.add_parser('review')
    reviewed.add_argument('--scope', required=True)
    reviewed.add_argument('--certification', required=True)
    reviewed.add_argument('--task-profile-file', required=True)
    reviewed.add_argument('--continuity-evidence', required=True)
    reviewed.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args)
    elif args.command == 'review':
        write_new(Path(args.output), native_unscored_review(args.scope,
            args.certification, args.task_profile_file, args.continuity_evidence))
    else:
        run(args)


if __name__ == '__main__':
    main()
