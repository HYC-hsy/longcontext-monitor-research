"""Deterministic checks only; never import a provider or launch a task."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import unittest
import zipfile

from . import freeze_inputs as frozen


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(name: str):
    return json.loads((frozen.HERE / name).read_text(encoding="utf-8"))


class OfflinePreflight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.identity = load("SOURCE_IDENTITY.json")
        cls.workspace = load("WORKSPACE_REPLAY_CHECKS.json")

    def test_archive_commit_and_source_blobs(self):
        self.assertEqual(self.identity["archive_commit"], frozen.ARCHIVE_COMMIT)
        for path in (frozen.GATEWAY_ZIP, frozen.ARCHIVE / "monitor/audit/dialogue.jsonl",
                     frozen.ARCHIVE / "monitor/task_evidence/public_events.jsonl",
                     frozen.ARCHIVE / "runner/manifest.json",
                     frozen.ARCHIVE / "agent/output.txt"):
            self.assertTrue(frozen.git_blob_matches(path), path)

    def test_reference_source_integrity(self):
        book = frozen.ARCHIVE / "monitor/private/reference.md"
        self.assertTrue(frozen.git_blob_matches(book))
        book_sha = "f6f070f65896a81ba3eeda1b9034b9eb34f23627099e5356e2bde24d24c77355"
        self.assertEqual(sha(book.read_bytes()), book_sha)
        for scene in self.identity["scene_requests"]:
            self.assertIn(book_sha, json.dumps(load(f"{scene}_B_REQUEST_DRAFT.json")))

    def test_gateway_request_is_full_recorded_input(self):
        with zipfile.ZipFile(frozen.GATEWAY_ZIP) as gateway:
            for scene, row in self.identity["scene_requests"].items():
                actual = json.loads(gateway.read(row["gateway_entry"]))
                draft = load(f"{scene}_B_REQUEST_DRAFT.json")
                self.assertEqual(actual, draft)
                self.assertEqual(sha(frozen.canonical(draft)), row["B_request_canonical_sha256"])
                self.assertEqual(sha(gateway.read(row["gateway_entry"])), row["gateway_raw_sha256"])

    def test_two_prompt_replacements_only(self):
        before = (frozen.HERE / "B_SYSTEM.txt").read_text(encoding="utf-8")
        after = (frozen.HERE / "F_SYSTEM.txt").read_text(encoding="utf-8")
        self.assertEqual(sha(before.encode()), self.identity["B_system_sha256"])
        self.assertEqual(sha(after.encode()), self.identity["F_system_sha256"])
        expected = before
        for old, new in frozen.REPLACEMENTS:
            self.assertEqual(expected.count(old), 1)
            expected = expected.replace(old, new)
        self.assertEqual(after, expected)
        self.assertTrue(before.startswith(frozen.ase_prompt()))

    def test_request_difference_system_only(self):
        for scene, row in self.identity["scene_requests"].items():
            before = load(f"{scene}_B_REQUEST_DRAFT.json")
            after = load(f"{scene}_F_REQUEST_DRAFT.json")
            self.assertEqual(set(before), set(after))
            self.assertEqual({key: value for key, value in before.items() if key != "system"},
                             {key: value for key, value in after.items() if key != "system"})
            self.assertEqual(after["system"], (frozen.HERE / "F_SYSTEM.txt").read_text(encoding="utf-8"))
            self.assertEqual(sha(frozen.canonical(after)), row["F_request_canonical_sha256"])
            self.assertEqual([tool["name"] for tool in after["tools"]], row["tool_names"])
            self.assertEqual(after["model"], "claude-opus-4-8")

    def test_no_future_public_cursor_in_draft(self):
        for scene, row in self.identity["scene_requests"].items():
            for arm in ("B", "F"):
                request = load(f"{scene}_{arm}_REQUEST_DRAFT.json")
                text = json.dumps(request, ensure_ascii=False)
                cursors = [int(value) for value in re.findall(r"task/public_events\.jsonl#(\d+)", text)]
                self.assertTrue(all(cursor <= row["public_cutoff"] for cursor in cursors))

    def test_replayed_workspace_cutoffs(self):
        expected = {"120": (2472, "88b7f94d499368196bc8ac1870da4491769598eb4ce567b8c6e12a10bf289a0b"),
                    "161": (2476, "40acbedf3c03d863cac8514298618f74ca999c706466dc426ae8eb638708d2f0")}
        for cursor, (count, tree) in expected.items():
            data = self.workspace["cutoffs"][cursor]
            self.assertEqual(data["ordinary_file_count"], count)
            self.assertEqual(data["workspace_tree_sha256"], tree)
            manifest = frozen.HERE / f"WORKSPACE_FILE_MANIFEST_CURSOR_{cursor}.json"
            self.assertEqual(sha(manifest.read_bytes()), data["file_manifest_sha256"])
        self.assertEqual(self.workspace["cutoffs"]["161"]["workspace_tree_sha256"],
                         self.workspace["retained_final_tar_tree_sha256"])

    def test_no_live_execution_entry_in_this_package(self):
        for name in ("freeze_inputs.py", "check_workspace.py"):
            source = (frozen.HERE / name).read_text(encoding="utf-8")
            for forbidden in ("NativeToolClient(", "MonitorAgent(", "agent_runner_loop(",
                              "client.chat(", "provider.send(", "subprocess.Popen("):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
