import json
import subprocess
import sys
import tarfile

import pytest

from adapters.failure_snapshot import snapshot_workspace


def test_complete_archive_contains_modified_new_hidden_and_binary_files(tmp_path):
    root = tmp_path / 'task'
    root.mkdir()
    (root / '.git').mkdir()
    (root / '.git/config').write_text('fixture')
    (root / 'test.py').write_text('assert True')
    (root / 'new.bin').write_bytes(b'\x00\xff')
    dest = tmp_path / 'archive'
    result = snapshot_workspace(root, dest)
    assert result['status'] == 'complete'
    with tarfile.open(dest / 'workspace.tar') as archive:
        assert archive.extractfile('test.py').read() == b'assert True'
        assert archive.extractfile('new.bin').read() == b'\x00\xff'
        assert archive.extractfile('.git/config').read() == b'fixture'
    with pytest.raises(FileExistsError):
        snapshot_workspace(root, dest)


@pytest.mark.parametrize('options', [{'max_bytes': 1}, {'seconds': 0}])
def test_budget_failure_is_explicit_and_partial_preserved(tmp_path, options):
    root = tmp_path / 'task'
    root.mkdir()
    (root / 'large').write_text('too large')
    dest = tmp_path / 'archive'
    result = snapshot_workspace(root, dest, **options)
    assert result['status'] == 'partial'
    assert not (dest / 'workspace.tar').exists()
    assert json.loads((dest / 'report.json').read_text())['status'] == 'partial'


def test_same_self_contained_code_runs_in_fresh_python(tmp_path):
    import inspect
    root = tmp_path / 'task'
    root.mkdir()
    (root / 'evidence').write_text('public')
    dest = tmp_path / 'archive'
    code = inspect.getsource(snapshot_workspace) + '\nimport sys\nsnapshot_workspace(*sys.argv[1:])'
    result = subprocess.run([sys.executable, '-c', code, str(root), str(dest)],
                            capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads((dest / 'report.json').read_text())['status'] == 'complete'


def test_destination_inside_source_rejected(tmp_path):
    with pytest.raises(ValueError):
        snapshot_workspace(tmp_path, tmp_path / 'recursive')


def test_failed_remote_archive_does_not_replace_original_cancellation():
    import asyncio
    from adapters.failure_snapshot import preserve_failed_workspace

    class Offline:
        async def exec(self, command, **kwargs):
            assert kwargs['timeout_sec'] == 60
            raise RuntimeError('container unavailable')

    metadata = {}
    result = asyncio.run(preserve_failed_workspace(Offline(), 'python', '/app', metadata))
    assert result['status'] == 'unavailable'
    assert metadata['failure_workspace_snapshot'] == result
