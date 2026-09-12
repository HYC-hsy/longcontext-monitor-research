"""Stage the user-approved FBR native smoke, without launching a model."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import subprocess
from datetime import datetime, timezone

from prepare_pma_native_bundle import prepare, ROOT


def stage(output):
    source = ROOT / 'long_context_bench/.cache/m12_roadmap_tasks/fbr-2.43.0-roadmap'
    for name in ('instruction.md', 'task.toml', 'environment', 'tests'):
        if not (source / name).exists():
            raise FileNotFoundError(source / name)
    if any(p.is_symlink() for p in source.rglob('*')):
        raise ValueError('Task snapshot must not contain symbolic links')
    credentials = runpy.run_path(str(ROOT / 'GenericAgent-main/mykey.py'))['native_claude_cc_vibe']
    identity = prepare(output, {'base': credentials['apibase'], 'key': credentials['apikey']})
    output = Path(output).resolve()
    task = output / 'work/fbr-2.43.0-roadmap'
    task.mkdir()
    for name in ('instruction.md', 'task.toml'):
        shutil.copy2(source / name, task / name)
    for name in ('environment', 'tests'):
        shutil.copytree(source / name, task / name)
    inventory = {p.relative_to(task).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in task.rglob('*') if p.is_file()}
    revision = subprocess.check_output(['git', '-c', 'safe.directory=E:/LongContext',
        'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    manifest = {'status': 'prepared_not_executed',
        'prepared_utc': datetime.now(timezone.utc).isoformat(),
        'task_id': 'roadmapbench:fbr-2.43.0-roadmap', 'split': 'method_dev',
        'condition': 'native-pma-original-models-docker-ccvibe',
        'purpose': 'native runtime and behavior smoke; not a controlled GA comparison',
        'source_commit': revision, 'runtime_sha256': identity['runtime_sha256'],
        'task_files_sha256': inventory,
        'task_image': 'sha256:a6fa79e2dd6cf93c27ebae40cf35852b7aca0e61c3305600c1b41dfa75a24de0',
        'controller_image': identity['controller_image'],
        'task_model': 'anthropic/claude-sonnet-4-5-20250929',
        'memory_model': 'anthropic/claude-opus-4-6',
        'temperatures': {'task': .7, 'memory': .3},
        'max_turns': 50, 'agent_seconds': 7200, 'verifier_seconds': 1800,
        'controller_cpu_memory': '2 CPU / 2 GiB', 'task_cpu_memory': '2 CPU / 4 GiB',
        'network': 'task:none; controller:none; gateway:fixed-inference-only',
        'approval': 'User explicitly approved FBR original-configuration smoke in this turn',
        'estimated_cost_usd': None, 'usage_note': 'Record actual returned usage; relay billing unknown',
        'linux_task': identity['linux_work'] + '/fbr-2.43.0-roadmap',
        'linux_output': identity['linux_work'] + '/trial'}
    (output / 'run_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({k: manifest[k] for k in ('status', 'task_id', 'linux_task', 'linux_output')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    stage(parser.parse_args().output)
