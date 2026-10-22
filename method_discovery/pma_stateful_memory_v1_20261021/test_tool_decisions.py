"""Deterministic compiler checks against the real audit/selection validators."""

from copy import deepcopy
import unittest

from .audit import validate_audit_result
from .reminder import validate_selection
from .source import ContractError
from . import test_audit, test_audit_closure
from .test_schema_advanced import rich_state
from .tool_decisions import (audit_tool_definitions, selection_tool_definitions,
                             compile_audit, compile_selection)


def call(name, args):
    return [{"name": name, "arguments": args}]


def compact(result):
    result = deepcopy(result)
    del result["protocol"]
    del result["binding"]
    for assessment in result["closure_assessments"]:
        for key in ("gap_before", "gap_after", "closure_kind"):
            del assessment[key]
    return result


class ToolDecisionTests(unittest.TestCase):
    def setUp(self):
        self.audit = test_audit.AuditTests()
        self.audit.setUp()
        self.closure = test_audit_closure.AuditClosureTests()
        self.closure.setUp()
        self.snapshot, _ = rich_state()
        self.binding = {"state_version": self.snapshot["state_version"],
            "task_version": self.snapshot["B"]["G"]["task_version"], "phase2_view_id": "v"}
        self.ref = {"type": "gap", "gap_id": "ge", "revision": 1, "task_version": 1}

    def audit_compile(self, args, fixture=None):
        fixture = fixture or self.audit
        return compile_audit(call("submit_audit", args), view=fixture.view)

    def select(self, args):
        return compile_selection(call("submit_selection", args), binding=self.binding)

    def test_definitions_are_fresh_and_host_fields_absent(self):
        for factory, name in ((audit_tool_definitions, "submit_audit"),
                              (selection_tool_definitions, "submit_selection")):
            definitions = factory()
            self.assertEqual(len(definitions), 1)
            function = definitions[0]["function"]
            self.assertEqual(function["name"], name)
            self.assertFalse(function["parameters"]["additionalProperties"])
            self.assertTrue(set(function["parameters"]["properties"]).isdisjoint({
                "protocol", "binding", "state_version", "task_version", "phase2_view_id"}))
            function["parameters"]["properties"].clear()
            self.assertTrue(factory()[0]["function"]["parameters"]["properties"])

    def test_empty_duplicate_wrong_role_and_extra_call_fields_rejected(self):
        for compiler, kwargs, name, args in (
            (compile_audit, {"view": self.audit.view}, "submit_audit", compact(self.audit.clean())),
            (compile_selection, {"binding": self.binding}, "submit_selection",
             {"decision": "silent", "refs": None, "context_for_action": None})):
            good = call(name, args)
            for bad in ([], good * 2, call("wrong", args),
                        [{**good[0], "ignored": True}], call(name, "{}")):
                with self.subTest(bad=bad), self.assertRaises(ContractError):
                    compiler(bad, **kwargs)

    def test_non_json_inputs_fail_with_contract_error(self):
        for compiler, kwargs, name, args in (
            (compile_audit, {"view": self.audit.view}, "submit_audit", compact(self.audit.clean())),
            (compile_selection, {"binding": self.binding}, "submit_selection",
             {"decision": "silent", "refs": None, "context_for_action": None})):
            malformed = []
            cyclic = call(name, deepcopy(args))
            cyclic[0]["arguments"]["cycle"] = cyclic
            malformed.append(cyclic)
            mixed_keys = call(name, deepcopy(args))
            mixed_keys[0][1] = "not a string key"
            malformed.append(mixed_keys)
            huge_integer = call(name, deepcopy(args))
            huge_integer[0]["arguments"]["large"] = 10 ** 5000
            malformed.append(huge_integer)
            codes = ("cyclic_json_value", "non_string_json_key", "arguments_not_serializable")
            for index, value in enumerate(malformed):
                with self.subTest(role=name, case=index), self.assertRaisesRegex(
                        ContractError, "tool_argument_schema: " + codes[index]):
                    compiler(value, **kwargs)
        # Arbitrary-valued field witnesses must still be strict serializable JSON.
        args = compact(self.audit.clean())
        args.update(outcome="issues", issues=[self.audit.issue()])
        args["issues"][0]["witnesses"] = [{"kind": "field",
            "field": args["issues"][0]["target"], "exact_value": 10 ** 5000}]
        with self.assertRaisesRegex(ContractError, "arguments_not_serializable"):
            self.audit_compile(args)

    def test_clean_coverage_unchanged_and_no_binding_echo(self):
        args = compact(self.audit.clean())
        result = self.audit_compile(args)
        self.assertEqual(result, self.audit.clean())
        self.assertNotIn("coverage", result)
        validate_audit_result(result, view=self.audit.view, catalog=self.audit.catalog)
        for key in ("binding", "protocol", "coverage"):
            with self.subTest(key=key), self.assertRaises(ContractError):
                self.audit_compile({**args, key: self.audit.clean().get(key)})

    def test_closure_identity_expansion_and_payload_immutability(self):
        args = compact(self.closure.result())
        original_args, original_view = deepcopy(args), deepcopy(self.closure.view)
        result = self.audit_compile(args, self.closure)
        self.assertEqual(result, self.closure.result())
        validate_audit_result(result, view=self.closure.view, catalog=self.closure.catalog)
        self.assertEqual(args, original_args)
        self.assertEqual(self.closure.view, original_view)
        result["binding"].clear()
        result["closure_assessments"][0]["basis_refs"].clear()
        self.assertEqual(args, original_args)
        self.assertEqual(self.closure.view, original_view)

    def test_unknown_duplicate_missing_and_echoed_resolution_fields(self):
        base = compact(self.closure.result())
        bads = []
        missing = deepcopy(base)
        missing["closure_assessments"] = []
        bads.append(missing)
        duplicate = deepcopy(base)
        duplicate["closure_assessments"] *= 2
        bads.append(duplicate)
        unknown = deepcopy(base)
        unknown["closure_assessments"][0]["resolution_id"] = "unknown"
        bads.append(unknown)
        echo = deepcopy(base)
        echo["closure_assessments"][0]["gap_after"] = {"revision": 999}
        bads.append(echo)
        for bad in bads:
            with self.subTest(bad=bad), self.assertRaises(ContractError):
                self.audit_compile(bad, self.closure)

    def test_unusable_is_explicit_and_contains_no_conclusions(self):
        args = {"outcome": "unusable", "issues": [], "closure_assessments": [],
                "unusable_reason": {"code": "cannot_complete_audit", "detail": "No conclusion"}}
        result = self.audit_compile(args, self.closure)
        validate_audit_result(result, view=self.closure.view, catalog=self.closure.catalog)
        for key, value in (("issues", [self.audit.issue()]),
                           ("closure_assessments", compact(self.closure.result())["closure_assessments"]),
                           ("unusable_reason", None)):
            with self.subTest(key=key), self.assertRaises(ContractError):
                self.audit_compile({**args, key: value}, self.closure)

    def test_mixed_issue_fails_without_filtering_or_cleaning(self):
        args = compact(self.audit.clean())
        args.update(outcome="issues", issues=[self.audit.issue(), self.audit.issue()])
        args["issues"][1]["issue_id"] = "i2"
        good = self.audit_compile(args)
        validate_audit_result(good, view=self.audit.view, catalog=self.audit.catalog)
        args["issues"][1]["target"]["field_path"] = "missing"
        result = self.audit_compile(args)
        self.assertEqual(len(result["issues"]), 2)
        with self.assertRaisesRegex(ContractError, "invalid_field_path"):
            validate_audit_result(result, view=self.audit.view, catalog=self.audit.catalog)
        args["issues"][1]["wrong_field"] = True
        with self.assertRaises(ContractError):
            self.audit_compile(args)

    def test_real_source_role_and_closure_basis_remain_authoritative(self):
        args = compact(self.closure.result())
        args["closure_assessments"][0]["basis_refs"] = [{
            "evidence_id": self.closure.user.evidence_id, "quote": "task"}]
        result = self.audit_compile(args, self.closure)
        with self.assertRaisesRegex(ContractError, "source_role_misuse"):
            validate_audit_result(result, view=self.closure.view, catalog=self.closure.catalog)
        args["closure_assessments"][0]["basis_refs"] = []
        result = self.audit_compile(args, self.closure)
        with self.assertRaisesRegex(ContractError, "closure_basis_mismatch"):
            validate_audit_result(result, view=self.closure.view, catalog=self.closure.catalog)

    def test_goal_changed_and_merged_closures_round_trip(self):
        for kind in ("goal_changed", "merged_into"):
            fixture = self.closure
            view = deepcopy(fixture.view)
            entry = view["resolve_manifest"][0]
            entry["closure_kind"] = kind
            if kind == "goal_changed":
                basis = {"type": "goal_delta", "goal_delta_id": "d2",
                         "from_task_version": 1, "to_task_version": 2}
                view["candidate_layout"]["B"]["G"]["goal_deltas"] = [basis]
                entry["gap_after"]["closure"] = {"kind": kind, "goal_delta_ref": basis}
            else:
                basis = {"type": "gap", "gap_id": "ga", "revision": 1, "task_version": 1}
                entry["gap_after"]["closure"] = {"kind": kind, "replacement_gap_ref": basis}
            args = compact(fixture.result())
            args["closure_assessments"][0]["basis_refs"] = [basis]
            result = compile_audit(call("submit_audit", args), view=view)
            self.assertEqual(result["closure_assessments"][0]["closure_kind"], kind)
            validate_audit_result(result, view=view, catalog=fixture.catalog)

    def test_missing_fields_reject_whole_submission(self):
        for name, args, compiler, kwargs in (
            ("submit_audit", compact(self.closure.result()), compile_audit, {"view": self.closure.view}),
            ("submit_selection", {"decision": "silent", "refs": None, "context_for_action": None},
             compile_selection, {"binding": self.binding})):
            for key in args:
                bad = deepcopy(args)
                del bad[key]
                with self.subTest(key=key), self.assertRaises(ContractError):
                    compiler(call(name, bad), **kwargs)
        args = compact(self.closure.result())
        del args["closure_assessments"][0]["assessed_scope"]
        with self.assertRaises(ContractError):
            self.audit_compile(args, self.closure)

    def test_selection_silent_exact_old_shape_and_remind_domain_validation(self):
        silent = self.select({"decision": "silent", "refs": None, "context_for_action": None})
        self.assertEqual(silent, {"decision": "silent", **self.binding})
        validate_selection(silent, snapshot=self.snapshot, phase2_view_id="v", selected_refs=[])
        args = {"decision": "remind", "refs": [self.ref], "context_for_action": "Check this gap."}
        original = deepcopy(args)
        result = self.select(args)
        validate_selection(result, snapshot=self.snapshot, phase2_view_id="v", selected_refs=[self.ref])
        with self.assertRaisesRegex(ContractError, "selection_invisible_ref"):
            validate_selection(result, snapshot=self.snapshot, phase2_view_id="v", selected_refs=[])
        result["refs"][0]["gap_id"] = "changed"
        self.assertEqual(args, original)

    def test_selection_rejects_missing_extra_nullable_and_bounds(self):
        base = {"decision": "remind", "refs": [self.ref], "context_for_action": "x"}
        bads = [{**base, "refs": value} for value in (None, [], [self.ref] * 4, [self.ref] * 2)]
        bads += [{**base, "context_for_action": value} for value in (None, "", "x" * 1201)]
        bads += [{**base, key: value} for key, value in self.binding.items()]
        bads += [{"decision": "silent"}, {**base, "decision": "silent"},
                 {"decision": "silent", "refs": [], "context_for_action": None}]
        malformed = deepcopy(base)
        malformed["refs"][0]["wrong_field"] = 1
        bads.append(malformed)
        for bad in bads:
            with self.subTest(bad=bad), self.assertRaises(ContractError):
                self.select(bad)
        self.select({**base, "context_for_action": "x" * 1200})


if __name__ == "__main__":
    unittest.main()
