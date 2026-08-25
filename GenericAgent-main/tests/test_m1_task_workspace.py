import json

from m1_task_workspace import PersistentTaskWorkspace


def test_bootstrap_preserves_immutable_public_task(tmp_path):
    workspace = PersistentTaskWorkspace(tmp_path, "Implement A and do not edit tests.")

    snapshot = workspace.view()
    assert snapshot["objects"][0]["id"] == "root:public-task"
    assert (tmp_path / "original_public_task.txt").read_text(encoding="utf-8") == (
        "Implement A and do not edit tests."
    )

    reloaded = PersistentTaskWorkspace(tmp_path, "Implement A and do not edit tests.")
    assert reloaded.public_task_sha256 == workspace.public_task_sha256


def test_different_task_does_not_restore_old_projection(tmp_path):
    first = PersistentTaskWorkspace(tmp_path, "Task A")
    first.apply_delta({"upsert": [{
        "id": "intent:one", "role": "local_intent", "summary": "edit A",
        "source_anchors": ["turn:1"], "root_links": ["root:public-task"],
    }], "deactivate": [], "relations": []}, turn=1, decision_index=1)

    second = PersistentTaskWorkspace(tmp_path, "Task B")
    assert "intent:one" not in {row["id"] for row in second.view()["objects"]}
    assert (tmp_path / "original_public_task.txt").read_text(encoding="utf-8") == "Task B"


def test_apply_open_semantic_delta_and_search(tmp_path):
    workspace = PersistentTaskWorkspace(tmp_path, "Implement A.")
    result = workspace.apply_delta({
        "upsert": [
            {"id": "intent:edit-a", "role": "local_intent", "summary": "Edit module A",
             "state": "active", "source_anchors": ["turn:2 response"],
             "root_links": ["root:public-task"]},
            {"id": "hypothesis:parser", "role": "causal_hypothesis",
             "summary": "Parser rejects the new syntax", "source_anchors": ["test output"],
             "root_links": ["root:public-task"]},
        ],
        "relations": [{"source": "intent:edit-a", "relation": "motivated_by",
                       "target": "hypothesis:parser", "summary": "stated diagnosis"}],
        "deactivate": [],
    }, turn=2, decision_index=1)

    assert result == {"applied": True, "upserted": 2, "deactivated": 0,
                      "relations": 1, "invalid": 0}
    assert workspace.search("parser")["matched"] == 1
    assert json.loads((tmp_path / "m1_workspace.json").read_text(encoding="utf-8"))
    event = json.loads((tmp_path / "m1_workspace_events.jsonl").read_text(encoding="utf-8"))
    assert event["decision_index"] == 1


def test_root_audit_projects_stable_obligations(tmp_path):
    workspace = PersistentTaskWorkspace(tmp_path, "Implement A and B.")
    changed = workspace.sync_root_obligations([
        {"obligation": "Implement A", "status": "supported",
         "public_evidence": ["tests/test_a.py:12"]},
        {"obligation": "Implement B", "status": "unknown", "public_evidence": []},
    ], turn=7, decision_index=2)
    workspace.apply_delta({}, turn=7, decision_index=2)

    obligations = [row for row in workspace.view()["objects"]
                   if row["role"] == "root_obligation"]
    assert {row["summary"]: row["state"] for row in obligations} == {
        "Implement A": "supported", "Implement B": "unknown",
    }
    assert all(row["root_links"] == ["root:public-task"] for row in obligations)
    assert changed == 2


def test_root_ledger_identity_is_frozen_across_paraphrases(tmp_path):
    workspace = PersistentTaskWorkspace(tmp_path, "Implement A and B.")
    workspace.sync_root_obligations([
        {"obligation": "Implement A", "status": "unknown", "public_evidence": []},
        {"obligation": "Implement B", "status": "unknown", "public_evidence": []},
    ], turn=1, decision_index=1)

    workspace.sync_root_obligations([
        {"obligation": "A is now implemented", "status": "supported",
         "public_evidence": ["turn 4 test"]},
        {"obligation": "B remains to be done", "status": "contested",
         "public_evidence": ["turn 5 diff"]},
    ], turn=5, decision_index=2)

    roots = sorted(
        (row for row in workspace.view()["objects"] if row["role"] == "root_obligation"),
        key=lambda row: row["source_order"],
    )
    assert [(row["id"], row["summary"], row["state"]) for row in roots] == [
        ("obligation:0000", "Implement A", "supported"),
        ("obligation:0001", "Implement B", "contested"),
    ]


