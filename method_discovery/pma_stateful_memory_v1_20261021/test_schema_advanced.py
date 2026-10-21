"""Cross-record schema invariants, without semantic-truth claims."""

from copy import deepcopy
import unittest

from .schema import validate_snapshot
from .source import ContractError
from .test_contracts import empty_snapshot, leaf


def ref(source_id, text):
    return {"source_id": source_id, "start": 0, "end": len(text), "quote": text}


def rich_state():
    user = leaf("task")
    tool = leaf("feature absent", source_id="tool", source_kind="tool_result")
    tool.update(event_id="tool-use", event_seq=1, ga_turn=1)
    ledger = {"u0": user, "tool": tool}
    snap = empty_snapshot()
    snap["state_version"] = 1
    goal = snap["B"]["G"]
    goal["specifications"] = [{"requirement_id": "req", "revision": 1,
        "task_version": 1, "interpretation": "complete task",
        "source_refs": [ref("u0", "task")], "status": "active", "retirement": None}]
    world = snap["B"]["W"]
    world["entities"] = [{"entity_id": "e", "entity_type": "environment",
                           "display_name": "workspace"}]
    state = {"record_id": "s", "revision": 1, "entity_id": "e",
        "scope": {"task_id": "task", "entity_ids": ["e"], "conditions": []},
        "use_status": "active", "updated_at_step": 1, "supersedes": [],
        "kind": "knowledge", "claim": {"text": "feature absent",
            "assertion_origin": "tool_observation", "time_role": "present_fact",
            "support_refs": [ref("tool", "feature absent")], "challenge_refs": []}}
    world["states"] = [state]
    world["relations"] = [{"relation_id": "link", "from_entity_id": "e",
        "to_entity_id": "e", "predicate": "self-check",
        "anchored_by": {"type": "state", "record_id": "s", "revision": 1}}]
    base_gap = {"revision": 1, "task_version": 1, "target": "task complete",
        "reason": "not complete", "goal_refs": [{"type": "requirement",
            "requirement_id": "req", "revision": 1, "task_version": 1}],
        "record_refs": [{"type": "state", "record_id": "s", "revision": 1}],
        "status": "open", "closure": None}
    snap["B"]["DeltaE"] = [{**base_gap, "gap_id": "ge",
                               "gap_kind": "epistemic"}]
    snap["B"]["DeltaA"] = [{**base_gap, "gap_id": "ga",
                               "gap_kind": "achievement"}]
    return snap, ledger


class SchemaAdvancedTests(unittest.TestCase):
    def test_identity_relation_and_source_role(self):
        snap, ledger = rich_state()
        validate_snapshot(snap, ledger)
        bad = deepcopy(snap)
        bad["B"]["W"]["entities"][0]["installed"] = True
        with self.assertRaisesRegex(ContractError, "schema_fields"):
            validate_snapshot(bad, ledger)
        bad = deepcopy(snap)
        bad["B"]["W"]["relations"][0]["anchored_by"]["revision"] = 9
        with self.assertRaisesRegex(ContractError, "version_mismatch"):
            validate_snapshot(bad, ledger)
        bad = deepcopy(snap)
        bad["B"]["W"]["states"][0]["claim"]["support_refs"] = [ref("u0", "task")]
        with self.assertRaisesRegex(ContractError, "source_role_misuse"):
            validate_snapshot(bad, ledger)

    def test_negative_information_answer_does_not_close_achievement(self):
        snap, ledger = rich_state()
        info = snap["B"]["DeltaE"][0]
        info["status"] = "supported"
        info["closure"] = {"kind": "environment_supported",
            "conclusion": "feature is absent", "evidence_refs": [
                ref("tool", "feature absent")], "state_refs": []}
        validate_snapshot(snap, ledger)
        self.assertEqual(snap["B"]["DeltaA"][0]["status"], "open")
        bad = deepcopy(snap)
        bad["B"]["DeltaA"][0]["status"] = "supported"
        bad["B"]["DeltaA"][0]["closure"] = {"kind": "environment_supported",
            "conclusion": "done", "evidence_refs": [ref("u0", "task")],
            "state_refs": []}
        with self.assertRaisesRegex(ContractError, "source_role_misuse"):
            validate_snapshot(bad, ledger)

    def test_direct_history_and_cycle(self):
        snap, ledger = rich_state()
        old = deepcopy(snap["B"]["W"]["states"][0])
        head = snap["B"]["W"]["states"][0]
        head["revision"] = 2
        head["supersedes"] = [{"type": "state", "record_id": "s", "revision": 1}]
        snap["B"]["W"]["relations"][0]["anchored_by"]["revision"] = 2
        for gap in snap["B"]["DeltaE"] + snap["B"]["DeltaA"]:
            gap["record_refs"][0]["revision"] = 2
        validate_snapshot(snap, ledger, {("s", 1): old})
        cycle = deepcopy(old)
        cycle["supersedes"] = [{"type": "state", "record_id": "s", "revision": 2}]
        with self.assertRaisesRegex(ContractError, "supersedes_cycle"):
            validate_snapshot(snap, ledger, {("s", 1): cycle})


if __name__ == "__main__":
    unittest.main()
