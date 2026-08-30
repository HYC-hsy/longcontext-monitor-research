import json
import threading

from monitor_semantic_files import MonitorSemanticFiles


def workspace(tmp_path):
    return MonitorSemanticFiles(tmp_path, "Implement A and preserve B.")


def test_initializes_read_only_task_and_free_semantic_files(tmp_path):
    files = workspace(tmp_path)
    listed = files.execute({"operation": "list_files"})
    paths = {row["path"] for row in listed["files"]}
    assert "task/original_task.md" in paths
    assert "state/task_model.md" in paths
    assert "state/working_state.md" in paths
    assert "state/current_repair.md" in paths
    assert "evidence/index.md" in paths
    task = files.execute({
        "operation": "read_file", "path": "task/original_task.md",
    })
    assert task["ok"] is True
    assert "Implement A" in task["content"]
    rejected = files.execute({
        "operation": "edit_file",
        "path": "task/original_task.md",
        "expected_sha256": task["sha256"],
        "edits": [{"old_text": "Implement A", "new_text": "Ignore A"}],
    })
    assert rejected["ok"] is False
    assert "read-only" in rejected["error"]


def test_exact_edit_returns_receipt_and_archives_previous_version(tmp_path):
    files = workspace(tmp_path)
    before = files.execute({
        "operation": "read_file", "path": "state/working_state.md",
    })
    result = files.execute({
        "operation": "edit_file",
        "path": "state/working_state.md",
        "expected_sha256": before["sha256"],
        "edits": [{
            "old_text": "Record the current task-level picture",
            "new_text": "Target A is supported. Record the current task-level picture",
        }],
    })
    assert result["ok"] is True
    assert result["changed"] is True
    assert result["previous_sha256"] == before["sha256"]
    assert result["sha256"] != before["sha256"]
    after = files.execute({
        "operation": "read_file", "path": "state/working_state.md",
    })
    assert "Target A is supported" in after["content"]
    versions = list((tmp_path / "semantic_files" / ".versions").glob("*.json"))
    assert len(versions) == 1
    archived = json.loads(versions[0].read_text(encoding="utf-8"))
    assert archived["path"] == "state/working_state.md"
    assert archived["previous_sha256"] == before["sha256"]


def test_stale_edit_returns_conflict_without_overwriting(tmp_path):
    files = workspace(tmp_path)
    first = files.execute({
        "operation": "read_file", "path": "state/current_repair.md",
    })
    accepted = files.execute({
        "operation": "edit_file",
        "path": "state/current_repair.md",
        "expected_sha256": first["sha256"],
        "edits": [{
            "old_text": "No repair is currently open.",
            "new_text": "A repair is open.",
        }],
    })
    assert accepted["ok"] is True
    stale = files.execute({
        "operation": "edit_file",
        "path": "state/current_repair.md",
        "expected_sha256": first["sha256"],
        "edits": [{
            "old_text": "No repair is currently open.",
            "new_text": "A different repair is open.",
        }],
    })
    assert stale["ok"] is False
    assert stale["conflict"] is True
    assert stale["current_sha256"] == accepted["sha256"]
    current = files.execute({
        "operation": "read_file", "path": "state/current_repair.md",
    })
    assert "A repair is open" in current["content"]
    assert "different repair" not in current["content"]


def test_edit_requires_read_receipt_for_existing_file(tmp_path):
    files = workspace(tmp_path)
    result = files.execute({
        "operation": "edit_file",
        "path": "evidence/index.md",
        "edits": [{"old_text": "# Evidence index", "new_text": "# Index"}],
    })
    assert result["ok"] is False
    assert result["conflict"] is True
    assert "expected_sha256" in result["error"]


def test_edit_is_all_or_nothing_within_one_file(tmp_path):
    files = workspace(tmp_path)
    before = files.execute({
        "operation": "read_file", "path": "state/task_model.md",
    })
    result = files.execute({
        "operation": "edit_file",
        "path": "state/task_model.md",
        "expected_sha256": before["sha256"],
        "edits": [
            {"old_text": "# Task model", "new_text": "# Revised task model"},
            {"old_text": "text that does not exist", "new_text": "replacement"},
        ],
    })
    assert result["ok"] is False
    after = files.execute({
        "operation": "read_file", "path": "state/task_model.md",
    })
    assert after["sha256"] == before["sha256"]
    assert "# Task model" in after["content"]


