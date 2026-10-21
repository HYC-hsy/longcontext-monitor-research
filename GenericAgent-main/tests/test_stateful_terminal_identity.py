"""The new B carrier has its own terminal receipt, never PMA's saved receipt."""

import unittest

from agentmain import build_task_terminal_record
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.pma_harbor_hooks import PMATrialHooks


class StatefulTerminalIdentityTests(unittest.TestCase):
    def test_stateful_terminal_is_distinct_from_old_pma(self):
        hook = PMATrialHooks.__new__(PMATrialHooks)
        hook.spec = {"condition": "B", "research_candidate": "pma_stateful_memory_v1",
                     "run_id": "run-1", "task_id": "task-1"}
        record = build_task_terminal_record("run-1", "task-1",
            {"result": "CURRENT_TASK_DONE"}, {"status": "not_enabled"},
            stateful_finalization={"closed": True, "cycle_count": 2})
        self.assertTrue(hook.terminal_identity_valid(record))
        self.assertEqual(record["result"], "CURRENT_TASK_DONE")
        self.assertFalse(hook.terminal_identity_valid({
            **record, "stateful_finalization": {"status": "missing_or_unknown"}}))
        self.assertFalse(hook.terminal_identity_valid({
            **record, "pma_finalization": {"status": "saved"}}))
        hook.spec["research_candidate"] = "U"
        self.assertFalse(hook.terminal_identity_valid(record))


if __name__ == "__main__":
    unittest.main()
