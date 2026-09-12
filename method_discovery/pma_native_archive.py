"""Snapshot public workspace before hidden evaluation changes it."""
import asyncio
import hashlib
from pathlib import Path, PurePosixPath
import shlex
import uuid


async def archive_workspace(environment, output, workspace='/app'):
    path = PurePosixPath(workspace)
    if not path.is_absolute() or str(path) == '/' or '..' in path.parts:
        raise ValueError('An explicit non-root absolute workspace is required')
    remote = '/tmp/pma-workspace-' + uuid.uuid4().hex + '.tar.gz'
    local = Path(output) / 'workspace.before-verifier.tar.gz'
    if local.exists():
        raise FileExistsError(local)
    command = ('tar -czf ' + shlex.quote(remote) + ' -C ' + shlex.quote(str(path)) + ' .')
    result = await environment.exec(command, timeout_sec=180)
    if result.return_code:
        raise RuntimeError('Public workspace archive failed')
    await asyncio.wait_for(environment.download_file(remote, local), timeout=180)
    # Streaming hash avoids loading a potentially large workspace into memory.
    with local.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'status': 'saved', 'workspace': str(path), 'path': local.name,
            'bytes': local.stat().st_size, 'sha256': digest,
            'boundary': 'agent stopped; before hidden verifier'}
