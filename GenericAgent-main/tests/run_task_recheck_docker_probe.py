"""Disposable zero-model Docker commit/clone and GA-tool source check."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import uuid


IMAGE = 'alexgshaw/financial-document-processor:20251031'
PYTHON = '/opt/m2-runtime/ga-env/bin/python'


def docker(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(['docker', *args], capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=120)
    if check and result.returncode:
        raise RuntimeError(f'docker {args[0]} failed ({result.returncode}): {result.stderr[:500]}')
    return result


def main():
    source_root = Path(__file__).resolve().parents[1]
    runtime = Path('E:/LongContext/bench_runtime/m2/linux').resolve(strict=True)
    fixture = source_root / 'tests/task_recheck_probe_extraction.csv'
    token = uuid.uuid4().hex[:12]
    source, left, right = (f'lc-recheck-probe-{token}-{part}'
                           for part in ('source', 'left', 'right'))
    tag = f'lc-recheck-probe:{token}'
    names = (source, left, right)
    runtime_mount = f'type=bind,src={runtime.as_posix()},dst=/opt/m2-runtime,readonly'
    code_mount = f'type=bind,src={source_root.as_posix()},dst=/opt/genericagent-source,readonly'
    created = []
    image_created = False
    try:
        docker('create', '--name', source, '--network', 'none',
               '--mount', runtime_mount, '--entrypoint', 'sleep', IMAGE, '3600')
        created.append(source)
        docker('start', source)
        docker('cp', str(fixture), source + ':/app/extraction.csv')
        image_id = docker('commit', source, tag).stdout.strip()
        image_created = True
        if not image_id.startswith('sha256:'):
            raise RuntimeError('Docker commit did not yield image identity')
        outputs = {}
        for name in (left, right):
            docker('create', '--name', name, '--network', 'none',
                   '--mount', runtime_mount, '--mount', code_mount,
                   '--entrypoint', 'sleep', tag, '3600')
            created.append(name)
            docker('start', name)
            result = docker('exec', '--env', 'PYTHONPATH=/opt/genericagent-source',
                            name, PYTHON,
                            '/opt/genericagent-source/tests/task_recheck_container_probe.py')
            outputs[name] = json.loads(result.stdout.strip().splitlines()[-1])
        if outputs[left] != outputs[right]:
            raise RuntimeError('clone source/output hashes differ')
        docker('exec', left, PYTHON, '-c',
               "from pathlib import Path;Path('/app/extraction.csv').write_text("
               "'source,amount\\nUsN9tVTKskms.pdf,0\\n',encoding='utf-8')")
        unchanged = docker('exec', '--env', 'PYTHONPATH=/opt/genericagent-source',
                           right, PYTHON,
                           '/opt/genericagent-source/tests/task_recheck_container_probe.py')
        if json.loads(unchanged.stdout.strip().splitlines()[-1]) != outputs[right]:
            raise RuntimeError('clone workspaces are not isolated')
        print(json.dumps({'status': 'passed', 'source_image': IMAGE,
                          'snapshot_image_id': image_id,
                          'tool': 'GA code_run', 'network': 'none',
                          'source_document_sha256': outputs[right]['source_sha256'],
                          'probe_output_sha256': outputs[right]['output_sha256'],
                          'clone_isolation': True,
                          'extraction_is_synthetic_probe_fixture': True}, sort_keys=True))
    finally:
        for name in reversed(created):
            if name in names:
                docker('rm', '-f', name, check=False)
        if image_created:
            docker('image', 'rm', tag, check=False)


if __name__ == '__main__':
    main()
