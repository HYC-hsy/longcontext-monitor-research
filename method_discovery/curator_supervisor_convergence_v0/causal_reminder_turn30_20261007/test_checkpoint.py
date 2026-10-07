"""Deterministic checkpoint gates. No provider/Task Agent/evaluator imports."""

from __future__ import annotations

import json
from pathlib import Path
import unittest
import uuid

from . import materialize as m
from .freeze import EXPECTED_WORKSPACE_TREE, MATERIALIZED, provider_history_manifest
from .git_state import EXPECTED_HEAD_TREE, EXPECTED_TURN30_STATUS, certify_git_state
from .reconstruct_next_request import NEXT_SHA256, comparison, reconstruct, sha
from .runtime_checkpoint import certify as certify_runtime, recovered_state
from .materialize import HERE


class Turn30CheckpointTests(unittest.TestCase):
    def test_source_identity(self):
        m.verify_sources()

    def test_workspace_full_tree(self):
        tree, files = m.source_tree(MATERIALIZED, exclude_git=True)
        self.assertEqual(tree, EXPECTED_WORKSPACE_TREE)
        self.assertEqual(len(files), 2472)
        self.assertEqual(m.sha_file(MATERIALIZED / m.ORIGINAL_TASK_SIDECAR), m.EXPECTED[m.TASK])
        self.assertTrue((MATERIALIZED / ".git" / "index").is_file())

    def test_workspace_replay_deterministic(self):
        destination = Path("E:\\") / f"fyne_turn30_zero_model_test_{uuid.uuid4().hex}"
        result = m.materialize(destination)
        self.assertEqual(result["workspace_tree_sha256"], EXPECTED_WORKSPACE_TREE)
        self.assertEqual(result["workspace_file_count"], 2472)
        self.assertEqual(len(result["mutations"]), 10)
        self.assertEqual(certify_git_state(destination)["turn30_status_porcelain_v1_untracked_all"],
                         EXPECTED_TURN30_STATUS)

    def test_git_state_certification(self):
        result = certify_git_state(MATERIALIZED)
        self.assertEqual(result["clean_historical_head_tree"], EXPECTED_HEAD_TREE)
        self.assertEqual(result["turn30_index_tree"], EXPECTED_HEAD_TREE)
        self.assertEqual(result["turn30_status_porcelain_v1_untracked_all"], EXPECTED_TURN30_STATUS)
        self.assertTrue(result["git_diff_available"])

    def test_git_absence_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "not Git-backed"):
            certify_git_state(Path("E:\\") / f"nonexistent_git_checkpoint_{uuid.uuid4().hex}")

    def test_sidecar_historical_provenance(self):
        rows = m.jsonl(m.PUBLIC_EVENTS)
        early = next(row for row in rows if row["archive_sequence"] == 4)
        self.assertEqual(early["task_turn"], 2)
        self.assertIn(m.ORIGINAL_TASK_SIDECAR, json.dumps(early, ensure_ascii=False))
        self.assertIn(".git", json.dumps(early, ensure_ascii=False))

    def test_unsupported_shell_mutation_fails_closed(self):
        event = {"task_turn": 30, "boundary": "post_tool_pre_next_llm",
                 "tool_calls": [{"name": "code_run", "args": {"script": "touch /app/unknown"}}]}
        with self.assertRaisesRegex(RuntimeError, "Unsupported shell mutation risk"):
            m._check_shell_calls([event])

    def test_provider_history_lossless_reconstruction(self):
        original, reconstructed, _, report = comparison()
        self.assertEqual(original["messages"], reconstructed["messages"])
        history = provider_history_manifest(reconstructed["messages"])
        self.assertEqual(history["history_item_count"], 51)
        self.assertTrue(history["all_tool_calls_have_results"])

    def test_model_visible_canonical_equality(self):
        original, reconstructed, _, report = comparison()
        self.assertTrue(report["model_visible_equal"])
        self.assertEqual(sha(original), sha(reconstructed))
        self.assertEqual(report["mismatches"], [])

    def test_no_semantic_field_ignored_as_transport(self):
        _, _, _, report = comparison()
        self.assertEqual(report["ignored_transport_fields"], [])
        self.assertEqual(set(report["exact_equal_fields"]),
                         {"model", "messages", "max_tokens", "stream", "thinking",
                          "context_management", "metadata", "tools", "system"})

    def test_working_checkpoint_visible_exactly(self):
        _, reconstructed, working = reconstruct()
        prompt = reconstructed["messages"][-1]["content"][-1]["text"]
        self.assertEqual(prompt, working["next_prompt"])
        self.assertEqual(working["call"]["name"], "update_working_checkpoint")
        self.assertEqual(json.loads(working["result"]["content"])["result"],
                         "working key_info updated")

    def test_future_turns_not_in_replay_input(self):
        events = m.jsonl(m.PUBLIC_EVENTS)
        mutations = [call for row in events if row["task_turn"] <= 30
                     and row["boundary"] == "post_tool_pre_next_llm"
                     for call in row["tool_calls"] if call["name"] in ("file_patch", "file_write")]
        self.assertEqual(len(mutations), 10)
        self.assertTrue(all(row["archive_sequence"] <= 58 for row in events
                            if row["task_turn"] <= 30))
        _, files = m.source_tree(MATERIALIZED, exclude_git=True)
        paths = {row["path"] for row in files}
        self.assertNotIn("IMPLEMENTATION_COMPLETE.md", paths)
        self.assertNotIn("IMPLEMENTATION_SUMMARY.md", paths)
        self.assertFalse(any(path.startswith(("verifier/", "solution/", "monitor/"))
                             for path in paths))

    def test_runtime_state_has_true_pending_and_history(self):
        state = recovered_state()
        self.assertEqual(len(state["backend_history"]), 50)
        self.assertEqual(state["handler_current_turn"], 30)
        self.assertEqual(state["next_task_turn"], 31)
        self.assertEqual(state["native_tool_client_pending_tool_ids"],
                         [state["turn30_tool_result"]["tool_use_id"]])
        self.assertEqual(len(state["history_info"]), 30)
        self.assertEqual(sha(state["handler_working_state"]),
                         "bb0590c60c8033c9ba1e11e701cceae0e4429adcccd73d5ee7bbe912fd6c7d64")
        self.assertFalse(any("cache_control" in block for msg in state["backend_history"]
                             for block in msg["content"]))

    def test_production_request_builder_stops_before_network(self):
        _, generated, report = certify_runtime()
        self.assertFalse(report["network_send_attempted"])
        self.assertTrue(report["model_visible_equal"])
        self.assertEqual(report["original_raw_bytes_sha256"], NEXT_SHA256)
        self.assertEqual(len(report["exact_equal_fields"]), 9)
        self.assertEqual(report["ignored_transport_fields"], [])
        self.assertEqual(report["mismatches"], [])

    def test_runtime_request_deterministic(self):
        _, first, _ = certify_runtime()
        _, second, _ = certify_runtime()
        self.assertEqual(first, second)

    def test_runtime_archive_excludes_private_profile_values(self):
        state = recovered_state()
        encoded = json.dumps(state, ensure_ascii=False)
        self.assertNotIn("isolated-local-channel", encoded)
        self.assertNotIn("http://127.0.0.1:18765", encoded)

    def test_no_continuation_authorization_and_git_requirement(self):
        protocol = json.loads((HERE / "PROTOCOL.json").read_text(encoding="utf-8"))
        self.assertFalse(protocol["provider_execution_authorized"])
        self.assertFalse(protocol["task_agent_execution_authorized"])
        self.assertFalse(protocol["control_continuation_authorized"])
        self.assertIn("Git-backed", protocol["future_continuation_workspace_requirement"])

    def test_fresh_destination_enforced(self):
        with self.assertRaisesRegex(RuntimeError, "destination exists"):
            m.materialize(MATERIALIZED)


if __name__ == "__main__":
    unittest.main()
