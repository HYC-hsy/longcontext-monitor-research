"""No-total-deadline spool behavior for the opt-in stateful candidate."""

import tempfile
import threading
import time
import unittest
from pathlib import Path

from .event_spool import EventClient, SpoolError, _atomic_json


class StatefulSpoolTests(unittest.TestCase):
    def test_unbounded_episode_waits_for_a_later_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requests, responses = root / "requests", root / "responses"
            requests.mkdir(); responses.mkdir()
            client = EventClient(requests, responses, "r", "t",
                deadline_monotonic=None, worker_exit=root / "worker_exit.json")
            def reply():
                while not list(requests.glob("*.json")):
                    time.sleep(.005)
                request = next(requests.glob("*.json"))
                time.sleep(.05)
                _atomic_json(responses / request.name, {"run_id": "r",
                    "task_id": "t", "event_id": request.stem,
                    "status": "ok", "result": {"ready": True}})
            thread = threading.Thread(target=reply)
            thread.start()
            try:
                self.assertEqual(client.exchange("initialize"), {"ready": True})
            finally:
                thread.join(timeout=2)
            self.assertFalse(thread.is_alive())

    def test_worker_exit_stops_unknown_wait_without_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requests, responses = root / "requests", root / "responses"
            requests.mkdir(); responses.mkdir()
            exit_file = root / "worker_exit.json"
            client = EventClient(requests, responses, "r", "t",
                deadline_monotonic=None, worker_exit=exit_file)
            def stop():
                while not list(requests.glob("*.json")):
                    time.sleep(.005)
                _atomic_json(exit_file, {"reason": "failed"})
            thread = threading.Thread(target=stop)
            thread.start()
            try:
                with self.assertRaisesRegex(SpoolError, "result unknown"):
                    client.exchange("initialize")
            finally:
                thread.join(timeout=2)
            self.assertEqual(len(list(requests.glob("*.json"))), 1)


if __name__ == "__main__":
    unittest.main()