def test_searches_natural_language_across_monitor_files(tmp_path):
    files = workspace(tmp_path)
    state = files.execute({
        "operation": "read_file", "path": "state/working_state.md",
    })
    files.execute({
        "operation": "edit_file",
        "path": "state/working_state.md",
        "expected_sha256": state["sha256"],
        "edits": [{
            "old_text": "# Working state",
            "new_text": "# Working state\n\nMenu.Refresh window behavior is supported.",
        }],
    })
    result = files.execute({
        "operation": "search", "pattern": r"menu\.refresh|system tray",
    })
    assert result["ok"] is True
    assert any(row["path"] == "state/working_state.md" for row in result["matches"])


def test_rejects_escape_and_nonsemantic_write_targets(tmp_path):
    files = workspace(tmp_path)
    for path in ("../outside.md", ".workspace.json", ".versions/1.json", "other/x.md"):
        result = files.execute({
            "operation": "edit_file",
            "path": path,
            "edits": [{"old_text": "x", "new_text": "y"}],
        })
        assert result["ok"] is False


def test_reopening_same_task_preserves_model_authored_state(tmp_path):
    first = workspace(tmp_path)
    state = first.execute({
        "operation": "read_file", "path": "state/working_state.md",
    })
    first.execute({
        "operation": "edit_file",
        "path": "state/working_state.md",
        "expected_sha256": state["sha256"],
        "edits": [{
            "old_text": "# Working state",
            "new_text": "# Working state\n\nPersistent monitor cognition.",
        }],
    })
    restored = workspace(tmp_path)
    current = restored.execute({
        "operation": "read_file", "path": "state/working_state.md",
    })
    assert "Persistent monitor cognition" in current["content"]


def test_rejects_artifact_reuse_for_different_task(tmp_path):
    workspace(tmp_path)
    try:
        MonitorSemanticFiles(tmp_path, "A different public task")
    except ValueError as error:
        assert "different public task" in str(error)
    else:
        raise AssertionError("different task must not inherit semantic cognition")


def test_turn_zero_audit_seeds_natural_task_model_only_once(tmp_path):
    files = workspace(tmp_path)
    result = files.initialize_task_model(
        "Implement A and preserve B. Both remain unresolved until public evidence exists."
    )
    assert result["ok"] is True
    assert result["changed"] is True
    model = files.execute({"operation": "read_file", "path": "state/task_model.md"})
    assert "Implement A and preserve B" in model["content"]
    repeated = files.initialize_task_model("replacement that must not overwrite cognition")
    assert repeated == {"ok": True, "changed": False, "reason": "already_initialized"}


def test_independent_worker_instances_cannot_both_commit_same_read(tmp_path):
    first = workspace(tmp_path)
    second = workspace(tmp_path)
    opened = first.execute({
        "operation": "read_file", "path": "state/working_state.md",
    })
    barrier = threading.Barrier(2)
    results = []

    def edit(files, replacement):
        barrier.wait()
        results.append(files.execute({
            "operation": "edit_file",
            "path": "state/working_state.md",
            "expected_sha256": opened["sha256"],
            "edits": [{"old_text": "# Working state", "new_text": replacement}],
        }))

    threads = [
        threading.Thread(target=edit, args=(first, "# Worker one")),
        threading.Thread(target=edit, args=(second, "# Worker two")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(result["ok"] for result in results) == 1
    assert sum(bool(result.get("conflict")) for result in results) == 1


def test_edit_file_can_create_one_new_natural_language_file(tmp_path):
    files = workspace(tmp_path)
    created = files.execute({
        "operation": "edit_file",
        "path": "evidence/api_contract.md",
        "edits": [{"old_text": "", "new_text": "# API evidence\n\nStill unknown.\n"}],
    })
    assert created["ok"] is True
    assert created["edits"][0]["created"] is True
    opened = files.execute({
        "operation": "read_file", "path": "evidence/api_contract.md",
    })
    assert "Still unknown" in opened["content"]
