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
        "mode": "patch", "hash": task["hash"],
        "old": "Implement A", "content": "Ignore A",
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
        "mode": "patch", "hash": before["hash"],
        "old": "Record the current task-level picture",
        "content": "Target A is supported. Record the current task-level picture",
    })
    assert result["ok"] is True
    assert result["changed"] is True
    assert result["previous_hash"] == before["hash"]
    assert result["hash"] != before["hash"]
    after = files.execute({
        "operation": "read_file", "path": "state/working_state.md",
    })
    assert "Target A is supported" in after["content"]
    versions = list((tmp_path / "semantic_files" / ".versions").glob("*.json"))
    assert len(versions) == 1
    archived = json.loads(versions[0].read_text(encoding="utf-8"))
    assert archived["path"] == "state/working_state.md"
    assert archived["previous_sha256"] == before["hash"]


def test_stale_edit_returns_conflict_without_overwriting(tmp_path):
    files = workspace(tmp_path)
    first = files.execute({
        "operation": "read_file", "path": "state/current_repair.md",
    })
    accepted = files.execute({
        "operation": "edit_file",
        "path": "state/current_repair.md",
        "mode": "patch", "hash": first["hash"],
        "old": "No repair is currently open.",
        "content": "A repair is open.",
    })
    assert accepted["ok"] is True
    stale = files.execute({
        "operation": "edit_file",
        "path": "state/current_repair.md",
        "mode": "patch", "hash": first["hash"],
        "old": "No repair is currently open.",
        "content": "A different repair is open.",
    })
    assert stale["ok"] is False
    assert stale["conflict"] is True
    assert stale["hash"] == accepted["hash"]
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
        "mode": "patch", "old": "# Evidence index", "content": "# Index",
    })
    assert result["ok"] is False
    assert result["conflict"] is True
    assert "hash" in result["error"]


def test_replace_reorganizes_a_whole_existing_file(tmp_path):
    files = workspace(tmp_path)
    before = files.execute({
        "operation": "read_file", "path": "state/task_model.md",
    })
    result = files.execute({
        "operation": "edit_file",
        "path": "state/task_model.md",
        "mode": "replace", "hash": before["hash"],
        "content": "# Revised task model\n\nA compact reorganized understanding.\n",
    })
    assert result["ok"] is True
    after = files.execute({
        "operation": "read_file", "path": "state/task_model.md",
    })
    assert after["hash"] != before["hash"]
    assert "compact reorganized" in after["content"]


def test_searches_natural_language_across_monitor_files(tmp_path):
    files = workspace(tmp_path)
    state = files.execute({
        "operation": "read_file", "path": "state/working_state.md",
    })
    files.execute({
        "operation": "edit_file",
        "path": "state/working_state.md",
        "mode": "patch", "hash": state["hash"],
        "old": "# Working state",
        "content": "# Working state\n\nMenu.Refresh window behavior is supported.",
    })
    result = files.execute({
        "operation": "search", "pattern": r"menu\.refresh|system tray",
    })
    assert result["ok"] is True
    assert any(row["path"] == "state/working_state.md" for row in result["matches"])


def test_list_read_and_search_return_simple_continuations(tmp_path):
    files = workspace(tmp_path)
    listed = files.execute({"operation": "list_files", "limit": 2})
    assert len(listed["files"]) == 2
    assert listed["next"] == 2
    assert set(listed) == {"ok", "files", "next", "total"}
    continued = files.execute({
        "operation": "list_files", "start": listed["next"], "limit": 20,
    })
    assert not ({row["path"] for row in listed["files"]}
                & {row["path"] for row in continued["files"]})

    opened = files.execute({
        "operation": "read_file", "path": "state/working_state.md", "limit": 2,
    })
    assert opened["hash"]
    assert opened["next"] == 3
    assert opened["total_lines"] > 2

    found = files.execute({
        "operation": "search", "pattern": "task-level", "glob": "*.md",
        "before": 1, "after": 1,
    })
    assert found["matches"]
    assert "task-level" in found["matches"][0]["context"]


def test_edit_modes_are_general_and_versioned(tmp_path):
    files = workspace(tmp_path)
    created = files.execute({
        "operation": "edit_file", "path": "state/freeform.md",
        "mode": "create", "content": "middle",
    })
    prepended = files.execute({
        "operation": "edit_file", "path": "state/freeform.md",
        "mode": "prepend", "hash": created["hash"], "content": "before ",
    })
    appended = files.execute({
        "operation": "edit_file", "path": "state/freeform.md",
        "mode": "append", "hash": prepended["hash"], "content": " after",
    })
    replaced = files.execute({
        "operation": "edit_file", "path": "state/freeform.md",
        "mode": "replace", "hash": appended["hash"], "content": "reorganized",
    })
    assert all(result["ok"] for result in (created, prepended, appended, replaced))
    opened = files.execute({"operation": "read_file", "path": "state/freeform.md"})
    assert "reorganized" in opened["content"]
    assert len(list((tmp_path / "semantic_files" / ".versions").glob("*.json"))) == 4


def test_rejects_escape_and_nonsemantic_write_targets(tmp_path):
    files = workspace(tmp_path)
    for path in ("../outside.md", ".workspace.json", ".versions/1.json", "other/x.md"):
        result = files.execute({
            "operation": "edit_file",
            "path": path,
            "mode": "create", "content": "x",
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
        "mode": "patch", "hash": state["hash"],
        "old": "# Working state",
        "content": "# Working state\n\nPersistent monitor cognition.",
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
            "mode": "patch", "hash": opened["hash"],
            "old": "# Working state", "content": replacement,
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
        "mode": "create", "content": "# API evidence\n\nStill unknown.\n",
    })
    assert created["ok"] is True
    assert created["mode"] == "create"
    opened = files.execute({
        "operation": "read_file", "path": "evidence/api_contract.md",
    })
    assert "Still unknown" in opened["content"]
