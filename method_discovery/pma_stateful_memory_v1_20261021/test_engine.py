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
                 create_requirement=False, remind=False):
        self.outcomes = list(outcomes)
        self.fail_role = fail_role
        self.create_requirement = create_requirement
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
            if self.create_requirement and role == "maintenance":
                additions = [{"requirement_id": "r1", "revision": 1,
                    "task_version": 1, "interpretation": "perform task",
                    "source_refs": [{"evidence_id": next(item["evidence_id"] for item
                        in content["source_catalog"] if item["source_id"] == "u0" and
                        item["purpose"] == "maintenance"), "quote": "task"}],
                    "status": "active", "retirement": None}]
            return canonical({"protocol": "maintenance-proposal/1",
                "request_id": binding["request_id"],
                "active_task_version": binding["active_task_version"],
                "base_state_version": binding["base_state_version"],
                "world_patch": {"entity_upserts": [], "state_upserts": [],
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
                    "witnesses": [], "repair_constraint": "remove the unsupported reading"}]
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

    def test_audit_contract_one_shared_correction(self):
        provider = ScriptedProvider(outcomes=["malformed"])
        result = CycleEngine(self.store, provider, task_text="task").run("trigger-2")
        self.assertEqual(result["status"], "committed_selection_silent")
        self.assertEqual(result["logical_calls"], 4)
        self.assertEqual([item["role"] for item in provider.calls],
                         ["maintenance", "audit", "audit_correction", "selection"])

    def test_failure_preserves_pending_for_next_real_trigger(self):
        provider = ScriptedProvider(fail_role="audit")
        result = CycleEngine(self.store, provider, task_text="task").run("trigger-3")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], "RuntimeError")
        self.assertEqual(self.store.snapshot()["committed_event_seq"], 0)
        fixed = ScriptedProvider()
        replay = CycleEngine(self.store, fixed, task_text="task").run("trigger-4")
        self.assertEqual(replay["status"], "committed_selection_silent")
        self.assertEqual(self.store.snapshot()["committed_event_seq"], 1)

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
        self.assertEqual(reminder["anchors"][0]["ref"]["requirement_id"], "r1")
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

    def test_unusable_and_exhausted_audit_do_not_commit(self):
        for outcomes in (["unusable"], ["malformed", "malformed"]):
            provider = ScriptedProvider(outcomes=outcomes)
            result = CycleEngine(self.store, provider, task_text="task").run(
                "unusable-" + str(len(outcomes)))
            self.assertEqual(result["status"], "failed")
            self.assertEqual(self.store.snapshot()["state_version"], 0)
            self.assertNotIn("selection", [call["role"] for call in provider.calls])

    def test_selection_failure_does_not_roll_back_commit(self):
        provider = ScriptedProvider(fail_role="selection")
        result = CycleEngine(self.store, provider, task_text="task").run("select-fail")
        self.assertEqual(result["status"], "committed_selection_failed")
        self.assertEqual(self.store.snapshot()["committed_event_seq"], 1)

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
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], "goal_epoch_mismatch")
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
