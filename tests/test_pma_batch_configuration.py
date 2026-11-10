"""Offline configuration/identity wiring; no provider, Docker or real task runs."""
import ast
import hashlib
import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from experiment_runner import __main__ as frontend
from experiment_runner.methods import (clean_candidate_environment,
    parse_pma_batch_rounds, resolve, validate_pma_batch_rounds)

DRIVER = frontend.DRIVER
ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / DRIVER.replace('.', '/')
INVALID = (0, -1, 1.5, 3.0, True, False, '3', None, [], {})
UNCAPPED = {'agent_timeout': 'uncapped', 'task_turns': 'uncapped',
            'verifier_timeout': 'official'}


def write_json(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def prepared_fixture(tmp_path, monkeypatch):
    """Exercise real prepare logic with only external asset discovery replaced."""
    manifest = importlib.import_module(DRIVER + '.prepare_six_task_manifest')
    task_profile = tmp_path / 'task.py'
    task_profile.write_text("native_claude_cc_vibe_opus48 = {'model': 'claude-opus-4-8'}\n")
    pma_profile = tmp_path / 'pma.json'
    pma_profile.write_text('{}')
    monkeypatch.setattr(manifest, 'load_profile', lambda *_: ('fixture-profile', {}))
    asset = {'image_tag': 'fixture/task:fixed', 'native_agent_seconds': 900,
             'native_verifier_seconds': 900, 'public_members': [],
             'evaluator_members': [], 'expected_native_reports': []}
    monkeypatch.setattr(manifest, 'descriptor', lambda *_a, **_k: dict(asset))
    monkeypatch.setattr(manifest, 'materialize_public',
                        lambda _source, _task, dest, *_a, **_k: dest.mkdir())
    monkeypatch.setattr(manifest, 'export_task',
                        lambda _source, _task, dest, **_k: (dest / 'test.sh').write_text('fixture'))
    monkeypatch.setattr(manifest, 'image_identity', lambda _tag: {
        'image_id': 'fixture-image', 'repo_digests': ['fixture/task@sha256:fixture'],
        'platform': 'linux/amd64'})
    monkeypatch.setattr(frontend, 'catalog', lambda *_: {'tasks': [{
        'task': 'db-wal-recovery', 'agent_timeout_sec': 900, 'verifier_timeout_sec': 900}]})
    monkeypatch.setattr('experiment_runner.startup.code_identity', lambda _: {
        'kind': 'synthetic_unit_fixture', 'code_commit': 'fixture'})
    config = {'schema': 'ga-experiment-plan-v1',
        'dataset': {'source_git': str(tmp_path), 'commit':
                    '2fd12b88aafdd04a52c298e3940bcb189f9766d6'},
        'method': 'pma-predictive-read-context', 'slots': [{'task': 'db-wal-recovery'}],
        'runtime_policy': dict(UNCAPPED), 'environment': {'profiles': {
            'task_profile_file': str(task_profile), 'pma_profile_file': str(pma_profile)}}}
    return config, manifest


@pytest.mark.parametrize('value', INVALID)
def test_reject_non_positive_json_integers(tmp_path, value):
    with pytest.raises(ValueError, match='pma_batch_rounds'):
        validate_pma_batch_rounds(value)
    config = {'schema': 'ga-experiment-plan-v1', 'pma_batch_rounds': value}
    path = tmp_path / 'config.json'
    write_json(path, config)
    with pytest.raises(ValueError, match='pma_batch_rounds'):
        frontend.load_config(path)
    with pytest.raises(ValueError, match='pma_batch_rounds'):
        frontend.build_plan(config)


@pytest.mark.parametrize('value', ('0', '-1', '1.5', '3.0', 'true', 'False', ''))
def test_cli_rejects_invalid_round_counts(value, tmp_path):
    with pytest.raises(SystemExit) as error:
        frontend.main(['plan', '--config', str(tmp_path / 'never-read.json'),
                       '--output', str(tmp_path / 'never-written.json'),
                       '--pma-batch-rounds', value])
    assert error.value.code == 2
    assert not (tmp_path / 'never-written.json').exists()


@pytest.mark.parametrize('rounds', (3, 8, None))
def test_json_to_plan_manifest_and_run_identity(prepared_fixture, tmp_path, rounds):
    config, _ = prepared_fixture
    if rounds is not None:
        config['pma_batch_rounds'] = rounds
    path = tmp_path / 'config.json'
    write_json(path, config)
    plan = frontend.build_plan(frontend.load_config(path))
    expected = 8 if rounds is None else rounds
    assert plan['config']['pma_batch_rounds'] == expected
    output = tmp_path / 'prepared'
    result = frontend.execute(plan, output, 'prepare')
    assert frontend.succeeded(result, 1, 'prepare'), result
    slot = output / '01-db-wal-recovery-r1'
    single = json.loads((slot / 'plan.json').read_text())
    manifest = json.loads((slot / 'manifest.json').read_text())
    identity = json.loads((slot / 'run_identity.json').read_text())
    for record in (single, manifest['config'], identity):
        assert record['pma_batch_rounds'] == expected
    assert single['runtime_policy'] == UNCAPPED
    assert manifest['config']['task_turns_max'] is None
    assert manifest['config']['agent_wall_seconds'] is None
    assert identity['manifest_sha256'] == hashlib.sha256((slot / 'manifest.json').read_bytes()).hexdigest()
    assert identity['execution_authorized'] is False


def test_cli_override_and_rounds_change_hashes(prepared_fixture, tmp_path):
    config, _ = prepared_fixture
    config['pma_batch_rounds'] = 8
    path = tmp_path / 'config.json'
    write_json(path, config)
    output = tmp_path / 'plan.json'
    assert frontend.main(['plan', '--config', str(path), '--output', str(output),
                          '--pma-batch-rounds', '3']) == 0
    plan3 = json.loads(output.read_text())
    plan8 = frontend.build_plan(config)
    assert plan3['config']['pma_batch_rounds'] == 3
    assert plan3['plan_sha256'] != plan8['plan_sha256']
    hashes = []
    for n in (3, 8):
        result = frontend.execute(frontend.build_plan(dict(config, pma_batch_rounds=n)),
                                  tmp_path / f'prepared-{n}', 'prepare')
        assert frontend.succeeded(result, 1, 'prepare'), result
        manifest = json.loads((tmp_path / f'prepared-{n}/01-db-wal-recovery-r1/manifest.json').read_text())
        hashes.append(manifest['config_sha256'])
    assert hashes[0] != hashes[1]


def test_single_prepare_cli_and_legacy_default(monkeypatch, tmp_path):
    single = importlib.import_module(DRIVER + '.single_run')
    seen = Mock(return_value={})
    monkeypatch.setattr(single, 'prepare', seen)
    base = ['single_run', 'prepare', '--task', 'db-wal-recovery', '--condition', 'B',
            '--output', str(tmp_path), '--official-source-git', str(tmp_path),
            '--task-profile-file', str(tmp_path / 'unused.py')]
    for extra, expected in (([], 8), (['--pma-batch-rounds', '3'], 3)):
        monkeypatch.setattr('sys.argv', base + extra)
        single.main()
        assert seen.call_args.args[0].pma_batch_rounds == expected


@pytest.mark.parametrize('value', INVALID)
def test_single_and_manifest_reject_before_artifacts(prepared_fixture, tmp_path, value):
    _, manifest = prepared_fixture
    single = importlib.import_module(DRIVER + '.single_run')
    output = tmp_path / 'must-not-exist'
    with pytest.raises(ValueError, match='pma_batch_rounds'):
        single.prepare(SimpleNamespace(output=str(output), pma_batch_rounds=value))
    with pytest.raises(ValueError, match='pma_batch_rounds'):
        manifest.prepare(tmp_path, tmp_path, tmp_path, plan={'pma_batch_rounds': value})
    assert not output.exists()


def test_environment_inheritance_is_clean_and_restored(monkeypatch):
    monkeypatch.setenv('GA_PMA_BATCH_ROUNDS', '999')
    assert 'GA_PMA_BATCH_ROUNDS' not in clean_candidate_environment({'GA_PMA_BATCH_ROUNDS': '999'})
    with frontend.method_environment(resolve('pma-predictive-read-context')):
        assert 'GA_PMA_BATCH_ROUNDS' not in os.environ
    assert os.environ['GA_PMA_BATCH_ROUNDS'] == '999'
    assert parse_pma_batch_rounds('3') == 3
    for value in (True, False, 3.5):
        with pytest.raises(ValueError):
            parse_pma_batch_rounds(value)


def test_source_identity_and_adapter_forwarding(prepared_fixture):
    _, manifest = prepared_fixture
    sources = importlib.import_module(DRIVER + '.single_run_certification').READ_CONTEXT_PREDICTIVE_SOURCE_FILES
    for path in ('GenericAgent-main/task_trajectory.py', 'GenericAgent-main/ga_trajectory.py',
                 DRIVER.replace('.', '/') + '/public_trajectory.py'):
        assert path in manifest.V3_SOURCE_FILES
        assert path in sources
        assert (ROOT / path).is_file()
    tree = ast.parse((STAGE / 'harbor_adapter.py').read_text())
    forward = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == 'FORWARD'
                           for target in node.targets))
    assert 'GA_PMA_BATCH_ROUNDS' in ast.literal_eval(forward)


