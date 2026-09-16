import hashlib
from pathlib import Path

import pytest

from monitor_agent_core.workspace import MonitorPathError, MonitorWorkspace


@pytest.fixture
def workspace(tmp_path):
    task = tmp_path / "task"
    private = tmp_path / "private"
    task.mkdir()
    (task / "task.txt").write_text("root contract\nsecond line\n", encoding="utf-8")
    (task / "src").mkdir()
    (task / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    return MonitorWorkspace(task, private), task, private


def test_read_supports_both_namespaces_and_returns_content_hash(workspace):
    ws, task, _ = workspace
    ws.write_text("monitor/notes.md", "private cognition")

    task_result = ws.read_text("task/task.txt", start=2, count=1)
    private_result = ws.read_text("monitor/notes.md")

    assert task_result["content"] == "second line\n"
    assert task_result["total_lines"] == 2
    assert task_result["sha256"] == hashlib.sha256((task / "task.txt").read_bytes()).hexdigest()
    assert private_result["content"] == "private cognition"


@pytest.mark.parametrize(
    "path",
    ["task/task.txt", "../task/task.txt", "monitor/../task/task.txt", "C:/Windows/system.ini"],
)
def test_writes_cannot_escape_private_namespace(workspace, path):
    ws, _, _ = workspace
    with pytest.raises(MonitorPathError):
        ws.write_text(path, "attempt")


def test_private_write_modes_and_exact_patch(workspace):
    ws, _, private = workspace
    ws.write_text("monitor/state/working.md", "middle")
    ws.write_text("monitor/state/working.md", "start-", mode="prepend")
    ws.write_text("monitor/state/working.md", "-end", mode="append")
    receipt = ws.patch_text("monitor/state/working.md", "middle", "updated")

    assert (private / "state" / "working.md").read_text(encoding="utf-8") == "start-updated-end"
    assert receipt["characters"] == len("start-updated-end")
    with pytest.raises(ValueError, match="exactly once"):
        ws.patch_text("monitor/state/working.md", "missing", "x")


def test_analysis_snapshot_is_disposable_and_does_not_follow_symlinks(workspace):
    ws, task, private = workspace
    external = task.parent / "secret.txt"
    external.write_text("secret", encoding="utf-8")
    link = task / "external-link.txt"
    try:
        link.symlink_to(external)
    except OSError:
        link = None

    snapshot = ws.refresh_snapshot()
    (snapshot / "src" / "app.py").write_text("VALUE = 99\n", encoding="utf-8")
    (snapshot / "scratch.txt").write_text("analysis", encoding="utf-8")

    assert (task / "src" / "app.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert not (task / "scratch.txt").exists()
    if link is not None:
        assert not (snapshot / "external-link.txt").exists()

    refreshed = ws.refresh_snapshot()
    assert (refreshed / "src" / "app.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert not (refreshed / "scratch.txt").exists()


def test_snapshot_directory_is_runtime_owned(workspace):
    ws, _, _ = workspace
    with pytest.raises(MonitorPathError, match="runtime-owned"):
        ws.write_text("monitor/.task_view/tamper.txt", "bad")


def test_named_task_mount_is_read_only_and_available_in_analysis_snapshot(tmp_path):
    evidence = tmp_path / "evidence"
    live_workspace = tmp_path / "live-workspace"
    evidence.mkdir()
    live_workspace.mkdir()
    (evidence / "original_task.txt").write_text("contract", encoding="utf-8")
    (live_workspace / "test_app.py").write_text("assert True", encoding="utf-8")
    ws = MonitorWorkspace(
        evidence, tmp_path / "private", task_mounts={"workspace": live_workspace}
    )

    assert ws.read_text("task/workspace/test_app.py")["content"] == "assert True"
    with pytest.raises(MonitorPathError):
        ws.write_text("task/workspace/test_app.py", "assert False")
    snapshot = ws.refresh_snapshot()
    assert (snapshot / "workspace" / "test_app.py").read_text(encoding="utf-8") == "assert True"
