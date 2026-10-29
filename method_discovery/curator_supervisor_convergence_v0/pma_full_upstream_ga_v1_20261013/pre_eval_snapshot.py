"""Private GA-only filesystem checkpoint before the native verifier runs.

Docker commit retains only the Task container's writable layer on top of its
shared base image. It does not capture process state or mounted volumes and is
not a posthoc score. This module never runs a verifier or restarts a Task.
"""

from __future__ import annotations

import json
import re
import subprocess


class UnsafeSnapshot(RuntimeError):
    """The main container could not be restored to a safe running state."""


def _run(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(['docker', *args], capture_output=True, text=True,
                          timeout=timeout, check=True)


def _inspect(container_id: str) -> dict:
    rows = json.loads(_run('inspect', container_id, timeout=30).stdout)
    if len(rows) != 1 or rows[0].get('Id') != container_id:
        raise RuntimeError('main container identity unavailable')
    return rows[0]


def capture(*, run_id: str, task_id: str, container_id: str,
            source_image_id: str) -> dict:
    """Checkpoint one stopped-agent, still-running Task container privately.

    The caller establishes that all GA writers have stopped and that native
    verifier upload has not begun. A failed snapshot does not imply a failed
    Task; the caller records the failure separately. Unpause failure is fatal.
    """
    if not re.fullmatch(r'pma-[0-9a-f]{16}', run_id):
        raise ValueError('invalid run identity for private checkpoint')
    main = _inspect(container_id)
    if (main.get('Image') != source_image_id or
            main['State'].get('Running') is not True or
            main['State'].get('Paused') is True):
        raise RuntimeError('Task container changed before checkpoint')
    mounts = main.get('Mounts') or []
    # /app is part of the writable layer for these fixed Harbor tasks. A
    # mounted /app would be absent from docker commit and is not supported.
    if any(item.get('Destination') == '/app' or
           str(item.get('Destination', '')).startswith('/app/') for item in mounts):
        raise RuntimeError('mounted /app cannot be captured by image checkpoint')
    tag = 'ga-pre-eval:' + run_id
    existing = subprocess.run(['docker', 'image', 'inspect', tag],
                              capture_output=True, timeout=30, check=False)
    if existing.returncode == 0:
        raise RuntimeError('checkpoint tag already exists')
    try:
        committed = _run('commit', '--pause=true', container_id, tag,
                         timeout=1800).stdout.strip()
    except BaseException:
        # Docker normally unpauses after commit, including errors. Verify that
        # before allowing the caller to continue to native evaluation.
        after = _inspect(container_id)['State']
        if after.get('Running') is not True or after.get('Paused') is True:
            raise UnsafeSnapshot('main container state unsafe after failed commit')
        raise
    finally:
        after = _inspect(container_id)['State']
        if after.get('Running') is not True or after.get('Paused') is True:
            raise UnsafeSnapshot('main container state unsafe after checkpoint')
    image = json.loads(_run('image', 'inspect', tag, timeout=30).stdout)[0]
    image_id = image['Id']
    if committed != image_id or not re.fullmatch(r'sha256:[0-9a-f]{64}', image_id):
        raise RuntimeError('checkpoint image identity mismatch')
    return {'schema': 'ga-pre-evaluation-filesystem-checkpoint-v1',
            'run_id': run_id, 'task_id': task_id,
            'source_container_id': container_id,
            'source_image_id': source_image_id,
            'checkpoint_image_tag': tag, 'checkpoint_image_id': image_id,
            'filesystem_capture': 'docker_commit_writable_layer',
            'mounted_paths_excluded': sorted(item.get('Destination') for item in mounts),
            'process_state_captured': False,
            'native_evaluator_started': False,
            'local_private_only': True}
