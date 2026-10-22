import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gap_store import GapMemory
from memory_agent.memory.universal_memory import MemoryEntry


class GapMemoryTests(unittest.TestCase):
    def test_staging_preserves_old_and_unmentioned_entries(self):
        store = GapMemory()
        store.begin()
        old = store.stage_save("Acceptance remains unverified")
        keep = store.stage_save("Input contract is unknown")
        self.assertEqual(store.entries, [])
        store.commit()
        before = store.entries
        store.begin()
        self.assertTrue(store.stage_delete(old))
        new = store.stage_save("Valid test failed: required behavior is absent")
        self.assertEqual(store.entries, before)
        store.commit()
        self.assertEqual([e.id for e in store.entries], [keep, new])
        self.assertIsInstance(store.entries[0], MemoryEntry)
        self.assertTrue(store.entries[0].created_at)

    def test_discard_and_external_reads_cannot_change_official_entries(self):
        store = GapMemory()
        store.begin()
        key = store.stage_save("Existing gap")
        store.commit()
        store.entries[0].content = "external mutation"
        store.begin()
        store.stage_delete(key)
        store.stage_save("Unapproved replacement")
        store.discard()
        self.assertEqual(store.entries[0].content, "Existing gap")

    def test_original_save_and_load_serialize_only_official_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gaps.json"
            store = GapMemory()
            ordinary = store.save_knowledge("Normal memory")
            store.begin()
            key = store.stage_save("Old official gap")
            store.commit()
            store.begin()
            store.stage_delete(key)
            store.stage_save("Candidate gap")
            store.save_to_file(path)
            original = path.read_bytes()
            self.assertEqual(store.entries[0].id, key)
            loaded = GapMemory.load_from_file(path)
            self.assertEqual(loaded.entries, store.entries)
            self.assertEqual(loaded.get(ordinary).content, "Normal memory")
            self.assertIsNone(loaded.candidate)
            self.assertEqual(json.loads(original)["gaps"][0]["id"], key)
            store.discard()

    def test_failed_commit_keeps_official_group_and_normal_writes(self):
        store = GapMemory()
        store.begin()
        old = store.stage_save("Old gap")
        store.commit()
        store.begin()
        store.stage_delete(old)
        store.stage_save("Replacement")
        ordinary = store.save_knowledge("Already applied")
        with patch("gap_store.deepcopy", side_effect=RuntimeError("fixture")):
            with self.assertRaises(RuntimeError):
                store.commit()
        self.assertEqual(store.to_dict()["gaps"][0]["id"], old)
        self.assertEqual(store.get(ordinary).content, "Already applied")

    def test_invalid_content_and_unknown_delete_do_not_mutate_candidate(self):
        store = GapMemory()
        store.begin()
        for invalid in (None, 1, {}, "", "   "):
            with self.assertRaises(ValueError):
                store.stage_save(invalid)
        self.assertFalse(store.stage_delete("gap_missing"))
        self.assertEqual(store.candidate, [])

    def test_clear_removes_official_and_staged_gaps_preserving_parent_semantics(self):
        for keep_status in (False, True):
            with self.subTest(keep_status=keep_status):
                store = GapMemory()
                store.update_status("In progress")
                store.save_knowledge("Previous task fact")
                store.save_procedural("Previous task experience")
                store.begin()
                store.stage_save("Previous task gap")
                store.commit()
                store.begin()
                store.stage_save("Unreviewed gap")
                store.clear(keep_status=keep_status)
                expected = {"status": "In progress" if keep_status else "",
                            "knowledge": [], "procedural": [], "gaps": []}
                self.assertEqual(store.to_dict(), expected)
                self.assertIsNone(store.candidate)
                self.assertEqual(store.changes, [])
                store.begin()
                self.assertEqual(store.candidate, [])
                self.assertEqual(store.changes, [])
                self.assertEqual(store.to_dict(), expected)


if __name__ == "__main__":
    unittest.main()
