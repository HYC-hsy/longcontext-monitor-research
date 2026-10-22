"""One continuous fake episode with stored memory, repair, delivery and goal migration."""

import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from .engine import CycleEngine
from .budget import TokenProxy
from .reminder import attach_once
from .source import digest
from .store import MemoryStore
from .test_contracts import empty_snapshot, leaf
from .test_engine import event


def wire(payload, source_id, quote):
    match = next(item for item in payload["source_catalog"] if item[
        "source_id"] == source_id and item["purpose"] == "maintenance" and
        quote in item["text"])
    return {"evidence_id": match["evidence_id"], "quote": quote}


class FiniteProvider:
    def __init__(self):
        self.phase = "init"
        self.roles = []
        self.calls = []
        self.audit_count = 0
        self.proxy = TokenProxy()

    def __call__(self, role, messages, call_id, max_output):
        response = self._answer(role, messages, call_id, max_output)
        assert isinstance(response, str)
        self.calls[-1]["request_size"] = self.proxy.measure(messages)
        self.calls[-1]["response_size"] = {"characters": len(response),
            "utf8_bytes": len(response.encode("utf-8")),
            "proxy_tokens": len(self.proxy.encoding.encode(
                response, disallowed_special=()))}
        self.calls[-1]["response_sha256"] = digest(response)
        self.calls[-1]["raw_response_utf8_sha256"] = hashlib.sha256(
            response.encode("utf-8")).hexdigest()
        return response

    def _answer(self, role, messages, call_id, max_output):
        self.roles.append(role)
        self.calls.append({"phase": self.phase, "role": role, "call_id": call_id,
                           "messages_sha256": digest(messages)})
        payload = json.loads(messages[1]["content"])
        if role in {"maintenance", "candidate_repair"}:
            binding = payload["binding"]
            patch = {"entity_upserts": [], "state_upserts": [],
                     "relation_upserts": [], "record_transitions": []}
            requirements = gaps = resolutions = []
            focus = {"op": "keep"}
            if self.phase == "build":
                tool = wire(payload, "tool-1", "tests passed")
                action = wire(payload, "action-1", "read_file")
                user = wire(payload, "u0", "task")
                scope = {"task_id": "task", "entity_ids": ["@e"], "conditions": []}
                observed = {"text": "tests passed", "assertion_origin":
                    "tool_observation", "time_role": "past_episode",
                    "support_refs": [tool], "challenge_refs": []}
                patch["entity_upserts"] = [{"entity_id": "@e", "entity_type":
                    "environment", "display_name": "synthetic workspace"}]
                patch["state_upserts"] = [
                    {"record_id": "@k", "revision": 1, "entity_id": "@e",
                     "scope": scope, "use_status": "active", "updated_at_step": 1,
                     "supersedes": [], "kind": "knowledge", "claim": {
                         **observed, "time_role": "present_fact"}},
                    {"record_id": "@p", "revision": 1, "entity_id": "@e",
                     "scope": scope, "use_status": "active", "updated_at_step": 1,
                     "supersedes": [], "kind": "procedural", "episode": {
                         "conditions": observed, "action_text": "read_file",
                         "action_refs": [action], "result": observed,
                         "time_role": "past_episode"}, "lesson": {
                         "text": "Check before generalizing", "assertion_origin": "inference",
                         "time_role": "general_hypothesis", "support_refs": [tool],
                         "challenge_refs": []}}]
                requirements = [{"requirement_id": "@r", "revision": 1,
                    "task_version": 1, "interpretation": "complete task",
                    "source_refs": [user], "status": "active", "retirement": None}]
                gaps = [{"gap_id": "@g", "revision": 1, "task_version": 1,
                    "gap_kind": "achievement", "target": "task complete",
                    "reason": "synthetic check is local", "goal_refs": [{
                        "type": "requirement", "requirement_id": "@r",
                        "revision": 1, "task_version": 1}], "record_refs": [{
                        "type": "state", "record_id": "@k", "revision": 1}],
                    "status": "open", "closure": None}]
                focus = {"op": "set", "value": {"gap_ref": {"type": "gap",
                    "gap_id": "@g", "revision": 1, "task_version": 1},
                    "reason": "synthetic task remains open", "changed_at_step": 1}}
            elif self.phase == "challenge":
                before = payload["before_view"]
                state = next(item for item in before["B"]["W"]["states"] if
                             item["kind"] == "knowledge")
                latest = wire(payload, "tool-2", "command not found")
                revised = json.loads(json.dumps(state))
                revised["revision"] = state["revision"] + 1
                revised["supersedes"].append({"type": "state", "record_id": state[
                    "record_id"], "revision": state["revision"]})
                revised["claim"]["text"] = ("command not found" if role ==
                    "candidate_repair" else "tests passed everywhere")
                revised["claim"]["support_refs"] = [latest]
                revised["updated_at_step"] = 2
                patch["state_upserts"] = [revised]
            elif self.phase == "goal":
                before = payload["before_view"]
                requirement = before["B"]["G"]["specifications"][0]
                gap = before["B"]["DeltaA"][0]
                delta = payload["goal_ledger"]["deltas"][-1]
                requirements = [{**requirement, "revision": 2,
                    "task_version": 2, "interpretation": "revised task",
                    "source_refs": [wire(payload, "u1", "revised task")]}]
                resolutions = [{**gap, "revision": 2, "status": "superseded",
                    "closure": {"kind": "goal_changed", "goal_delta_ref": delta}}]
                focus = {"op": "clear", "reason": "target revision"}
            return json.dumps({"protocol": "maintenance-proposal/1",
                "request_id": binding["request_id"],
                "active_task_version": binding["active_task_version"],
                "base_state_version": binding["base_state_version"],
                "world_patch": patch, "specification_upserts": requirements,
                "gap_upserts": gaps, "gap_resolutions": resolutions,
                "gap_reopens": [], "focus": focus})
        if role == "audit":
            self.audit_count += 1
            outcome = "issues" if self.phase == "challenge" and self.audit_count == 3 else "clean"
            issues = []
            if outcome == "issues":
                changed = next(item for item in payload["changed_objects"] if
                               item["after_body"].get("kind") == "knowledge")
                body = changed["after_body"]
                target = {"snapshot": "candidate", "target": {"kind": "state",
                    "id": body["record_id"], "revision": body["revision"]},
                    "field_path": "claim.text"}
                issues = [{"issue_id": "i1", "kind": "scope_overreach",
                    "target": target, "related_targets": [],
                    "explanation": "synthetic review flags unsupported global scope",
                    "witnesses": [{"kind": "field", "field": target,
                                   "exact_value": body["claim"]["text"]}],
                    "repair_constraint": "keep only observed local result"}]
            assessments = []
            for item in payload["resolve_manifest"]:
                def gap_ref(gap):
                    return {"type": "gap", "gap_id": gap["gap_id"],
                            "revision": gap["revision"],
                            "task_version": gap["task_version"]}
                assessments.append({"resolution_id": item["resolution_id"],
                    "gap_before": gap_ref(item["gap_before"]),
                    "gap_after": gap_ref(item["gap_after"]),
                    "closure_kind": item["closure_kind"], "verdict": "supported",
                    "assessed_scope": {}, "explanation": "synthetic goal revision",
                    "basis_refs": [item["gap_after"]["closure"]["goal_delta_ref"]],
                    "blocking_issue_ids": []})
            return json.dumps({"protocol": "audit-result/2",
                "binding": payload["binding"],
                "outcome": outcome, "issues": issues,
                "closure_assessments": assessments, "unusable_reason": None})
        if role == "selection":
            binding = payload["binding"]
            decision = {"decision": "silent", "state_version": binding["state_version"],
                "task_version": binding["task_version"],
                "phase2_view_id": binding["phase2_view_id"]}
            if self.phase == "build":
                decision.update(decision="remind", refs=[next(ref for ref in
                    payload["selected_refs"] if ref["type"] == "gap")],
                    context_for_action="Review the local result before generalizing.")
            return json.dumps(decision)
        raise AssertionError("unexpected fake role; no provider fallback")


