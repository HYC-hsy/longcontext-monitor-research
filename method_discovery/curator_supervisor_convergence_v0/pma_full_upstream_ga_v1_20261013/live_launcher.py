"""Explicitly authorized PMA/GA four-arm entry; no offline flag enables it."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

from long_context_bench.scripts.isolated_run_bundle import digest_tree

from .offline_launcher import (STAGE, TASKS, _prepare_common,
                               capture_mounts, clean_owned_containers)
from .pma_harbor_hooks import verify_live_spec
from .export_official_evaluator import (COMMIT as OFFICIAL_COMMIT,
                                         export_task, official_members)
from .prepare_six_task_manifest import (SOURCE_FILES, V3_SOURCE_FILES, EVIDENCE_FILES,
                                        _committed_source_sha)
from .two_task_certification import verify_evidence


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _native_schema(manifest: dict) -> bool:
    return manifest.get('schema') in {'pma-ga-live-manifest-v2',
                                      'pma-ga-live-manifest-v3',
                                      'pma-ga-live-manifest-v4',
                                      'pma-ga-live-manifest-v5',
                                      'pos-ga-single-manifest-v1'}


def _evaluator_members(manifest: dict, task: str) -> list[dict]:
    """Resolve the frozen evaluator member schema without losing either alias."""
    asset = manifest['assets'][task]
    pos_formal = (manifest.get('schema') == 'pos-ga-single-manifest-v1' and
                  manifest.get('zero_model_fixture_only') is not True)
    primary = 'evaluator_members' if pos_formal else 'official_evaluator_members'
    alternate = ('official_evaluator_members' if primary == 'evaluator_members'
                 else 'evaluator_members')
    for name in (primary, alternate):
        if name in asset and (not isinstance(asset[name], list) or
                any(not isinstance(item, dict) or
                    not isinstance(item.get('path'), str) or not item['path'] or
                    not isinstance(item.get('sha256'), str) or not item['sha256']
                    for item in asset[name])):
            raise RuntimeError('invalid frozen evaluator members: ' + name)
    if primary not in asset:
        raise RuntimeError('frozen evaluator members missing: ' + primary)
    members = asset[primary]
    if alternate in asset and asset[alternate] != members:
        raise RuntimeError('conflicting frozen evaluator member aliases')
    if not members and not (manifest.get('zero_model_fixture_only') is True and
                            task == 'pos-synthetic-file-http'):
        raise RuntimeError('formal evaluator member list is empty')
    return members


def _stage_verifier(root: Path, task: str, manifest: dict,
                    official_source_git: Path) -> dict:
    target = root / 'public_task' / 'tests'
    commits = [manifest.get(name) for name in
               ('official_source_git_commit', 'official_evaluator_commit')
               if name in manifest]
    if not commits or any(commit != OFFICIAL_COMMIT for commit in commits):
        raise RuntimeError('PMA manifest does not identify fixed official evaluator blobs')
    expected = manifest['assets'][task]
    source = official_source_git.resolve(strict=True)
    members = [{k: v for k, v in item.items() if k != 'raw'}
               for item in official_members(source, task,
                   registered=manifest.get('schema') in {
                       'pma-ga-live-manifest-v4', 'pma-ga-live-manifest-v5',
                       'pos-ga-single-manifest-v1'})]
    if members != _evaluator_members(manifest, task):
        raise RuntimeError('PMA official evaluator members differ from frozen manifest')
    export_task(source, task, target,
                registered=manifest.get('schema') in {
                    'pma-ga-live-manifest-v4', 'pma-ga-live-manifest-v5',
                    'pos-ga-single-manifest-v1'})
    identity = {'native_tests_tree_sha256': digest_tree(target),
                'native_test_sh_sha256': _sha(target / 'test.sh')}
    if any(identity[key] != expected[key] for key in identity):
        raise RuntimeError('PMA native evaluator differs from frozen source')
    if digest_tree(target) != identity['native_tests_tree_sha256']:
        raise RuntimeError('PMA staged evaluator bytes changed')
    return identity


def _require_evaluation_state_contract(manifest: dict) -> None:
    """Bind the native SHARED protocol to code and zero-model raw evidence."""
    if manifest.get('schema') == 'pos-ga-single-manifest-v1':
        from method_discovery.pos_upstream_ga_v1_20261017.single_manifest import (
            source_hashes, vendor_hashes, pma_vendor_hashes, synthetic_members)
        if (manifest.get('upstream_commit') !=
                '6818cfa6434dbc91fcf67f0b3eb12a91db47433f' or
                manifest.get('source_files_sha256') != source_hashes() or
                manifest.get('vendor_files_sha256') != vendor_hashes() or
                manifest.get('pma_vendor_files_sha256') != pma_vendor_hashes()):
            raise RuntimeError('PoS source/vendor freeze changed')
        if manifest.get('zero_model_fixture_only') is True:
            asset = next(iter(manifest['assets'].values()))
            if asset.get('synthetic_package_files') != synthetic_members():
                raise RuntimeError('PoS synthetic package freeze changed')
            return
        cert = manifest.get('native_shared_certification')
        if not isinstance(cert, dict) or not cert.get('committed_evidence_sha256'):
            raise RuntimeError('PoS native-SHARED synthetic certification absent')
        from method_discovery.pos_upstream_ga_v1_20261017.single_manifest import CHECKOUT
        path = (CHECKOUT / cert.get('relative_path', '')).resolve(strict=True)
        if not path.is_relative_to(CHECKOUT) or _sha(path) != cert['committed_evidence_sha256']:
            raise RuntimeError('PoS native-SHARED certification bytes differ')
        from method_discovery.pos_upstream_ga_v1_20261017.certification import verify_evidence
        research = manifest['planned_order'][0]['research_candidate']
        if verify_evidence(path.parent, require_committed=True,
                           research_candidate=research) != cert.get('result'):
            raise RuntimeError('PoS native-SHARED certification result differs')
        return
    if manifest.get('schema') == 'pma-ga-live-manifest-v3':
        if manifest.get('zero_model_fixture_only') is True:
            return
        cert = manifest.get('native_shared_certification')
        if (manifest.get('status') != 'prepared_not_executed' or
                not isinstance(cert, dict) or
                cert.get('harbor_commit') !=
                '459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc' or
                set(cert.get('source_files', {})) != set(V3_SOURCE_FILES)):
            raise RuntimeError('V3 target-image lifecycle certification not frozen')
        checkout = STAGE.parents[2]
        for name in V3_SOURCE_FILES:
            if _committed_source_sha(checkout, name) != cert['source_files'][name]:
                raise RuntimeError('V3 certified source bytes changed')
        evidence = STAGE / 'two_task_live_20261015' / 'zero_model_certification'
        if verify_evidence(evidence, checkout, manifest['planned_order']) != cert.get('evidence'):
            raise RuntimeError('V3 zero-model evidence changed')
        return
    if manifest.get('schema') in {'pma-ga-live-manifest-v4',
                                  'pma-ga-live-manifest-v5'}:
        if manifest.get('zero_model_fixture_only') is True:
            return
        from .single_run_certification import (HARBOR_COMMIT, SOURCE_FILES,
                                               CANDIDATE_SOURCE_FILES,
                                               source_identity, verify_evidence)
        cert = manifest.get('native_shared_certification')
        checkout = STAGE.parents[2]
        research = (manifest['planned_order'][0]['research_candidate']
                    if manifest['schema'] == 'pma-ga-live-manifest-v5' else None)
        expected_files = CANDIDATE_SOURCE_FILES if research is not None else SOURCE_FILES
        if (manifest.get('status') != 'prepared_not_executed' or
                not isinstance(cert, dict) or cert.get('harbor_commit') != HARBOR_COMMIT or
                set(cert.get('source_files', {})) != set(expected_files) or
                cert.get('source_files') != source_identity(checkout,
                    candidate=research is not None)):
            raise RuntimeError('single-run native lifecycle source certification differs')
        evidence = (checkout / cert.get('evidence_path', '')).resolve(strict=True)
        if (not evidence.is_relative_to(checkout) or
                verify_evidence(evidence, research_candidate=research) != cert.get('evidence')):
            raise RuntimeError('single-run native lifecycle evidence differs')
        return
    if manifest.get('schema') == 'pma-ga-live-manifest-v2':
        cert = manifest.get('native_shared_certification')
        if (manifest.get('status') != 'prepared_not_executed' or
                not isinstance(cert, dict) or
                cert.get('harbor_commit') !=
                '459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc' or
                set(cert.get('source_files', {})) != set(SOURCE_FILES) or
                set(cert.get('evidence_files', {})) != set(EVIDENCE_FILES)):
            raise RuntimeError('six-task SHARED evidence/identity not frozen')
        checkout = STAGE.parents[2]
        evidence = STAGE / 'six_task_native_base_20261014_v3'
        for name in SOURCE_FILES:
            if _committed_source_sha(checkout, name) != cert['source_files'][name]:
                raise RuntimeError('six-task SHARED source bytes changed')
        for name in EVIDENCE_FILES:
            if _sha(evidence / name) != cert['evidence_files'][name]:
                raise RuntimeError('six-task SHARED evidence bytes changed')
        index = json.loads((evidence / 'FILE_HASHES.json').read_text(encoding='utf-8'))
        for item in index['files']:
            path = (checkout / item['path']).resolve(strict=True)
            if not path.is_relative_to(evidence) or _sha(path) != item['sha256']:
                raise RuntimeError('six-task SHARED raw evidence changed')
        images = json.loads((evidence / 'image_checks.json').read_text(encoding='utf-8'))
        if (len(images) != 6 or any(row.get('exit_code') != 0 or
                                    not row.get('hidden_material_absent') for row in images)):
            raise RuntimeError('six-task image/hidden-material evidence incomplete')
        compared = json.loads((evidence / 'request_comparison.json').read_text(
            encoding='utf-8'))
        if (compared.get('only_metadata_differs') is not True or
                compared.get('b_second_request_reminder_visible') is not True):
            raise RuntimeError('six-task A/B fake request identity not established')
        controller = json.loads((evidence / 'controller_entry/batch.json').read_text(
            encoding='utf-8'))
        if (len(controller.get('arms', [])) != 1 or
                len(controller.get('not_started', [])) != 23 or
                controller['arms'][0]['order'] != 1 or
                controller['arms'][0].get('status', {}).get('cleanup_confirmed') is not True):
            raise RuntimeError('six-task controller-to-Harbor fixture incomplete')
        test_log = (evidence / 'unittest.stderr.txt').read_text(encoding='utf-16')
        match = re.search(r'Ran (\d+) tests', test_log)
        if (match is None or int(match.group(1)) < 19 or
                re.search(r'\bOK(?: \(skipped=\d+\))?\s*$', test_log) is None):
            raise RuntimeError('six-task offline test record incomplete')
        def fixture(number: str) -> dict:
            return json.loads((evidence / 'fixtures' / number / 'archive' /
                               'fixture_result.json').read_text(encoding='utf-8'))
        if (not fixture('02').get('verification_released') or
                not fixture('03').get('verification_released') or
                fixture('04').get('verification_released') or
                fixture('08').get('native_result', {}).get('status') != 'unavailable' or
                fixture('09').get('native_result', {}).get('exception_info', {}).get(
                    'exception_type') != 'AgentTimeoutError' or
                not fixture('10').get('native_reports_checked', {}).get(
                    'all_reports_executed') or
                fixture('11').get('frozen_product') or
                fixture('13').get('native_result', {}).get('exception_info', {}).get(
                    'exception_type') != 'AgentTimeoutError' or
                not fixture('13').get('verification_released') or
                fixture('16').get('native_result', {}).get('exception_info', {}).get(
                    'exception_type') != 'NonZeroAgentExitCodeError' or
                not fixture('16').get('verification_released')):
            raise RuntimeError('six-task native lifecycle fixture outcomes changed')
        return
    raise RuntimeError('PMA live evaluation state/environment transition is not '
                       'certified; no Task/provider request may start')


def _worker_clearance(root: Path, worker: subprocess.Popen | None, run_id: str) -> dict | None:
    target = root / 'control' / 'sidecar_stopped.json'
    if target.exists():
        return json.loads(target.read_text(encoding='utf-8'))
    if worker is None:
        clearance = {'run_id': run_id, 'clean': True, 'stopped': True,
                     'pma_finalization': 'not_enabled'}
    elif worker.poll() is None:
        return None
    else:
        receipt = root / 'host_private' / 'worker_exit.json'
        try:
            exit_value = json.loads(receipt.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            exit_value = None
        identity_valid = (not isinstance(exit_value, dict) or
                          exit_value.get('run_id', run_id) == run_id)
        stopped_receipt = root / 'host_private/worker_stopped_without_task_end.json'
        try:
            stopped_value = json.loads(stopped_receipt.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            stopped_value = None
        finalization = (dict(exit_value) if isinstance(exit_value, dict) else
                        {'status': 'unknown_no_exit_receipt'})
        if isinstance(stopped_value, dict):
            finalization['local_save'] = stopped_value.get('local_save')
            finalization['remote_execution'] = stopped_value.get('remote_execution')
            finalization['stop_reason_detail'] = stopped_value.get('reason')
        # A dead worker cannot issue another response. Saving memory is a
        # separate outcome, not the definition of writer quiescence.
        clearance = {'run_id': run_id, 'clean': identity_valid, 'stopped': True,
                     'worker_pid': worker.pid, 'worker_return_code': worker.returncode,
                     'pma_finalization': finalization}
    target.write_text(json.dumps(clearance, sort_keys=True), encoding='utf-8')
    return clearance


def _advance_worker_stop(root: Path, worker: subprocess.Popen | None,
                         deadline: float, pending_at: float | None,
                         stop_at: float | None) -> tuple[float | None, float | None]:
    if (root / 'control/agent_end_pending.json').is_file() and pending_at is None:
        pending_at = time.monotonic()
    if worker is None or worker.poll() is not None:
        return pending_at, stop_at
    if (time.time() >= deadline or
            (pending_at is not None and time.monotonic() - pending_at >= 2)):
        if stop_at is None:
            (root / 'host_private/stop.request').touch()
            stop_at = time.monotonic()
        elif time.monotonic() - stop_at >= 10:
            worker.kill()
    return pending_at, stop_at


def _native_trial_result(root: Path) -> dict:
    """Read this fresh Harbor job's result, without interpreting task answers."""
    candidates = []
    for path in (root / 'jobs').glob('*/*/result.json'):
        data = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data, dict) and 'verifier_result' in data:
            candidates.append((path, data))
    if len(candidates) != 1:
        return {'status': 'unavailable', 'reason': 'one_trial_result_not_found',
                'candidates': len(candidates)}
    path, data = candidates[0]
    verifier = data.get('verifier_result')
    rewards = verifier.get('rewards') if isinstance(verifier, dict) else None
    if not isinstance(rewards, dict) or not rewards:
        return {'status': 'unavailable', 'reason': 'native_reward_missing',
                'result_path': str(path.relative_to(root)),
                'exception_info': data.get('exception_info')}
    return {'status': 'native_recorded', 'rewards': rewards,
            'result_path': str(path.relative_to(root)),
            'exception_info': data.get('exception_info'),
            'agent_execution': data.get('agent_execution'),
            'verifier': data.get('verifier')}


