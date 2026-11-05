"""Zero-model checks for the new two-task route; no Task is started."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from .pma_harbor_hooks import _docker_top_pids, _nginx_service_only
from .prepare_two_task_manifest import HARBOR_COMMIT, source_identity
from .two_task_plan import ORDER


ROOT = Path(__file__).resolve().parents[3]


def run(command: list[str], *, env: dict | None = None, timeout: int = 120) -> dict:
    result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                            capture_output=True, timeout=timeout)
    return {'argv': command, 'exit_code': result.returncode,
            'stdout': result.stdout, 'stderr': result.stderr}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--harbor-source-root', type=Path, required=True)
    parser.add_argument('--official-source-git', type=Path, required=True)
    parser.add_argument('--task-profile-file', type=Path, required=True)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--worker-python', type=Path, required=True)
    parser.add_argument('--harbor-exe', type=Path, required=True)
    parser.add_argument('--bench-root', type=Path, required=True)
    parser.add_argument('--fixture-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    head, _ = source_identity()
    report = {'code_commit': head, 'harbor_commit': HARBOR_COMMIT,
              'dataset_commit': '2fd12b88aafdd04a52c298e3940bcb189f9766d6',
              'tasks': [row[1] for row in ORDER], 'checks': [],
              'nginx_service_preserved': False,
              'extra_writer_rejected': False, 'passed': False}
    env = dict(os.environ)
    env['PYTHONUTF8'] = '1'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
    env['PYTHONPATH'] = os.pathsep.join((str(args.harbor_source_root / 'src'),
        str(ROOT), str(ROOT / 'GenericAgent-main')))
    suites = (
        [sys.executable, '-B', '-m', 'unittest', 'tests.test_simple', '-v'],
        [sys.executable, '-B', '-m', 'pytest',
         'GenericAgent-main/tests/test_pma_upstream_ga_bridge.py', '-q'],
        [sys.executable, '-B', '-m', 'unittest',
         'method_discovery.curator_supervisor_convergence_v0.'
         'pma_full_upstream_ga_v1_20261013.test_two_task_lifecycle', '-v'],
    )
    try:
        for command in suites:
            check = run(command, env=env)
            report['checks'].append(check)
            if check['exit_code']:
                raise RuntimeError('offline suite failed')
        for path, expected in ((args.harbor_source_root, HARBOR_COMMIT),
                               (args.official_source_git, report['dataset_commit'])):
            check = run(['git', '-C', str(path), 'rev-parse', 'HEAD'])
            report['checks'].append(check)
            if check['exit_code'] or check['stdout'].strip() != expected:
                raise RuntimeError('fixed external checkout differs')
        info = run(['docker', 'info', '--format', '{{.OSType}}'])
        report['checks'].append(info)
        if info['exit_code'] or info['stdout'].strip() != 'linux':
            raise RuntimeError('Linux Docker Engine unavailable')
        for _, task, _, _ in ORDER:
            from .offline_launcher import TASKS, image_identity
            image = image_identity(TASKS[task])
            if image['platform'] != 'linux/amd64' or len(image['repo_digests']) != 1:
                raise RuntimeError(f'{task}: image identity incomplete')
            report.setdefault('images', {})[task] = image
        if args.fixture_root.exists():
            raise FileExistsError(args.fixture_root)
        args.fixture_root.mkdir(parents=True)
        for _, task, _, _ in ORDER:
            fixture = args.fixture_root / task
            command = [sys.executable, '-B', '-m',
                'method_discovery.curator_supervisor_convergence_v0.'
                'pma_full_upstream_ga_v1_20261013.offline_launcher',
                '--task', task, '--condition', 'B',
                '--run-id', 'pma-two-zero-' + task,
                '--run-root', str(fixture),
                '--ga-source', str(ROOT / 'GenericAgent-main'),
                '--runtime-root', str(args.runtime_root),
                '--task-profile-file', str(args.task_profile_file),
                '--worker-python', str(args.worker_python),
                '--harbor-exe', str(args.harbor_exe),
                '--bench-root', str(args.bench_root),
                '--official-source-git', str(args.official_source_git),
                '--timeout-sec', '180']
            checked = run(command, env=env, timeout=270)
            report['checks'].append(checked)
            status_path = fixture / 'archive' / 'offline_result.json'
            if checked['exit_code'] or not status_path.is_file():
                raise RuntimeError(f'{task}: zero-model GA/PMA Harbor fixture failed')
            status = json.loads(status_path.read_text(encoding='utf-8'))
            if status.get('integration_ok') is not True or status.get('cleanup_confirmed') is not True:
                raise RuntimeError(f'{task}: zero-model lifecycle or cleanup failed')
            report.setdefault('fixtures', {})[task] = {
                'result_path': str(status_path), 'integration_ok': True,
                'cleanup_confirmed': True}
        name = 'pma-nginx-preflight-' + uuid.uuid4().hex[:12]
        started = run(['docker', 'run', '--rm', '-d', '--name', name,
                       'alexgshaw/nginx-request-logging:20251031', 'sleep', '600'])
        report['checks'].append(started)
        if started['exit_code'] or not started['stdout'].strip():
            raise RuntimeError('Nginx zero-model container did not start')
        container = started['stdout'].strip()
        try:
            baseline = run(['docker', 'top', container])
            report['checks'].append(baseline)
            if baseline['exit_code']:
                raise RuntimeError('Nginx baseline process inventory failed')
            installed = run(['docker', 'exec', container, 'sh', '-c',
                'apt-get update -qq && DEBIAN_FRONTEND=noninteractive '
                'apt-get install -y -qq nginx'], timeout=300)
            report['checks'].append(installed)
            if installed['exit_code']:
                raise RuntimeError('Nginx zero-model install failed')
            service = run(['docker', 'exec', container, 'nginx'])
            report['checks'].append(service)
            if service['exit_code']:
                raise RuntimeError('Nginx zero-model service failed')
            after = run(['docker', 'top', container])
            report['checks'].append(after)
            if after['exit_code']:
                raise RuntimeError('Nginx service inventory failed')
            baseline_pids = _docker_top_pids(baseline['stdout'])
            report['nginx_service_preserved'] = _nginx_service_only(
                container, after['stdout'], baseline_pids)
            writer = run(['docker', 'exec', '-d', container, 'python3', '-c',
                          'import time;time.sleep(120)'])
            report['checks'].append(writer)
            with_writer = run(['docker', 'top', container])
            report['checks'].append(with_writer)
            report['extra_writer_rejected'] = (
                writer['exit_code'] == 0 and with_writer['exit_code'] == 0 and
                'time.sleep(120)' in with_writer['stdout'] and
                not _nginx_service_only(container, with_writer['stdout'], baseline_pids))
            if not report['nginx_service_preserved'] or not report['extra_writer_rejected']:
                raise RuntimeError('Nginx service/writer boundary unverified')
        finally:
            removed = run(['docker', 'rm', '-f', container])
            report['checks'].append(removed)
            if removed['exit_code']:
                raise RuntimeError('Nginx zero-model container cleanup unconfirmed')
        report['passed'] = True
    except BaseException as exc:
        report['error'] = {'type': type(exc).__name__, 'message': str(exc)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                           encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'error': report.get('error'),
                      'output': str(args.output)}, ensure_ascii=False))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
