"""Zero-model checks for read-only, pre-verifier final-file capture."""

import asyncio
import hashlib
import inspect
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from harbor.trial.artifact_handler import ArtifactHandler
from harbor.trial.single_step import SingleStepTrial
from harbor.trial.trial import Trial
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013 import (
    pma_harbor_hooks as hooks,
)


def _spec(task='rstan-to-pystan'):
    return {'run_id': 'zero-model-run', 'task_id': task, 'condition': 'B',
            'research_candidate': 'pma_predictive_read_context_v1',
            'evaluation_protocol': 'official_shared_v2'}


def test_capture_scope_and_real_harbor_lifecycle():
    assert hooks.final_artifact_sources(_spec()) == (
        '/app/pystan_analysis.py', '/app/alpha_est.csv', '/app/sigma_est.csv',
        '/app/rho_est.csv', '/app/beta_est.csv')
    assert hooks.final_artifact_sources(_spec('merge-diff-arc-agi-task')) == (
        '/app/repo/algo.py',)
    assert hooks.final_artifact_sources({**_spec(), 'condition': 'P'}) == ()
    run_source = inspect.getsource(SingleStepTrial._run)
    verify_source = inspect.getsource(SingleStepTrial._run_verifier)
    assert run_source.index('await self._collect_artifacts(') < run_source.index(
        'await self._run_verifier()')
    assert verify_source.index('TrialEvent.VERIFICATION_START') < verify_source.index(
        'self._run_shared_verifier(')


def test_trial_create_injects_host_artifacts_before_harbor_initialization(
        tmp_path, monkeypatch):
    spec_path = tmp_path / 'spec.json'
    spec_path.write_text(json.dumps(_spec()), encoding='utf-8')
    monkeypatch.setenv('PMA_HARBOR_SPEC', str(spec_path))
    monkeypatch.setattr(hooks, 'verify_live_spec', lambda spec: None)
    events = []

    class FakeTrial:
        def add_hook(self, event, callback):
            events.append(('hook', event.value))

        async def _run_verifier(self):
            events.append(('verifier', None))

    async def original_create(cls, config):
        events.append(('created_with_artifacts', tuple(config.artifacts)))
        return FakeTrial()

    class FakeNativeHooks(hooks.NativeSharedTrialHooks):
        def __init__(self, trial, spec):
            self.trial = trial
            self.spec = spec

        async def check_post_verification_artifacts(self):
            events.append(('postcheck', None))

    monkeypatch.setattr(Trial, 'create', classmethod(original_create))
    monkeypatch.setattr(hooks, 'NativeSharedTrialHooks', FakeNativeHooks)
    hooks.install_trial_hooks()
    trial = asyncio.run(Trial.create(SimpleNamespace(artifacts=[])))
    asyncio.run(trial._run_verifier())
    assert events[0] == ('created_with_artifacts', hooks.FINAL_ARTIFACT_SOURCES[
        'rstan-to-pystan'])
    assert events[-2:] == [('verifier', None), ('postcheck', None)]


class FakeEnvironment:
    def __init__(self, files):
        self.files = dict(files)
        self.capabilities = SimpleNamespace(mounted=False)

    async def service_is_dir(self, source, *, service=None, user=None):
        return source == '/logs/artifacts'

    async def service_download_dir(self, *, source_dir, target_dir, service=None):
        target_dir.mkdir(parents=True, exist_ok=True)

    async def service_download_file(self, *, source_path, target_path, service=None):
        if source_path not in self.files:
            raise FileNotFoundError(source_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(self.files[source_path])


def test_installed_harbor_downloads_without_changing_container_bytes(tmp_path):
    files = {'/app/pystan_analysis.py': b'print(1)\n',
             '/app/alpha_est.csv': b'1.09\n'}
    environment = FakeEnvironment(files)
    handler = ArtifactHandler(artifacts=list(files), logger=logging.getLogger(__name__))
    handler.begin_collection()
    manifest = asyncio.run(handler.download_artifacts(
        source_env=environment, artifacts_dir=tmp_path / 'artifacts',
        source_artifacts_dir=Path('/logs/artifacts')))
    rows = {row.source: row for row in manifest.entries}
    assert all(rows[source].status == 'ok' for source in files)
    assert (tmp_path / 'artifacts/app/pystan_analysis.py').read_bytes() == files[
        '/app/pystan_analysis.py']
    assert environment.files == files


def _prepared_hook(tmp_path, files):
    trial_dir = tmp_path / 'trial'
    artifact_dir = trial_dir / 'artifacts'
    artifact_dir.mkdir(parents=True)
    manifest = []
    for source in hooks.final_artifact_sources(_spec()):
        destination = artifact_dir / source.lstrip('/')
        if source in files:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(files[source])
            status = 'ok'
        else:
            status = 'failed'
        manifest.append({'source': source,
                         'destination': f'artifacts/{source.lstrip("/")}',
                         'type': 'file', 'status': status, 'service': None})
    (artifact_dir / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    instance = object.__new__(hooks.NativeSharedTrialHooks)
    instance.spec = _spec()
    instance.archive = tmp_path / 'archive'
    instance.archive.mkdir()
    (instance.archive / 'writer_termination_check.json').write_text(
        json.dumps({'task_owned_pids_preserved': []}), encoding='utf-8')
    instance.trial = SimpleNamespace(
        paths=SimpleNamespace(trial_dir=trial_dir, artifacts_dir=artifact_dir),
        agent_environment=FakeEnvironment(files))
    return instance


def test_pre_and_post_verifier_bytes_match_without_writing_task(tmp_path):
    files = {'/app/pystan_analysis.py': b'original script\n',
             '/app/alpha_est.csv': b'1.09\n'}
    instance = _prepared_hook(tmp_path, files)
    instance.record_pre_verification_artifacts()
    asyncio.run(instance.check_post_verification_artifacts())
    after = json.loads((instance.archive / 'final_artifacts_after_verifier.json').read_text())
    assert after['matches'] is True
    assert instance.trial.agent_environment.files == files
    assert hashlib.sha256(files['/app/alpha_est.csv']).hexdigest() == next(
        row['identity']['sha256'] for row in after['files']
        if row['source'] == '/app/alpha_est.csv')
    assert sum(row['identity'] is None for row in after['files']) == 3


def test_post_verifier_change_fails_and_preserves_both_copies(tmp_path):
    instance = _prepared_hook(tmp_path, {'/app/alpha_est.csv': b'before\n'})
    instance.record_pre_verification_artifacts()
    instance.trial.agent_environment.files['/app/alpha_est.csv'] = b'after\n'
    with pytest.raises(RuntimeError, match='artifact identity changed'):
        asyncio.run(instance.check_post_verification_artifacts())
    after = json.loads((instance.archive / 'final_artifacts_after_verifier.json').read_text())
    assert after['conflicts'] == ['/app/alpha_est.csv']
    assert (instance.trial.paths.artifacts_dir / 'app/alpha_est.csv').read_bytes() == b'before\n'


def test_remaining_task_process_prevents_snapshot_claim(tmp_path):
    instance = _prepared_hook(tmp_path, {'/app/alpha_est.csv': b'before\n'})
    (instance.archive / 'writer_termination_check.json').write_text(
        json.dumps({'task_owned_pids_preserved': [123]}), encoding='utf-8')
    with pytest.raises(RuntimeError, match='Task-owned processes remain'):
        instance.record_pre_verification_artifacts()
