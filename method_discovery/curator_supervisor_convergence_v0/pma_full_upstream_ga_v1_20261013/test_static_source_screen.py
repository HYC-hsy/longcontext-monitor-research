"""End-to-end fixed-trace shadow entry checks; all provider calls intercepted."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from static_source_screen import HERE, MANIFEST, projected_events, run_fake


class StaticScreenTests(unittest.TestCase):
    def test_six_independent_slots_exact_calls_and_public_projection(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertIs(manifest["execution_authorized"], False)
        self.assertEqual(manifest["conditions"], ["U", "S", "R"])
        with TemporaryDirectory() as directory:
            root = Path(directory) / "shadow"
            rows = asyncio.run(run_fake(manifest, root))
            self.assertEqual(len(rows), 6)
            self.assertEqual(sum(row["logical_phase_calls"] for row in rows), 210)
            self.assertEqual([row["logical_phase_calls"] for row in rows], [28] * 3 + [42] * 3)
            self.assertEqual(len({row["run_id"] for row in rows}), 6)
            for row in rows:
                self.assertEqual(row["provider_attempts"], 0)
                self.assertFalse(row["input_sent"])
                self.assertFalse(row["task_completed"])
                slot = root / row["run_id"]
                bank = json.loads((slot / "memory.json").read_text(encoding="utf-8"))
                self.assertEqual(len(bank["knowledge"]), 0 if row["variant"] == "U" else 1)
                self.assertFalse((slot / "episode" / "task_end.json").exists())
                events = [json.loads(line)["event"] for line in
                          (slot / "episode" / "events.jsonl").read_text(encoding="utf-8").splitlines()]
                self.assertTrue(all("result" not in event and "thinking" not in event
                                    and "old_memory_bank" not in event for event in events))
                self.assertTrue(all(event["run_id"] == row["run_id"] for event in events))
                requests = [json.loads(line) for line in
                            (slot / "requests.jsonl").read_text(encoding="utf-8").splitlines()]
                self.assertEqual(len(requests), row["logical_phase_calls"])
                if row["variant"] != "U":
                    self.assertIn("bound_evidence", requests[1]["prompt"])
                    self.assertIn("<memory_refs>", requests[1]["response_content"])
                    self.assertTrue(any(json.loads(line)["result"]["status"] == "reminder"
                        for line in (slot / "episode" / "events.jsonl").read_text(encoding="utf-8").splitlines()))

    def test_live_mode_rejected_before_any_provider_request(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "must_not_exist"
            result = subprocess.run([sys.executable, str(HERE / "static_source_screen.py"),
                "--mode", "live", "--output", str(output)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("requires a later authorization", result.stderr)
            self.assertFalse(output.exists())

    def test_cutoff_identity_and_source_hashes(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for case in manifest["cases"]:
            events = projected_events(case, "new-run")
            self.assertEqual(len(events), case["inclusive_event_sequence"])
            self.assertEqual(events[0]["kind"], "task_start")
            self.assertTrue(any(e["kind"] == "actor_step" for e in events))
            self.assertNotIn("result", events[0])


if __name__ == "__main__":
    unittest.main()
