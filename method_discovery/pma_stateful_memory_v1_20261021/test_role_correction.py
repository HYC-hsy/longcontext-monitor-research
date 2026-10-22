"""Role-separated correction and whole-response refusal regressions."""

import json
import tempfile
import unittest
from pathlib import Path

from .engine import CycleEngine
from .model_output import decode_model_object
from .source import ContractError, canonical
from .store import MemoryStore
from .test_contracts import empty_snapshot, leaf
from .test_engine import ScriptedProvider


class RoleCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.temp.name) / "memory.sqlite3")
        self.store.initialize(empty_snapshot(), leaf("task"))

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_audit_correction_retains_frozen_view_and_only_requests_report(self):
        scripted = ScriptedProvider(create_requirement=True)
        calls = []
        def provider(role, messages, call_id, max_output):
            calls.append((role, messages))
            if role == "audit":
                return "not JSON"
            return scripted(role, messages, call_id, max_output)
        result = CycleEngine(self.store, provider, task_text="task").run("correction")
        self.assertEqual(result["status"], "committed_selection_silent")
        self.assertEqual([role for role, _ in calls],
                         ["maintenance", "audit", "audit_correction", "selection"])
        original, correction = calls[1][1], calls[2][1]
        self.assertEqual(correction[:2], original)
        self.assertIn("audit-result/2", correction[0]["content"])
        self.assertEqual(correction[1], original[1])
        extra = json.loads(correction[2]["content"])
        self.assertEqual(extra["last_raw_audit_response"], "not JSON")
        self.assertEqual(extra["validation_error"], "malformed_output")
        self.assertIn("audit-result/2", extra["instruction"])
        self.assertNotIn("original_base", extra)
        self.assertNotIn("rejected_candidate_or_output", extra)
        self.assertNotIn("replacement object for the original base", extra["instruction"])
        self.assertEqual(len([row for row in self.store.journal_rows(result["cycle_id"])
                              if row["phase"] == "repair_credit_used"]), 1)

    def test_snapshot_returned_for_audit_correction_is_not_committed(self):
        scripted = ScriptedProvider(create_requirement=True)
        roles = []
        def provider(role, messages, call_id, max_output):
            roles.append(role)
            if role == "audit":
                return "not JSON"
            if role == "audit_correction":
                return canonical(empty_snapshot()).decode()
            return scripted(role, messages, call_id, max_output)
        result = CycleEngine(self.store, provider, task_text="task").run("snapshot")
        self.assertEqual(result["status"], "init_failed")
        self.assertEqual(result["error_code"], "schema_fields")
        self.assertEqual(self.store.snapshot()["state_version"], 0)
        self.assertEqual(roles, ["maintenance", "audit", "audit_correction"])

    def test_whole_refusal_stops_without_normal_format_correction(self):
        scripted = ScriptedProvider(create_requirement=True)
        roles = []
        def provider(role, messages, call_id, max_output):
            roles.append(role)
            return "I cannot discuss that." if role == "audit" else scripted(
                role, messages, call_id, max_output)
        result = CycleEngine(self.store, provider, task_text="task").run("refusal")
        self.assertEqual(result["status"], "init_failed")
        self.assertEqual(result["error_code"], "model_refusal")
        self.assertEqual(roles, ["maintenance", "audit"])
        self.assertEqual(self.store.snapshot()["state_version"], 0)
        self.assertFalse(any(row["phase"] == "repair_credit_used" for row in
                             self.store.journal_rows(result["cycle_id"])))
        decode = [row["body"] for row in self.store.journal_rows(result["cycle_id"])
                  if row["phase"] == "model_decode"]
        self.assertEqual(decode[-1]["failure_layer"], "refusal")

    def test_quoted_refusal_in_json_is_not_refusal(self):
        self.assertEqual(decode_model_object('{"quote":"I cannot discuss that."}'),
                         {"quote": "I cannot discuss that."})
        with self.assertRaisesRegex(ContractError, "model_refusal"):
            decode_model_object(" \r\nI cannot discuss that.\n")

    def test_maintenance_repair_is_replacement_proposal_not_snapshot(self):
        scripted = ScriptedProvider(create_requirement=True)
        calls = []
        def provider(role, messages, call_id, max_output):
            calls.append((role, messages))
            if len(calls) == 1:
                return '{"protocol":"maintenance-proposal/1","world_patch":[]}'
            return scripted(role, messages, call_id, max_output)
        result = CycleEngine(self.store, provider, task_text="task").run("proposal")
        self.assertEqual(result["status"], "committed_selection_silent")
        correction = json.loads(calls[1][1][-1]["content"])
        self.assertEqual(correction["repair_mode"], "maintenance_contract")
        self.assertIn("maintenance-proposal/1", correction["instruction"])
        self.assertIn("once to original_base", correction["instruction"])
        self.assertEqual(self.store.snapshot()["state_version"], 1)

    def test_shared_credit_exhaustion_does_not_call_audit_correction(self):
        scripted = ScriptedProvider()
        roles = []
        def provider(role, messages, call_id, max_output):
            roles.append(role)
            if len(roles) == 1:
                return "invalid maintenance"
            if role == "audit":
                return "invalid audit"
            return scripted(role, messages, call_id, max_output)
        result = CycleEngine(self.store, provider, task_text="task").run("credit")
        self.assertEqual(result["status"], "init_failed")
        self.assertEqual(roles, ["maintenance", "maintenance", "audit"])
        self.assertEqual(self.store.snapshot()["state_version"], 0)


if __name__ == "__main__":
    unittest.main()
