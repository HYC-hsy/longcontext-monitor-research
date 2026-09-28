"""Copy six existing public originals byte-for-byte and hash local snapshots.

Reads no benchmark solution or verifier; no task execution and no downloads.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVISION = '59184e779909300a5a0150b06b945d39da81a099'


def sha(data): return hashlib.sha256(data).hexdigest()


if __name__ == '__main__':
    records = []
    for name in ('ktx-0.13.0-roadmap', 'rat-0.22.0-roadmap'):
        original = ROOT / 'long_context_bench/.cache/m12_roadmap_tasks' / name
        files = []
        for rel in ('instruction.md', 'task.toml', 'environment/Dockerfile'):
            raw = (original / rel).read_bytes()
            out = HERE / 'task_originals' / name / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.exists() and out.read_bytes() != raw:
                raise RuntimeError('existing original copy differs: ' + str(out))
            out.write_bytes(raw)
            assert out.read_bytes() == raw
            files.append(dict(path=out.relative_to(HERE).as_posix(),
                original_path=(original / rel).relative_to(ROOT).as_posix(),
                bytes=len(raw), sha256=sha(raw)))
        workspace = original / 'environment/repo'
        manifest = [{'path': p.relative_to(workspace).as_posix(), 'sha256': sha(p.read_bytes())}
            for p in sorted(workspace.rglob('*')) if p.is_file()]
        raw = json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()
        manifest_path = HERE / 'task_originals' / name / 'local_workspace_file_manifest.json'
        manifest_path.write_bytes(raw)
        records.append(dict(task_id='roadmapbench:' + name, split='method_dev', panel='dev_pilot',
            source_host='Hugging Face dataset', source_repo='UnipatAI/RoadmapBench',
            source_revision=REVISION, source_locator='https://huggingface.co/datasets/UnipatAI/RoadmapBench/tree/' + REVISION,
            remote_revision_refetched=False, files=files,
            local_workspace_manifest=manifest_path.relative_to(HERE).as_posix(),
            local_workspace_manifest_sha256=sha(raw), local_workspace_files=len(manifest),
            upstream_initial_commit=None, container_image_digest=None,
            initial_container_snapshot_verified=False, mounts_verified=False))
    index = dict(schema='public-task-originals/1', preparation_only=True,
        exclusion='No solution, benchmark hidden tests, old trajectories or judgments copied; manifests hash existing environment/repo only.',
        snapshot_limit='Local cached repo identity is not a proof of the eventual image or mounted initial workspace; those remain unverified.',
        records=records)
    (HERE / 'task_source_index.json').write_text(json.dumps(index, indent=2), encoding='utf-8')
    print(json.dumps({'copied_originals': 6, 'byte_equal': True,
        'local_workspace_file_counts': {r['task_id']: r['local_workspace_files'] for r in records},
        'model_requests': 0, 'containers_started': 0}))
