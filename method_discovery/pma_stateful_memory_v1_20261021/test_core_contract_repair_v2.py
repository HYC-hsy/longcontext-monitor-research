"""Audit counterexamples for the fixed v1 contract; fake-only."""

from copy import deepcopy
import json
import tempfile
import unittest
from pathlib import Path

from .audit import AuditCodec, validate_audit_result
from .engine import CycleEngine
from .proposal import build_candidate, validate_proposal
from .reminder import render_reminder
from .schema import validate_snapshot
from .source import ContractError, SourceCatalog, digest
from .store import MemoryStore
from .test_contracts import empty_snapshot, leaf
from . import test_engine as engine_fixtures
from .test_schema_advanced import rich_state


class CoreContractRepairTests(unittest.TestCase):
    def test_requirement_history_through_candidate_audit_commit(self):
        with tempfile.TemporaryDirectory() as root:
            store = MemoryStore(Path(root) / "history.sqlite3")
            try:
                store.initialize(empty_snapshot(), leaf("task"))
                base = store.snapshot()
                catalog = SourceCatalog(store.sources(), "w1")
                source = catalog.add("u0", 0, 4, "maintenance")
                proposal = {"protocol": "maintenance-proposal/1", "request_id": "r1",
                    "active_task_version": 1, "base_state_version": 0,
                    "world_patch": {"entity_upserts": [], "state_upserts": [],
                        "relation_upserts": [], "record_transitions": []},
                    "specification_upserts": [{"requirement_id": "@requirement",
                        "revision": 1, "task_version": 1, "interpretation": "original task",
                        "source_refs": [{"evidence_id": source.evidence_id,
                            "quote": "task"}], "status": "active", "retirement": None}],
                    "gap_upserts": [{"gap_id": "@gap", "revision": 1,
                        "task_version": 1, "gap_kind": "achievement",
                        "target": "finish task", "reason": "pending",
                        "goal_refs": [{"type": "requirement", "requirement_id": "@requirement",
                            "revision": 1, "task_version": 1}], "record_refs": [],
                        "status": "open", "closure": None}],
                    "gap_resolutions": [], "gap_reopens": [], "focus": {"op": "keep"}}
                first = build_candidate(proposal=proposal, base=base, catalog=catalog,
                    cycle_id="c1", processed_to=0, goal_ledger=store.goals(),
                    visible_existing_ids=set(), archive=store.archive())
                self._audit_clean(base, first["candidate"], catalog)
                store.compare_and_swap(update_id=first["update_id"], cycle_id="c1",
                    base=base, candidate=first["candidate"],
                    archive_delta=first["archive_delta"])
                before = store.snapshot()
                requirement = before["B"]["G"]["specifications"][0]
                gap = before["B"]["DeltaA"][0]
                user = leaf("revised task", source_id="u1")
                user.update(event_id="user-2", event_seq=1, ga_turn=1)
                store.append_event({"event_id": "user-2", "event_seq": 1,
                    "kind": "user_message", "occurred_at_step": 1,
                    "source_ids": ["u1"], "payload": {}}, [user])
                goals = store.goals()
                delta = goals["deltas"]["goal-delta-2"]
                catalog2 = SourceCatalog(store.sources(), "w2")
                user_span = catalog2.add("u1", 0, len(user["text"]), "maintenance")
                second = deepcopy(proposal)
                second["request_id"] = "r2"
                second["active_task_version"] = 2
                second["base_state_version"] = 1
                second["specification_upserts"] = [{**requirement,
                    "revision": 2, "task_version": 2,
                    "interpretation": "revised task", "source_refs": [{
                        "evidence_id": user_span.evidence_id, "quote": user["text"]}]}]
                second["gap_upserts"] = []
                second["gap_resolutions"] = [{**gap, "revision": 2,
                    "status": "superseded", "closure": {"kind": "goal_changed",
                        "goal_delta_ref": delta}}]
                built = build_candidate(proposal=second, base=before,
                    catalog=catalog2, cycle_id="c2", processed_to=1,
                    goal_ledger=goals, visible_existing_ids={
                        ("requirement", requirement["requirement_id"]),
                        ("gap", gap["gap_id"])}, archive=store.archive())
                self._audit_clean(before, built["candidate"], catalog2)
                store.compare_and_swap(update_id=built["update_id"], cycle_id="c2",
                    base=before, candidate=built["candidate"],
                    archive_delta=built["archive_delta"])
                historical = store.archive()[("requirement", requirement[
                    "requirement_id"], 1)]
                self.assertEqual(historical["interpretation"], "original task")
                closed = store.snapshot()["B"]["DeltaA"][0]
                self.assertEqual(closed["goal_refs"][0]["revision"], 1)
                bad = deepcopy(store.snapshot())
                bad["B"]["DeltaA"][0]["status"] = "open"
                bad["B"]["DeltaA"][0]["closure"] = None
                bad["B"]["DeltaA"][0]["task_version"] = 2
                with self.assertRaisesRegex(ContractError, "version_mismatch"):
                    validate_snapshot(bad, store.sources(), store.archive(),
                                      store.goals()["deltas"])
            finally:
                store.close()

    @staticmethod
    def _audit_clean(before, candidate, catalog):
        old_gaps = {item["gap_id"]: item for item in before["B"]["DeltaE"] +
                    before["B"]["DeltaA"]}
        resolved = [item for item in candidate["B"]["DeltaE"] + candidate["B"]["DeltaA"]
                    if item["status"] in {"supported", "superseded"} and
                    old_gaps.get(item["gap_id"], {}).get("status") in {"open", "blocked"}]
        manifest = [{"resolution_id": item["gap_id"],
            "gap_before": old_gaps[item["gap_id"]], "gap_after": item,
            "closure_kind": item["closure"]["kind"]} for item in resolved]
        view = AuditCodec().encode(before, candidate, binding={"cycle_id": "offline"},
            sources=[], observations={"events": []}, operation_index=[],
            resolve_manifest=manifest)
        response = {"protocol": "audit-result/1", "binding": view["binding"],
            "coverage": view["required_coverage"], "outcome": "clean", "issues": [],
            "closure_assessments": [{"resolution_id": item["gap_id"],
                "gap_before": {"type": "gap", "gap_id": item["gap_id"],
                    "revision": old_gaps[item["gap_id"]]["revision"],
                    "task_version": old_gaps[item["gap_id"]]["task_version"]},
                "gap_after": {"type": "gap", "gap_id": item["gap_id"],
                    "revision": item["revision"], "task_version": item["task_version"]},
                "closure_kind": item["closure"]["kind"], "verdict": "supported",
                "assessed_scope": {}, "explanation": "synthetic accepted delta",
                "basis_refs": [item["closure"]["goal_delta_ref"]],
                "blocking_issue_ids": []} for item in resolved],
            "unusable_reason": None}
        validate_audit_result(response, view=view, catalog=catalog)

    def test_lesson_cannot_claim_tool_observation(self):
        snap, ledger = rich_state()
        state = snap["B"]["W"]["states"][0]
        state.pop("claim")
        state["kind"] = "procedural"
        state["episode"] = {"conditions": {"text": "feature absent",
            "assertion_origin": "tool_observation", "time_role": "past_episode",
            "support_refs": [{"source_id": "tool", "start": 0, "end": 14,
                              "quote": "feature absent"}], "challenge_refs": []},
            "action_text": "check feature", "action_refs": [],
            "result": {"text": "feature absent", "assertion_origin": "tool_observation",
                "time_role": "past_episode", "support_refs": [{"source_id": "tool",
                    "start": 0, "end": 14, "quote": "feature absent"}],
                "challenge_refs": []}, "time_role": "past_episode"}
        action = leaf("check feature", source_id="action", source_kind="executed_action")
        ledger["action"] = action
        state["episode"]["action_refs"] = [{"source_id": "action", "start": 0,
            "end": 13, "quote": "check feature"}]
        state["lesson"] = {"text": "feature absent", "assertion_origin": "tool_observation",
            "time_role": "present_fact", "support_refs": [{"source_id": "tool",
                "start": 0, "end": 14, "quote": "feature absent"}], "challenge_refs": []}
        with self.assertRaisesRegex(ContractError, "lesson_"):
            validate_snapshot(snap, ledger)

    def test_transition_cannot_restore_active(self):
        base = empty_snapshot()
        proposal = {"protocol": "maintenance-proposal/1", "request_id": "req",
            "active_task_version": 1, "base_state_version": 0,
            "world_patch": {"entity_upserts": [], "state_upserts": [],
                "relation_upserts": [], "record_transitions": [{"record_ref": {
                    "type": "state", "record_id": "s", "revision": 1},
                    "to_status": "active", "reason": "wrong", "evidence_refs": []}]},
            "specification_upserts": [], "gap_upserts": [], "gap_resolutions": [],
            "gap_reopens": [], "focus": {"op": "keep"}}
        with self.assertRaisesRegex(ContractError, "transition_status"):
            validate_proposal(proposal, request_id="req", task_version=1, base_version=0)

    def test_historical_knowledge_is_not_current_anchor(self):
        snap, _ = rich_state()
        snap["B"]["W"]["states"][0]["claim"]["time_role"] = "past_episode"
        decision = {"decision": "remind", "state_version": 1,
            "task_version": 1, "phase2_view_id": "v", "refs": [{"type": "state",
                "record_id": "s", "revision": 1}], "context_for_action": "consider"}
        anchor = render_reminder(decision, snapshot=snap, cycle_id="c",
            commit_id="k", reviewed_refs=[])["anchors"][0]
        self.assertEqual(anchor["render_mode"], "historical_record")
        self.assertEqual(anchor["use_status"], "active")

    def test_maintenance_has_goal_ledger(self):
        fixture = engine_fixtures.EngineTests("test_clean_commit_silent_and_same_trigger_idempotence")
        fixture.setUp()
        try:
            provider = engine_fixtures.ScriptedProvider()
            CycleEngine(fixture.store, provider, task_text="task").run("v2-goals")
            sent = json.loads(provider.calls[0]["messages"][1]["content"])
            self.assertEqual(sent["goal_ledger"]["epoch"], 1)
        finally:
            fixture.tearDown()

    def test_maintenance_catalog_carries_action_context(self):
        fixture = engine_fixtures.EngineTests("test_clean_commit_silent_and_same_trigger_idempotence")
        fixture.setUp()
        try:
            provider = engine_fixtures.ScriptedProvider(create_state=True)
            CycleEngine(fixture.store, provider, task_text="task").run("v2-first")
            fixture.store.append_event(*engine_fixtures.event(2, "next result"))
            provider2 = engine_fixtures.ScriptedProvider()
            CycleEngine(fixture.store, provider2, task_text="task").run("v2-second")
            sent = json.loads(provider2.calls[0]["messages"][1]["content"])
            self.assertTrue(any(item.get("executed_actions") for item in
                sent["source_catalog"] if item["source_kind"] == "tool_result"))
            for role in ("maintenance", "audit", "selection"):
                request = next(call for call in provider2.calls if call["role"] == role)
                payload = json.loads(request["messages"][1]["content"])
                results = [item for item in payload["source_catalog"] if item[
                    "source_kind"] == "tool_result" and item["source_id"] == "tool-1"]
                self.assertTrue(results, role)
                self.assertEqual(results[0]["executed_actions"][0]["source_id"],
                                 "action-1")
                self.assertEqual(results[0]["executed_actions"][0][
                    "result_source_id"], "tool-1")
                self.assertTrue(any(item["source_id"] == "action-1" for item in
                    payload["source_catalog"]))
        finally:
            fixture.tearDown()

    def test_multi_tool_historical_context_keeps_pairing_and_truncation(self):
        with tempfile.TemporaryDirectory() as root:
            store = MemoryStore(Path(root) / "multi.sqlite3")
            try:
                store.initialize(empty_snapshot(), leaf("task"))
                first, leaves = engine_fixtures.event(1)
                action = leaf("echo tests passed", source_id="action-extra",
                              source_kind="executed_action")
                action.update(event_id="tool-call-extra", event_seq=1, ga_turn=1,
                              field_path="actions.1.arguments")
                output = leaf("tests passed", source_id="tool-extra",
                              source_kind="tool_result")
                output.update(event_id="tool-call-extra", event_seq=1, ga_turn=1,
                              field_path="tool_results.1.result.content",
                              truncated=True)
                first["source_ids"].extend([action["source_id"], output["source_id"]])
                first["payload"]["actions"].append({"tool_use_id": "tool-call-extra"})
                store.append_event(first, leaves + [action, output])
                inner = engine_fixtures.ScriptedProvider(create_state=True)
                def provider(role, messages, call_id, max_output):
                    answer = inner(role, messages, call_id, max_output)
                    if role != "maintenance":
                        return answer
                    content = json.loads(messages[1]["content"])
                    second = next(item for item in content["source_catalog"] if
                        item["source_id"] == "tool-extra" and item["purpose"] ==
                        "maintenance")
                    parsed = json.loads(answer)
                    parsed["world_patch"]["state_upserts"][0]["claim"][
                        "support_refs"].append({"evidence_id": second["evidence_id"],
                                                "quote": "tests passed"})
                    return json.dumps(parsed)
                first_result = CycleEngine(store, provider, task_text="task").run("multi-1")
                self.assertEqual(first_result["status"], "committed_selection_silent")
                store.append_event(*engine_fixtures.event(2, "later observation"))
                later = engine_fixtures.ScriptedProvider()
                result = CycleEngine(store, later, task_text="task").run("multi-2")
                self.assertEqual(result["status"], "committed_selection_silent")
                for call in later.calls:
                    payload = json.loads(call["messages"][1]["content"])
                    catalog = payload["source_catalog"]
                    for source_id, action_id in (("tool-1", "action-1"),
                                                 ("tool-extra", "action-extra")):
                        historical = next(item for item in catalog if item[
                            "source_id"] == source_id)
                        self.assertEqual(historical["executed_actions"][0][
                            "source_id"], action_id)
                        self.assertEqual(historical["executed_actions"][0][
                            "event_id"], historical["event_id"])
                    self.assertTrue(next(item for item in catalog if item[
                        "source_id"] == "tool-extra")["truncated"])
            finally:
                store.close()

    def test_goal_context_visible_without_advancing_pending_frontier(self):
        fixture = engine_fixtures.EngineTests("test_clean_commit_silent_and_same_trigger_idempotence")
        fixture.setUp()
        try:
            fixture.store.append_event(*engine_fixtures.event(2, "huge " * 40000))
            user = leaf("revised task", source_id="u1")
            user.update(event_id="user-3", event_seq=3, ga_turn=3)
            fixture.store.append_event({"event_id": "user-3", "event_seq": 3,
                "kind": "user_message", "occurred_at_step": 3,
                "source_ids": ["u1"], "payload": {}}, [user])
            provider = engine_fixtures.ScriptedProvider()
            result = CycleEngine(fixture.store, provider, task_text="task").run(
                "partial-with-new-goal")
            self.assertEqual(result["status"], "committed_backlog_pending")
            self.assertEqual(result["commit"]["event_seq"], 1)
            self.assertEqual(result["logical_calls"], 2)
            maintenance = json.loads(provider.calls[0]["messages"][1]["content"])
            audit = json.loads(provider.calls[1]["messages"][1]["content"])
            self.assertEqual(maintenance["goal_ledger"], audit["goal_ledger"])
            self.assertEqual(maintenance["goal_ledger"]["epoch"], 2)
            self.assertFalse(maintenance["goal_ledger"]["messages"][-1][
                "within_processing_prefix"])
            self.assertEqual(maintenance["goal_ledger"]["messages"][-1]["text"],
                             "revised task")
            self.assertTrue(any(item["source_id"] == "u1" for item in
                audit["source_catalog"]))
        finally:
            fixture.tearDown()

    def test_preselection_failure_counts_no_phantom_call(self):
        fixture = engine_fixtures.EngineTests("test_clean_commit_silent_and_same_trigger_idempotence")
        fixture.setUp()
        try:
            provider = engine_fixtures.ScriptedProvider()
            engine = CycleEngine(fixture.store, provider, task_text="task")
            original = engine.proxy.enforce
            def fail_only_selection(messages, tools=None):
                if "reminder-decision/1" in messages[0]["content"]:
                    raise ContractError("input_budget_exceeded", "synthetic selection")
                return original(messages, tools)
            engine.proxy.enforce = fail_only_selection
            result = engine.run("selection-preflight")
            self.assertEqual(result["status"], "committed_selection_failed")
            self.assertEqual(result["logical_calls"], 2)
            self.assertEqual(result["observable_attempts"], 2)
            self.assertEqual(result["responses_received"], 2)
            self.assertEqual([call["role"] for call in provider.calls],
                             ["maintenance", "audit"])
        finally:
            fixture.tearDown()

    def test_candidate_audit_budget_uses_only_shared_repair_credit(self):
        fixture = engine_fixtures.EngineTests("test_clean_commit_silent_and_same_trigger_idempotence")
        fixture.setUp()
        try:
            provider = engine_fixtures.ScriptedProvider(create_requirement=True)
            engine = CycleEngine(fixture.store, provider, task_text="task")
            original = engine.proxy.enforce
            def reject_large_candidate(messages, tools=None):
                if "audit-result/1" in messages[0]["content"]:
                    payload = json.loads(messages[1]["content"])
                    if payload["added_objects"]:
                        raise ContractError("input_budget_exceeded", "synthetic candidate")
                return original(messages, tools)
            engine.proxy.enforce = reject_large_candidate
            result = engine.run("candidate-size-repair")
            self.assertEqual(result["status"], "committed_selection_silent")
            self.assertEqual([call["role"] for call in provider.calls],
                ["maintenance", "candidate_repair", "audit", "selection"])
            self.assertEqual(result["logical_calls"], 4)
            self.assertEqual(len([row for row in fixture.store.journal_rows(result[
                "cycle_id"]) if row["phase"] == "repair_credit_used"]), 1)
        finally:
            fixture.tearDown()

    def test_strict_request_contains_wire_contract_not_only_field_names(self):
        fixture = engine_fixtures.EngineTests("test_clean_commit_silent_and_same_trigger_idempotence")
        fixture.setUp()
        try:
            provider = engine_fixtures.ScriptedProvider()
            result = CycleEngine(fixture.store, provider, task_text="task").run(
                "wire-contract")
            self.assertEqual(result["status"], "committed_selection_silent")
            maintenance, audit, selection = [call["messages"][0]["content"]
                                              for call in provider.calls]
            for field in ("Scope=", "RequirementRef=", "GoalDeltaRef=",
                          "environment_supported", "interpretation_replaced",
                          "general_hypothesis", "@local"):
                self.assertIn(field, maintenance)
            for field in ("BoundField=", "ClosureAssessment=", "unusable_reason",
                          "witnesses", "blocking_issue_ids"):
                self.assertIn(field, audit)
            for field in ("phase2_view_id", "context_for_action", "no protocol field",
                          "state_version", "task_version"):
                self.assertIn(field, selection)
            for call in provider.calls:
                self.assertIn("budget_notice", json.loads(call["messages"][1]["content"]))
        finally:
            fixture.tearDown()

    def test_selection_prompt_declares_output_shapes(self):
        from .prompts import SELECTION_SYSTEM
        self.assertIn("phase2_view_id", SELECTION_SYSTEM)
        self.assertIn("context_for_action", SELECTION_SYSTEM)


if __name__ == "__main__":
    unittest.main()
