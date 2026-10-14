"""Byte check around Harbor's original SHARED Verifier; no scoring logic."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from harbor.models.trial.paths import EnvironmentPaths
from harbor.verifier.verifier import Verifier

from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.pilot_harbor_hooks import _atomic


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
        if spec.get('evaluation_protocol') != 'official_shared_v2':
            raise RuntimeError('native shared verifier protocol mismatch')
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
        self._skip_tests_upload = True
        original_exec = self.environment.exec
        executions = []

        async def recorded_exec(*args, **kwargs):
            command = kwargs.get('command', args[0] if args else '')
            result = await original_exec(*args, **kwargs)
            if 'tests/test.sh' in str(command) and '/logs/verifier/' in str(command):
                executions.append({'command': str(command),
                                   'return_code': result.return_code,
                                   'stdout': result.stdout, 'stderr': result.stderr})
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
                raise RuntimeError('native evaluator report missing, incomplete or no tests executed')
            return result
        finally:
            self.environment.exec = original_exec
            _atomic(archive / 'native_test_execution.json', {
                'run_id': spec['run_id'], 'executions': executions,
                'observed': bool(executions)})
