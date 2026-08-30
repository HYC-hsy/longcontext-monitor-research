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


def test_pre_identity_root_projection_is_archived_and_reset(tmp_path):
    workspace = PersistentTaskWorkspace(tmp_path, "Implement A and B.")
    workspace.sync_root_obligations([
        {"obligation": "Polluted paraphrase A", "status": "supported",
         "public_evidence": ["legacy evidence"]},
        {"obligation": "Polluted paraphrase B", "status": "unknown",
         "public_evidence": []},
    ], 1, 1)

    workspace.archive_and_reset_root_projection()

    assert not [
        row for row in workspace.view()["objects"]
        if row.get("role") == "root_obligation"
    ]
    assert workspace.root_ledger_frozen is False
    archive = tmp_path / "m1_workspace_pre_identity_migration.json"
    archived = json.loads(archive.read_text(encoding="utf-8"))
    assert sum(
        row.get("role") == "root_obligation" for row in archived["objects"]
    ) == 2


def test_workspace_crash_before_checkpoint_restores_write_ahead_backup(tmp_path):
    workspace = PersistentTaskWorkspace(tmp_path, "Implement A.")
    workspace.begin_transaction("decision:0001")
    workspace.apply_delta({
        "upsert": [{
            "id": "intent:uncommitted", "role": "local_intent",
            "summary": "uncommitted state", "source_anchors": ["turn:1"],
            "root_links": ["root:public-task"],
        }], "deactivate": [], "relations": [],
    }, turn=1, decision_index=1)

    restarted = PersistentTaskWorkspace(tmp_path, "Implement A.")
    assert restarted.recover_incomplete_transaction("decision:0000") is True
    assert "intent:uncommitted" not in restarted.objects
    assert not (tmp_path / "m1_workspace_transaction_backup.json").exists()


def test_workspace_crash_after_checkpoint_keeps_matching_transaction(tmp_path):
    workspace = PersistentTaskWorkspace(tmp_path, "Implement A.")
    workspace.begin_transaction("decision:0001")
    workspace.apply_delta({
        "upsert": [{
            "id": "intent:committed", "role": "local_intent",
            "summary": "committed state", "source_anchors": ["turn:1"],
            "root_links": ["root:public-task"],
        }], "deactivate": [], "relations": [],
    }, turn=1, decision_index=1)

    restarted = PersistentTaskWorkspace(tmp_path, "Implement A.")
    assert restarted.recover_incomplete_transaction("decision:0001") is False
    assert "intent:committed" in restarted.objects
    assert not (tmp_path / "m1_workspace_transaction_backup.json").exists()


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


def test_m2_versioning_preserves_replaced_semantics_and_evidence_scope(tmp_path):
    workspace = PersistentTaskWorkspace(
        tmp_path, "Implement A.", versioned_revision_enabled=True,
    )
    workspace.apply_delta({
        "upsert": [{
            "id": "evidence:a", "role": "public_evidence",
            "summary": "Test A passed against implementation v1", "state": "supported",
            "source_anchors": ["turn:3:test-a", "code:a@v1"],
            "root_links": ["root:public-task"],
        }], "deactivate": [], "relations": [],
    }, turn=3, decision_index=1)
    workspace.apply_delta({
        "upsert": [{
            "id": "evidence:a", "role": "public_evidence",
            "summary": "Implementation changed; old test scope is no longer current",
            "state": "unknown", "source_anchors": ["turn:8:patch-a", "code:a@v2"],
            "root_links": ["root:public-task"],
        }], "deactivate": [], "relations": [],
    }, turn=8, decision_index=2)

    current = workspace.get_object("evidence:a")
    assert current["object"]["object_version"] == 2
    assert current["object"]["state"] == "unknown"
    assert current["revision_history"][0]["previous"]["state"] == "supported"
    assert current["revision_history"][0]["previous"]["source_anchors"] == [
        "turn:3:test-a", "code:a@v1",
    ]
    assert workspace.metrics()["revision_count"] == 1
    assert "revision_history" not in workspace.active_view()

    restored = PersistentTaskWorkspace(
        tmp_path, "Implement A.", versioned_revision_enabled=True,
    )
    assert restored.get_object("evidence:a")["object"]["object_version"] == 2
    assert restored.metrics()["revision_count"] == 1


def test_m2_unchanged_update_does_not_invent_revision(tmp_path):
    workspace = PersistentTaskWorkspace(
        tmp_path, "Implement A.", versioned_revision_enabled=True,
    )
    delta = {"upsert": [{
        "id": "intent:a", "role": "local_intent", "summary": "Implement A",
        "state": "active", "source_anchors": ["turn:1"],
        "root_links": ["root:public-task"],
    }], "deactivate": [], "relations": []}
    workspace.apply_delta(delta, turn=1, decision_index=1)
    workspace.apply_delta(delta, turn=5, decision_index=2)

    assert workspace.get_object("intent:a")["object"]["object_version"] == 1
    assert workspace.get_object("intent:a")["revision_history"] == []


