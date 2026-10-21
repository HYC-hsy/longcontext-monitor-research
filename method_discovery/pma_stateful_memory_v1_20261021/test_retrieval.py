"""Pinned ranking and deterministic whole-bundle budget controls."""

from copy import deepcopy
import json
import unittest

from .retrieval import MemoryIndex, WorksetBuilder, query_text
from .source import ContractError
from .test_contracts import empty_snapshot, leaf
from .test_schema_advanced import rich_state


def record(index, kind="knowledge"):
    base = {"record_id": f"r{index}", "revision": 1, "entity_id": "e",
            "use_status": "active", "kind": kind}
    if kind == "knowledge":
        base["claim"] = {"text": f"alpha item {index}", "support_refs": [],
                         "challenge_refs": []}
    else:
        base["episode"] = {"conditions": {"text": "alpha"},
                           "action_text": "inspect", "result": {"text": "done"}}
        base["lesson"] = None
    return base


class RetrievalTests(unittest.TestCase):
    def test_pinned_bm25_and_threshold(self):
        snapshot = empty_snapshot()
        states = snapshot["B"]["W"]["states"]
        states.extend(record(index) for index in range(50))
        index = MemoryIndex(snapshot)
        self.assertEqual(len(index.select("unmatched")), 50)
        states.append(record(50))
        index = MemoryIndex(snapshot)
        self.assertEqual(len(index.select("alpha", threshold=50)), 20)
        self.assertEqual(index.select("unmatched", threshold=50), [])

    def test_query_command_limit_and_recent_window(self):
        steps = [{"commands": [str(i) for i in range(9)],
                  "observation": "observed"} for _ in range(9)]
        query = query_text("task", [], steps)
        self.assertEqual(query.count("[4 commands omitted]"), 8)

    def test_first_event_cannot_be_skipped_and_optional_is_whole(self):
        snapshot = empty_snapshot()
        snapshot["B"]["W"]["entities"] = [{"entity_id": "e"}]
        snapshot["B"]["W"]["states"] = [record(0)]
        source = leaf("result", source_id="out", source_kind="tool_result")
        source.update(event_id="batch", event_seq=1, ga_turn=1)
        event = {"event_id": "batch", "event_seq": 1, "kind": "action_batch",
                 "occurred_at_step": 1, "source_ids": ["out"], "payload": {}}
        measure = lambda value: len(json.dumps(value))
        builder = WorksetBuilder(input_limit=100)
        with self.assertRaisesRegex(ContractError, "input_budget_exceeded"):
            builder.build(snapshot, [event], {"out": source}, [], "cycle", 1, measure)
        builder.input_limit = 2000
        work = builder.build(snapshot, [event], {"out": source},
                             snapshot["B"]["W"]["states"], "cycle", 1, measure)
        self.assertEqual(len(work.observation_batch["events"]), 1)
        self.assertEqual(work.observation_batch["processing_range"]["to_event_seq"], 1)
        self.assertEqual(len(work.optional_bundles), 1)
        builder.input_limit = measure(work.payload()) - 1
        smaller = builder.build(snapshot, [event], {"out": source},
                                snapshot["B"]["W"]["states"], "cycle", 1, measure)
        self.assertEqual(smaller.optional_bundles, [])
        self.assertEqual(smaller.omissions[0]["record_id"], "r0")

    def test_open_gap_pins_old_revision_and_current_head(self):
        snapshot = empty_snapshot()
        snapshot["B"]["W"]["entities"] = [{"entity_id": "e"}]
        current = record(0)
        current["revision"] = 2
        old = record(0)
        snapshot["B"]["W"]["states"] = [current]
        snapshot["B"]["DeltaE"] = [{"gap_id": "g", "status": "open",
            "record_refs": [{"type": "state", "record_id": "r0", "revision": 1}]}]
        work = WorksetBuilder(input_limit=100000).build(snapshot, [], {}, [],
            "cycle", 0, lambda body: len(json.dumps(body)),
            archive={("r0", 1): old})
        self.assertEqual([(bundle["state"]["record_id"], bundle["state"]["revision"])
                          for bundle in work.mandatory["bundles"]],
                         [("r0", 2), ("r0", 1)])
        self.assertTrue(work.mandatory["bundles"][1]["historical_revision"])

    def test_optional_state_carries_direct_closed_gap_and_old_version(self):
        snapshot, ledger = rich_state()
        old = deepcopy(snapshot["B"]["W"]["states"][0])
        head = snapshot["B"]["W"]["states"][0]
        head["revision"] = 2
        snapshot["B"]["DeltaA"][0]["record_refs"] = []
        closed = snapshot["B"]["DeltaE"][0]
        closed["status"] = "supported"
        closed["closure"] = {"kind": "environment_supported",
            "conclusion": "feature absent", "evidence_refs": [{"source_id": "tool",
                "start": 0, "end": 14, "quote": "feature absent"}],
            "state_refs": []}
        work = WorksetBuilder(input_limit=100000).build(snapshot, [], ledger,
            [head], "cycle", 0, lambda body: len(json.dumps(body)),
            archive={("s", 1): old})
        bundle = work.optional_bundles[0]
        self.assertEqual(bundle["linked_closed_gaps"][0]["gap_id"], "ge")
        self.assertEqual(bundle["linked_state_versions"][0]["revision"], 1)


if __name__ == "__main__":
    unittest.main()
