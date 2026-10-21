"""Maintenance wire proposal application to an isolated original base."""

from copy import deepcopy
import unittest

from .proposal import build_candidate
from .source import ContractError, SourceCatalog
from .test_contracts import empty_snapshot, leaf


def proposal(request="request"):
    return {"protocol": "maintenance-proposal/1", "request_id": request,
            "active_task_version": 1, "base_state_version": 0,
            "world_patch": {"entity_upserts": [], "state_upserts": [],
                            "relation_upserts": [], "record_transitions": []},
            "specification_upserts": [], "gap_upserts": [],
            "gap_resolutions": [], "gap_reopens": [], "focus": {"op": "keep"}}


class ProposalTests(unittest.TestCase):
    def setUp(self):
        self.base = empty_snapshot()
        self.source = leaf("task")
        self.catalog = SourceCatalog({"u0": self.source}, "window")
        self.span = self.catalog.add("u0", 0, 4, "maintenance")
        self.goals = {"epoch": 1, "deltas": {}, "messages": ["u0"]}

    def build(self, patch):
        return build_candidate(proposal=patch, base=self.base,
            catalog=self.catalog, cycle_id="cycle", processed_to=0,
            goal_ledger=self.goals, visible_existing_ids=set(), archive={})

    def test_empty_patch_still_forms_candidate_without_mutating_base(self):
        result = self.build(proposal())
        self.assertEqual(result["candidate"]["state_version"], 1)
        self.assertEqual(self.base["state_version"], 0)
        self.assertEqual(result["canonical_patch"]["gap_upserts"], [])

    def test_local_ids_and_requirement_source(self):
        patch = proposal()
        evidence = {"evidence_id": self.span.evidence_id, "quote": "task"}
        patch["world_patch"]["entity_upserts"].append({"entity_id": "@e",
            "entity_type": "other", "display_name": "task object"})
        patch["specification_upserts"].append({"requirement_id": "@r",
            "revision": 1, "task_version": 1, "interpretation": "do task",
            "source_refs": [evidence], "status": "active", "retirement": None})
        patch["gap_upserts"].append({"gap_id": "@g", "revision": 1,
            "task_version": 1, "gap_kind": "achievement", "target": "task complete",
            "reason": "not done", "goal_refs": [{"type": "requirement",
                "requirement_id": "@r", "revision": 1, "task_version": 1}],
            "record_refs": [], "status": "open", "closure": None})
        result = self.build(patch)
        belief = result["candidate"]["B"]
        self.assertEqual(belief["G"]["specifications"][0]["source_refs"][0][
            "source_id"], "u0")
        self.assertEqual(belief["DeltaA"][0]["goal_refs"][0]["requirement_id"],
                         result["local_id_map"]["@r"])
        self.assertEqual(self.base["B"]["DeltaA"], [])

    def test_conflicting_operations_and_stored_ref_rejected(self):
        patch = proposal()
        patch["gap_upserts"].append({"gap_id": "g"})
        patch["gap_resolutions"].append({"gap_id": "g"})
        with self.assertRaisesRegex(ContractError, "conflicting_operations"):
            self.build(patch)
        patch = proposal()
        patch["specification_upserts"].append({"requirement_id": "r",
            "source_refs": [{"source_id": "u0", "start": 0, "end": 4,
                             "quote": "task"}]})
        with self.assertRaisesRegex(ContractError, "stored_ref_in_wire_proposal"):
            self.build(patch)


if __name__ == "__main__":
    unittest.main()