@pytest.mark.parametrize('actual', (8, 0, True, '3'))
def test_live_spec_rejects_changed_round_identity(tmp_path, actual):
    hooks = importlib.import_module(DRIVER + '.pma_harbor_hooks')
    manifest = tmp_path / 'manifest.json'
    auth = tmp_path / 'auth.json'
    spec = {'schema': 'pma-ga-live-run-v1', 'mode': 'authorized_live',
            'manifest_path': str(manifest), 'authorization_path': str(auth),
            'manifest_sha256': write_json(manifest, {'config': {'pma_batch_rounds': 3}}),
            'authorization_sha256': write_json(auth, {}), 'pma_batch_rounds': actual}
    with pytest.raises((ValueError, RuntimeError), match='pma_batch_rounds'):
        hooks.verify_live_spec(spec)


@pytest.mark.parametrize('rounds,ready_rounds', ((3, 3), (8, 8), (3, 8)))
def test_real_launcher_builds_bound_worker_and_task_commands(
        prepared_fixture, tmp_path, monkeypatch, rounds, ready_rounds):
    """Run the actual launcher with process/asset I/O mocked, not a model run."""
    launcher = importlib.import_module(DRIVER + '.live_launcher')
    config, _ = prepared_fixture
    config['pma_batch_rounds'] = rounds
    output = tmp_path / 'prepared'
    result = frontend.execute(frontend.build_plan(config), output, 'prepare')
    assert frontend.succeeded(result, 1, 'prepare'), result
    slot = output / '01-db-wal-recovery-r1'
    manifest_path = slot / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['assets']['db-wal-recovery']['official_evaluator_members'] = [
        {'path': 'db-wal-recovery/tests/test.sh', 'sha256': 'fixture'}]
    manifest['assets']['db-wal-recovery']['evaluator_members'] = (
        manifest['assets']['db-wal-recovery']['official_evaluator_members'])
    manifest_hash = write_json(manifest_path, manifest)
    auth = tmp_path / 'authorization.json'
    write_json(auth, {'execution_authorized': True, 'manifest_sha256': manifest_hash,
                      'audited_code_commit': 'fixture', 'batch_id': 'unit'})
    root = tmp_path / 'run'
    profiles = config['environment']['profiles']
    args = SimpleNamespace(manifest=str(manifest_path), authorization=str(auth),
        condition='B', research_candidate='pma_predictive_read_context_v1',
        task='db-wal-recovery', run_root=str(root), run_id='unit', order=1, repeat=1,
        ga_source=str(ROOT / 'GenericAgent-main'), runtime_root=str(tmp_path),
        worker_python=sys.executable, harbor_python=sys.executable,
        bench_root=str(tmp_path), official_source_git=str(tmp_path),
        harbor_source_root=str(tmp_path), python_home='fixture-python',
        task_profile='native_claude_cc_vibe_opus48', **profiles)
    def prepare(_args, *, fake_gateway):
        assert fake_gateway is False
        for name in ('control', 'archive', 'bundle/source', 'host_private', 'public_task'):
            (root / name).mkdir(parents=True, exist_ok=True)
        return {'image_id': 'fixture-image', 'ga_bundle_tree_sha256': 'fixture',
                'public_task_tree_sha256': manifest['assets'][args.task]['public_task_tree_sha256']}
    calls = []
    def start(command, **options):
        calls.append((command, options['env']))
        if len(calls) == 1:
            write_json(root / 'host_private/worker_ready.json', {
                'run_id': 'unit', 'task_id': args.task, 'fake_memory': False,
                'research_candidate': args.research_candidate, 'pma_batch_rounds': ready_rounds})
        return SimpleNamespace(pid=123456789, returncode=0, poll=lambda: 0)
    monkeypatch.setenv('GA_PMA_BATCH_ROUNDS', '999')
    monkeypatch.setattr(launcher, '_prepare_common', prepare)
    verified_specs = []
    monkeypatch.setattr(launcher, 'verify_live_spec', lambda spec: verified_specs.append(dict(spec)))
    monkeypatch.setattr(launcher, '_stage_verifier', lambda *_: {})
    monkeypatch.setattr(launcher, '_require_evaluation_state_contract', lambda *_: None)
    monkeypatch.setattr(launcher, 'clean_owned_containers', lambda *_: [])
    monkeypatch.setattr(launcher, 'capture_mounts', lambda *_a, **_k: [])
    monkeypatch.setattr(launcher, '_owned_volume_clearance', lambda *_: {'status': 'clean'})
    monkeypatch.setattr(launcher.subprocess, 'Popen', start)
    monkeypatch.setattr(launcher.subprocess, 'run', lambda command, **_: SimpleNamespace(
        stdout='459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc' if 'rev-parse' in command else ''))
    outcome = launcher.run_live(args)
    assert calls[0][0][calls[0][0].index('--pma-batch-rounds') + 1] == str(rounds)
    assert calls[0][0][calls[0][0].index('--deadline-epoch') + 1] == 'uncapped'
    assert 'GA_PMA_BATCH_ROUNDS' not in calls[0][1]
    assert verified_specs[0]['pma_batch_rounds'] == rounds
    if ready_rounds != rounds:
        assert len(calls) == 1
        assert 'pma_batch_rounds identity mismatch' in outcome['primary_failure']['message']
        return
    assert outcome['primary_failure'] is None, outcome
    assert len(calls) == 2
    command, env = calls[1]
    assert env['GA_PMA_BATCH_ROUNDS'] == str(rounds)
    assert env['GA_EXPERIMENT_TASK_TURNS'] == 'uncapped'
    assert 'max_turns=0' in command and 'timeout_sec=uncapped' in command
    public = json.loads((root / 'archive/live_command_public.json').read_text())
    assert public['pma_batch_rounds'] == rounds
    assert public['agent_deadline_epoch'] is None
    assert public['outer_timeout_sec'] is None


