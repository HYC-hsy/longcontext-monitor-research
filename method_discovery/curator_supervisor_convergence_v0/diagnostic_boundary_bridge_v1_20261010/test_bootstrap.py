"""Zero-model checks of the frozen C02 root-review bootstrap."""

import tempfile
import unittest
import json
from pathlib import Path

from .archive_batch import build as build_archive
from .freeze_inputs import build_requests
from .bootstrap import candidate_config, prepare_agent
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009 import adapter
from monitor_agent_core.provider import MonitorProviderClient  # noqa: E402


class BootstrapTests(unittest.TestCase):
    def test_archive_crc_and_member_hashes_without_model_calls(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "raw"
            root.mkdir()
            (root / "FROZEN_RUN_IDENTITY.json").write_text(
                json.dumps({"source_commit": "offline-test"}), encoding="utf-8")
            (root / "BATCH_RESULT.json").write_text(
                json.dumps({"slots": [], "started_count": 0, "planned_count": 12}),
                encoding="utf-8")
            outcome = build_archive(root, Path(temporary) / "archive")
            self.assertEqual(outcome["started_slots"], 0)
            self.assertGreater(outcome["indexed_files"], 10)

    def test_frozen_temporary_context_reconstructs(self):
        requests, _ = build_requests()
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary) / "fixture"
            adapter.materialize("C02", fixture)
            for arm, request in requests.items():
                with self.subTest(arm=arm):
                    client = MonitorProviderClient("claude_monitor_opus48", candidate_config())
                    agent = prepare_agent(fixture, request, client)
                    text = agent._active_working_context()
                    self.assertEqual(text, request["messages"][-1]["content"][0]["text"])
                    self.assertEqual(agent.client.history, request["messages"][:-1])
                    self.assertIsNone(agent.crs.root_contrast)
                    self.assertIsNone(agent.crs.root_reorientation)


if __name__ == "__main__":
    unittest.main()
