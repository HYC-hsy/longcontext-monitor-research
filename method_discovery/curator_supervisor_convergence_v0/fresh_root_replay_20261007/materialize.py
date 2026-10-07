"""Mechanically project the pre-evaluator Fyne workspace into a reviewer fixture.

No provider, evaluator, or task process is imported or executed here.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile


RUN_ID = 'crs-rhr-rer-v0-fyne-bji-high-budget-r1'
ARCHIVE = (Path(__file__).resolve().parents[1] / 'crs_rhr_rer_fyne_high_budget_20261007' / 'archive' / 'r1')
CAPTURE = (Path(r'E:\LongContext\long_context_bench\output\crs_rhr_rer_fyne_mechanism_gate')
           / 'bridge' / RUN_ID / 'evidence' / 'pre_verification_app.tar')
DESTINATION = Path(r'E:\crs_rhr_rer_fresh_replay_fixture_ready_20261007')
EXPECTED_CAPTURE_SHA256 = 'e4bec1565382c5d49b4e06aa051ec909d22a2319c560c4da1b2b2341362229eb'
EXPECTED_TASK_SHA256 = 'cae5f11a98aa573cf93629b8fb0becc18f395c5bdad25e09b8927d06f0725080'
EXPECTED_PATCH_SHA256 = 'bef5566c3665068c06663eb4abef31a48b7585d883e162f3bc2e9bb1c859edd1'
NARRATIVE_NAMES = {'IMPLEMENTATION_COMPLETE.md', 'IMPLEMENTATION_SUMMARY.md'}
EXCLUDED_ROOTS = {'.git', 'monitor', 'monitor_private', 'task_evidence', 'verifier', 'solution'}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exclude_reason(relative: PurePosixPath) -> str | None:
    if relative.parts[0] in EXCLUDED_ROOTS:
        return 'not_public_review_workspace_or_repository_metadata'
    if len(relative.parts) == 1 and relative.name in NARRATIVE_NAMES:
        return 'run_generated_completion_narrative'
    if len(relative.parts) == 1 and relative.name.startswith('.monitor_original_task_'):
        return 'run_generated_original_task_copy'
    return None


def _safe_relative(name: str) -> PurePosixPath:
    relative = PurePosixPath(name.removeprefix('./'))
    if relative.is_absolute() or not relative.parts or any(part in ('.', '..') for part in relative.parts):
        raise RuntimeError(f'Unsafe capture member: {name}')
    return relative


def _identity_lines(files: list[dict]) -> bytes:
    return ''.join(f"{row['path']}\0{row['sha256']}\n" for row in files).encode('utf-8')


def materialize(destination: Path = DESTINATION, capture: Path = CAPTURE) -> dict:
    if destination.exists():
        raise RuntimeError('Fresh review fixture already exists; refusing overwrite')
    if digest(capture) != EXPECTED_CAPTURE_SHA256:
        raise RuntimeError('Pre-evaluator workspace capture SHA mismatch')
    recorded = json.loads((ARCHIVE / 'RAW_FILE_MANIFEST.json').read_text(encoding='utf-8'))
    matches = [row for row in recorded['local_only_large_artifacts']
               if Path(row['path']) == capture and row['sha256'] == EXPECTED_CAPTURE_SHA256]
    if not matches:
        raise RuntimeError('Capture is not bound to the accepted raw archive')
    task = ARCHIVE / 'monitor/task_evidence/original_task.txt'
    patch = ARCHIVE / 'task_final/tracked_changes.patch'
    if digest(task) != EXPECTED_TASK_SHA256 or digest(patch) != EXPECTED_PATCH_SHA256:
        raise RuntimeError('Authoritative task or tracked patch identity mismatch')

    destination.mkdir(parents=True, exist_ok=False)
    workspace = destination / 'workspace'
    workspace.mkdir()
    included, excluded = [], []
    with tarfile.open(capture, mode='r') as source:
        for member in source.getmembers():
            if member.isdir():
                continue
            relative = _safe_relative(member.name)
            if not member.isfile():
                raise RuntimeError(f'Unsupported capture member type: {member.name}')
            reason = exclude_reason(relative)
            if reason:
                excluded.append({'path': relative.as_posix(), 'reason': reason})
                continue
            target = workspace.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            stream = source.extractfile(member)
            if stream is None:
                raise RuntimeError(f'Unreadable capture member: {member.name}')
            data = stream.read()
            target.write_bytes(data)
            included.append({'path': relative.as_posix(), 'bytes': len(data),
                             'sha256': hashlib.sha256(data).hexdigest()})
    included.sort(key=lambda row: row['path'])
    excluded.sort(key=lambda row: row['path'])
    task_copy = destination / 'task/original_task.txt'
    task_copy.parent.mkdir()
    task_copy.write_bytes(task.read_bytes())

    original_untracked = json.loads((ARCHIVE / 'task_final/MANIFEST.json').read_text(encoding='utf-8'))['files']
    source_additions = []
    for row in original_untracked:
        relative = row['path']
        if relative.startswith('untracked/') and relative.endswith('.go'):
            workspace_path = relative.removeprefix('untracked/')
            matching = next((item for item in included if item['path'] == workspace_path), None)
            if matching is None or matching['sha256'] != row['sha256']:
                raise RuntimeError(f'Untracked implementation source not restored exactly: {workspace_path}')
            source_additions.append({'path': workspace_path, 'sha256': row['sha256']})
    manifest = {
        'schema': 'fresh-root-release-review-fixture/1',
        'run_id': RUN_ID,
        'archive_commit': 'ca3648a925eb709deb09603e36e0f4981a03743a',
        'checkpoint': 'final Task workspace captured before native evaluator',
        'capture_path': str(capture), 'capture_sha256': EXPECTED_CAPTURE_SHA256,
        'source_task_package_tree_sha256': '36991e23b078c5b14b5ea96b8026592932048abfe5e3321c483f0430578cbe1a',
        'source_identity_task_tree_sha256': '928e4d98926e9c6038f2538ec960be19fa1fb199bfc11f06e3fe01a7d50259d6',
        'clean_workspace_git_head': '7229e889d49c81a83b0b7e09400837f67f6ddad5',
        'public_task_sha256': EXPECTED_TASK_SHA256,
        'tracked_patch_sha256': EXPECTED_PATCH_SHA256,
        'untracked_implementation_sources': source_additions,
        'workspace_tree_sha256': hashlib.sha256(_identity_lines(included)).hexdigest(),
        'workspace_file_count': len(included),
        'included_paths': included, 'excluded_paths': excluded,
        'fixture_root': str(destination),
        'review_readable_paths': ['task/original_task.txt', 'workspace/**'],
        'native_evaluator_or_history_in_review_view': False,
    }
    (destination / 'FIXTURE_MANIFEST.json').write_bytes(
        (json.dumps(manifest, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))
    return manifest


if __name__ == '__main__':
    result = materialize()
    print(json.dumps({'workspace_tree_sha256': result['workspace_tree_sha256'],
                      'workspace_file_count': result['workspace_file_count'],
                      'excluded_file_count': len(result['excluded_paths'])}, ensure_ascii=False))