@pytest.mark.parametrize('filename', ('plan.json', 'manifest.json', 'run_identity.json'))
def test_frontend_rejects_a_driver_ignoring_nondefault_rounds(
        prepared_fixture, tmp_path, monkeypatch, filename):
    config, _ = prepared_fixture
    config['pma_batch_rounds'] = 3
    single = importlib.import_module(DRIVER + '.single_run')
    original = single.prepare
    def dropping_driver(args):
        result = original(args)
        path = Path(args.output) / filename
        value = json.loads(path.read_text())
        target = value['config'] if filename == 'manifest.json' else value
        target.pop('pma_batch_rounds')
        write_json(path, value)
        return result
    monkeypatch.setattr(single, 'prepare', dropping_driver)
    result = frontend.execute(frontend.build_plan(config), tmp_path / 'prepared', 'prepare')
    assert result[0]['status'] == 'preparation_failed'
    assert 'pma_batch_rounds' in result[0]['error']


@pytest.mark.parametrize('rounds', (3, 8, None))
def test_live_spec_accepts_bound_or_legacy_default_rounds(tmp_path, monkeypatch, rounds):
    hooks = importlib.import_module(DRIVER + '.pma_harbor_hooks')
    arms = [dict(order=i, task=task, condition=condition) for i, task, condition in (
        (1, 'db-wal-recovery', 'A'), (2, 'db-wal-recovery', 'B'),
        (3, 'fix-code-vulnerability', 'B'), (4, 'fix-code-vulnerability', 'A'))]
    bindings = [dict(arm, run_id=f'unit-{arm["order"]}',
                     run_root=str(tmp_path / str(arm['order']))) for arm in arms]
    manifest = tmp_path / 'manifest.json'
    auth = tmp_path / 'auth.json'
    config = {} if rounds is None else {'pma_batch_rounds': rounds}
    manifest_hash = write_json(manifest, {'schema': 'pma-ga-live-manifest-v1',
        'execution_authorized': False, 'arms': arms, 'config': config})
    auth_hash = write_json(auth, {'execution_authorized': True,
        'manifest_sha256': manifest_hash, 'audited_code_commit': 'unit',
        'approved_arms': arms, 'run_bindings': bindings})
    spec = dict(schema='pma-ga-live-run-v1', mode='authorized_live',
        manifest_path=str(manifest), manifest_sha256=manifest_hash,
        authorization_path=str(auth), authorization_sha256=auth_hash,
        audited_code_commit='unit', task_id=arms[0]['task'], **bindings[0], **config)
    monkeypatch.setattr(hooks.subprocess, 'run', lambda *_a, **_k: SimpleNamespace(stdout='unit'))
    hooks.verify_live_spec(spec)


def test_single_run_rejects_changed_round_identity(tmp_path):
    single = importlib.import_module(DRIVER + '.single_run')
    write_json(tmp_path / 'manifest.json', {'config': {'pma_batch_rounds': 3}})
    write_json(tmp_path / 'run_identity.json', {'pma_batch_rounds': 8})
    with pytest.raises(RuntimeError, match='pma_batch_rounds identity mismatch'):
        single.run(SimpleNamespace(output=str(tmp_path)))
