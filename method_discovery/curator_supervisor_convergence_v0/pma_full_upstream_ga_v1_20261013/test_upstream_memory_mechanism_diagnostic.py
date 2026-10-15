"""Zero-network guards for the archived-input original-U diagnostic."""
import asyncio
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import litellm

import upstream_memory_mechanism_diagnostic as diagnostic


class DiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen = diagnostic.prepare()

    def test_fixed_identity_and_allowlisted_variants(self):
        self.assertEqual(len(self.frozen["checks"]), 14)
        self.assertEqual(sum(u["stage_count"] for u in self.frozen["units"]), 44)
        self.assertEqual(len(self.frozen["units"]), 40)
        for label in ("A1", "A2", "A3", "P1", "H1"):
            changed = [u for u in self.frozen["units"] if u["label"] == label]
            self.assertEqual(len(changed), 4)
            self.assertEqual(len({u["prompt"] for u in changed}), 1)
        self.assertIn("[fJCxMuJa]", self.frozen["units"][4]["prompt"])

    def test_original_process_fake_updates_phase2(self):
        result = asyncio.run(diagnostic.fake_cycle())
        self.assertEqual(result["requests"], 2)
        self.assertTrue(result["phase2_contains_updated_bank"])
        self.assertEqual(result["network_requests"], 0)

    def test_real_send_boundary_with_fake_response(self):
        unit = next(u for u in self.frozen["units"] if u["label"] == "H0")
        profile = diagnostic.profile_identity(Path("E:/LongContext/monitor_config/models.local.json"))[0]
        sent = []

        async def fake_completion(**kwargs):
            sent.append(kwargs)
            return {"model": "fake-transport", "usage": {"prompt_tokens": 1},
                    "choices": [{"message": {"content": "<no_intervention/>",
                                              "tool_calls": None}, "finish_reason": "stop"}]}

        with TemporaryDirectory() as temp, patch.object(litellm, "acompletion", fake_completion):
            result = asyncio.run(diagnostic.execute_unit(self.frozen, unit, profile,
                                                         Path(temp) / "unit"))
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["logical_calls"], 1)
            self.assertEqual(result["observable_lower_calls"], 1)
            self.assertEqual(sent[0]["model"], "anthropic/claude-opus-4-8")
            self.assertEqual(sent[0]["messages"][-1]["content"][0]["text"], unit["prompt"])
            self.assertEqual(len((Path(temp) / "unit" / "requests.jsonl").read_text(encoding="utf-8").splitlines()), 1)

    def test_phase1_final_failure_blocks_phase2(self):
        unit = next(u for u in self.frozen["units"] if u["mode"] == "original_process")
        profile = diagnostic.profile_identity(Path("E:/LongContext/monitor_config/models.local.json"))[0]
        sent = []

        async def fail_completion(**kwargs):
            sent.append(kwargs)
            raise RuntimeError("synthetic final transport failure")

        with TemporaryDirectory() as temp, patch.object(litellm, "acompletion", fail_completion):
            result = asyncio.run(diagnostic.execute_unit(self.frozen, unit, profile,
                                                         Path(temp) / "unit"))
            self.assertEqual(result["status"], "stopped_failure")
            self.assertEqual(result["observable_lower_calls"], len(sent))
            self.assertEqual(len(sent), 3)  # Upstream retry limit, no new outer retry.
            blocked = (Path(temp) / "unit" / "blocked_requests.jsonl").read_text(encoding="utf-8")
            self.assertIn('"sent": false', blocked)

    def test_mismatched_authorization_rejected_without_send(self):
        with TemporaryDirectory() as temp:
            parent = Path(temp)
            manifest = copy.deepcopy(self.frozen)
            manifest.update(code_commit=diagnostic.code_commit(), output_root=str(parent / "out"),
                            profile_public={}, batch_id="synthetic")
            (parent / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (parent / "auth.json").write_text(json.dumps({"execution_authorized": True}),
                                              encoding="utf-8")
            with self.assertRaises(PermissionError):
                diagnostic.check_authorized(parent / "manifest.json", parent / "auth.json",
                                            Path("E:/LongContext/monitor_config/models.local.json"))
            self.assertFalse((parent / "out").exists())


if __name__ == "__main__":
    unittest.main()
