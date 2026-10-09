"""Zero-model tests. Container probes are reported separately, not faked here."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from . import adapter
from method_discovery.curator_supervisor_convergence_v0.diagnostic_flex_preflight_v0_20261009 import freeze_inputs


def load_workspace_class():
    path = freeze_inputs.REPO / "GenericAgent-main/monitor_agent_core/workspace.py"
    spec = importlib.util.spec_from_file_location("static_diagnostic_workspace", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MonitorWorkspace


class StaticOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="static-diagnostic-tests-")
        cls.root = Path(cls.temp.name)
        cls.manifests = {scene: adapter.materialize(scene, cls.root / scene)
                         for scene in adapter.SCENES}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_request_only_common_note_and_frozen_replacements(self):
        for scene in adapter.SCENES:
            check = adapter.request_checks(scene)
            self.assertNotEqual(check["archived_B_sha256"], check["B_static_sha256"])
            self.assertNotEqual(check["B_static_sha256"], check["F_static_sha256"])
            b, f = adapter.request(scene, "B"), adapter.request(scene, "F")
            self.assertEqual(b["messages"], f["messages"])
            self.assertEqual(b["tools"], f["tools"])
            self.assertEqual({k: v for k, v in b.items() if k != "system"},
                             {k: v for k, v in f.items() if k != "system"})
            self.assertIn(adapter.COMMON_NOTE, b["system"])
            self.assertIn(adapter.COMMON_NOTE, f["system"])
            self.assertNotIn("temperature", b)

    def test_frozen_order_and_budget(self):
        self.assertEqual(adapter.ORDER, [("C01", 1, "B", "F"), ("C02", 1, "F", "B"),
                                         ("C01", 2, "F", "B"), ("C02", 2, "B", "F"),
                                         ("C01", 3, "B", "F"), ("C02", 3, "F", "B")])
        self.assertEqual(adapter.LIMITS, {"provider_requests_including_retries": 12,
                                          "tool_calls_including_failures_and_polls": 48,
                                          "wall_seconds": 1200, "new_code_run_seconds": 60,
                                          "cumulative_tool_wait_seconds": 600})

    def test_materialized_workspace_and_public_prefix(self):
        for scene, (_, cursor, line) in adapter.SCENES.items():
            fixture, manifest = self.root / scene, self.manifests[scene]
            self.assertEqual(manifest["public"]["records"], cursor)
            self.assertEqual(manifest["synopsis"]["records"], cursor)
            self.assertEqual(manifest["dialogue_records"], line)
            self.assertFalse(manifest["isolation_certified"])
            self.assertTrue((fixture / "app/menu.go").is_file())
            self.assertTrue((fixture / "task_evidence/original_task.txt").is_file())
            self.assertEqual(len((fixture / "task_evidence/public_events.jsonl").read_bytes().splitlines()), cursor)
            self.assertEqual(len((fixture / "monitor_private/audit/dialogue.jsonl").read_bytes().splitlines()), line)

    def test_visible_files_have_hash_and_cutoff_basis(self):
        for scene, manifest in self.manifests.items():
            for item in manifest["visible_files"]:
                path = self.root / scene / item["mount"] / item["path"]
                self.assertEqual(adapter.sha(path.read_bytes()), item["sha256"])
                self.assertTrue(item["cutoff_basis"])
            listed = {x["path"] for x in manifest["visible_files"]}
            self.assertNotIn("RUNNER_MANIFEST.json", listed)
            self.assertNotIn("native_result.json", listed)

    def test_historical_sessions_are_capped_and_not_resumed(self):
        for scene, manifest in self.manifests.items():
            outputs = manifest["outputs"]
            self.assertIn("Historical IDs are never rebound", outputs["session_resume_rule"])
            self.assertEqual(outputs["unavailable_sessions"], {})
            self.assertGreater(len(outputs["historical_completed_outputs"]), 0)
        self.assertEqual(len(self.manifests["C01"]["outputs"]["historical_completed_outputs"]), 11)
        self.assertEqual(len(self.manifests["C02"]["outputs"]["historical_completed_outputs"]), 18)

    def test_missing_historical_output_is_unavailable(self):
        receipt = {"event": "tool_result", "data": {"session_id": "historical", "stdout": "partial",
                   "status": "running", "next_read": {"session_id": "historical"}, "unread_bytes": 0}}
        with tempfile.TemporaryDirectory() as root:
            result = adapter._historic_outputs([receipt], Path(root) / "private", Path(root) / "absent")
            self.assertIn("historical", result["unavailable_sessions"])
            self.assertEqual(result["historical_completed_outputs"], {})

    def test_file_read_boundary_and_private_write_isolation(self):
        Workspace = load_workspace_class()
        first = self.root / "C01"
        second = self.root / "C02"
        view = Workspace(first / "task_evidence", first / "monitor_private",
                         task_mounts={"workspace": first / "app"})
        for path in ("E:/research/secret", "/etc/passwd", "task/../future", "monitor/../../other_arm"):
            with self.assertRaises((ValueError, FileNotFoundError)):
                view.resolve_read(path)
        view.write_text("monitor/test_private_note", "first-only")
        self.assertFalse((second / "monitor_private/test_private_note").exists())
        with self.assertRaises(ValueError):
            view.write_text("task/workspace/menu.go", "bad")

    def test_control_proposal_is_record_only_and_later_tools_skipped(self):
        for scene, name, args, expected in (("C01", "wait", {"after_turns": 1}, "wait_proposal"),
                                           ("C01", "intervene", {"message": "a"}, "intervention_proposal"),
                                           ("C02", "allow_complete", {
                                               "release_blocking_state": "state", "grounding": "task",
                                               "ground_refs": ["task/original_task.txt"],
                                               "exclusion_reason": "evidence", "observation_refs": ["obs:code:one"]},
                                               "release_proposal")):
            run = adapter.FakeDiagnostic(scene)
            self.assertEqual(run.attempt([{"name": name, "arguments": args},
                                          {"name": "file_read", "arguments": {"path": "task/original_task.txt"}}]),
                             expected)
            self.assertEqual(run.events[-1]["kind"], "not_executed_after_proposal")
            with self.assertRaises(RuntimeError):
                run.attempt([])

    def test_conflict_and_invalid_args(self):
        run = adapter.FakeDiagnostic("C01")
        self.assertIsNone(run.attempt([{"name": "intervene", "arguments": {"message": ""}}]))
        self.assertEqual(run.events[-1]["reason"], "invalid_schema")
        self.assertEqual(run.attempt([{"name": "wait", "arguments": {"after_turns": 1}},
                                      {"name": "intervene", "arguments": {"message": "x"}}]),
                         "protocol_invalid_conflicting_control")

    def test_budgets_keep_undecided_trace(self):
        run = adapter.FakeDiagnostic("C01")
        for _ in range(12):
            self.assertIsNone(run.attempt([]))
        self.assertEqual(run.attempt([]), "undecided_budget")
        self.assertEqual(len(run.events), 13)
        tools = adapter.FakeDiagnostic("C01")
        self.assertEqual(tools.attempt([{"name": "file_read", "arguments": {"path": "task/original_task.txt"}}] * 49),
                         "undecided_budget")
        self.assertEqual(tools.tool_calls, 49)
        wait = adapter.FakeDiagnostic("C01")
        self.assertEqual(wait.attempt([], tool_wait_seconds=600), "undecided_budget")
        wall = adapter.FakeDiagnostic("C01")
        self.assertEqual(wall.attempt([], elapsed_seconds=1200), "undecided_budget")

    def test_new_command_limit_and_live_provider_fail_closed(self):
        run = adapter.FakeDiagnostic("C01")
        self.assertIsNone(run.attempt([{"name": "code_run", "arguments": {"code": "pass", "timeout": 61}}]))
        self.assertEqual(run.events[-1]["reason"], "static_command_timeout_cap")
        with self.assertRaises(RuntimeError):
            adapter.NoLiveProvider().send({"model": "claude-opus-4-8"})


if __name__ == "__main__":
    unittest.main()
