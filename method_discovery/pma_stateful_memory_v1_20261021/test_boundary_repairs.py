"""Offline regressions for nested audit shapes and scope visibility boundaries."""

from copy import deepcopy
import json
import tempfile
import unittest
from pathlib import Path

from .audit import validate_audit_result
from .engine import CycleEngine
from .proposal import build_candidate
from .source import ContractError, SourceCatalog, canonical
from .store import MemoryStore
from . import test_audit, test_audit_closure
from .test_contracts import empty_snapshot, leaf
from .test_engine import ScriptedProvider, event
from .test_proposal import proposal


class AuditBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.audit = test_audit.AuditTests()
        self.audit.setUp()
        self.closure = test_audit_closure.AuditClosureTests()
        self.closure.setUp()

    def validate(self, result, fixture=None):
        fixture = fixture or self.audit
        return validate_audit_result(result, view=fixture.view,
                                     catalog=fixture.catalog)

    def issues(self):
        result = self.audit.clean()
        result.update(outcome="issues", issues=[self.audit.issue()])
        return result

    def test_malformed_bound_fields_are_contract_errors_in_all_positions(self):
        mutations = [("snapshot", []), ("snapshot", {}), ("target", []),
                     ("kind", []), ("kind", {}), ("id", []), ("id", {}),
                     ("revision", []), ("revision", {}), ("revision", True),
                     ("field_path", [])]
        for position in ("target", "related", "witness"):
            for key, value in mutations:
                with self.subTest(position=position, field=key, value=value):
                    result = self.issues()
                    issue = result["issues"][0]
                    bound = deepcopy(issue["target"])
                    if key in {"kind", "id", "revision"}:
                        bound["target"][key] = value
                    else:
                        bound[key] = value
                    if position == "target":
                        issue["target"] = bound
                    elif position == "related":
                        bound["snapshot"] = (value if key == "snapshot" else "archive")
                        issue["related_targets"] = [bound]
                    else:
                        issue["witnesses"] = [{"kind": "field", "field": bound,
                                               "exact_value": "do task"}]
                    with self.assertRaises(ContractError):
                        self.validate(result)

    def test_nested_enum_shapes_reject_without_runtime_errors(self):
        for key in ("outcome", "kind"):
            result = self.issues()
            (result if key == "outcome" else result["issues"][0])[key] = []
            with self.subTest(field=key), self.assertRaises(ContractError):
                self.validate(result)
        result = self.audit.clean()
        result.update(outcome="unusable", unusable_reason={"code": [], "detail": "x"})
        with self.assertRaises(ContractError):
            self.validate(result)

    def test_closure_entry_and_hash_inputs_have_explicit_shape_checks(self):
        self.assertEqual(self.validate(self.closure.result(), self.closure)["outcome"],
                         "clean")
        for entry in (None, [], "bad", 1, {}):
            result = self.closure.result()
            result["closure_assessments"] = [entry]
            with self.subTest(entry=entry), self.assertRaises(ContractError):
                self.validate(result, self.closure)
        for key, value in (("resolution_id", []), ("resolution_id", {}),
                           ("verdict", []), ("blocking_issue_ids", [[]]),
                           ("blocking_issue_ids", [{}])):
            result = self.closure.result()
            result["closure_assessments"][0][key] = value
            with self.subTest(field=key), self.assertRaises(ContractError):
                self.validate(result, self.closure)

    def test_valid_multi_issue_and_field_witness_still_accepted(self):
        result = self.issues()
        second = deepcopy(result["issues"][0])
        second["issue_id"] = "i2"
        second["witnesses"] = [{"kind": "field", "field": second["target"],
                                "exact_value": "do task"}]
        result["issues"].append(second)
        self.assertEqual(len(self.validate(result)["issues"]), 2)
        result["issues"][1]["target"]["target"]["id"] = []
        with self.assertRaises(ContractError):
            self.validate(result)

    def test_actual_engine_nested_fault_uses_one_existing_shared_credit(self):
        for field in ("snapshot", "id"):
            for persistent in (False, True):
                with self.subTest(field=field, persistent=persistent):
                    with tempfile.TemporaryDirectory() as root:
                        store = MemoryStore(Path(root) / "memory.sqlite3")
                        try:
                            store.initialize(empty_snapshot(), leaf("task"))
                            store.append_event(*event(1))
                            provider = ScriptedProvider(create_requirement=True,
                                outcomes=["issues", "issues"] if persistent else ["issues"])
                            def respond(role, messages, call_id, max_output):
                                answer = json.loads(provider(role, messages, call_id, max_output))
                                if role == "audit" or (persistent and role == "audit_correction"):
                                    bound = answer["issues"][0]["target"]
                                    (bound if field == "snapshot" else bound["target"])[field] = []
                                return canonical(answer).decode()
                            result = CycleEngine(store, respond, task_text="task").run("nested")
                            roles = [call["role"] for call in provider.calls]
                            self.assertEqual(roles[:3], ["maintenance", "audit", "audit_correction"])
                            credits = [row for row in store.journal_rows(result["cycle_id"])
                                       if row["phase"] == "repair_credit_used"]
                            self.assertEqual(len(credits), 1)
                            self.assertEqual(credits[0]["body"]["mode"], "audit_contract")
                            self.assertEqual(result["status"], "update_unusable" if persistent
                                             else "committed_selection_silent")
                            self.assertEqual(result["logical_calls"], 3 if persistent else 4)
                            self.assertEqual(store.snapshot()["state_version"], 0 if persistent else 1)
                            if persistent:
                                self.assertNotIn("selection", roles)
                        finally:
                            store.close()


class ScopeVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.base = empty_snapshot()
        self.base["B"]["W"]["entities"] = [
            {"entity_id": name, "entity_type": "other", "display_name": name}
            for name in ("owner", "hidden")]
        self.catalog = SourceCatalog({"u0": leaf("task")}, "scope-window")

    def patch(self, scoped_ids):
        patch = proposal()
        patch["world_patch"]["state_upserts"] = [{
            "record_id": "@s", "revision": 1, "entity_id": "owner",
            "scope": {"task_id": "task", "entity_ids": scoped_ids, "conditions": []},
            "use_status": "active", "updated_at_step": 0, "supersedes": [],
            "kind": "knowledge", "claim": {"text": "possible relation",
                "assertion_origin": "inference", "time_role": "general_hypothesis",
                "support_refs": [], "challenge_refs": []}}]
        return patch

    def build(self, patch, visible):
        return build_candidate(proposal=patch, base=self.base, catalog=self.catalog,
            cycle_id="scope", processed_to=0,
            goal_ledger={"epoch": 1, "messages": ["u0"], "deltas": {}},
            visible_existing_ids={("entity", name) for name in visible}, archive={})

    def test_hidden_scope_entity_rejected_even_with_visible_owner(self):
        before = deepcopy(self.base)
        with self.assertRaisesRegex(ContractError, "invisible_existing_reference: hidden"):
            self.build(self.patch(["owner", "hidden"]), {"owner"})
        self.assertEqual(self.base, before)

    def test_visible_scope_and_same_proposal_local_scope_are_allowed(self):
        patch = self.patch(["owner", "hidden"])
        result = self.build(patch, {"owner", "hidden"})
        self.assertEqual(result["candidate"]["B"]["W"]["states"][0]["scope"][
            "entity_ids"], ["owner", "hidden"])
        patch = self.patch(["owner", "@local"])
        patch["world_patch"]["entity_upserts"] = [{"entity_id": "@local",
            "entity_type": "other", "display_name": "new scoped entity"}]
        result = self.build(patch, {"owner"})
        self.assertEqual(result["candidate"]["B"]["W"]["states"][0]["scope"][
            "entity_ids"], ["owner", result["local_id_map"]["@local"]])

    def test_unknown_scope_and_hidden_owner_remain_rejected(self):
        for scoped_ids in (["unknown"], ["@not_created"]):
            with self.subTest(scope=scoped_ids), self.assertRaisesRegex(
                    ContractError, "unknown_reference"):
                self.build(self.patch(scoped_ids), {"owner"})
        with self.assertRaisesRegex(ContractError, "invisible_existing_reference: owner"):
            self.build(self.patch(["hidden"]), {"hidden"})

    def test_scope_shape_is_validated_before_iteration_or_hashing(self):
        for value in ([], None, {"task_id": "task", "entity_ids": {}, "conditions": []},
                      {"task_id": "task", "entity_ids": [[]], "conditions": []}):
            patch = self.patch(["owner"])
            patch["world_patch"]["state_upserts"][0]["scope"] = value
            with self.subTest(scope=value), self.assertRaises(ContractError):
                self.build(patch, {"owner"})


if __name__ == "__main__":
    unittest.main()
