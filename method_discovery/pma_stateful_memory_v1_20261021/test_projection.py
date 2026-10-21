"""Frozen working-set audit visibility with opaque retained state outside it."""

from copy import deepcopy
import json
import unittest

from .audit import AuditCodec
from .proposal import build_candidate
from .projection import project_snapshot, visible_existing
from .retrieval import WorksetBuilder
from .source import ContractError, SourceCatalog, digest
from .test_schema_advanced import rich_state


class ProjectionTests(unittest.TestCase):
    def test_unselected_current_state_preserved_but_not_claimed_reviewed(self):
        full, ledger = rich_state()
        hidden = deepcopy(full["B"]["W"]["states"][0])
        hidden["record_id"] = "hidden"
        full["B"]["W"]["states"].append(hidden)
        work = WorksetBuilder(input_limit=100000).build(full, [], ledger, [],
            "cycle", 0, lambda body: len(json.dumps(body)), archive={}).payload()
        before = project_snapshot(full, full, work)
        self.assertEqual([item["record_id"] for item in before["B"]["W"]["states"]],
                         ["s"])
        self.assertNotIn(("state", "hidden"), visible_existing(full, work))
        after_full = deepcopy(full)
        after_full["state_version"] += 1
        after_full["B"]["W"]["states"][1]["claim"]["text"] = "still hidden"
        after = project_snapshot(after_full, full, work)
        view = AuditCodec().encode(before, after, binding={"cycle_id": "c"},
            sources=[], observations={"events": []}, operation_index=[],
            resolve_manifest=[])
        AuditCodec().verify(view, before, after)
        self.assertNotIn("hidden", {entry["id"] for entry in
            view["required_coverage"]})
        self.assertNotEqual(digest(before), digest(full))
        self.assertEqual(full["B"]["W"]["states"][1]["record_id"], "hidden")
        catalog = SourceCatalog(ledger, work["source_window_id"])
        span = catalog.add("tool", 0, len(ledger["tool"]["text"]), "maintenance")
        attempted = deepcopy(hidden)
        attempted["revision"] = 2
        attempted["supersedes"] = [{"type": "state", "record_id": "hidden",
                                    "revision": 1}]
        attempted["claim"]["support_refs"] = [{"evidence_id": span.evidence_id,
                                                 "quote": "feature absent"}]
        proposal = {"protocol": "maintenance-proposal/1", "request_id": "req",
            "active_task_version": 1, "base_state_version": 1,
            "world_patch": {"entity_upserts": [], "state_upserts": [attempted],
                "relation_upserts": [], "record_transitions": []},
            "specification_upserts": [], "gap_upserts": [],
            "gap_resolutions": [], "gap_reopens": [], "focus": {"op": "keep"}}
        with self.assertRaisesRegex(ContractError, "invisible_existing_object"):
            build_candidate(proposal=proposal, base=full, catalog=catalog,
                cycle_id="cycle", processed_to=0,
                goal_ledger={"epoch": 1, "deltas": {}, "messages": ["u0"]},
                visible_existing_ids=visible_existing(full, work), archive={})


if __name__ == "__main__":
    unittest.main()