def test_m2b_withdrawn_evidence_invalidates_only_direct_supported_obligation(tmp_path):
    workspace = PersistentTaskWorkspace(
        tmp_path, "Implement A and B.", justification_invalidation_enabled=True,
    )
    workspace.sync_root_obligations([
        {"obligation": "Implement A", "status": "supported",
         "public_evidence": ["test:a passes"]},
        {"obligation": "Implement B", "status": "supported",
         "public_evidence": ["test:b passes"]},
    ], turn=1, decision_index=1)
    workspace.apply_delta({"upsert": [{
        "id": "evidence:a", "role": "public_evidence",
        "summary": "Focused test A passes.", "state": "observed",
        "source_anchors": ["test:a"], "root_links": ["obligation:0000"],
    }], "deactivate": [], "relations": [{
        "source": "evidence:a", "relation": "supports",
        "target": "obligation:0000", "summary": "Focused behavior A",
    }]}, turn=2, decision_index=2)

    result = workspace.apply_delta({"upsert": [{
        "id": "evidence:a", "role": "public_evidence",
        "summary": "The same focused test used the wrong oracle.",
        "state": "contested", "source_anchors": ["test:a review"],
        "root_links": ["obligation:0000"],
    }], "deactivate": [], "relations": []}, turn=3, decision_index=3)
    workspace.sync_root_obligations([
        {"obligation": "Implement A", "status": "supported",
         "public_evidence": ["stale test:a passes"]},
        {"obligation": "Implement B", "status": "supported",
         "public_evidence": ["test:b passes"]},
    ], turn=4, decision_index=4)

    assert result["dependency_invalidations"] == 1
    view = workspace.view()
    roots = {row["id"]: row for row in view["objects"]
             if row["role"] == "root_obligation"}
    assert roots["obligation:0000"]["state"] == "contested"
    assert roots["obligation:0001"]["state"] == "supported"
    assert len(view["pending_invalidations"]) == 1
    assert "revision_count" not in workspace.metrics()


def test_m2b_replacement_evidence_clears_pending_invalidation(tmp_path):
    workspace = PersistentTaskWorkspace(
        tmp_path, "Implement A.", justification_invalidation_enabled=True,
    )
    workspace.sync_root_obligations([
        {"obligation": "Implement A", "status": "supported",
         "public_evidence": ["old probe"]},
    ], turn=1, decision_index=1)
    workspace.apply_delta({"upsert": [{
        "id": "evidence:old", "role": "public_evidence", "summary": "Old probe",
        "state": "observed", "source_anchors": ["probe:old"],
        "root_links": ["obligation:0000"],
    }], "deactivate": [], "relations": [{
        "source": "evidence:old", "relation": "supports",
        "target": "obligation:0000", "summary": "Old support",
    }]}, turn=2, decision_index=2)
    workspace.apply_delta({"upsert": [], "deactivate": ["evidence:old"],
                           "relations": []}, turn=3, decision_index=3)
    result = workspace.apply_delta({"upsert": [{
        "id": "evidence:new", "role": "public_evidence", "summary": "New probe",
        "state": "observed", "source_anchors": ["probe:new"],
        "root_links": ["obligation:0000"],
    }], "deactivate": [], "relations": [{
        "source": "evidence:new", "relation": "revalidates",
        "target": "obligation:0000", "summary": "Replacement support",
    }]}, turn=4, decision_index=4)

    assert result["dependency_revalidations"] == 1
    assert workspace.metrics()["pending_invalidations"] == 0


def test_m2c_validated_semantic_impact_reopens_only_named_obligation(tmp_path):
    workspace = PersistentTaskWorkspace(
        tmp_path, "Implement A and B.", semantic_impact_enabled=True,
    )
    audit = [
        {"obligation": "Implement A", "status": "supported", "public_evidence": ["old:a"]},
        {"obligation": "Implement B", "status": "supported", "public_evidence": ["test:b"]},
    ]
    workspace.sync_root_obligations(audit, turn=1, decision_index=1)
    result = workspace.apply_delta({
        "upsert": [{
            "id": "evidence:a-changed", "role": "public_evidence",
            "summary": "Implementation A changed after its old test passed.",
            "state": "observed", "source_anchors": ["turn:4:diff-a"],
            "root_links": ["obligation:0000"],
        }],
        "deactivate": [],
        "relations": [{
            "source": "evidence:a-changed", "relation": "bears_on",
            "target": "obligation:0000", "summary": "Old support may be stale",
        }],
        "semantic_impacts": [{
            "target_id": "obligation:0000", "cause_id": "evidence:a-changed",
            "effect": "contest", "reason": "The old test predates the new implementation.",
            "public_anchors": ["Turn 4 implementation A diff"],
        }],
    }, turn=4, decision_index=2)
    workspace.sync_root_obligations(audit, turn=5, decision_index=3)

    roots = {row["id"]: row for row in workspace.view()["objects"]
             if row["role"] == "root_obligation"}
    assert result["semantic_impacts"] == 1
    assert result["rejected_semantic_impacts"] == 0
    assert roots["obligation:0000"]["state"] == "contested"
    assert roots["obligation:0001"]["state"] == "supported"
    assert workspace.metrics()["semantic_impact_count"] == 1
    assert "revision_count" not in workspace.metrics()

    repeated = workspace.apply_delta({
        "upsert": [], "deactivate": [], "relations": [],
        "semantic_impacts": [{
            "target_id": "obligation:0000", "cause_id": "evidence:a-changed",
            "effect": "contest", "reason": "The old test predates the new implementation.",
            "public_anchors": ["Turn 4 implementation A diff"],
        }],
    }, turn=6, decision_index=4)
    assert repeated["semantic_impacts"] == 0
    assert workspace.metrics()["semantic_impact_count"] == 1