def _owned_volume_clearance(root: Path) -> dict:
    try:
        identity = json.loads((root / 'archive/agent_start_identity.json').read_text(
            encoding='utf-8'))
    except (OSError, ValueError):
        return {'status': 'unknown', 'reason': 'mount_identity_unavailable'}
    names = {m.get('Name') for m in identity.get('mounts', [])
             if m.get('Type') == 'volume'}
    if None in names or not names:
        return {'status': 'unknown', 'reason': 'owned_volume_names_unavailable'}
    remaining = []
    for name in sorted(names):
        check = subprocess.run(['docker', 'volume', 'inspect', name],
                               capture_output=True, text=True, timeout=30)
        if check.returncode == 0:
            remaining.append(name)
        elif 'no such volume' not in check.stderr.lower():
            return {'status': 'unknown', 'reason': 'docker_volume_inspect_failed',
                    'name': name}
    return {'status': 'clean' if not remaining else 'remaining',
            'names': sorted(names), 'remaining': remaining}


def run_live(args) -> dict:
    manifest_path = Path(args.manifest).resolve(strict=True)
    authorization_path = Path(args.authorization).resolve(strict=True)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    authorized = json.loads(authorization_path.read_text(encoding='utf-8'))
    if (manifest.get('schema') not in {'pma-ga-live-manifest-v1',
                                       'pma-ga-live-manifest-v2',
                                       'pma-ga-live-manifest-v3',
                                       'pma-ga-live-manifest-v4',
                                       'pma-ga-live-manifest-v5',
                                       'pos-ga-single-manifest-v1'} or
            manifest.get('execution_authorized') is not False or
            authorized.get('execution_authorized') is not True or
            authorized.get('manifest_sha256') != _sha(manifest_path)):
        raise RuntimeError('PMA authorization absent or changed')
    task_policy = manifest.get('config', {}).get('task_complete_response_policy', 'disabled')
    actual_task_policy = ('complete-response-v1' if
        os.environ.get('GA_TASK_COMPLETE_RESPONSE') == '1' else 'disabled')
    if manifest.get('schema') == 'pos-ga-single-manifest-v1' and (
            task_policy not in {'disabled', 'complete-response-v1'} or
            authorized.get('task_complete_response_policy', 'disabled') != task_policy or
            actual_task_policy != task_policy):
        raise RuntimeError('Task response policy differs from PoS manifest/authorization')
    fixture = bool(getattr(args, 'zero_model_fixture', False))
    if fixture != (manifest.get('zero_model_fixture_only') is True and
                   authorized.get('zero_model_fixture_only') is True):
        raise RuntimeError('zero-model fixture identity does not match both records')
    profile_fixture = bool(getattr(args, 'candidate_profile_fixture', False))
    if profile_fixture != (manifest.get('candidate_profile_fixture_only') is True and
                           authorized.get('candidate_profile_fixture_only') is True):
        raise RuntimeError('candidate profile fixture identity differs')
    candidate = getattr(args, 'research_candidate', 'U')
    expected_candidate = (manifest['planned_order'][0]['research_candidate']
        if manifest['schema'] in {'pma-ga-live-manifest-v5',
                                  'pos-ga-single-manifest-v1'} else 'U')
    if candidate != expected_candidate or (args.condition == 'A' and candidate != 'U'):
        raise RuntimeError('PMA candidate differs from frozen plan')
    if (manifest.get('schema') in {'pma-ga-live-manifest-v3',
                                   'pma-ga-live-manifest-v4',
                                   'pma-ga-live-manifest-v5',
                                   'pos-ga-single-manifest-v1'} and
            Path(args.ga_source).resolve(strict=True) !=
            (STAGE.parents[2] / 'GenericAgent-main').resolve(strict=True)):
        raise RuntimeError('V3 GA source is not the frozen repository bridge')
    candidate_profile = (args.condition == 'P' and candidate in
                         {'pos_pma_complement_v1', 'pos_pma_shared_view_v1'}
                         and (not fixture or profile_fixture))
    if profile_fixture and (not fixture or not candidate_profile or
            args.task != 'pos-synthetic-file-http'):
        raise RuntimeError('profile fixture requires isolated synthetic candidate')
    memory_profile_path = None
    if args.condition == 'B' or candidate_profile:
        if not args.pma_profile_file:
            raise RuntimeError('PMA Opus 4.8 profile is required for B')
        memory_profile_path = Path(args.pma_profile_file).resolve(strict=True)
        if _sha(memory_profile_path) != manifest.get('pma_profile_sha256'):
            raise RuntimeError('PMA memory profile differs from frozen identity')
    if Path(args.run_root).exists():
        raise FileExistsError(args.run_root)
    if args.condition == 'P':
        if candidate not in {'PoS', 'PoS-citation-fixed',
                             'pos_pma_complement_v1', 'pos_pma_shared_view_v1'} or fixture != (
                             args.task == 'pos-synthetic-file-http'):
            raise RuntimeError('PoS method or fixture identity differs')
        if fixture:
            from method_discovery.pos_upstream_ga_v1_20261017.single_manifest import ROOT
            args.pos_fake_replies = str((ROOT.parent / 'pos_pma_complement_v1_20261019' /
                'synthetic_replies.json') if candidate in
                {'pos_pma_complement_v1', 'pos_pma_shared_view_v1'} else
                (ROOT / 'synthetic_task/pos_replies.json'))
    args.execution_authorized = False
    prepared = _prepare_common(args, fake_gateway=False)
    root = Path(args.run_root).resolve(strict=True)
    if fixture:
        from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.pilot_offline_harbor import _offline_gateway
        compose_path = root / 'bundle/isolation.compose.json'
        compose = json.loads(compose_path.read_text(encoding='utf-8'))
        main_network = compose['services']['main'].pop('network_mode', None)
        compose['services']['main']['network_mode'] = 'none'
        compose_path.write_text(json.dumps(compose), encoding='utf-8')
        _offline_gateway(root, Path(args.runtime_root), args.python_home)
        compose = json.loads(compose_path.read_text(encoding='utf-8'))
        if profile_fixture:
            from method_discovery.pos_upstream_ga_v1_20261017.single_manifest import ROOT
            replies = ROOT.parent / 'pos_pma_complement_v1_20261019' / 'synthetic_replies.json'
            compose['services']['model-gateway']['volumes'].append(
                f'{replies.resolve(strict=True).as_posix()}:/pos_role_replies.json:ro')
        compose['services']['model-gateway']['environment'] = {
            'PMA_MULTITURN_FIXTURE': '1',
            'PMA_SERVICE_FIXTURE': '1' if os.environ.get('PMA_SERVICE_FIXTURE') == '1' else '0',
            'POS_SYNTHETIC_FIXTURE': '1' if args.condition == 'P' else '0',
            'POS_CANDIDATE_PROFILE_FIXTURE': '1' if profile_fixture else '0'}
        if profile_fixture and os.environ.get('POS_SYNTHETIC_LONG_OUTPUT') == '1':
            compose['services']['model-gateway']['environment'][
                'POS_SYNTHETIC_LONG_OUTPUT'] = '1'
        if main_network is None:
            compose['services']['main'].pop('network_mode')
        else:
            compose['services']['main']['network_mode'] = main_network
        compose_path.write_text(json.dumps(compose), encoding='utf-8')
    if prepared['public_task_tree_sha256'] != manifest['assets'][args.task]['public_task_tree_sha256']:
        raise RuntimeError('PMA public task package differs from frozen identity')
    order = args.order
    spec = {
        'schema': 'pma-ga-live-run-v1', 'mode': 'authorized_live',
        'execution_authorized': True, 'order': order, 'task': args.task,
        'task_id': args.task, 'condition': args.condition, 'run_id': args.run_id,
        'research_candidate': candidate,
        'zero_model_fixture_only': fixture,
        'candidate_profile_fixture_only': profile_fixture,
        'run_root': str(root), 'image_id': prepared['image_id'],
        'control_root': str(root / 'control'), 'archive_root': str(root / 'archive'),
        'manifest_path': str(manifest_path), 'manifest_sha256': _sha(manifest_path),
        'authorization_path': str(authorization_path),
        'authorization_sha256': _sha(authorization_path),
        'audited_code_commit': authorized['audited_code_commit'],
    }
    if _native_schema(manifest):
        spec.update(repeat=args.repeat, batch_id=authorized['batch_id'],
                    config_sha256=manifest['config_sha256'],
                    evaluation_protocol='official_shared_v2',
                    official_source_git_commit=OFFICIAL_COMMIT,
                    expected_native_reports=manifest['assets'][args.task][
                        'expected_native_reports'],
                    official_evaluator_files=[{
                        'relative': '/'.join(item['path'].split('/')[1:]),
                        'sha256': item['sha256']}
                        for item in _evaluator_members(manifest, args.task)])
    verify_live_spec(spec)
    if _sha(Path(args.task_profile_file)) != manifest['task_profile_sha256']:
        raise RuntimeError('PMA Task profile differs from frozen identity')
    # A zero-model lifecycle fixture never places official tests in the Task
    # tree. The live path still stages and byte-checks the fixed Git blobs.
    if fixture and args.condition == 'P':
        from method_discovery.pos_upstream_ga_v1_20261017.single_manifest import ROOT
        test_script = root / 'public_task/tests/test.sh'
        test_script.write_bytes((ROOT / 'synthetic_task/tests/test.sh').read_bytes())
        staged = {'native_tests_tree_sha256': digest_tree(test_script.parent),
                  'native_test_sh_sha256': _sha(test_script)}
    elif fixture:
        test_script = root / 'public_task/tests/test.sh'
        service_check = ("/opt/m4-runtime/python/cpython-3.12.12-linux-x86_64-gnu/"
                         "bin/python3.12 -c \"import urllib.request; "
                         "assert urllib.request.build_opener("
                         "urllib.request.ProxyHandler({})).open("
                         "'http://127.0.0.1:19173').status == 200\"\n"
                         if os.environ.get('PMA_SERVICE_FIXTURE') == '1' else '')
        test_script.write_text('#!/bin/sh\nset -e\n' + service_check +
                               'mkdir -p /logs/verifier\n'
                               'printf "1\\n" > /logs/verifier/reward.txt\n',
                               encoding='utf-8', newline='\n')
        staged = {'native_tests_tree_sha256': digest_tree(test_script.parent),
                  'native_test_sh_sha256': _sha(test_script)}
    else:
        staged = _stage_verifier(root, args.task, manifest,
                                 Path(args.official_source_git))
    spec.update(staged)
    if fixture:
        spec.update(official_source_git_commit='synthetic_no_official_evaluator',
                    expected_native_reports=[],
                    official_evaluator_files=[{'relative': 'tests/test.sh',
                                               'sha256': staged['native_test_sh_sha256']}])
        if args.condition == 'P':
            spec['evaluation_protocol'] = 'synthetic_shared_v1'
    _require_evaluation_state_contract(manifest)
    if args.condition == 'P' and (not fixture or profile_fixture):
        staged_pos = root / 'bundle/source/pos_runtime'
        binding = {
            'schema': 'pos-ga-transport-binding-v1', 'transport': 'profile',
            'run_id': args.run_id, 'task_id': args.task,
            'upstream_commit': manifest['upstream_commit'],
            'manifest_sha256': _sha(manifest_path),
            'authorization_sha256': _sha(authorization_path),
            'config_sha256': manifest['config_sha256'],
            'worker_sha256': _sha(staged_pos / 'worker.py'),
            'episode_sha256': _sha(staged_pos / 'episode.py'),
            'citation_fix_sha256': _sha(staged_pos / 'citation_fix.py'),
            'candidate_sha256': _sha(staged_pos / 'candidate.py'),
            'memory_adapter_sha256': _sha(staged_pos / 'memory_adapter.py'),
            'event_spool_sha256': _sha(staged_pos / 'event_spool.py'),
            'profile_sha256': _sha(root / 'bundle/source/mykey.json'),
            'vendor_files_sha256': manifest['vendor_files_sha256'],
            'pma_vendor_files_sha256': manifest['pma_vendor_files_sha256'],
        }
        if candidate_profile:
            if candidate == 'pos_pma_shared_view_v1':
                binding['shared_view_sha256'] = _sha(staged_pos / 'shared_view.py')
            binding['candidate_config'] = {
                **({'name': candidate} if candidate == 'pos_pma_shared_view_v1' else {}),
                'pma_trigger': manifest['config']['pma_trigger'],
                'candidate_limits': manifest['config'].get('candidate_limits'),
                'pma_profile_sha256': manifest['pma_profile_sha256']}
        binding_path = root / 'control/pos_archive/binding.json'
        with binding_path.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(binding, stream, sort_keys=True)
            stream.write('\n')
        spec['pos_binding_sha256'] = _sha(binding_path)
    spec_path = root / 'control' / 'harbor_spec.json'
    spec_path.write_text(json.dumps(spec, indent=2), encoding='utf-8')
    agent_seconds = manifest['config']['agent_wall_seconds'] if args.condition == 'P' else 14400
    deadline = time.time() + agent_seconds
    worker = harbor = None
    worker_logs = []
    first_error = None
    cleanup_errors = []
    result = None
    stop_requested_at = None
    pending_end_at = None
    try:
        if args.condition == 'B' or candidate_profile:
            for name in ('worker.stdout.log', 'worker.stderr.log'):
                worker_logs.append((root / 'archive' / name).open('wb'))
            worker_env = dict(os.environ)
            worker_env['PYTHONPATH'] = os.pathsep.join((str(STAGE),
                str(STAGE / 'vendor' / 'pma_89e5c0d' / 'src'),
                str(STAGE / 'vendor' / 'pma_89e5c0d' / 'external' / 'harbor' / 'src')))
            worker_env['PMA_MEMORY_PROFILE_FILE'] = str(memory_profile_path)
            worker_env['PMA_MEMORY_PROFILE_SHA256'] = manifest['pma_profile_sha256']
            worker_env['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
            if profile_fixture:
                worker_env['CANDIDATE_FAKE_HOST_CAPTURE'] = str(
                    root / 'archive/fake_host_calls.jsonl')
            worker_env.pop('PMA_MEMORY_API_BASE', None)
            worker_env.pop('PMA_MEMORY_API_KEY', None)
            worker_script = ('candidate_transport_worker.py' if candidate_profile
                             else 'worker_main.py')
            worker_path = STAGE / worker_script
            if profile_fixture:
                worker_path = (STAGE.parents[2] / 'method_discovery' /
                    'pos_pma_complement_v1_20261019/test_fake_host_entry.py')
            worker = subprocess.Popen([
                str(Path(args.worker_python).resolve(strict=True)), str(worker_path),
                '--run-id', args.run_id, '--task-id', args.task,
                '--private-root', str(root / 'host_private'),
                '--requests', str(root / 'control' / 'spool' / 'requests'),
                '--responses', str(root / 'control' / 'spool' / 'responses'),
                '--deadline-epoch', str(deadline),
                '--research-candidate', candidate,
                *(['--fake-memory', '--fake-memory-update'] if fixture and not candidate_profile else [])],
                cwd=STAGE, env=worker_env,
                stdout=worker_logs[0], stderr=worker_logs[1])
            ready = root / 'host_private' / 'worker_ready.json'
            ready_limit = min(deadline, time.time() + 20)
            while not ready.is_file():
                if worker.poll() is not None or time.time() >= ready_limit:
                    raise RuntimeError('PMA host worker not ready')
                time.sleep(.05)
            ready_data = json.loads(ready.read_text(encoding='utf-8'))
            if (ready_data.get('run_id'), ready_data.get('task_id'),
                    ready_data.get('fake_memory'), ready_data.get('research_candidate')) != (
                    args.run_id, args.task, fixture and not candidate_profile, candidate):
                raise RuntimeError('PMA worker identity or transport mode mismatch')
        else:
            _worker_clearance(root, None, args.run_id)
        repo = STAGE.parents[2]
        mounts = [
            {'type': 'bind', 'source': str(Path(args.runtime_root).resolve(strict=True)),
             'target': '/opt/m4-runtime', 'read_only': True},
            {'type': 'bind', 'source': str((root / 'bundle/source').resolve(strict=True)),
             'target': '/opt/genericagent-source', 'read_only': True},
        ]
        command = [str(Path(args.harbor_python).resolve(strict=True)), '-m',
            'method_discovery.curator_supervisor_convergence_v0.'
            'pma_full_upstream_ga_v1_20261013.pma_harbor_cli',
            'jobs', 'start', '--job-name', args.run_id, '--jobs-dir', str(root / 'jobs'),
            '--path', str(root / 'public_task'),
            '--agent', ('method_discovery.curator_supervisor_convergence_v0.'
                        'pma_full_upstream_ga_v1_20261013.harbor_adapter:HarborGenericAgent'),
            '--model', 'claude-opus-4-8', '--mounts', json.dumps(mounts),
            '--extra-docker-compose', str(root / 'bundle/isolation.compose.json'),
            '--n-concurrent', '1', '--max-retries', '0', '--yes',
            '--enable-verification',
            '--agent-timeout-multiplier', str(agent_seconds /
                manifest['assets'][args.task]['native_agent_seconds'])
                if _native_schema(manifest) else '16',
            '--verifier-timeout-multiplier', '1']
        if _native_schema(manifest):
            command += ['--verifier-import-path',
                'method_discovery.curator_supervisor_convergence_v0.'
                'pma_full_upstream_ga_v1_20261013.native_shared_verifier:NativeSharedVerifier']
        kwargs = {'llm_no': 0, 'run_id': args.run_id, 'task_id': args.task,
                  'expected_model': 'claude-opus-4-8', 'python_home': args.python_home,
                  'ga_source_sha256': prepared['ga_bundle_tree_sha256'],
                  'timeout_sec': 180 if fixture else agent_seconds,
                  'max_turns': 2 if fixture else manifest.get('config', {}).get('task_turns_max', 300),
                  'llm_config_name': args.task_profile, 'condition_id': 'pma-neutral'}
        for key, value in kwargs.items():
            command += ['--ak', f'{key}={value}']
        env = dict(os.environ)
        for name in ('PMA_MEMORY_API_KEY', 'OPENROUTER_API_KEY', 'ANTHROPIC_API_KEY'):
            env.pop(name, None)
        python_roots = [str(repo), str(repo / 'GenericAgent-main'),
                        str(Path(args.bench_root).resolve(strict=True))]
        if _native_schema(manifest):
            harbor_source = Path(args.harbor_source_root).resolve(strict=True)
            head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=harbor_source,
                                  capture_output=True, text=True, check=True).stdout.strip()
            dirty = subprocess.run(['git', 'status', '--porcelain'], cwd=harbor_source,
                                   capture_output=True, text=True, check=True).stdout.strip()
            if head != '459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc' or dirty:
                raise RuntimeError('fixed clean native Harbor source unavailable')
            python_roots.insert(0, str(harbor_source / 'src'))
        env['PYTHONPATH'] = os.pathsep.join(python_roots)
        env.update(PMA_HARBOR_SPEC=str(spec_path), PYTHONUTF8='1', PYTHONIOENCODING='utf-8',
                   GA_RUN_ISOLATION=('networked-host-keyed-v1' if
                       _native_schema(manifest) else
                       'no-network-unix-inference-v1'),
                   GA_PMA_UPSTREAM_ENABLED='1' if args.condition == 'B' else '0',
                   GA_PMA_CAPTURE_TASK_REQUESTS='1',
                   GA_PMA_ENABLED='0', GA_MONITOR_ENABLED='0', GA_M0_MONITOR_ENABLED='0')
        if task_policy == 'complete-response-v1' or (
                args.condition != 'P' and env.get('GA_TASK_COMPLETE_RESPONSE') == '1'):
            env['GA_TASK_COMPLETE_RESPONSE'] = '1'
            env['GA_TASK_DEADLINE_EPOCH'] = str(deadline)
        elif manifest.get('schema') == 'pos-ga-single-manifest-v1':
            env.pop('GA_TASK_COMPLETE_RESPONSE', None)
            env.pop('GA_TASK_DEADLINE_EPOCH', None)
        if args.condition == 'P':
            env.update(GA_POS_ENABLED='1',
                       GA_POS_CITATION_FIXED=('0' if manifest['config'].get('citation_mode') ==
                           'released_core' else '1'),
                       GA_POS_PMA_COMPLEMENT=('1' if manifest['config']['name'] ==
                           'pos_pma_complement_v1' else '0'),
                       GA_POS_PMA_SHARED_VIEW=('1' if manifest['config']['name'] ==
                           'pos_pma_shared_view_v1' else '0'),
                       GA_POS_TRANSPORT='fake' if fixture and not profile_fixture else 'profile',
                       GA_POS_WORKER_SCRIPT='/opt/genericagent/pos_runtime/worker.py',
                       GA_POS_VENDOR_ROOT='/opt/genericagent/pos_runtime/vendor',
                       GA_POS_EPISODE_MODULE='/opt/genericagent/pos_runtime/episode.py',
                       GA_POS_ARCHIVE='/run/pos-archive/events.jsonl',
                       GA_POS_TIMEOUT=str(min(180, agent_seconds)),
                       GA_POS_DEADLINE_EPOCH=str(deadline))
            if fixture and not profile_fixture:
                env['GA_POS_FAKE_REPLIES'] = '/run/pos-fake-replies.json'
            else:
                env['GA_POS_PROFILE_FILE'] = '/opt/genericagent/mykey.json'
                env['GA_POS_PROFILE_NAME'] = manifest['config']['task_profile_name']
                env['GA_POS_BINDING_FILE'] = '/run/pos-archive/binding.json'
        if args.condition == 'B':
            env.update(GA_PMA_UPSTREAM_REQUESTS='/run/pma-bridge/requests',
                       GA_PMA_UPSTREAM_RESPONSES='/run/pma-bridge/responses',
                       GA_PMA_UPSTREAM_DEADLINE_EPOCH=str(deadline))
        (root / 'archive' / 'live_command_public.json').write_text(json.dumps({
            'argv': command, 'public_env': {name: env[name] for name in (
                'GA_RUN_ISOLATION', 'GA_PMA_UPSTREAM_ENABLED', 'GA_MONITOR_ENABLED')},
            'agent_deadline_epoch': deadline,
            'task_complete_response_policy': ('complete-response-v1' if
                env.get('GA_TASK_COMPLETE_RESPONSE') == '1' else 'disabled'),
            'evaluator_timeout_sec': manifest['assets'][args.task].get(
                'native_verifier_seconds', 900),
            'outer_timeout_sec': agent_seconds + manifest['assets'][args.task].get(
                'native_verifier_seconds', 900) + 600}, indent=2), encoding='utf-8')
        with (root / 'archive/harbor.stdout.log').open('wb') as out, (
                root / 'archive/harbor.stderr.log').open('wb') as err:
            harbor = subprocess.Popen(command, cwd=repo, env=env, stdout=out, stderr=err)
            outer_deadline = deadline + manifest['assets'][args.task].get(
                'native_verifier_seconds', 900) + 600
            while harbor.poll() is None:
                pending_end_at, stop_requested_at = _advance_worker_stop(
                    root, worker, deadline, pending_end_at, stop_requested_at)
                _worker_clearance(root, worker, args.run_id)
                if time.time() >= outer_deadline:
                    raise subprocess.TimeoutExpired(command, agent_seconds +
                        manifest['assets'][args.task].get('native_verifier_seconds', 900) + 600)
                time.sleep(.25)
            result = harbor.returncode
    except BaseException as exc:
        first_error = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        if worker is not None and worker.poll() is None:
            try:
                (root / 'host_private/stop.request').touch()
                worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    worker.kill()
                    worker.wait(timeout=5)
                except BaseException as exc:
                    cleanup_errors.append(f'worker_force_stop_unknown:{type(exc).__name__}:{exc}')
            except BaseException as exc:
                cleanup_errors.append(f'worker_stop_unknown:{type(exc).__name__}:{exc}')
        if worker is not None and worker.poll() is None:
            cleanup_errors.append('worker_still_running')
        if harbor is not None and harbor.poll() is None:
            try:
                harbor.kill()
                harbor.wait(timeout=10)
            except BaseException as exc:
                cleanup_errors.append(f'harbor_stop_unknown:{type(exc).__name__}:{exc}')
        for stream in worker_logs:
            stream.close()
        try:
            cleanup_errors.extend(clean_owned_containers(root))
            remaining = capture_mounts(root, include_stopped=True)
        except BaseException as exc:
            cleanup_errors.append(f'container_cleanup_unknown:{type(exc).__name__}:{exc}')
            remaining = None
        native_shared = _native_schema(manifest)
        volumes = _owned_volume_clearance(root) if native_shared else None
        frozen = root / 'archive' / ('agent_end_native.json' if native_shared else
                                     'agent_end_frozen.json')
        release = root / 'archive/verification_released.json'
        native = _native_trial_result(root) if native_shared else None
        execution = None
        reports = None
        if native_shared:
            try:
                execution = json.loads((root / 'archive/native_test_execution.json').read_text(
                    encoding='utf-8'))
            except (OSError, ValueError):
                execution = None
            try:
                reports = json.loads((root / 'archive/native_reports_checked.json').read_text(
                    encoding='utf-8'))
            except (OSError, ValueError):
                reports = None
        clearance = (_worker_clearance(root, worker, args.run_id)
                     if worker is None or worker.poll() is not None else None)
        fake_requests = root / 'archive/fake_provider_requests'
        fake_captures = sorted(fake_requests.glob('*.json')) if fixture else []
        try:
            pos_archive = json.loads((root / 'archive/pos_archive_status.json').read_text(
                encoding='utf-8')) if args.condition == 'P' else None
        except (OSError, ValueError):
            pos_archive = {'status': 'missing_or_unknown'}
        status = {'schema': manifest['schema'], 'run_id': args.run_id,
                  'task': args.task, 'condition': args.condition,
                  'research_candidate': candidate,
                  'zero_model_fixture_only': fixture,
                  'candidate_profile_fixture_only': profile_fixture,
                  'fake_provider_captures': len(fake_captures) if fixture else None,
                  'harbor_return_code': result, 'primary_failure': first_error,
                  'worker_return_code': None if worker is None else worker.poll(),
                  'fake_host_calls': (len((root / 'archive/fake_host_calls.jsonl').read_text(
                      encoding='utf-8').splitlines()) if profile_fixture and
                      (root / 'archive/fake_host_calls.jsonl').is_file() else None),
                  'pma_finalization': clearance.get('pma_finalization')
                      if isinstance(clearance, dict) else None,
                  'pos_archive_status': pos_archive,
                  'sidecar_clearance': clearance,
                  'remaining_containers': None if remaining is None else [m['id'] for m in remaining],
                  'cleanup_errors': cleanup_errors,
                  'cleanup_confirmed': remaining == [] and not cleanup_errors and
                  (not native_shared or volumes.get('status') == 'clean') and
                  isinstance(clearance, dict) and clearance.get('clean') is True and
                  (worker is None or worker.poll() is not None) and
                  (harbor is None or harbor.poll() is not None),
                  'frozen_product': frozen.is_file(), 'evaluation_released': release.is_file(),
                  'native_result': native,
                  'native_upload_checked': (root / 'archive/native_evaluator_uploaded.json').is_file()
                      if native_shared else None,
                  'native_script_observed': (isinstance(execution, dict) and
                      execution.get('run_id') == args.run_id and
                      execution.get('observed') is True) if native_shared else None,
                  'native_script_executions': execution.get('executions')
                      if isinstance(execution, dict) else None,
                  'native_reports_checked': (isinstance(reports, dict) and
                      reports.get('run_id') == args.run_id and
                      reports.get('all_reports_executed') is True)
                      if native_shared else None,
                  'native_report_diagnostics': reports}
        status['owned_volume_clearance'] = volumes
        (root / 'archive/live_result.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
    return status


def live_status_success(status: dict) -> bool:
    if status.get('condition') == 'P':
        archive = status.get('pos_archive_status') or {}
        if (archive.get('result_bound') is not True or
                archive.get('close_bound') is not True or
                archive.get('close_status') != 'graceful_exit' or
                archive.get('result_status') != 'completed'):
            return False
        if status.get('research_candidate') in {'pos_pma_complement_v1',
                                                'pos_pma_shared_view_v1'} and (
                archive.get('archive_incomplete') is not False or
                archive.get('task_archive_incomplete') is not False or
                archive.get('task_terminal_status') != 'available'):
            return False
    if status.get('zero_model_fixture_only') is True:
        return (status.get('primary_failure') is None and
                status.get('harbor_return_code') == 0 and
                status.get('cleanup_confirmed') is True and
                status.get('frozen_product') is True and
                status.get('evaluation_released') is True and
                status.get('native_result', {}).get('status') == 'native_recorded' and
                status.get('native_upload_checked') is True and
                status.get('native_script_observed') is True and
                status.get('native_reports_checked') is True and
                isinstance(status.get('fake_provider_captures'), int) and
                status['fake_provider_captures'] >= 2 and
                (status.get('candidate_profile_fixture_only') is not True or
                 (status.get('worker_return_code') == 0 and
                  status.get('fake_host_calls') == 4)) and
                (status.get('condition') != 'B' or
                 status.get('worker_return_code') == 0))
    native = status.get('native_result')
    native_required = _native_schema(status)
    return (status.get('primary_failure') is None and
            status.get('harbor_return_code') == 0 and
            status.get('cleanup_confirmed') is True and
            status.get('frozen_product') is True and
            status.get('evaluation_released') is True and
            (not native_required or (isinstance(native, dict) and
                                native.get('status') == 'native_recorded' and
                                status.get('native_upload_checked') is True and
                                status.get('native_script_observed') is True and
                                status.get('native_reports_checked') is True)) and
            (status.get('condition') != 'B' or
             status.get('worker_return_code') == 0))


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ('manifest', 'authorization', 'run-id', 'run-root', 'ga-source',
                 'runtime-root', 'task-profile-file', 'worker-python', 'harbor-python',
                 'bench-root', 'official-source-git'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--order', type=int, required=True)
    parser.add_argument('--repeat', type=int)
    parser.add_argument('--task', required=True)
    parser.add_argument('--condition', choices=('A', 'B', 'P'), required=True)
    parser.add_argument('--research-candidate', choices=(
        'U', 'V1', 'D1', 'PoS', 'PoS-citation-fixed',
        'pos_pma_complement_v1', 'pos_pma_shared_view_v1'), default='U')
    parser.add_argument('--task-profile', default='native_claude_cc_vibe_opus48')
    parser.add_argument('--pma-profile-file')
    parser.add_argument('--harbor-source-root')
    parser.add_argument('--zero-model-fixture', action='store_true')
    parser.add_argument('--candidate-profile-fixture', action='store_true')
    parser.add_argument('--python-home', default='cpython-3.12.12-linux-x86_64-gnu')
    args = parser.parse_args()
    status = run_live(args)
    print(json.dumps(status, indent=2))
    if not live_status_success(status):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
