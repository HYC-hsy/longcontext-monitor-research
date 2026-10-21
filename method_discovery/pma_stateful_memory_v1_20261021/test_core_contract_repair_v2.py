"""Audit counterexamples for the fixed v1 contract; fake-only."""

from copy import deepcopy
import json
import unittest

from .engine import CycleEngine
from .proposal import build_candidate, validate_proposal
from .reminder import render_reminder
from .schema import validate_snapshot
from .source import ContractError, SourceCatalog
from .test_contracts import empty_snapshot, leaf
from .test_engine import EngineTests, ScriptedProvider, event
from .test_schema_advanced import rich_state


class CoreContractRepairTests(unittest.TestCase):
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
        fixture = EngineTests("test_clean_commit_silent_and_same_trigger_idempotence")
        fixture.setUp()
        try:
            provider = ScriptedProvider()
            CycleEngine(fixture.store, provider, task_text="task").run("v2-goals")
            sent = json.loads(provider.calls[0]["messages"][1]["content"])
            self.assertEqual(sent["goal_ledger"]["epoch"], 1)
        finally:
            fixture.tearDown()

    def test_maintenance_catalog_carries_action_context(self):
        fixture = EngineTests("test_clean_commit_silent_and_same_trigger_idempotence")
        fixture.setUp()
        try:
            provider = ScriptedProvider(create_state=True)
            CycleEngine(fixture.store, provider, task_text="task").run("v2-first")
            fixture.store.append_event(*event(2, "next result"))
            provider2 = ScriptedProvider()
            CycleEngine(fixture.store, provider2, task_text="task").run("v2-second")
            sent = json.loads(provider2.calls[0]["messages"][1]["content"])
            self.assertTrue(any(item.get("executed_actions") for item in
                sent["source_catalog"] if item["source_kind"] == "tool_result"))
        finally:
            fixture.tearDown()

    def test_selection_prompt_declares_output_shapes(self):
        from .prompts import SELECTION_SYSTEM
        self.assertIn("phase2_view_id", SELECTION_SYSTEM)
        self.assertIn("context_for_action", SELECTION_SYSTEM)


if __name__ == "__main__":
    unittest.main()
