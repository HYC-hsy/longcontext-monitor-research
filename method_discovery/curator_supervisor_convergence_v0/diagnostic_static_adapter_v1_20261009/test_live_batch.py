"""No-model batch sequencing and stopping tests."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from . import adapter
from .live_batch import execute_slots, slots


class BatchTests(unittest.TestCase):
    def test_exact_order_independent_slots(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            visited = []
            def launch(slot, scene, arm):
                visited.append((slot.name, scene, arm))
                return {"terminal": "wait_proposal", "provider_requests": 1}
            records = execute_slots(root, launch)
            self.assertEqual(len(records), 12)
            self.assertEqual(visited, list(slots()))
            self.assertEqual(json.loads((root / "BATCH_PROGRESS.json").read_text())["unstarted"], [])

    def test_first_infrastructure_failure_preserves_unstarted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            records = execute_slots(root, lambda *_: {"terminal": "protocol_or_infrastructure_failure",
                                                      "provider_requests": 1})
            self.assertEqual(len(records), 1)
            progress = json.loads((root / "BATCH_PROGRESS.json").read_text())
            self.assertEqual(len(progress["unstarted"]), 11)
            self.assertEqual(progress["started"][0]["slot"], "C01-R1-B_static")

    def test_valid_wrong_or_undecided_does_not_remove_next_slot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outcomes = iter(["release_proposal", "valid_capped"] + ["wait_proposal"] * 10)
            records = execute_slots(root, lambda *_: {"terminal": next(outcomes), "provider_requests": 300})
            self.assertEqual(len(records), 12)
            self.assertEqual(records[1]["terminal"], "valid_capped")
