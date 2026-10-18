"""Four real prepared PoS manifests through run_live, stopped before Harbor Popen.

This uses no synthetic task manifest, provider, official evaluator, or Task run.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from unittest.mock import patch

from long_context_bench.scripts.isolated_run_bundle import digest_tree
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013 import live_launcher, single_run
from method_discovery.pos_upstream_ga_v1_20261017.single_manifest import FOUR

CHECKOUT = Path(__file__).resolve().parents[2]


class HarborBoundaryReached(Exception):
    pass


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def run_boundary(args):
    root = Path(args.output).resolve(strict=False)
    root.mkdir(parents=True, exist_ok=False)
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=CHECKOUT,
        capture_output=True, text=True, check=True).stdout.strip()
    records = []
    for order, task in enumerate(FOUR, 1):
        directory = root / f'{order:02d}_{task}'
        identity = single_run.prepare(argparse.Namespace(output=str(directory),
            task=task, condition='P', research_candidate='PoS', occurrence=1,
            fake_only=False, synthetic_pos_fixture=False,
            official_source_git=args.official_source_git,
            task_profile_file=args.task_profile_file, pma_profile_file=None,
            certification_dir=args.certification))
        manifest_path = directory / 'manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        members = manifest['assets'][task]['evaluator_members']
        assert manifest['zero_model_fixture_only'] is False
        assert 'official_evaluator_members' not in manifest['assets'][task]
        assert members and (len(members) == 4 if task == 'write-compressor' else True)
        row = manifest['planned_order'][0]
        binding = dict(row, run_id=identity['run_id'], run_root=identity['run_root'],
                       batch_id=identity['run_id'], config_sha256=manifest['config_sha256'])
        auth_path = directory / 'test_only_authorization.json'
        write_new(auth_path, {'execution_authorized': True,
            'zero_model_fixture_only': False, 'manifest_sha256': sha(manifest_path),
            'audited_code_commit': head, 'approved_arms': [row],
            'run_bindings': [binding], 'run_id': identity['run_id'],
            'batch_id': identity['run_id'], 'config_sha256': manifest['config_sha256'],
            'output_root': identity['output_root']})
        test_authorization_bytes = auth_path.read_bytes()
        launch_args = argparse.Namespace(manifest=str(manifest_path),
            authorization=str(auth_path), task=task, condition='P', order=1,
            repeat=1, research_candidate='PoS', run_id=identity['run_id'],
            run_root=identity['run_root'], zero_model_fixture=False,
            ga_source=args.ga_source, runtime_root=args.runtime_root,
            task_profile_file=args.task_profile_file, pma_profile_file=None,
            worker_python=args.worker_python, harbor_python=args.harbor_python,
            bench_root=args.bench_root, official_source_git=args.official_source_git,
            harbor_source_root=args.harbor_source_root,
            python_home='cpython-3.12.12-linux-x86_64-gnu',
            task_profile='native_claude_cc_vibe_opus48')
        original_popen = subprocess.Popen
        observed = []
        def stop_only_harbor(command, *positional, **keywords):
            if isinstance(command, list) and any('pma_harbor_cli' in str(x) for x in command):
                observed.append(command)
                raise HarborBoundaryReached('test-only pre-Harbor boundary')
            return original_popen(command, *positional, **keywords)
        try:
            with patch.object(subprocess, 'Popen', side_effect=stop_only_harbor):
                status = live_launcher.run_live(launch_args)
        finally:
            auth_path.unlink(missing_ok=True)
        run = Path(identity['run_root'])
        spec = json.loads((run / 'control/harbor_spec.json').read_text(encoding='utf-8'))
        public_command = json.loads((run / 'archive/live_command_public.json').read_text(
            encoding='utf-8'))
        staged = run / 'public_task/tests'
        assert len(observed) == 1 and public_command['argv'] == observed[0]
        assert status['primary_failure']['type'] == 'HarborBoundaryReached'
        assert status['harbor_return_code'] is None
        assert spec['official_evaluator_files'] == [{
            'relative': '/'.join(m['path'].split('/')[1:]), 'sha256': m['sha256']}
            for m in members]
        assert len(spec['official_evaluator_files']) == len(members)
        assert spec['native_tests_tree_sha256'] == digest_tree(staged) == manifest[
            'assets'][task]['native_tests_tree_sha256']
        assert spec['native_test_sh_sha256'] == sha(staged / 'test.sh') == manifest[
            'assets'][task]['native_test_sh_sha256']
        for member in members:
            relative = '/'.join(member['path'].split('/')[1:])
            file = run / 'public_task' / relative
            assert file.is_file() and sha(file) == member['sha256']
            assert file.stat().st_size == member['bytes']
        assert '--enable-verification' in observed[0]
        assert not (run / 'jobs').exists()
        assert status['native_result']['status'] == 'unavailable'
        assert status['evaluation_released'] is False
        assert status['cleanup_confirmed'] is False and status['remaining_containers'] == []
        assert status['owned_volume_clearance']['status'] == 'unknown'
        # The actual verify_live_spec ran during run_live; exercise a wrong identity
        # against that exact frozen spec without replacing its implementation.
        wrong = dict(spec, run_id='old-or-wrong-run-id')
        with auth_path.open('xb') as stream:
            stream.write(test_authorization_bytes)
        try:
            try:
                live_launcher.verify_live_spec(wrong)
            except RuntimeError:
                pass
            else:
                raise AssertionError('old/wrong run identity passed verify_live_spec')
        finally:
            auth_path.unlink(missing_ok=True)
        # The actual staging code must reject a modified frozen member.
        corrupt = json.loads(json.dumps(manifest))
        corrupt['assets'][task]['evaluator_members'][0]['sha256'] = '0' * 64
        bad_root = directory / 'tampered_staging'
        (bad_root / 'public_task/tests').mkdir(parents=True)
        try:
            live_launcher._stage_verifier(bad_root, task, corrupt,
                Path(args.official_source_git))
        except RuntimeError:
            pass
        else:
            raise AssertionError('tampered evaluator member accepted')
        records.append({'order': order, 'task': task, 'manifest_sha256': sha(manifest_path),
            'run_id': identity['run_id'], 'zero_model_fixture_only': False,
            'member_count': len(members), 'member_sha256': [m['sha256'] for m in members],
            'spec_sha256': sha(run / 'control/harbor_spec.json'),
            'command_sha256': sha(run / 'archive/live_command_public.json'),
            'staged_tree_sha256': digest_tree(staged),
            'boundary': 'real run_live reached Harbor Popen; intercepted before process creation',
            'verify_live_spec': 'passed in actual run_live',
            'tampered_member': 'rejected', 'wrong_run_identity': 'rejected',
            'harbor_started': False, 'provider_calls': 0,
            'official_evaluator_calls': 0, 'cleanup_confirmed': False,
            'owned_volume_clearance': 'unknown_pre_harbor',
            'test_authorization_removed': not auth_path.exists()})
    write_new(root / 'boundary_result.json', {'schema': 'pos-four-formal-pre-harbor-v1',
        'source_commit': head, 'status': 'pass', 'runs': records,
        'real_model_calls': 0, 'official_evaluator_calls': 0})
    return records


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('output', 'certification', 'official-source-git',
                 'task-profile-file', 'ga-source', 'runtime-root', 'worker-python',
                 'harbor-python', 'bench-root', 'harbor-source-root'):
        parser.add_argument('--' + name, required=True)
    rows = run_boundary(parser.parse_args())
    print(json.dumps({'status': 'pass', 'four_boundaries': len(rows),
                      'members': {r['task']: r['member_count'] for r in rows},
                      'model_calls': 0, 'official_evaluator_calls': 0}))
