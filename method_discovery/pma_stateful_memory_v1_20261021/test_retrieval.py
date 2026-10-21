"""Pinned ranking and deterministic whole-bundle budget controls."""

from copy import deepcopy
import json
import unittest

from .retrieval import MemoryIndex, WorksetBuilder, query_text
from .source import ContractError
from .test_contracts import empty_snapshot, leaf


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


if __name__ == "__main__":
    unittest.main()
