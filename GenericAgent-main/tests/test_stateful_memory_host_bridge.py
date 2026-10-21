"""Actual GA Task loop plus private subprocess/spool; finite local model replies."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import agent_loop
import llmcore
from research_runtime import research_context
from tests.test_stateful_memory_ga_bridge import SyntheticToolHandler
from tests.test_task_complete_response import ScriptedServer, stream


class StatefulHostBridgeTests(unittest.TestCase):
    def test_ga_request_consumes_private_worker_reminder_once(self):
        repo = Path(__file__).resolve().parents[2]
        run = repo / "method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013"
        sys.path.insert(0, str(run))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requests, responses = root / "spool/requests", root / "spool/responses"
            requests.mkdir(parents=True); responses.mkdir()
            private = root / "host_private"
            replies = root / "roles.json"
            replies.write_text(json.dumps([{"role": role, "shape": shape}
                for role, shape in [("maintenance", "empty"), ("audit", "clean"),
                    ("selection", "silent"), ("maintenance", "observed_state"),
                    ("audit", "clean"), ("selection", "remind"),
                    ("maintenance", "empty"), ("audit", "clean"),
                    ("selection", "silent")]]), encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONPATH"] = os.pathsep.join([str(repo), str(repo / "GenericAgent-main")])
            worker = subprocess.Popen([sys.executable, "-B", str(run / "stateful_memory_worker.py"),
                "--run-id", "host-ga-test", "--task-id", "synthetic-local-task",
                "--private-root", str(private), "--requests", str(requests),
                "--responses", str(responses), "--fake-replies", str(replies)],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                until = time.monotonic() + 10
                while not (private / "worker_ready.json").exists() and time.monotonic() < until:
                    self.assertIsNone(worker.poll())
                    time.sleep(.02)
                self.assertTrue((private / "worker_ready.json").exists())
                overrides = {"GA_STATEFUL_MEMORY_ENABLED": "1",
                    "GA_STATEFUL_MEMORY_MODE": "live", "GA_STATEFUL_LIVE_AUTHORIZED": "1",
                    "GA_STATEFUL_REQUESTS": str(requests),
                    "GA_STATEFUL_RESPONSES": str(responses),
                    "GA_BENCH_RUN_ID": "host-ga-test",
                    "GA_BENCH_TASK_ID": "synthetic-local-task",
                    "GA_TASK_COMPLETE_RESPONSE": "1",
                    "GA_PROVIDER_MAX_RETRIES": "0",
                    "GA_TASK_DEADLINE_EPOCH": str(time.time() + 30),
                    "GA_POS_ENABLED": "0", "GA_PMA_UPSTREAM_ENABLED": "0",
                    "GA_PMA_ENABLED": "0", "GA_MONITOR_ENABLED": "0"}
                with mock.patch.dict(os.environ, overrides), ScriptedServer([
                    stream(tools=["touch"]), stream(tools=["touch"]),
                    stream(text="Synthetic task complete.", stop="end_turn")]) as server:
                    backend = llmcore.NativeClaudeSession({
                        "apikey": "synthetic-only", "apibase": server.url,
                        "model": "claude-synthetic", "max_tokens": 100,
                        "max_retries": 0, "stream": True, "timeout": 1,
                        "read_timeout": 5})
                    client = llmcore.NativeToolClient(backend)
                    client.backend.tools = [{"type": "function", "function": {
                        "name": "touch", "description": "isolated synthetic file",
                        "parameters": {"type": "object", "properties": {}}}}]
                    handler = SyntheticToolHandler(root)
                    with research_context({"task_id": "synthetic-local-task",
                                           "run_id": "host-ga-test"}, lambda _: None):
                        agent_loop.exhaust(agent_loop.agent_runner_loop(client,
                            "Synthetic system", "Create synthetic artifact", handler,
                            client.backend.tools, max_turns=3, verbose=False))
                self.assertEqual(len(server.payloads), 3)
                self.assertEqual(handler.calls, 2)
                inserts = [raw.count(b"Auxiliary memory information")
                           for raw in server.payloads]
                self.assertEqual(inserts, [0, 1, 1])
                self.assertTrue((private / "memory.sqlite3").exists())
                self.assertFalse((root / "memory.sqlite3").exists())
            finally:
                private.mkdir(exist_ok=True)
                (private / "stop.request").touch()
                try:
                    _, stderr = worker.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    worker.kill()
                    _, stderr = worker.communicate(timeout=5)
                self.assertEqual(worker.returncode, 0,
                    stderr.decode("utf-8", errors="replace"))
                sys.path.remove(str(run))


if __name__ == "__main__":
    unittest.main()
