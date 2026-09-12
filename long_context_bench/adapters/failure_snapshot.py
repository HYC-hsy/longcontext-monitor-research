"""Bounded, post-failure evidence preservation; no task correctness decisions."""

def snapshot_workspace(source, destination, max_bytes=512 * 1024 * 1024, seconds=45):
    # Self-contained so the identical tested function can execute inside the container.
    import json
    import os
    import stat
    import tarfile
    import time
    from pathlib import Path

    root = Path(source).resolve(strict=True)
    target = Path(destination).resolve()
    if not root.is_dir() or root == Path(root.anchor):
        raise ValueError('Snapshot source must be a specific task directory')
    if target == root or root in target.parents:
        raise ValueError('Snapshot destination must be outside the task directory')
    target.mkdir(parents=True, exist_ok=True)
    report_path = target / 'report.json'
    if report_path.exists():
        raise FileExistsError('Preserve existing failure snapshot')
    report = {'status': 'started', 'source': str(root), 'files': 0, 'payload_bytes': 0,
              'max_payload_bytes': max_bytes, 'seconds_limit': seconds,
              'consistency': 'best_effort_filesystem_copy_not_atomic', 'started_at': time.time()}

    def save():
        pending = target / 'report.pending'
        pending.write_text(json.dumps(report, ensure_ascii=False), encoding='utf-8')
        pending.replace(report_path)

    save()  # Even forced termination leaves an explicit unfinished marker.
    deadline = time.monotonic() + seconds

    def check():
        if time.monotonic() >= deadline:
            raise TimeoutError('Snapshot time budget exceeded')

    class TimedReader:
        def __init__(self, stream):
            self.stream = stream

        def read(self, size=-1):
            check()
            return self.stream.read(size)

    def walk_error(error):
        raise error

    partial = target / 'workspace.partial.tar'
    try:
        with tarfile.open(partial, 'w', dereference=False) as archive:
            for directory, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
                check()
                for name in sorted(dirs + files):
                    check()
                    path = Path(directory) / name
                    mode = path.lstat().st_mode
                    if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode) or stat.S_ISLNK(mode)):
                        raise ValueError('Special file not archived: ' + str(path.relative_to(root)))
                    info = archive.gettarinfo(str(path), arcname=path.relative_to(root).as_posix())
                    if report['payload_bytes'] + info.size > max_bytes:
                        raise ValueError('Snapshot payload budget exceeded at ' + info.name)
                    if info.isfile():
                        with path.open('rb') as stream:
                            archive.addfile(info, TimedReader(stream))
                        report['payload_bytes'] += info.size
                    else:
                        archive.addfile(info)
                    report['files'] += 1
        partial.replace(target / 'workspace.tar')
        report['status'] = 'complete'
        report['archive'] = 'workspace.tar'
    except Exception as exc:
        report.update(status='partial', error_type=type(exc).__name__, error=str(exc),
                      archive='workspace.partial.tar')
    report['finished_at'] = time.time()
    save()
    return report


def snapshot_command(python_bin, workspace):
    import inspect
    import shlex
    code = inspect.getsource(snapshot_workspace) + (
        '\nimport json, sys\nprint(json.dumps(snapshot_workspace(sys.argv[1], sys.argv[2])))')
    return ' '.join(shlex.quote(arg) for arg in [
        python_bin, '-c', code, workspace, '/logs/agent/failure_workspace'])


async def preserve_failed_workspace(environment, python_bin, workspace, metadata):
    import json
    status = {'status': 'unavailable'}
    try:
        result = await environment.exec(snapshot_command(python_bin, workspace),
                                        timeout_sec=60, user='root')
        if result.return_code:
            status['error'] = 'snapshot command exit ' + str(result.return_code)
        else:
            status = json.loads((result.stdout or '').strip())
            if not isinstance(status, dict):
                raise ValueError('Invalid snapshot report')
    except BaseException as exc:
        status = {'status': 'unavailable', 'error_type': type(exc).__name__}
    if metadata is not None:
        metadata['failure_workspace_snapshot'] = status
    return status
