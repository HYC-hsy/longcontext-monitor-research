"""Transaction, immutable event, frontier and delivery tests."""

from copy import deepcopy
import tempfile
import unittest
from pathlib import Path

from .source import ContractError
from .store import MemoryStore
from .test_contracts import empty_snapshot, leaf


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.temporary.name) / "method.sqlite3")
        self.base = empty_snapshot()
        self.store.initialize(self.base, leaf("task"))

    def tearDown(self):
        self.store.close()
        self.temporary.cleanup()

    def action(self, seq=1, text="exit 0"):
        source = leaf(text, source_id=f"out-{seq}", source_kind="tool_result")
        source.update(event_id=f"tool-use-{seq}", event_seq=seq, ga_turn=seq,
                      field_path="result.stdout")
        action = leaf("run synthetic command", source_id=f"action-{seq}",
                      source_kind="executed_action")
        action.update(event_id=f"tool-use-{seq}", event_seq=seq, ga_turn=seq,
                      field_path="action.arguments")
        event = {"event_id": f"batch-{seq}", "event_seq": seq,
                 "kind": "action_batch", "occurred_at_step": seq,
                 "source_ids": [action["source_id"], source["source_id"]],
                 "payload": {"actions": [{"tool_use_id": f"tool-use-{seq}"}]}}
        return event, [action, source]

    def test_idempotent_source_and_atomic_batch(self):
        event, sources = self.action()
        source = sources[1]
        self.store.append_event(event, sources)
        self.store.append_event(event, sources)
        self.assertEqual(len(self.store.events_after(0)), 1)
        self.assertEqual(self.store.sources()[source["source_id"]]["event_id"],
                         "tool-use-1")
        changed = deepcopy(source)
        changed["text"] = "different"
        with self.assertRaises(ContractError):
            self.store.append_event(event, [sources[0], changed])
        self.assertEqual(self.store.sources()[source["source_id"]], source)
        event2, sources2 = self.action(seq=3)
        with self.assertRaises(ContractError):
            self.store.append_event(event2, sources2)
        self.assertEqual(len(self.store.events_after(0)), 1)

    def test_commit_cas_frontier_and_uncertain_result_lookup(self):
        event, sources = self.action()
        self.store.append_event(event, sources)
        candidate = deepcopy(self.base)
        candidate["state_version"] = 1
        candidate["committed_event_seq"] = 1
        result = self.store.compare_and_swap(update_id="update-1", cycle_id="cycle-1",
                                             base=self.base, candidate=candidate,
                                             archive_delta=[])
        self.assertEqual(result["event_seq"], 1)
        self.assertEqual(self.store.commit_result("update-1"), result)
        self.assertEqual(self.store.compare_and_swap(update_id="update-1",
            cycle_id="cycle-1", base=self.base, candidate=candidate,
            archive_delta=[]), result)
        with self.assertRaises(ContractError):
            self.store.compare_and_swap(update_id="update-2", cycle_id="cycle-2",
                base=self.base, candidate=candidate, archive_delta=[])

    def test_action_batch_rejects_unpaired_tool_result_or_action(self):
        event, sources = self.action()
        for orphan in sources:
            incomplete = {**event, "source_ids": [orphan["source_id"]]}
            with self.assertRaisesRegex(ContractError, "incomplete_atomic_action_batch"):
                self.store.append_event(incomplete, [orphan])
        mismatched = {**event, "payload": {"actions": [
            {"tool_use_id": "different-call"}]}}
        with self.assertRaisesRegex(ContractError, "action_result_identity_mismatch"):
            self.store.append_event(mismatched, sources)
        self.assertEqual(self.store.events_after(0), [])

    def test_multi_tool_batch_is_one_event_and_failed_commit_rolls_back(self):
        first, first_sources = self.action()
        second, second_sources = self.action()
        second_sources[0].update(source_id="action-other", event_id="other-call")
        second_sources[1].update(source_id="out-other", event_id="other-call")
        for item in second_sources:
            item["event_seq"] = 1
        batch = deepcopy(first)
        batch["source_ids"] += [item["source_id"] for item in second_sources]
        batch["payload"]["actions"].append({"tool_use_id": "other-call"})
        self.store.append_event(batch, first_sources + second_sources)
        self.assertEqual([item["event_seq"] for item in self.store.events_after(0)], [1])
        self.assertEqual(len(self.store.sources()), 5)  # task plus four tool leaves
        invalid = deepcopy(self.base)
        invalid["state_version"] = 1
        invalid["committed_event_seq"] = 1
        invalid["B"]["W"]["entities"] = [{"entity_id": "e", "entity_type": "file",
            "display_name": "x", "unsupported_fact": True}]
        with self.assertRaises(ContractError):
            self.store.compare_and_swap(update_id="bad-update", cycle_id="bad-cycle",
                base=self.base, candidate=invalid,
                archive_delta=[("state", "archived", 1, {"marker": "rollback"})])
        self.assertEqual(self.store.snapshot(), self.base)
        self.assertEqual(self.store.archive(), {})
        self.assertIsNone(self.store.commit_result("bad-update"))

    def test_goal_epoch_and_delivery_idempotency(self):
        source = leaf("new task", source_id="u1")
        source.update(event_id="user-1", event_seq=1, ga_turn=1)
        event = {"event_id": "user-1", "event_seq": 1, "kind": "user_message",
                 "occurred_at_step": 1, "source_ids": ["u1"], "payload": {}}
        self.store.append_event(event, [source])
        self.assertEqual(self.store.goals()["epoch"], 2)
        candidate = deepcopy(self.base)
        candidate["state_version"] = 1
        candidate["committed_event_seq"] = 1
        with self.assertRaises(ContractError):
            self.store.compare_and_swap(update_id="old", cycle_id="cycle",
                base=self.base, candidate=candidate, archive_delta=[])
        self.assertEqual(self.store.snapshot(), self.base)
        result = {"status": "included_in_request"}
        self.assertEqual(self.store.delivery("reminder", "request", result), result)
        self.assertEqual(self.store.delivery("reminder", "request", result), result)
        with self.assertRaises(ContractError):
            self.store.delivery("reminder", "another_request", result)


if __name__ == "__main__":
    unittest.main()
