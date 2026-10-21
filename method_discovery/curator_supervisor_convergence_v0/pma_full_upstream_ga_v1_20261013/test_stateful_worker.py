"""Real subprocess/spool with finite role replies; no model network."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from .event_spool import EventClient


class StatefulWorkerTests(unittest.TestCase):
    def test_private_worker_commits_and_confirms_one_reminder(self):
        repo = Path(__file__).resolve().parents[3]
        ga = repo / "GenericAgent-main"
        script = Path(__file__).with_name("stateful_memory_worker.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requests, responses = root / "spool/requests", root / "spool/responses"
            requests.mkdir(parents=True); responses.mkdir()
            private = root / "private"
            replies = root / "replies.json"
            replies.write_text(json.dumps([{"role": role, "shape": shape}
                for role, shape in [("maintenance", "empty"), ("audit", "clean"),
                    ("selection", "silent"), ("maintenance", "observed_state"),
                    ("audit", "clean"), ("selection", "remind")]]),
                encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONPATH"] = os.pathsep.join([str(repo), str(ga)])
            process = subprocess.Popen([sys.executable, "-B", str(script),
                "--run-id", "r", "--task-id", "t", "--private-root", str(private),
                "--requests", str(requests), "--responses", str(responses),
                "--fake-replies", str(replies)], env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                ready = private / "worker_ready.json"
                until = time.monotonic() + 10
                while not ready.exists() and time.monotonic() < until:
                    self.assertIsNone(process.poll())
                    time.sleep(.02)
                self.assertTrue(ready.exists())
                client = EventClient(requests, responses, "r", "t",
                    deadline_monotonic=time.monotonic() + 20,
                    worker_exit=private / "worker_exit.json")
                initial = client.exchange("initialize", task="Synthetic task")
                self.assertEqual(initial["state_version"], 1)
                actions = [{"id": "tool-1", "name": "touch", "arguments": {}}]
                receipts = [{"tool_use_id": "tool-1", "status": "ok",
                             "result": {"written": True}}]
                updated = client.exchange("action_batch", batch_id="batch-1",
                    turn=1, actions=actions, receipts=receipts)
                self.assertEqual(updated["status"], "committed_reminder_ready")
                self.assertTrue(updated["pending_reminder"])
                prepared = client.exchange("prepare_task", request_id="task-2",
                    messages=[{"role": "user", "content": "Synthetic task"}])
                self.assertTrue(prepared["has_reminder"])
                self.assertIn("Auxiliary memory information",
                              prepared["messages"][-1]["content"])
                client.exchange("confirm_task", cycle_id=prepared["cycle_id"],
                    binding=prepared["binding"], accepted=True)
                finished = client.exchange("finish", terminal={"result": "done"})
                self.assertTrue(finished["closed"])
                self.assertFalse((requests / "memory.sqlite3").exists())
                self.assertTrue((private / "memory.sqlite3").exists())
            finally:
                private.mkdir(exist_ok=True)
                (private / "stop.request").touch()
                try:
                    _, stderr = process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    _, stderr = process.communicate(timeout=5)
                self.assertEqual(process.returncode, 0,
                                 stderr.decode("utf-8", errors="replace"))


if __name__ == "__main__":
    unittest.main()
