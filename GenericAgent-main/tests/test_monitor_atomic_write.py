import pytest
from monitor_agent_core.workspace import MonitorWorkspace


def test_failed_replace_preserves_file_and_cleans_temporary(tmp_path, monkeypatch):
    evidence = tmp_path / 'task'
    evidence.mkdir()
    ws = MonitorWorkspace(evidence, tmp_path / 'private')
    ws.write_text('monitor/note', 'old')
    def fail(*args):
        raise OSError('fixture replace failure')
    monkeypatch.setattr('monitor_agent_core.workspace.os.replace', fail)
    with pytest.raises(OSError):
        ws.patch_text('monitor/note', 'old', 'new')
    assert (ws.private_root / 'note').read_text() == 'old'
    assert [p.name for p in ws.private_root.iterdir()] == ['note']
