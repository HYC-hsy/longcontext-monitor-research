"""Copy three frozen public task assets into role-separated local pilot inputs.

No model, Docker build, provider, or evaluator is invoked here.
"""

import hashlib
import json
import shutil
from pathlib import Path


SOURCE = Path(r'E:\LongContext\long_context_bench\.cache\m12_roadmap_tasks')
TASKS = {
    'mko-7.0.0-roadmap': ('67ef17fccb86a393bb3cbb9aeec7faa7731545a95d6bd1ffab9fb1d408438e73',
                          '2e99c8ef876d92e98ea56862d1a59ca60b6c7775d8b72eb63c625ab9c55650c9',
                          'a5c7bac2491c30f17b48346e663b5e234046e3572692f5359c7a31c3622ae92c',
                          '25511e376935fcd587b9bf54dd22578f50c47ad37f3237c4555f1256c847e785',
                          2592, 'eb1f36f2da999b11e13c85a32152905d328cdf5125c22f8a6fd1b576f5df732f'),
    'fal-2.0.0-roadmap': ('472a40e8a78836495a2ed0b4d4b0cf9083c4210b0db639094e6c00b61ce8b3a0',
                          'f079ab63422a0293c4e0e77e84bfcbb6f7319742a46f2a6779fd1a1f142d4fdb',
                          'fa135267a7df2ff558fa4e67b851fbef1e844684284db12b86bacf6962d31410',
                          '4114280a86a7549f8b17844958ed76a6a66d40baf7763babdc038c8532706c1a',
                          229, '5604d903235b79c3acc7ce1e556f8376f918b4366b66c67e947896eb2c63aa38'),
    'glz-7.0.0-roadmap': ('6b2ec8fb4afdab95c3fb593ca2769b05c6bf09e23c232174b47977df49e441e9',
                          '7a92c045d2f6c4bb839ee5714705a981247c7e2cff33b439fa5a8f0e507328ca',
                          'c691c367f1f6a14b0abc1158aaf92144a2a242216604241fb37e971897a612be',
                          'b1f4fe59ad0b40934e4d4668426d563c4a6754d056a57faee736c76af8e8e3c3',
                          493, '38ff16edf48aaff1f24ebdff6679707a8413fd58f2827c908bc7c53d43ef636b'),
}


def file_sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def tree_identity(root):
    lines = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError(f'Symlink is not a frozen source asset: {path}')
        if path.is_file():
            lines.append(path.relative_to(root).as_posix() + '\t' + file_sha(path))
    raw = ('\n'.join(lines) + '\n').encode('utf-8')
    return len(lines), hashlib.sha256(raw).hexdigest()


def materialize(destination):
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    inventory = {}
    for name, (instruction, task_toml, dockerfile, evaluator, count, tree) in TASKS.items():
        base = SOURCE / name
        paths = (base / 'instruction.md', base / 'task.toml',
                 base / 'environment/Dockerfile', base / 'tests/test.sh')
        if tuple(file_sha(p) for p in paths) != (instruction, task_toml, dockerfile, evaluator):
            raise ValueError(f'Frozen source-file identity changed: {name}')
        if tree_identity(base / 'environment/repo') != (count, tree):
            raise ValueError(f'Frozen source-tree identity changed: {name}')
        inventory[name] = {'instruction_sha256': instruction, 'task_toml_sha256': task_toml,
                           'dockerfile_sha256': dockerfile, 'evaluator_sha256': evaluator,
                           'source_file_count': count, 'source_tree_sha256': tree}
    destination.mkdir(parents=True)
    for name in TASKS:
        source = SOURCE / name
        task = destination / name / 'task'
        build = destination / name / 'image_build'
        evaluator = destination / name / 'evaluator_only'
        task.mkdir(parents=True)
        build.mkdir()
        evaluator.mkdir()
        shutil.copy2(source / 'instruction.md', task / 'instruction.md')
        shutil.copy2(source / 'task.toml', task / 'task.toml')
        shutil.copy2(source / 'environment/Dockerfile', build / 'Dockerfile')
        shutil.copytree(source / 'environment/repo', build / 'repo')
        shutil.copytree(source / 'tests', evaluator / 'tests')
        if tree_identity(build / 'repo') != tree_identity(source / 'environment/repo'):
            raise RuntimeError(f'Copied source-tree identity mismatch: {name}')
        if file_sha(evaluator / 'tests/test.sh') != inventory[name]['evaluator_sha256']:
            raise RuntimeError(f'Copied evaluator identity mismatch: {name}')
    manifest = {'status': 'materialized_not_executed', 'source': str(SOURCE),
                'source_revision': '59184e779909300a5a0150b06b945d39da81a099',
                'role_policy': {'task': 'instruction and task.toml only',
                                'image_build': 'Dockerfile and source repo only',
                                'evaluator_only': 'tests; never mounted online'},
                'tasks': inventory}
    (destination / 'ASSET_MANIFEST.json').write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding='utf-8')
    return manifest


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('destination')
    args = parser.parse_args()
    print(json.dumps(materialize(args.destination), sort_keys=True))