class MultiRoundV2Tests(unittest.TestCase):
    def test_continuous_fake_episode(self):
        with tempfile.TemporaryDirectory() as root:
            store = MemoryStore(Path(root) / "chain.sqlite3")
            try:
                store.initialize(empty_snapshot(), leaf("task"))
                provider = FiniteProvider()
                engine = CycleEngine(store, provider, task_text="task")
                initial = engine.run("initial")
                self.assertEqual(initial["status"], "committed_selection_silent")
                provider.phase = "build"
                store.append_event(*event(1, "tests passed"))
                built = engine.run("built")
                self.assertEqual(built["status"], "committed_reminder_ready")
                sent = []
                def fake_task(messages):
                    sent.append(messages)
                    return {"accepted": True, "public_text": "synthetic continuation"}
                attach_once(store=store, reminder=built["reminder"],
                    task_messages=[{"role": "user", "content": "task"}],
                    request_id="fake-task-1", cycle_id=built["cycle_id"],
                    send=fake_task)
                self.assertEqual(len(sent), 1)
                self.assertIn("Auxiliary memory information", sent[0][-1]["content"])
                provider.phase = "challenge"
                store.append_event(*event(2, "command not found"))
                challenged = engine.run("challenge")
                self.assertEqual(challenged["status"], "committed_selection_silent")
                self.assertEqual(challenged["logical_calls"], 5)
                self.assertEqual(store.snapshot()["B"]["W"]["states"][0]["claim"][
                    "text"], "command not found")
                provider.phase = "goal"
                user = leaf("revised task", source_id="u1")
                user.update(event_id="user-3", event_seq=3, ga_turn=3)
                store.append_event({"event_id": "user-3", "event_seq": 3,
                    "kind": "user_message", "occurred_at_step": 3,
                    "source_ids": ["u1"], "payload": {}}, [user])
                migrated = engine.run("goal")
                self.assertEqual(migrated["status"], "committed_selection_silent")
                snapshot = store.snapshot()
                self.assertEqual(snapshot["committed_event_seq"], 3)
                self.assertEqual(snapshot["B"]["DeltaA"][0]["status"], "superseded")
                self.assertEqual(snapshot["B"]["DeltaA"][0]["goal_refs"][0][
                    "revision"], 1)
                self.assertEqual(snapshot["B"]["G"]["specifications"][0][
                    "revision"], 2)
                self.assertEqual(len(store.archive()), 3)
                self.assertEqual([item["role"] for item in provider.calls],
                    ["maintenance", "audit", "selection"] * 2 +
                    ["maintenance", "audit", "candidate_repair", "audit",
                     "selection"] + ["maintenance", "audit", "selection"])
                print(json.dumps({"fixture": "continuous_fake_v2",
                    "role_calls": len(provider.calls), "observable_attempts": sum(
                        row["phase"] == "call_attempt" for result in
                        (initial, built, challenged, migrated) for row in
                        store.journal_rows(result["cycle_id"])),
                    "synthetic_task_tool_calls": 2,
                    "task_delivery": "included_in_accepted_request",
                    "frontier": snapshot["committed_event_seq"],
                    "state_version": snapshot["state_version"],
                    "message_sizes": [{"phase": row["phase"], "role": row["role"],
                        "request": {key: row["request_size"][key] for key in
                            ("characters", "utf8_bytes", "proxy_tokens")},
                        "response": row["response_size"],
                        "request_sha256": row["messages_sha256"],
                        "response_sha256": row["response_sha256"],
                        "raw_response_utf8_sha256": row["raw_response_utf8_sha256"]}
                        for row in provider.calls],
                    "real_model_calls": 0, "official_evaluator_calls": 0},
                    sort_keys=True))
            finally:
                store.close()

    def test_response_measurement_uses_returned_string_not_json_wrapper(self):
        class Literal(FiniteProvider):
            def _answer(self, role, messages, call_id, max_output):
                self.calls.append({"phase": "synthetic", "role": role,
                    "call_id": call_id, "messages_sha256": digest(messages)})
                return '"quoted" \\slash\n中文'
        provider = Literal()
        messages = [{"role": "user", "content": "synthetic"}]
        raw = provider("synthetic", messages, "id", 1)
        size = provider.calls[0]["response_size"]
        self.assertEqual(size["characters"], len(raw))
        self.assertEqual(size["utf8_bytes"], len(raw.encode("utf-8")))
        self.assertEqual(size["proxy_tokens"], len(provider.proxy.encoding.encode(
            raw, disallowed_special=())))
        self.assertNotEqual(size["utf8_bytes"], len(json.dumps(raw,
            ensure_ascii=False).encode("utf-8")))