def test_delta_cannot_create_root_obligations(tmp_path):
    workspace = PersistentTaskWorkspace(tmp_path, "Implement A.")
    workspace.sync_root_obligations([
        {"obligation": "Implement A", "status": "unknown", "public_evidence": []},
    ], turn=1, decision_index=1)

    result = workspace.apply_delta({
        "upsert": [{
            "id": "obligation:invented", "role": "root_obligation",
            "summary": "A temporary test must compile", "state": "unknown",
            "source_anchors": ["turn 2"], "root_links": ["root:public-task"],
        }],
        "deactivate": [], "relations": [],
    }, turn=2, decision_index=2)

    assert result["invalid"] == 1
    assert workspace.metrics()["root_obligations"] == 1
    assert workspace.metrics()["rejected_root_mutations"] == 1


def test_frozen_root_ledger_allows_audit_to_recover_an_omission(tmp_path):
    workspace = PersistentTaskWorkspace(tmp_path, "Implement A.")
    first = [{"obligation": "Implement A", "status": "unknown", "public_evidence": []}]
    workspace.sync_root_obligations(first, turn=1, decision_index=1)
    workspace.sync_root_obligations([
        *first,
        {"obligation": "Implement B", "status": "unknown",
         "public_evidence": []},
    ], turn=2, decision_index=2)

    roots = sorted(
        (row for row in workspace.view()["objects"] if row["role"] == "root_obligation"),
        key=lambda row: row["source_order"],
    )
    assert [(row["id"], row["summary"]) for row in roots] == [
        ("obligation:0000", "Implement A"),
        ("obligation:0001", "Implement B"),
    ]
    assert workspace.metrics()["rejected_root_mutations"] == 0


def test_active_view_is_bounded_and_keeps_root_ledger(tmp_path):
    workspace = PersistentTaskWorkspace(tmp_path, "Implement A and B.")
    workspace.sync_root_obligations([
        {"obligation": "Implement A", "status": "unknown", "public_evidence": []},
        {"obligation": "Implement B", "status": "unknown", "public_evidence": []},
    ], turn=1, decision_index=1)
    for index in range(20):
        workspace.apply_delta({
            "upsert": [{
                "id": f"evidence:{index}", "role": "public_evidence",
                "summary": f"Evidence {index}", "state": "active",
                "source_anchors": [f"turn:{index + 2}"],
                "root_links": ["obligation:0000"],
            }],
            "deactivate": [], "relations": [],
        }, turn=index + 2, decision_index=index + 2)

    active = workspace.active_view(object_limit=7)
    ids = {row["id"] for row in active["objects"]}
    assert {"root:public-task", "obligation:0000", "obligation:0001"} <= ids
    assert len(active["objects"]) == 7
    assert active["truncated"] is True


def test_invalid_delta_cannot_replace_root_or_create_dangling_relation(tmp_path):
    workspace = PersistentTaskWorkspace(tmp_path, "Root task")
    result = workspace.apply_delta({
        "upsert": [
            {"id": "root:public-task", "role": "other", "summary": "replacement"},
            {"id": "bad id", "role": "other", "summary": "bad"},
        ],
        "relations": [{"source": "missing", "relation": "supports",
                       "target": "root:public-task"}],
        "deactivate": ["root:public-task"],
    }, turn=3, decision_index=1)

    root = {row["id"]: row for row in workspace.view()["objects"]}["root:public-task"]
    assert root["role"] == "root_contract"
    assert result["invalid"] == 4


def test_unchanged_projection_does_not_create_false_updates(tmp_path):
    workspace = PersistentTaskWorkspace(tmp_path, "Implement A.")
    rows = [{"obligation": "Implement A", "status": "unknown", "public_evidence": []}]
    assert workspace.sync_root_obligations(rows, 1, 1) == 1
    assert workspace.sync_root_obligations(rows, 9, 2) == 0
    obligation = next(row for row in workspace.view()["objects"]
                      if row["role"] == "root_obligation")
    assert obligation["updated_turn"] == 1


def test_repair_episode_is_projected_then_deactivated(tmp_path):
    workspace = PersistentTaskWorkspace(tmp_path, "Implement A.")
    episode = {
        "opened_turn": 3,
        "original_discrepancy": "A was omitted",
        "current_residual": "A test still uses the wrong oracle",
        "current_exit_condition": "contract-faithful test passes",
    }
    assert workspace.sync_repair_episode(episode, turn=4, decision_index=2) == 1
    repair = next(row for row in workspace.view()["objects"]
                  if row["role"] == "repair_episode")
    assert repair["summary"] == "A test still uses the wrong oracle"
    assert workspace.sync_repair_episode(episode, turn=5, decision_index=3) == 0
    assert workspace.sync_repair_episode(None, turn=6, decision_index=4) == 1
    assert not [row for row in workspace.view()["objects"]
                if row["role"] == "repair_episode"]
