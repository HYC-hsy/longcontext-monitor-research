"""Same-cycle maintainer continuity; deterministic providers only."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import engine, prompts
from .budget import TokenProxy
from .proposal import build_candidate
from .source import ContractError, canonical
from .store import MemoryStore
from .test_contracts import empty_snapshot, leaf
from .test_engine import ScriptedProvider, event


class ContinuousRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.temp.name) / "memory.sqlite3")
        self.store.initialize(empty_snapshot(), leaf("task"))
        self.store.append_event(*event(1))
        self.calls = []
        self.returned = []
        self.candidates = []

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def run_cycle(self, *, outcomes=("issues",), first_raw=None,
                  keep_proposal=False, proxy=None):
        scripted = ScriptedProvider(outcomes=outcomes, create_requirement=True,
                                    create_state=True)
        def provider(role, messages, call_id, max_output):
            self.calls.append((role, deepcopy(messages)))
            if first_raw is not None and len(self.calls) == 1:
                raw = first_raw
            elif keep_proposal and role == "candidate_repair":
                raw = self.returned[0]
            else:
                raw = scripted(role, messages, call_id, max_output)
                if role == "maintenance":
                    # Whitespace proves the assistant turn is not reserialized.
                    raw = " \n" + raw + "\n "
            self.returned.append(raw)
            return raw
        def capture_candidate(**kwargs):
            candidate = build_candidate(**kwargs)
            self.candidates.append(deepcopy(candidate))
            return candidate
        with patch.object(engine, "build_candidate", side_effect=capture_candidate):
            return engine.CycleEngine(self.store, provider, task_text="task",
                                      token_proxy=proxy).run("continuity")

    def assert_continuous(self, repair_index, *, mode):
        original = self.calls[0][1]
        messages = self.calls[repair_index][1]
        self.assertEqual([m["role"] for m in messages],
                         ["system", "user", "assistant", "user"])
        self.assertEqual(messages[:2], original)
        self.assertEqual(messages[2]["content"], self.returned[0])
        self.assertEqual(sum(m == original[0] for m in messages), 1)
        self.assertEqual(sum(m == original[1] for m in messages), 1)
        feedback = json.loads(messages[-1]["content"])
        self.assertEqual(feedback["repair_mode"], mode)
        for key in ("original_base", "rejected_candidate_or_output", "candidate",
                    "proposal", "last_raw_response", "last_raw_audit_response"):
            self.assertNotIn(key, feedback)
        self.assertIn("complete maintenance-proposal/1", feedback["instruction"])
        self.assertIn("once to that original base", feedback["instruction"])
        self.assertIn("not a patch", feedback["instruction"])
        self.assertIn("binding.base_state_version", feedback["instruction"])
        self.assertIn("before_view is its visible projection", feedback["instruction"])
        return feedback

    def assert_credit(self, result, expected_calls):
        self.assertEqual(result["logical_calls"], expected_calls)
        rows = self.store.journal_rows(result["cycle_id"])
        self.assertEqual(sum(r["phase"] == "repair_credit_used" for r in rows), 1)

    def test_semantic_repair_uses_actual_assistant_and_exact_map_and_issues(self):
        result = self.run_cycle()
        self.assertEqual(result["status"], "committed_selection_silent")
        self.assertEqual([role for role, _ in self.calls],
                         ["maintenance", "audit", "candidate_repair", "audit", "selection"])
        feedback = self.assert_continuous(2, mode="replacement_proposal")
        audit_result = json.loads(self.returned[1])
        self.assertEqual(feedback["issues"], audit_result["issues"])
        self.assertEqual(feedback["local_id_map"], self.candidates[0]["local_id_map"])
        self.assertEqual(set(feedback["local_id_map"]), {"@e1", "@s1", "@r1"})
        self.assertNotEqual(self.calls[2][1][2]["content"], self.returned[1])
        self.assertNotIn(self.returned[1], canonical(self.calls[2][1]).decode())
        self.assertEqual(self.store.snapshot()["state_version"], 1)
        self.assertEqual(json.loads(self.returned[2])["base_state_version"], 0)
        self.assertEqual(self.store.snapshot()["B"]["G"]["specifications"], [])
        self.assert_credit(result, 5)

    def test_contract_repair_has_actual_bad_assistant_and_diagnostic_once(self):
        raw = '{"protocol":"maintenance-proposal/1","world_patch":[]}'
        result = self.run_cycle(outcomes=(), first_raw=raw)
        self.assertEqual(result["status"], "committed_selection_silent")
        feedback = self.assert_continuous(1, mode="maintenance_contract")
        self.assertEqual(set(feedback), {"repair_mode", "validation_error", "instruction"})
        self.assertEqual(feedback["validation_error"], "schema_fields")
        self.assert_credit(result, 4)

    def test_blank_response_repairs_without_empty_or_fabricated_assistant(self):
        for raw in ("", " \n\t "):
            with self.subTest(raw=repr(raw)), tempfile.TemporaryDirectory() as folder:
                store = MemoryStore(Path(folder) / "blank.sqlite3")
                try:
                    store.initialize(empty_snapshot(), leaf("task"))
                    scripted = ScriptedProvider(create_requirement=True)
                    calls = []
                    def provider(role, messages, call_id, max_output):
                        calls.append((role, deepcopy(messages)))
                        if len(calls) == 1:
                            return raw
                        return scripted(role, messages, call_id, max_output)
                    result = engine.CycleEngine(store, provider, task_text="task").run("blank")
                    self.assertEqual(result["status"], "committed_selection_silent")
                    self.assertEqual([role for role, _ in calls],
                                     ["maintenance", "maintenance", "audit", "selection"])
                    messages = calls[1][1]
                    self.assertEqual(messages[:2], calls[0][1])
                    self.assertEqual([m["role"] for m in messages], ["system", "user", "user"])
                    feedback = json.loads(messages[-1]["content"])
                    self.assertTrue(feedback["previous_response_empty"])
                    self.assertEqual(feedback["repair_mode"], "maintenance_contract")
                    self.assertEqual(feedback["validation_error"], "malformed_output")
                    rows = store.journal_rows(result["cycle_id"])
                    self.assertEqual(sum(r["phase"] == "repair_credit_used" for r in rows), 1)
                    first_return = next(r["body"] for r in rows if r["phase"] == "call_returned")
                    self.assertEqual(first_return["characters"], len(raw))
                    self.assertEqual(first_return["empty_response_raw"], raw)
                    self.assertEqual(first_return["public_response_sha256"], engine.digest(raw))
                finally:
                    store.close()

    def test_size_repair_has_same_context_and_normalization_without_fake_audit(self):
        proxy = TokenProxy()
        original_enforce = proxy.enforce
        blocked = []
        def enforce(messages, tools=None):
            payload = json.loads(messages[1]["content"])
            if (messages[0]["content"].startswith(prompts.AUDIT_SYSTEM) and
                    payload["operation_index"] and not blocked):
                blocked.append(True)
                raise ContractError("input_budget_exceeded")
            return original_enforce(messages, tools)
        proxy.enforce = enforce
        result = self.run_cycle(outcomes=(), proxy=proxy)
        self.assertEqual(result["status"], "committed_selection_silent")
        self.assertEqual([role for role, _ in self.calls],
                         ["maintenance", "candidate_repair", "audit", "selection"])
        feedback = self.assert_continuous(1, mode="replacement_proposal")
        self.assertEqual(feedback["validation_error"], "candidate_budget_exceeded")
        self.assertEqual(feedback["local_id_map"], self.candidates[0]["local_id_map"])
        self.assertNotIn("issues", feedback)
        self.assert_credit(result, 4)

    def test_rejected_final_state_never_published_or_selected(self):
        before = deepcopy(self.store.snapshot())
        result = self.run_cycle(outcomes=("issues", "issues"), keep_proposal=True)
        self.assertEqual(result["status"], "update_rejected")
        self.assertEqual(self.store.snapshot(), before)
        self.assertEqual([role for role, _ in self.calls],
                         ["maintenance", "audit", "candidate_repair", "audit"])
        self.assert_credit(result, 4)

    def test_unchanged_full_audit_view_and_retained_objects(self):
        # Commit an initial state, then make a no-op proposal on the next cycle.
        initial = ScriptedProvider(create_requirement=True, create_state=True)
        first = engine.CycleEngine(self.store, initial, task_text="task").run("seed")
        self.assertEqual(first["status"], "committed_selection_silent")
        self.store.append_event(*event(2))
        seen = []
        scripted = ScriptedProvider()
        original_encode = engine.AuditCodec.encode
        def encode(codec, *args, **kwargs):
            view = original_encode(codec, *args, **kwargs)
            seen.append(deepcopy(view))
            return view
        with patch.object(engine.AuditCodec, "encode", new=encode):
            result = engine.CycleEngine(self.store, scripted, task_text="task").run("retained")
        self.assertEqual(result["status"], "committed_selection_silent")
        audit_input = json.loads(scripted.calls[1]["messages"][1]["content"])
        self.assertEqual(audit_input, seen[0])
        self.assertEqual(audit_input["operation_index"], [])
        self.assertTrue(any(item["kind"] == "state" for item in audit_input["required_coverage"]))
        self.assertTrue(any(item["kind"] == "requirement" for item in audit_input["required_coverage"]))

    def test_feedback_never_trims_to_fit_budget(self):
        proxy = TokenProxy()
        enforce = proxy.enforce
        def reject_feedback(messages, tools=None):
            if any(item["role"] == "assistant" for item in messages):
                raise ContractError("input_budget_exceeded")
            return enforce(messages, tools)
        proxy.enforce = reject_feedback
        result = self.run_cycle(proxy=proxy)
        self.assertEqual(result["error_code"], "input_budget_exceeded")
        self.assertEqual([role for role, _ in self.calls], ["maintenance", "audit"])
        self.assertEqual(self.store.snapshot()["state_version"], 0)

    def test_helper_does_not_mutate_inputs_or_alias_message_dicts(self):
        original = prompts.maintenance({"untouched": "full original evidence"})
        issues = [{"issue_id": "i1", "explanation": "exact diagnostic"}]
        mapping = {"@new": "normalized-id"}
        before = deepcopy((original, issues, mapping))
        messages = prompts.continuous_repair(original_messages=original,
            maintenance_raw=" actual raw ", error="blocking_issues",
            mode="replacement_proposal", local_id_map=mapping, issues=issues)
        self.assertEqual((original, issues, mapping), before)
        messages[1]["content"] = "changed by caller"
        self.assertEqual((original, issues, mapping), before)

    def test_missing_context_fails_instead_of_reconstructing(self):
        args = dict(original_messages=prompts.maintenance({"evidence": "whole"}),
                    maintenance_raw="{}", error="blocking_issues",
                    mode="replacement_proposal", local_id_map={}, issues=[{"id": "i"}])
        for change in ({"original_messages": []}, {"maintenance_raw": None},
                       {"local_id_map": None}, {"issues": []}, {"issues": None}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                prompts.continuous_repair(**{**args, **change})

    def test_audit_correction_remains_its_own_role_and_callback(self):
        result = self.run_cycle(outcomes=("malformed",))
        self.assertEqual(result["status"], "committed_selection_silent")
        self.assertEqual([role for role, _ in self.calls],
                         ["maintenance", "audit", "audit_correction", "selection"])
        correction = self.calls[2][1]
        self.assertEqual(correction[:2], self.calls[1][1])
        self.assertEqual([m["role"] for m in correction], ["system", "user", "user"])
        self.assertEqual(json.loads(correction[-1]["content"])["last_raw_audit_response"],
                         self.returned[1])
        self.assert_credit(result, 4)


if __name__ == "__main__":
    unittest.main()
