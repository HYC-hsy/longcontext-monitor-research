"""Byte check around Harbor's original SHARED Verifier; no scoring logic."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from experiment_runner.evaluation_cache import prepare_cached

from harbor.models.trial.paths import EnvironmentPaths
from harbor.verifier.verifier import Verifier

from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.pilot_harbor_hooks import _atomic

from .evaluation_bootstrap import (BootstrapFailed, PROTOCOL as BOOTSTRAP_PROTOCOL,
                                   commands as bootstrap_commands, effective_script, prepare)
from .download_retry import (PROTOCOL as DOWNLOAD_PROTOCOL,
                             plan as download_plan, prepare as prepare_downloads)


class NativeSharedVerifier(Verifier):
    @staticmethod
    def _report_has_executed_tests(parsed: object) -> bool:
        if not isinstance(parsed, dict):
            return False
        results = parsed.get('results')
        if not isinstance(results, dict):
            return False
        tests, summary = results.get('tests'), results.get('summary')
        if not isinstance(tests, list) or not isinstance(summary, dict):
            return False
        total = summary.get('tests')
        counts = [summary.get(k) for k in ('passed', 'failed', 'skipped',
                                            'pending', 'other')]
        return (isinstance(total, int) and total == len(tests) and total > 0 and
                all(isinstance(n, int) and n >= 0 for n in counts) and
                sum(counts) == total and counts[0] + counts[1] > 0)

    async def verify(self):
        spec_path = os.environ.get('PMA_HARBOR_SPEC')
        if not spec_path:
            raise RuntimeError('native shared verifier has no run identity')
        spec = json.loads(Path(spec_path).read_text(encoding='utf-8'))
        if spec.get('evaluation_protocol') not in {'official_shared_v2',
                                                    'synthetic_shared_v1'}:
            raise RuntimeError('native shared verifier protocol mismatch')
        if (spec.get('evaluation_protocol') == 'synthetic_shared_v1' and
                (spec.get('condition') != 'P' or
                 spec.get('zero_model_fixture_only') is not True or
                 spec.get('official_source_git_commit') !=
                    'synthetic_no_official_evaluator')):
            raise RuntimeError('synthetic verifier identity mismatch')
        sources, _, _ = self._resolve_tests()
        target = str(EnvironmentPaths.for_os(self.environment.os).tests_dir)
        for source in sources:
            await self.environment.upload_dir(source_dir=source, target_dir=target)
        expected = spec['official_evaluator_files']
        if not expected or any(not isinstance(item.get('relative'), str) or
                               not item['relative'].startswith('tests/')
                               for item in expected):
            raise RuntimeError('official evaluator file list invalid')
        # Harbor's upload is complete here, but test.sh has not yet executed.
        # Read the actual container bytes and require the exact file set.
        command = ('cd / && test -z "$(find tests ! -type f ! -type d -print -quit)" '
                   '&& find tests -type f -print0 | sort -z | '
                   'xargs -0 -r sha256sum')
        listing = await self.environment.exec(command, timeout_sec=90, user='root')
        if listing.return_code:
            raise RuntimeError('container evaluator byte readback failed')
        actual = {}
        for line in listing.stdout.splitlines():
            sha, sep, path = line.partition('  ')
            if not sep or len(sha) != 64 or path in actual:
                raise RuntimeError('container evaluator file listing malformed')
            actual[path] = sha
        required = {item['relative']: item['sha256'] for item in expected}
        if actual != required:
            raise RuntimeError('container evaluator bytes or file set differ')
        archive = Path(spec['archive_root'])
        ended = json.loads((archive / 'agent_end_native.json').read_text(encoding='utf-8'))
        if ended.get('run_id') != spec['run_id'] or not ended.get('writers_stopped'):
            raise RuntimeError('native evaluator has no stopped agent identity')
        _atomic(archive / 'native_evaluator_uploaded.json', {
            'run_id': spec['run_id'], 'container_id': ended['container_id'],
            'files': actual, 'source_commit': spec['official_source_git_commit'],
            'test_sh_sha256': required['tests/test.sh']})
        protocol = spec.get('evaluation_bootstrap_protocol', 'original')
        if protocol not in {'original', BOOTSTRAP_PROTOCOL, 'persistent_bundle_v1',
                            DOWNLOAD_PROTOCOL}:
            raise RuntimeError('unknown evaluation bootstrap protocol')
        bootstrap = None
        effective_path = None
        if protocol in {BOOTSTRAP_PROTOCOL, 'persistent_bundle_v1', DOWNLOAD_PROTOCOL}:
            if (spec.get('evaluation_protocol') != 'official_shared_v2' or
                    (protocol == BOOTSTRAP_PROTOCOL and
                     spec.get('task_id') != 'sqlite-with-gcov') or
                    (protocol == 'persistent_bundle_v1' and
                     spec.get('task_id') not in {'sqlite-with-gcov', 'fix-ocaml-gc'})):
                raise RuntimeError('bootstrap protocol outside pinned official SQLite task')
            original = self.task.paths.test_path_for(self.environment.os).read_bytes()
            download = (download_plan(original, spec['evaluation_download_retry']['max_attempts'])
                        if protocol == DOWNLOAD_PROTOCOL else None)
            effective = (download.effective if download is not None else
                         effective_script(original, task=spec['task_id']))
            if hashlib.sha256(original).hexdigest() != required['tests/test.sh']:
                raise RuntimeError('bootstrap original does not match uploaded verifier')
            # No artifact from a previous attempt may satisfy this invocation.
            absent = await self.environment.exec(
                command='test ! -e /logs/verifier/ctrf.json && '
                        'test ! -e /logs/verifier/reward.txt && '
                        'test ! -e /logs/verifier/reward.json',
                user='root', timeout_sec=30)
            if absent.return_code or any((self.trial_paths.verifier_dir / name).exists()
                                         for name in ('ctrf.json', 'reward.txt', 'reward.json')):
                raise RuntimeError('previous verifier artifacts exist before bootstrap')
            bootstrap = {'run_id': spec['run_id'], 'protocol': protocol,
                         'original_sha256': hashlib.sha256(original).hexdigest(),
                         'effective_sha256': hashlib.sha256(effective).hexdigest(),
                         'status': 'preparing', 'stages': [], 'test_starts': 0}
            if download is not None:
                bootstrap.update(coverage=download.coverage,
                                 max_attempts=spec['evaluation_download_retry']['max_attempts'],
                                 preparation_commands_sha256=hashlib.sha256(json.dumps(
                                     download.stages, separators=(',', ':')).encode()).hexdigest())
            if protocol == BOOTSTRAP_PROTOCOL:
                bootstrap['preparation_commands_sha256'] = hashlib.sha256(json.dumps(
                    bootstrap_commands(), separators=(',', ':')).encode('utf-8')).hexdigest()
            receipt_path = archive / f'{protocol}.json'
            stage_dir = archive / f'{protocol}_stages'
            stage_dir.mkdir(exist_ok=False)
            def record(row):
                bootstrap['stages'].append(row)
                _atomic(stage_dir / f'{len(bootstrap["stages"]):03d}.json',
                        {'run_id': spec['run_id'], **row})
            try:
                if protocol == BOOTSTRAP_PROTOCOL:
                    await prepare(self.environment.exec, record)
                elif protocol == DOWNLOAD_PROTOCOL:
                    await self.environment.exec(
                        command=f'mkdir -p /logs/verifier/{protocol}', user='root',
                        timeout_sec=30)
                    await prepare_downloads(self.environment.exec, record, download.stages)
                else:
                    cache = spec['evaluation_cache']
                    frozen = json.loads(Path(spec['manifest_path']).read_text(encoding='utf-8'))
                    asset = frozen['assets'][spec['task_id']]
                    try:
                        container = subprocess.run(['docker', 'inspect', ended['container_id']],
                            check=True, capture_output=True, text=True, timeout=30)
                        containers = json.loads(container.stdout)
                        inspected = subprocess.run(['docker', 'image', 'inspect', spec['image_id']],
                            check=True, capture_output=True, text=True, timeout=30)
                        images = json.loads(inspected.stdout)
                    except (OSError, ValueError, subprocess.SubprocessError) as exc:
                        raise BootstrapFailed('image_identity', None, type(exc).__name__) from exc
                    if (len(containers) != 1 or containers[0]['Image'] != spec['image_id'] or
                            len(images) != 1 or images[0]['Id'] != spec['image_id'] or
                            asset['repo_digest'] not in images[0]['RepoDigests'] or
                            images[0]['Os'] + '/' + images[0]['Architecture'] != asset['platform'] or
                            cache['identity']['task'] != spec['task_id'] or
                            cache['identity']['original_sha256'] != required['tests/test.sh'] or
                            cache['identity']['base_image'] != asset['repo_digest'] or
                            cache['identity']['architecture'] != 'x86_64' or
                            asset['platform'] != 'linux/amd64'):
                        raise BootstrapFailed('image_identity', None, 'actual container image differs from cache')
                    try:
                        await prepare_cached(self.environment.exec, self.environment.upload_file,
                            cache['bundle_path'], cache['identity'], record,
                            expected_manifest_sha256=cache['manifest_sha256'])
                    except Exception as exc:
                        raise BootstrapFailed('cache_prepare', None, type(exc).__name__) from exc
                if download is None or download.coverage != 'uncovered_original_once':
                    effective_path = f'/logs/verifier/{protocol}/test.sh'
                    await self.environment.exec(command=f'mkdir -p /logs/verifier/{protocol}',
                                                user='root', timeout_sec=30)
                    with TemporaryDirectory(prefix='pma-eval-bootstrap-') as temporary:
                        local = Path(temporary) / 'test.sh'
                        local.write_bytes(effective)
                        await self.environment.upload_file(source_path=local,
                                                           target_path=effective_path)
                    readback = await self.environment.exec(
                        command=f'sha256sum {effective_path}', user='root', timeout_sec=30)
                    if (readback.return_code or (readback.stdout or '').split(' ', 1)[0] !=
                            bootstrap['effective_sha256']):
                        raise BootstrapFailed('effective_readback', readback.return_code,
                                              'effective verifier bytes differ')
                    executable = await self.environment.exec(
                        command=f'chmod +x {effective_path} && test -x {effective_path}',
                        user='root', timeout_sec=30)
                    if executable.return_code:
                        raise BootstrapFailed('effective_executable', executable.return_code,
                                              'effective verifier not executable')
                bootstrap['status'] = 'ready'
            except BootstrapFailed as exc:
                bootstrap.update(status='bootstrap_failed', failed_stage=exc.stage,
                                 return_code=exc.return_code, error_type=type(exc).__name__)
                _atomic(receipt_path, bootstrap)
                raise
            except Exception as exc:
                bootstrap.update(status='bootstrap_failed', failed_stage='effective_upload',
                                 return_code=None, error_type=type(exc).__name__)
                _atomic(receipt_path, bootstrap)
                raise
        self._skip_tests_upload = True
        original_exec = self.environment.exec
        executions = []

        async def recorded_exec(*args, **kwargs):
            command = kwargs.get('command', args[0] if args else '')
            if 'tests/test.sh' in str(command) and '/logs/verifier/' in str(command):
                if bootstrap is not None:
                    if bootstrap['test_starts']:
                        raise RuntimeError('verifier test entry repeated')
                    bootstrap['test_starts'] = 1
                    bootstrap['status'] = 'tests_started'
                    _atomic(archive / f'{protocol}_test_started.json', {
                        'run_id': spec['run_id'], 'protocol': protocol,
                        'effective_sha256': bootstrap['effective_sha256']})
                    if effective_path is not None:
                        kwargs['command'] = str(command).replace('/tests/test.sh', effective_path, 1)
                execution = {'command': str(command), 'status': 'started'}
                executions.append(execution)
                try:
                    result = await original_exec(*args, **kwargs)
                except Exception as exc:
                    execution.update(status='unknown', error_type=type(exc).__name__)
                    raise
                execution.update(status='returned', return_code=result.return_code,
                                 stdout=result.stdout, stderr=result.stderr)
                return result
            result = await original_exec(*args, **kwargs)
            return result

        self.environment.exec = recorded_exec
        try:
            result = await super().verify()
            reports = spec.get('expected_native_reports')
            if not isinstance(reports, list) or (
                    spec['official_source_git_commit'] != 'synthetic_no_official_evaluator'
                    and not reports):
                raise RuntimeError('native report identity absent')
            report_status = []
            for source_path in reports:
                if (not isinstance(source_path, str) or
                        not source_path.startswith('/logs/verifier/') or
                        '..' in Path(source_path).parts):
                    raise RuntimeError('native report path outside verifier logs')
                local = self.trial_paths.verifier_dir / Path(source_path).name
                try:
                    contents = local.read_bytes()
                    parsed = json.loads(contents)
                    valid = self._report_has_executed_tests(parsed)
                except (OSError, ValueError):
                    valid = False
                    contents = b''
                report_status.append({'source': source_path,
                                      'sha256': hashlib.sha256(contents).hexdigest()
                                          if valid else None,
                                      'present_parseable_executed': valid})
            _atomic(archive / 'native_reports_checked.json', {
                'run_id': spec['run_id'], 'reports': report_status,
                'all_reports_executed': all(row['present_parseable_executed']
                                            for row in report_status)})
            if any(not row['present_parseable_executed'] for row in report_status):
                if bootstrap is not None:
                    bootstrap['status'] = 'reports_missing'
                raise RuntimeError('native evaluator report missing, incomplete or no tests executed')
            if bootstrap is not None:
                bootstrap['status'] = 'evaluation_completed'
            return result
        finally:
            self.environment.exec = original_exec
            if bootstrap is not None:
                if bootstrap['status'] == 'ready':
                    bootstrap['status'] = 'test_entry_failed'
                if (bootstrap['status'] == 'tests_started' and
                        not all((self.trial_paths.verifier_dir / Path(path).name).is_file()
                                for path in spec['expected_native_reports'])):
                    bootstrap['status'] = 'reports_missing'
                _atomic(receipt_path, bootstrap)
            _atomic(archive / 'native_test_execution.json', {
                'run_id': spec['run_id'], 'executions': executions,
                'observed': bool(executions)})
