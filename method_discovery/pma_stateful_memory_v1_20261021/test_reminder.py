"""Offline strict reminder and one-shot host delivery checks."""

import tempfile
import unittest
from pathlib import Path

from .reminder import attach_once, render_reminder, validate_selection
from .source import ContractError
from .store import MemoryStore
from .test_contracts import empty_snapshot, leaf


class ReminderTests(unittest.TestCase):
    def test_silent_and_ref_contract(self):
        snapshot = empty_snapshot()
        silent = {"decision": "silent", "state_version": 0,
                  "task_version": 1, "phase2_view_id": "v"}
        self.assertEqual(validate_selection(silent, snapshot=snapshot,
                         phase2_view_id="v", selected_refs=[]), silent)
        selected = [{"type": "requirement", "requirement_id": "r1",
                     "revision": 1, "task_version": 1}]
        snapshot["B"]["G"]["specifications"] = [{"requirement_id": "r1",
            "revision": 1, "task_version": 1, "interpretation": "finish task",
            "source_refs": [], "status": "active", "retirement": None}]
        reminder = {**silent, "decision": "remind", "refs": selected,
                    "context_for_action": "Check the requirement."}
        validate_selection(reminder, snapshot=snapshot,
                           phase2_view_id="v", selected_refs=selected)
        rendered = render_reminder(reminder, snapshot=snapshot,
                                   cycle_id="c", commit_id="k", reviewed_refs=[])
        self.assertEqual(rendered["anchors"][0]["origin_badge"],
                         "model_interpretation_of_user_requirement")
        with self.assertRaisesRegex(ContractError, "selection_invisible_ref"):
            validate_selection(reminder, snapshot=snapshot,
                               phase2_view_id="v", selected_refs=[])

    def test_delivery_rejects_replay_after_unknown_send(self):
        with tempfile.TemporaryDirectory() as root:
            store = MemoryStore(Path(root) / "state.sqlite3")
            store.initialize(empty_snapshot(), leaf("task"))
            reminder = {"reminder_id": "r", "state_version": 0,
                        "task_version": 1}
            messages = [{"role": "user", "content": "task"}]
            seen = []
            def uncertain(payload):
                seen.append(payload)
                raise RuntimeError("unknown response")
            with self.assertRaises(RuntimeError):
                attach_once(store=store, reminder=reminder, task_messages=messages,
                            request_id="req", cycle_id="c", send=uncertain)
            self.assertEqual(len(seen), 1)
            self.assertEqual(messages, [{"role": "user", "content": "task"}])
            with self.assertRaisesRegex(ContractError, "outcome_unknown"):
                attach_once(store=store, reminder=reminder, task_messages=messages,
                            request_id="req", cycle_id="c", send=uncertain)
            self.assertEqual(len(seen), 1)
            store.close()


if __name__ == "__main__":
    unittest.main()
