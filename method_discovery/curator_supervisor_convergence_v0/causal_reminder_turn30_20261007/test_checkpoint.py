"""Deterministic checkpoint gates. No provider/Task Agent/evaluator imports."""

from __future__ import annotations

import json
from pathlib import Path
import unittest
import uuid

from . import materialize as m
from .freeze import EXPECTED_WORKSPACE_TREE, MATERIALIZED, provider_history_manifest
from .reconstruct_next_request import comparison, reconstruct, sha


class Turn30CheckpointTests(unittest.TestCase):
    def test_source_identity(self):
        m.verify_sources()

    def test_workspace_full_tree(self):
        tree, files = m.source_tree(MATERIALIZED)
        self.assertEqual(tree, EXPECTED_WORKSPACE_TREE)
        self.assertEqual(len(files), 2471)

    def test_workspace_replay_deterministic(self):
        destination = Path("E:\\") / f"fyne_turn30_zero_model_test_{uuid.uuid4().hex}"
        result = m.materialize(destination)
        self.assertEqual(result["workspace_tree_sha256"], EXPECTED_WORKSPACE_TREE)
        self.assertEqual(result["workspace_file_count"], 2471)
        self.assertEqual(len(result["mutations"]), 10)

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
        _, files = m.source_tree(MATERIALIZED)
        paths = {row["path"] for row in files}
        self.assertNotIn("IMPLEMENTATION_COMPLETE.md", paths)
        self.assertNotIn("IMPLEMENTATION_SUMMARY.md", paths)
        self.assertFalse(any(path.startswith(("verifier/", "solution/", "monitor/", ".git/"))
                             for path in paths))

    def test_fresh_destination_enforced(self):
        with self.assertRaisesRegex(RuntimeError, "destination exists"):
            m.materialize(MATERIALIZED)


if __name__ == "__main__":
    unittest.main()
