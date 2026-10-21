"""Actual prompt/codec/store chain under a finite, never-network provider."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from .engine import CycleEngine
from .reminder import attach_once
from .source import canonical
from .store import MemoryStore
from .test_contracts import empty_snapshot, leaf


def event(seq, text="observed result"):
    identifier = f"batch-{seq}"
    call_id = f"tool-call-{seq}"
    source = {"source_id": f"tool-{seq}", "event_id": call_id,
              "field_path": "tool_results.0.result.content", "source_kind": "tool_result",
              "ga_turn": seq, "event_seq": seq, "truncated": False,
              "text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest()}
    action = leaf("read_file", source_id=f"action-{seq}",
                  source_kind="executed_action")
    action.update(event_id=call_id, event_seq=seq, ga_turn=seq,
                  field_path="actions.0.arguments")
    return {"event_id": identifier, "event_seq": seq, "kind": "action_batch",
            "occurred_at_step": seq,
            "source_ids": [action["source_id"], source["source_id"]],
            "payload": {"actions": [{"tool_use_id": call_id}],
                        "commands": ["read_file"], "observation": text}}, [action, source]


class ScriptedProvider:
    def __init__(self, *, outcomes=(), fail_role=None,
                 create_requirement=False, create_state=False, remind=False):
        self.outcomes = list(outcomes)
        self.fail_role = fail_role
        self.create_requirement = create_requirement
        self.create_state = create_state
        self.remind = remind
        self.calls = []

    def __call__(self, role, messages, call_id, max_output):
        self.calls.append({"role": role, "messages": messages,
                           "call_id": call_id, "max_output": max_output})
        if role == self.fail_role:
            raise RuntimeError("synthetic provider error")
        content = json.loads(messages[1]["content"])
        if role in {"maintenance", "candidate_repair"}:
            binding = content.get("binding") or json.loads(messages[1]["content"])["binding"]
            additions = []
            entities, states = [], []
            if self.create_state and role == "maintenance":
                evidence_id = next(item["evidence_id"] for item in
                    content["source_catalog"] if item["source_kind"] == "tool_result"
                    and item["purpose"] == "maintenance")
                entities = [{"entity_id": "@e1", "entity_type": "environment",
                             "display_name": "synthetic workspace"}]
                states = [{"record_id": "@s1", "revision": 1, "entity_id": "@e1",
                    "scope": {"task_id": "task", "entity_ids": ["@e1"], "conditions": []},
                    "use_status": "active", "updated_at_step": 1, "supersedes": [],
                    "kind": "knowledge", "claim": {"text": "observed result",
                        "assertion_origin": "tool_observation",
                        "time_role": "present_fact", "support_refs": [{
                            "evidence_id": evidence_id, "quote": "observed result"}],
                        "challenge_refs": []}}]
            if self.create_requirement and role == "maintenance":
                additions = [{"requirement_id": "@r1", "revision": 1,
                    "task_version": 1, "interpretation": "perform task",
                    "source_refs": [{"evidence_id": next(item["evidence_id"] for item
                        in content["source_catalog"] if item["source_id"] == "u0" and
                        item["purpose"] == "maintenance"), "quote": "task"}],
                    "status": "active", "retirement": None}]
            return canonical({"protocol": "maintenance-proposal/1",
                "request_id": binding["request_id"],
                "active_task_version": binding["active_task_version"],
                "base_state_version": binding["base_state_version"],
                "world_patch": {"entity_upserts": entities, "state_upserts": states,
                                "relation_upserts": [], "record_transitions": []},
                "specification_upserts": additions, "gap_upserts": [],
                "gap_resolutions": [], "gap_reopens": [],
                "focus": {"op": "keep"}}).decode()
        if role in {"audit", "audit_correction"}:
            answer = {"protocol": "audit-result/1", "binding": content["binding"],
                "coverage": content["required_coverage"], "outcome": "clean",
                "issues": [], "closure_assessments": [], "unusable_reason": None}
            outcome = self.outcomes.pop(0) if self.outcomes else None
            if outcome == "malformed":
                answer["coverage"] = []
                answer["unexpected"] = True
            elif outcome == "issues":
                answer["outcome"] = "issues"
                answer["issues"] = [{"issue_id": "i1",
                    "kind": "goal_misinterpretation", "target": {
                        "snapshot": "candidate", "target": {"kind": "requirement",
                            "id": "r1", "revision": 1},
                        "field_path": "interpretation"},
                    "related_targets": [], "explanation": "synthetic issue",
                    "witnesses": [{"kind": "field", "field": {
                        "snapshot": "candidate", "target": {"kind": "requirement",
                            "id": next(item["id"] for item in content["required_coverage"]
                                       if item["kind"] == "requirement"),
                            "revision": 1}, "field_path": "interpretation"},
                        "exact_value": "perform task"}],
                    "repair_constraint": "remove the unsupported reading"}]
                answer["issues"][0]["target"]["target"]["id"] = next(
                    item["id"] for item in content["required_coverage"]
                    if item["kind"] == "requirement")
            elif outcome == "unusable":
                answer.update({"outcome": "unusable",
                    "unusable_reason": {"code": "insufficient_context",
                                        "detail": "synthetic"}})
            return canonical(answer).decode()
        if role == "selection":
            binding = content["binding"]
            answer = {"decision": "silent", "state_version": binding[
                "state_version"], "task_version": binding["task_version"],
                "phase2_view_id": binding["phase2_view_id"]}
            if self.remind:
                answer.update({"decision": "remind", "refs": [next(ref for ref in
                    content["selected_refs"] if ref["type"] == "requirement")],
                    "context_for_action": "Consider the goal."})
            return canonical(answer).decode()
        raise AssertionError("Unmatched fake role; network fallback forbidden")


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.temp.name) / "memory.sqlite3")
        self.store.initialize(empty_snapshot(), leaf("task"))
        self.store.append_event(*event(1))

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_clean_commit_silent_and_same_trigger_idempotence(self):
        provider = ScriptedProvider()
        engine = CycleEngine(self.store, provider, task_text="task")
        result = engine.run("trigger-1")
        self.assertEqual(result["status"], "committed_selection_silent")
        self.assertEqual(result["logical_calls"], 3)
        self.assertEqual([call["role"] for call in provider.calls],
                         ["maintenance", "audit", "selection"])
        self.assertEqual(self.store.snapshot()["committed_event_seq"], 1)
        self.assertEqual(engine.run("trigger-1"), result)
        self.assertEqual(len(provider.calls), 3)

    def test_initial_task_seq_zero_is_not_a_tool_transition(self):
        with tempfile.TemporaryDirectory() as root:
            store = MemoryStore(Path(root) / "initial.sqlite3")
            try:
                store.initialize(empty_snapshot(), leaf("task"))
                provider = ScriptedProvider(create_requirement=True)
                result = CycleEngine(store, provider, task_text="task").run("initial")
                self.assertEqual(result["status"], "committed_selection_silent")
                self.assertEqual(store.snapshot()["committed_event_seq"], 0)
                self.assertEqual(store.snapshot()["state_version"], 1)
                shown = json.loads(provider.calls[0]["messages"][1]["content"])
                self.assertEqual(shown["observation_batch"]["events"], [])
                self.assertTrue(all(item["source_kind"] == "user_requirement" for item
                    in shown["source_catalog"]))
            finally:
                store.close()

    def test_initial_provider_failure_is_not_an_empty_accepted_state(self):
        with tempfile.TemporaryDirectory() as root:
            store = MemoryStore(Path(root) / "initial-failure.sqlite3")
            try:
                store.initialize(empty_snapshot(), leaf("task"))
                provider = ScriptedProvider(fail_role="maintenance")
                result = CycleEngine(store, provider, task_text="task").run(
                    "initial-failure")
                self.assertEqual(result["status"], "init_failed")
                self.assertEqual(result["failure_stage"], "provider")
                self.assertEqual(result["logical_calls"], 1)
                self.assertEqual(result["observable_attempts"], 1)
                self.assertEqual(result["responses_received"], 0)
                self.assertEqual(store.snapshot()["state_version"], 0)
                self.assertEqual([item["role"] for item in provider.calls],
                                 ["maintenance"])
            finally:
                store.close()

    def test_audit_contract_one_shared_correction(self):
        provider = ScriptedProvider(outcomes=["malformed"])
        result = CycleEngine(self.store, provider, task_text="task").run("trigger-2")
        self.assertEqual(result["status"], "committed_selection_silent")
        self.assertEqual(result["logical_calls"], 4)
        self.assertEqual([item["role"] for item in provider.calls],
                         ["maintenance", "audit", "audit_correction", "selection"])

    def test_maintenance_contract_correction_uses_current_raw_and_one_credit(self):
        provider = ScriptedProvider()
        attempts = []
        def malformed_once(role, messages, call_id, max_output):
            attempts.append((role, messages))
            if len(attempts) == 1:
                return '{"protocol":"maintenance-proposal/1","world_patch":[]}'
            return provider(role, messages, call_id, max_output)
        result = CycleEngine(self.store, malformed_once, task_text="task").run(
            "maintenance-correction")
        self.assertEqual(result["status"], "committed_selection_silent")
        self.assertEqual(result["logical_calls"], 4)
        self.assertEqual([role for role, _ in attempts],
                         ["maintenance", "maintenance", "audit", "selection"])
        correction = json.loads(attempts[1][1][-1]["content"])
        self.assertEqual(correction["last_raw_response"],
                         '{"protocol":"maintenance-proposal/1","world_patch":[]}')
        self.assertEqual(correction["repair_mode"], "maintenance_contract")
        self.assertEqual(self.store.snapshot()["committed_event_seq"], 1)

    def test_failure_preserves_pending_for_next_real_trigger(self):
        provider = ScriptedProvider(fail_role="audit")
        result = CycleEngine(self.store, provider, task_text="task").run("trigger-3")
        self.assertEqual(result["status"], "runtime_failed")
        self.assertEqual(result["error_code"], "RuntimeError")
        self.assertEqual(result["failure_stage"], "provider")
        self.assertEqual(self.store.snapshot()["committed_event_seq"], 0)
        fixed = ScriptedProvider()
        replay = CycleEngine(self.store, fixed, task_text="task").run("trigger-4")
        self.assertEqual(replay["status"], "committed_selection_silent")
        self.assertEqual(self.store.snapshot()["committed_event_seq"], 1)
        replay_input = json.loads(fixed.calls[0]["messages"][1]["content"])[
            "observation_batch"]
        self.assertEqual(replay_input["events"][0]["event_id"], "batch-1")
        self.assertEqual(replay_input["events"][0]["delivery_kind"], "replayed")
        self.assertEqual(replay_input["events"][0]["previous_attempt_ids"],
                         [result["cycle_id"]])
        self.assertEqual(replay_input["previous_attempt_diagnostics"][0][
            "epistemic_status"], "diagnostic_not_evidence")

    def test_issues_repair_reaudit_five_calls(self):
        provider = ScriptedProvider(outcomes=["issues"], create_requirement=True)
        result = CycleEngine(self.store, provider, task_text="task").run("repair")
        self.assertEqual(result["status"], "committed_selection_silent")
        self.assertEqual(result["logical_calls"], 5)
        self.assertEqual([item["role"] for item in provider.calls],
            ["maintenance", "audit", "candidate_repair", "audit", "selection"])
        self.assertEqual(self.store.snapshot()["B"]["G"]["specifications"], [])

    def test_reminder_ready_not_delivered(self):
        provider = ScriptedProvider(create_requirement=True, remind=True)
        result = CycleEngine(self.store, provider, task_text="task").run("remind")
        self.assertEqual(result["status"], "committed_reminder_ready")
        self.assertEqual(result["logical_calls"], 3)
        reminder = result["reminder"]
        self.assertEqual(reminder["anchors"][0]["ref"]["requirement_id"],
                         self.store.snapshot()["B"]["G"]["specifications"][0]["requirement_id"])
        self.assertIsNone(self.store.delivery_result(reminder["reminder_id"]))
        original = [{"role": "system", "content": "task agent"},
                    {"role": "user", "content": "task"}]
        sent = []
        def task_send(messages):
            sent.append(messages)
            return {"accepted": True, "public_text": "I will check."}
        accepted = attach_once(store=self.store, reminder=reminder,
            task_messages=original, request_id="task-request-1",
            cycle_id=result["cycle_id"], send=task_send)
        self.assertTrue(accepted["accepted"])
        self.assertEqual(len(sent), 1)
        self.assertEqual(original[1]["content"], "task")
        self.assertEqual(sent[0][-1]["role"], "user")
        self.assertIn("not a new user requirement", sent[0][-1]["content"])
        self.assertIsNotNone(self.store.delivery_result(reminder["reminder_id"]))
        self.store.append_event(*event(2, "synthetic later action result"))
        self.assertEqual(self.store.events_after(1)[0]["event_id"], "batch-2")
        self.assertEqual(self.store.delivery_result(reminder["reminder_id"])[
            "request_id"], "task-request-1")

    def test_unusable_and_exhausted_audit_do_not_commit(self):
        for outcomes in (["unusable"], ["malformed", "malformed"]):
            provider = ScriptedProvider(outcomes=outcomes)
            result = CycleEngine(self.store, provider, task_text="task").run(
                "unusable-" + str(len(outcomes)))
            self.assertEqual(result["status"], "update_unusable")
            self.assertEqual(self.store.snapshot()["state_version"], 0)
            self.assertNotIn("selection", [call["role"] for call in provider.calls])

    def test_valid_issue_after_shared_credit_is_update_rejected(self):
        provider = ScriptedProvider(outcomes=["malformed", "issues"],
                                    create_requirement=True)
        result = CycleEngine(self.store, provider, task_text="task").run(
            "credit-exhausted")
        self.assertEqual(result["status"], "update_rejected")
        self.assertEqual(result["error_code"], "blocking_issues_repair_exhausted")
        self.assertEqual(self.store.snapshot()["state_version"], 0)
        self.assertEqual([item["role"] for item in provider.calls],
            ["maintenance", "audit", "audit_correction"])

    def test_selection_failure_does_not_roll_back_commit(self):
        provider = ScriptedProvider(fail_role="selection")
        result = CycleEngine(self.store, provider, task_text="task").run("select-fail")
        self.assertEqual(result["status"], "committed_selection_failed")
        self.assertEqual(self.store.snapshot()["committed_event_seq"], 1)

    def test_goal_change_after_commit_makes_selection_stale_without_rollback(self):
        provider = ScriptedProvider()
        original = self.store.compare_and_swap
        def commit_then_user_revision(**kwargs):
            committed = original(**kwargs)
            revised = leaf("new task", source_id="later-user")
            revised.update(event_id="later-message", event_seq=2, ga_turn=2)
            self.store.append_event({"event_id": "later-message", "event_seq": 2,
                "kind": "user_message", "occurred_at_step": 2,
                "source_ids": ["later-user"], "payload": {}}, [revised])
            return committed
        self.store.compare_and_swap = commit_then_user_revision
        result = CycleEngine(self.store, provider, task_text="task").run(
            "postcommit-goal-change")
        self.assertEqual(result["status"], "committed_backlog_pending")
        self.assertEqual(self.store.snapshot()["committed_event_seq"], 1)
        self.assertEqual(self.store.goals()["epoch"], 2)
        self.assertEqual([item["role"] for item in provider.calls],
                         ["maintenance", "audit"])
        self.assertEqual(result["logical_calls"], 2)
        self.assertEqual(result["observable_attempts"], 2)
        self.assertEqual(result["responses_received"], 2)

    def test_goal_change_during_selection_cannot_prepare_old_reminder(self):
        provider = ScriptedProvider(create_requirement=True, remind=True)
        def changed_during_selection(role, messages, call_id, max_output):
            answer = provider(role, messages, call_id, max_output)
            if role == "selection":
                revised = leaf("new task", source_id="later-user")
                revised.update(event_id="later-message", event_seq=2, ga_turn=2)
                self.store.append_event({"event_id": "later-message",
                    "event_seq": 2, "kind": "user_message", "occurred_at_step": 2,
                    "source_ids": ["later-user"], "payload": {}}, [revised])
            return answer
        result = CycleEngine(self.store, changed_during_selection,
                             task_text="task").run("during-selection")
        self.assertEqual(result["status"], "committed_selection_stale")
        self.assertNotIn("reminder", result)
        self.assertEqual(self.store.snapshot()["state_version"], 1)
        self.assertEqual(self.store.goals()["epoch"], 2)
        self.assertEqual([item["role"] for item in provider.calls],
                         ["maintenance", "audit", "selection"])

    def test_postcommit_index_rebuilt_before_selection(self):
        provider = ScriptedProvider(create_state=True)
        result = CycleEngine(self.store, provider, task_text="task").run("new-state")
        self.assertEqual(result["status"], "committed_selection_silent")
        selected = json.loads(provider.calls[-1]["messages"][1]["content"])[
            "selected_refs"]
        state_id = self.store.snapshot()["B"]["W"]["states"][0]["record_id"]
        self.assertIn({"type": "state", "record_id": state_id, "revision": 1}, selected)
        self.assertEqual(self.store.snapshot()["B"]["W"]["states"][0][
            "claim"]["support_refs"][0]["source_id"], "tool-1")

    def test_audit_operation_index_names_actual_changed_object(self):
        provider = ScriptedProvider(create_requirement=True)
        result = CycleEngine(self.store, provider, task_text="task").run("operation")
        self.assertEqual(result["status"], "committed_selection_silent")
        audit_view = json.loads(provider.calls[1]["messages"][1]["content"])
        self.assertEqual(audit_view["operation_index"][0]["operation"],
                         "specification_upserts")
        requirement_id = self.store.snapshot()["B"]["G"]["specifications"][0]["requirement_id"]
        self.assertEqual(audit_view["operation_index"][0]["target_ref"]["id"], requirement_id)

    def test_goal_epoch_change_blocks_commit(self):
        provider = ScriptedProvider()
        def change_goal(role, messages, call_id, max_output):
            answer = provider(role, messages, call_id, max_output)
            if role == "audit":
                user = leaf("revised task", source_id="u1")
                user.update(event_id="user-message-2", event_seq=2, ga_turn=2)
                self.store.append_event({"event_id": "user-message-2",
                    "event_seq": 2, "kind": "user_message", "occurred_at_step": 2,
                    "source_ids": ["u1"], "payload": {}}, [user])
            return answer
        result = CycleEngine(self.store, change_goal, task_text="task").run(
            "goal-change")
        self.assertEqual(result["status"], "runtime_failed")
        self.assertEqual(result["error_code"], "goal_epoch_mismatch")
        self.assertEqual(result["failure_stage"], "commit")
        self.assertEqual(self.store.snapshot()["state_version"], 0)

    def test_partial_prefix_commits_without_selection(self):
        very_long = " ".join(str(index) for index in range(40000))
        self.store.append_event(*event(2, very_long))
        provider = ScriptedProvider()
        result = CycleEngine(self.store, provider, task_text="task").run("backlog")
        self.assertEqual(result["status"], "committed_backlog_pending")
        self.assertEqual(result["logical_calls"], 2)
        self.assertEqual(self.store.snapshot()["committed_event_seq"], 1)
        self.assertEqual(result["pending_after_batch_count"], 1)


if __name__ == "__main__":
    unittest.main()