def test_m2c_rejects_unanchored_or_unrelated_impact_and_cannot_complete(tmp_path):
    workspace = PersistentTaskWorkspace(
        tmp_path, "Implement A.", semantic_impact_enabled=True,
    )
    workspace.sync_root_obligations([
        {"obligation": "Implement A", "status": "unknown", "public_evidence": []},
    ], turn=1, decision_index=1)
    result = workspace.apply_delta({
        "upsert": [{
            "id": "evidence:other", "role": "public_evidence",
            "summary": "An unrelated file changed.", "state": "observed",
            "source_anchors": ["turn:2:other"], "root_links": ["root:public-task"],
        }],
        "deactivate": [], "relations": [],
        "semantic_impacts": [
            {"target_id": "obligation:0000", "cause_id": "evidence:other",
             "effect": "contest", "reason": "No local causal relation.",
             "public_anchors": ["turn:2:other"]},
            {"target_id": "obligation:0000", "cause_id": "evidence:other",
             "effect": "complete", "reason": "A proposal cannot establish completion.",
             "public_anchors": ["turn:2:other"]},
        ],
    }, turn=2, decision_index=2)

    assert result["semantic_impacts"] == 0
    assert result["rejected_semantic_impacts"] == 2
    assert workspace.metrics()["pending_semantic_impacts"] == 0


def test_m2c_revalidation_requires_new_anchored_public_evidence(tmp_path):
    workspace = PersistentTaskWorkspace(
        tmp_path, "Implement A.", semantic_impact_enabled=True,
    )
    workspace.sync_root_obligations([
        {"obligation": "Implement A", "status": "supported", "public_evidence": ["old"]},
    ], turn=1, decision_index=1)
    workspace.apply_delta({
        "upsert": [{"id": "evidence:change", "role": "public_evidence",
                    "summary": "A changed", "state": "observed",
                    "source_anchors": ["diff:a"], "root_links": ["obligation:0000"]}],
        "deactivate": [], "relations": [],
        "semantic_impacts": [{"target_id": "obligation:0000", "cause_id": "evidence:change",
                              "effect": "contest", "reason": "Old support is stale",
                              "public_anchors": ["diff:a"]}],
    }, turn=2, decision_index=2)
    result = workspace.apply_delta({
        "upsert": [{"id": "evidence:new-test", "role": "public_evidence",
                    "summary": "A new focused test passed", "state": "observed",
                    "source_anchors": ["test:a:new"], "root_links": ["obligation:0000"]}],
        "deactivate": [], "relations": [{"source": "evidence:new-test",
                                          "relation": "revalidates",
                                          "target": "obligation:0000",
                                          "summary": "Post-change evidence"}],
        "semantic_impacts": [{"target_id": "obligation:0000", "cause_id": "evidence:new-test",
                              "effect": "revalidate", "reason": "Post-change test supports A",
                              "public_anchors": ["test:a:new"]}],
    }, turn=3, decision_index=3)

    assert result["semantic_revalidations"] == 1
    assert workspace.metrics()["pending_semantic_impacts"] == 0


def test_m2_versions_only_changed_object_and_off_switch_hides_metadata(tmp_path):
    workspace = PersistentTaskWorkspace(
        tmp_path, "Implement A and B.", versioned_revision_enabled=True,
    )
    workspace.apply_delta({"upsert": [
        {"id": "intent:a", "role": "local_intent", "summary": "A v1",
         "source_anchors": ["turn:1"], "root_links": ["root:public-task"]},
        {"id": "intent:b", "role": "local_intent", "summary": "B v1",
         "source_anchors": ["turn:1"], "root_links": ["root:public-task"]},
    ], "deactivate": [], "relations": []}, turn=1, decision_index=1)
    workspace.apply_delta({"upsert": [
        {"id": "intent:a", "role": "local_intent", "summary": "A v2",
         "source_anchors": ["turn:2"], "root_links": ["root:public-task"]},
    ], "deactivate": [], "relations": []}, turn=2, decision_index=2)

    assert workspace.get_object("intent:a")["object"]["object_version"] == 2
    assert workspace.get_object("intent:b")["object"]["object_version"] == 1
    assert workspace.metrics()["revision_count"] == 1

    m1_view = PersistentTaskWorkspace(tmp_path, "Implement A and B.").view()
    assert "revision_history" not in m1_view
    assert all("object_version" not in row for row in m1_view["objects"])
