import json
from pathlib import Path
import tempfile
import unittest

from gap_store import GapMemory
from memory_agent.memory.universal_memory import MemoryEntry


class GapMemoryTests(unittest.TestCase):
    def test_direct_save_delete_and_unmentioned_entries(self):
        bank = GapMemory()
        old = bank.save_gap("Acceptance unverified")
        keep = bank.save_gap("Input contract unknown")
        self.assertEqual([e.id for e in bank.entries], [old, keep])
        self.assertTrue(bank.delete_gap(old))
        new = bank.save_gap("Valid failing test shows unmet behavior")
        self.assertEqual([e.id for e in bank.entries], [keep, new])
        self.assertFalse(bank.delete_gap(old))
        self.assertIsInstance(bank.entries[0], MemoryEntry)
        self.assertTrue(bank.entries[0].created_at)
        bank.entries[0].content = "external mutation"
        self.assertEqual(bank.entries[0].content, "Input contract unknown")

    def test_failed_operation_does_not_roll_back_prior_success(self):
        bank = GapMemory()
        key = bank.save_gap("Already saved")
        for invalid in (None, 1, {}, "", "   "):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                bank.save_gap(invalid)
        self.assertFalse(bank.delete_gap("gap_missing"))
        self.assertEqual([e.id for e in bank.entries], [key])

    def test_save_load_old_snapshot_and_clear(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gaps.json"
            bank = GapMemory()
            ordinary = bank.save_knowledge("Normal memory")
            bank.save_procedural("Normal experience")
            bank.update_status("In progress")
            gap = bank.save_gap("Unverified result")
            bank.save_to_file(path)
            self.assertEqual(json.loads(path.read_bytes())["gaps"][0]["id"], gap)
            loaded = GapMemory.load_from_file(path)
            self.assertEqual(loaded.to_dict(), bank.to_dict())
            self.assertEqual(loaded.get(ordinary).content, "Normal memory")
            old = bank.to_dict()
            old.pop("gaps")
            self.assertEqual(GapMemory.from_dict(old).entries, [])
            loaded.clear(keep_status=True)
            self.assertEqual(loaded.to_dict(), {"status": "In progress", "knowledge": [],
                                                "procedural": [], "gaps": []})
            loaded.clear()
            self.assertEqual(loaded.status, "")

    def test_gap_identity_validation_and_bm25_length(self):
        bank = GapMemory()
        bank.save_gap("Gap only")
        self.assertEqual(len(bank), 0)
        bad = bank.to_dict()
        bad["gaps"][0]["id"] = "ordinary_id"
        with self.assertRaises(ValueError):
            GapMemory.from_dict(bad)
        duplicate = bank.to_dict()
        duplicate["gaps"].append(duplicate["gaps"][0])
        with self.assertRaises(ValueError):
            GapMemory.from_dict(duplicate)


if __name__ == "__main__":
    unittest.main()
