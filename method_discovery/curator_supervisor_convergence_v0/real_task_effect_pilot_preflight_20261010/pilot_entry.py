"""Research-only Fyne/Kitex pilot staging and fail-closed execution entry.

``prepare`` has no model or evaluator effects. ``live`` cannot proceed without
an exact future authorization bound to the audited checkout.
The historical C02 and six-arm authorizations are never accepted here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

from long_context_bench.scripts.isolated_run_bundle import build_bundle, digest_tree
from .pilot_analysis_bridge import SCHEMA
from .pilot_profile import resolved_supervisor_profile, public_profile_identity
from .pilot_task_package import materialize_public_agent_task


TASKS = {
    'roadmapbench:fyn-2.2.0-roadmap': (
        'fyn-2.2.0-roadmap',
        'sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1',
        '7229e889d49c81a83b0b7e09400837f67f6ddad5'),
    'roadmapbench:ktx-0.13.0-roadmap': (
        'ktx-0.13.0-roadmap',
        'sha256:7ffcd70e49d77031b8e67eaa99226dc8468fa046f33e615118e8922b89fff32e',
        '2a128be5c44b8de7af8d1e3988a2ac22da7c6578'),
}
TASK_PROFILE = 'native_claude_cc_vibe_opus48'
MONITOR_PROFILE = 'claude_monitor_opus48'


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ordinary_source_tree_sha256(root: Path) -> tuple[str, int]:
    """Freeze current cache bytes, distinct from historical task-tree IDs."""
    digest = hashlib.sha256()
    count = 0
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if '.git' in relative.parts:
            continue
        if path.is_symlink():
            raise RuntimeError('Pilot task source contains a redirected path')
        if path.is_file():
            digest.update(relative.as_posix().encode('utf-8') + b'\0')
            digest.update(path.read_bytes())
            count += 1
    return digest.hexdigest(), count


def _image_identity(image: str) -> dict:
    inspected = subprocess.run(['docker', 'image', 'inspect', image], capture_output=True,
                               text=True, timeout=30)
    if inspected.returncode:
        raise RuntimeError('Pinned pilot image is unavailable')
    record = json.loads(inspected.stdout)[0]
    if record['Id'] != image:
        raise RuntimeError('Pinned pilot image ID changed')
    return {'image_id': record['Id'], 'repo_digests': list(record.get('RepoDigests') or [])}


def _augment_compose(path: Path, *, volume: str, condition: str, root: Path) -> None:
    compose = json.loads(path.read_text(encoding='utf-8'))
    main = compose['services']['main']
    main.setdefault('volumes', []).append({'type': 'volume', 'source': volume,
                                            'target': '/app', 'read_only': False})
    compose['volumes'][volume] = {'external': True, 'name': volume}
    if condition == 'S':
        spool = root / 'control' / 'spool'
        for source, target, readonly in (
            (spool / 'requests', '/logs/agent/monitor_bridge/requests', False),
            (spool / 'responses', '/logs/agent/monitor_bridge/responses', True),
            (spool / 'identity.json', '/logs/agent/monitor_bridge/identity.json', True),
            (root / 'monitor', '/logs/agent/monitor', False),
        ):
            main['volumes'].append({'type': 'bind', 'source': source.resolve().as_posix(),
                                    'target': target, 'read_only': readonly})
    path.write_text(json.dumps(compose, indent=2), encoding='utf-8')


def prepare_run(*, manifest: Path, task_id: str, condition: str, run_id: str,
                run_root: Path, source_root: Path, ga_source: Path,
                runtime_root: Path, task_profile_file: Path, monitor_profile_file: Path,
                python_home: str) -> dict:
    if condition not in {'T', 'S'} or task_id not in TASKS:
        raise ValueError('Pilot task/condition is not approved in this draft')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{3,54}', run_id):
        raise ValueError('Pilot run_id must be a short lowercase opaque ID')
    manifest = Path(manifest).resolve(strict=True)
    frozen = json.loads(manifest.read_text(encoding='utf-8'))
    if frozen.get('execution_authorized') is not False:
        raise ValueError('Offline staging requires an unarmed draft manifest')
    if not any(row['task_id'] == task_id and row['condition'] == condition
               for row in frozen['arms']):
        raise ValueError('Arm is absent from the frozen draft')
    short, image, git_head = TASKS[task_id]
    if frozen['task_assets'][task_id]['image_id'] != image:
        raise ValueError('Draft image identity mismatch')
    image_identity = _image_identity(image)
    if image_identity['repo_digests'] != frozen['task_assets'][task_id]['repo_digests']:
        raise ValueError('RepoDigest list changed since draft freeze')
    source = Path(source_root).resolve(strict=True) / short
    source_tree, source_files = _ordinary_source_tree_sha256(source)
    if source_tree != frozen['task_assets'][task_id]['current_cache_non_git_tree_sha256']:
        raise RuntimeError('Pilot current task source tree differs from frozen draft')
    ga_source = Path(ga_source).resolve(strict=True)
    runtime_root = Path(runtime_root).resolve(strict=True)
    task_profile_file = Path(task_profile_file).resolve(strict=True)
    monitor_profile_file = Path(monitor_profile_file).resolve(strict=True)
    private_hashes = frozen['private_profile_file_sha256_only']
    if (sha_file(task_profile_file) != private_hashes['task'] or
            sha_file(monitor_profile_file) != private_hashes['supervisor']):
        raise RuntimeError('Pilot private profile identity differs from frozen draft')
    run_root = Path(run_root)
    if run_root.exists():
        raise FileExistsError(run_root)
    run_root.mkdir(parents=True)
    for name in ('control', 'archive', 'trusted', 'scratch', 'monitor', 'jobs'):
        (run_root / name).mkdir()
    public_task = run_root / 'public_agent_task'
    package_identity = materialize_public_agent_task(source, public_task)
    # The research checkout carries production code but intentionally does not
    # carry a credential file. Stage only its own source plus a separately
    # supplied private Task profile; build_bundle never mounts mykey.py.
    ga_stage = run_root / 'control' / 'ga_stage'
    shutil.copytree(ga_source, ga_stage, ignore=shutil.ignore_patterns(
        '.git', 'temp', 'tests', '__pycache__', '.pytest_cache', '*.pyc',
        '*.local.json', 'file_access_stats.json'))
    shutil.copy2(task_profile_file, ga_stage / 'mykey.py')
    profile_path = None
    if condition == 'S':
        profiles = json.loads(Path(monitor_profile_file).read_text(encoding='utf-8'))
        resolved = resolved_supervisor_profile(profiles[MONITOR_PROFILE])
        private_profiles = {MONITOR_PROFILE: resolved}
        profile_path = run_root / 'control' / 'resolved_monitor_profile.private.json'
        profile_path.write_text(json.dumps(private_profiles), encoding='utf-8')
        profile_identity = public_profile_identity(resolved)
    else:
        profile_identity = None
    bundle_source, compose = build_bundle(
        run_root / 'bundle', ga_stage, runtime_root, python_home,
        TASK_PROFILE, MONITOR_PROFILE if condition == 'S' else None, 15340,
        monitor_profile_path=profile_path)
    volume = 'lc-pilot-' + run_id
    created = subprocess.run(['docker', 'volume', 'create', volume], capture_output=True,
                             text=True, timeout=30)
    if created.returncode or created.stdout.strip() != volume:
        raise RuntimeError('Pilot task volume creation failed')
    if condition == 'S':
        # Mount the empty Monitor root.  The native runtime creates its own
        # task_identity.json before private/evidence directories.  Precreating
        # either child would look like unverified prior state and fail closed.
        spool = run_root / 'control' / 'spool'
        spool.mkdir()
        for child in ('requests', 'accepted', 'responses'):
            (spool / child).mkdir()
        (spool / 'identity.json').write_text(
            json.dumps({'schema': SCHEMA, 'run_id': run_id}), encoding='utf-8')
    _augment_compose(compose, volume=volume, condition=condition, root=run_root)
    spec = {'schema': 'pilot-harbor-run-v1', 'mode': 'unarmed',
            'execution_authorized': False, 'run_id': run_id, 'task_id': task_id,
            'condition': condition, 'image_id': image, 'git_head': git_head,
            'task_volume': volume, 'control_root': str((run_root / 'control').resolve()),
            'archive_root': str((run_root / 'archive').resolve())}
    (run_root / 'control' / 'harbor_spec.json').write_text(
        json.dumps(spec, indent=2), encoding='utf-8')
    receipt = {'manifest_sha256': sha_file(manifest), 'task_id': task_id,
               'condition': condition, 'run_id': run_id, 'image': image_identity,
               'public_package': package_identity,
               'current_cache_non_git_tree_sha256': source_tree,
               'current_cache_non_git_file_count': source_files,
               'bundle_source_sha256': digest_tree(bundle_source),
               'compose_sha256': sha_file(compose),
               'profile_public': profile_identity,
               'task_volume': volume, 'model_or_evaluator_calls': 0,
               'launch_authorized': False}
    (run_root / 'archive' / 'offline_preparation.json').write_text(
        json.dumps(receipt, indent=2), encoding='utf-8')
    return receipt


def unique_authorized_arm(arms: object, arm: dict) -> bool:
    """Match CLI/Harbor identity without discarding frozen order metadata."""
    if not isinstance(arms, list) or not isinstance(arm, dict):
        return False
    matches = [row for row in arms if isinstance(row, dict) and
               row.get('task_id') == arm.get('task_id') and
               row.get('condition') == arm.get('condition')]
    return len(matches) == 1


def exact_run_binding(granted: dict, arms: list, arm: dict, run_id: str,
                      run_root: Path, *, require_fresh: bool) -> bool:
    bindings = granted.get('run_bindings')
    if not isinstance(bindings, list) or len(bindings) != len(arms):
        return False
    if any(not isinstance(row, dict) or
           set(row) != {'order', 'task_id', 'condition', 'run_id', 'run_root'} or
           any(row.get(key) != expected.get(key) for key in
               ('order', 'task_id', 'condition')) or
           not isinstance(row['run_id'], str) or
           not isinstance(row['run_root'], str) or
           not Path(row['run_root']).is_absolute()
           for row, expected in zip(bindings, arms)):
        return False
    if (len({row['run_id'] for row in bindings}) != len(bindings) or
            len({row['run_root'] for row in bindings}) != len(bindings)):
        return False
    current = [row for row in bindings if row['task_id'] == arm.get('task_id') and
               row['condition'] == arm.get('condition')]
    if len(current) != 1:
        return False
    target = Path(run_root).resolve()
    return (current[0]['run_id'] == run_id and
            Path(current[0]['run_root']).resolve() == target and
            (not require_fresh or not target.exists()))


def require_live_authorization(manifest: Path, authorization: Path, arm: dict,
                               run_id: str, run_root: Path) -> None:
    frozen = json.loads(Path(manifest).read_text(encoding='utf-8'))
    granted = json.loads(Path(authorization).read_text(encoding='utf-8'))
    checkout = Path(__file__).resolve().parents[3]
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=checkout,
                          capture_output=True, text=True, timeout=10)
    if (frozen.get('execution_authorized') is not False or
            granted.get('execution_authorized') is not True or
            granted.get('manifest_sha256') != sha_file(Path(manifest)) or
            head.returncode or granted.get('audited_code_commit') != head.stdout.strip() or
            granted.get('approved_arms') != frozen.get('arms') or
            not unique_authorized_arm(frozen.get('arms'), arm) or
            not exact_run_binding(granted, frozen.get('arms', []), arm,
                                  run_id, run_root, require_fresh=True)):
        raise RuntimeError('Pilot live authorization absent or mismatched')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--authorization', type=Path)
    parser.add_argument('--harbor-python', type=Path)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--condition', choices=['T', 'S'], required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--ga-source', type=Path, required=True)
    parser.add_argument('--runtime-root', type=Path, required=True)
    parser.add_argument('--task-profile-file', type=Path, required=True)
    parser.add_argument('--monitor-profile-file', type=Path, required=True)
    parser.add_argument('--python-home', required=True)
    args = parser.parse_args()
    if args.live:
        if args.authorization is None or args.harbor_python is None:
            raise RuntimeError('Pilot live authorization or Harbor runtime is missing')
        require_live_authorization(args.manifest, args.authorization,
                                   {'task_id': args.task_id, 'condition': args.condition},
                                   args.run_id, args.run_root)
        from .pilot_offline_harbor import run_offline
        result = run_offline(
            manifest=args.manifest, task_id=args.task_id, condition=args.condition,
            run_id=args.run_id, run_root=args.run_root, source_root=args.source_root,
            ga_source=args.ga_source, runtime_root=args.runtime_root,
            task_profile_file=args.task_profile_file,
            monitor_profile_file=args.monitor_profile_file,
            python_home=args.python_home, harbor_python=args.harbor_python,
            timeout_seconds=10000, execution_mode='authorized_live',
            authorization=args.authorization)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    result = prepare_run(**{key: value for key, value in vars(args).items()
                            if key not in {'live', 'authorization', 'harbor_python'}})
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
