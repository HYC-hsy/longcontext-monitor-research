"""Audit codec reconstruction and whole-output rejection controls."""

from copy import deepcopy
import unittest

from .audit import AuditCodec, validate_audit_result, validate_audit_result_v1
from .budget import TokenProxy
from .prompts import audit as audit_messages
from .source import ContractError, SourceCatalog, canonical, digest
from .test_contracts import empty_snapshot, leaf
from .test_schema_advanced import rich_state


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.before = empty_snapshot()
        self.after = deepcopy(self.before)
        self.after["state_version"] = 1
        self.after["B"]["G"]["specifications"] = [{"requirement_id": "r1",
            "revision": 1, "task_version": 1, "interpretation": "do task",
            "source_refs": [{"source_id": "u0", "start": 0, "end": 4,
                             "quote": "task"}], "status": "active", "retirement": None}]
        self.after["B"]["DeltaA"] = [{"gap_id": "g1", "revision": 1,
            "task_version": 1, "gap_kind": "achievement", "target": "task done",
            "reason": "not yet", "goal_refs": [{"type": "requirement",
                "requirement_id": "r1", "revision": 1, "task_version": 1}],
            "record_refs": [], "status": "open", "closure": None}]
        self.view = AuditCodec().encode(self.before, self.after,
            binding={"cycle_id": "cycle", "candidate_hash": digest(self.after)},
            sources=[], observations={"events": []}, operation_index=[],
            resolve_manifest=[])
        self.catalog = SourceCatalog({"u0": leaf("task")}, "window")
        self.span = self.catalog.add("u0", 0, 4, "audit")

    def test_reconstructs_and_preserves_order(self):
        AuditCodec().verify(self.view, self.before, self.after)
        changed = deepcopy(self.view)
        changed["candidate_layout"]["B"]["DeltaA"].clear()
        with self.assertRaises(ContractError):
            AuditCodec().verify(changed, self.before, self.after)

    def clean(self):
        return {"protocol": "audit-result/2", "binding": self.view["binding"],
                "outcome": "clean",
                "issues": [], "closure_assessments": [], "unusable_reason": None}

    def issue(self, quote="task"):
        return {"issue_id": "i1", "kind": "goal_misinterpretation",
                "target": {"snapshot": "candidate", "target": {"kind": "requirement",
                    "id": "r1", "revision": 1}, "field_path": "interpretation"},
                "related_targets": [], "explanation": "meaning disputed",
                "witnesses": [{"kind": "source", "ref": {
                    "evidence_id": self.span.evidence_id, "quote": quote}}],
                "repair_constraint": "retain the original request"}

    def test_clean_and_mixed_invalid_issue(self):
        self.assertEqual(validate_audit_result(self.clean(), view=self.view,
                          catalog=self.catalog)["outcome"], "clean")
        issues = self.clean()
        issues["outcome"] = "issues"
        issues["issues"] = [self.issue(), {**self.issue(), "issue_id": "i2"}]
        self.assertEqual(validate_audit_result(issues, view=self.view,
                         catalog=self.catalog)["outcome"], "issues")
        issues["issues"][1]["witnesses"] = []
        with self.assertRaisesRegex(ContractError, "missing_issue_witness"):
            validate_audit_result(issues, view=self.view, catalog=self.catalog)
        issues["issues"][1]["witnesses"] = self.issue()["witnesses"]
        issues["issues"][1]["target"]["field_path"] = "does_not_exist"
        with self.assertRaisesRegex(ContractError, "invalid_field_path"):
            validate_audit_result(issues, view=self.view, catalog=self.catalog)
        issues["issues"] = [self.issue("TASK")]
        with self.assertRaisesRegex(ContractError, "quote_mismatch"):
            validate_audit_result(issues, view=self.view, catalog=self.catalog)

    def test_extra_coverage_and_outcome_not_filtered(self):
        result = self.clean()
        result["coverage"] = []
        with self.assertRaises(ContractError):
            validate_audit_result(result, view=self.view, catalog=self.catalog)
        historical = {**self.clean(), "protocol": "audit-result/1",
                      "coverage": self.view["required_coverage"]}
        self.assertEqual(validate_audit_result_v1(historical, view=self.view,
                         catalog=self.catalog)["outcome"], "clean")
        with self.assertRaises(ContractError):
            validate_audit_result(historical, view=self.view, catalog=self.catalog)
        with self.assertRaises(ContractError):
            validate_audit_result_v1(self.clean(), view=self.view,
                                     catalog=self.catalog)
        result = self.clean()
        result["issues"] = [self.issue()]
        with self.assertRaisesRegex(ContractError, "contradictory_audit_outcome"):
            validate_audit_result(result, view=self.view, catalog=self.catalog)

    def test_v2_unusable_binding_and_target_guards(self):
        unusable = {**self.clean(), "outcome": "unusable", "unusable_reason": {
            "code": "insufficient_context", "detail": "cannot decide"}}
        self.assertEqual(validate_audit_result(unusable, view=self.view,
                         catalog=self.catalog)["outcome"], "unusable")
        for changed in ({**self.clean(), "binding": {}},
                        {**self.clean(), "protocol": "audit-result/1"},
                        {**self.clean(), "unexpected": True}):
            with self.assertRaises(ContractError):
                validate_audit_result(changed, view=self.view,
                                      catalog=self.catalog)
        issues = {**self.clean(), "outcome": "issues", "issues": [self.issue()]}
        issues["issues"][0]["target"]["target"]["id"] = "nonexistent"
        with self.assertRaisesRegex(ContractError, "unknown_target_id"):
            validate_audit_result(issues, view=self.view, catalog=self.catalog)

    def test_audit_and_correction_requests_describe_v2_without_echo(self):
        from .prompts import audit_correction
        messages = audit_messages(self.view)
        self.assertIn("audit-result/2", messages[0]["content"])
        self.assertIn("required_coverage", messages[1]["content"])
        self.assertIn("No coverage field is allowed", messages[0]["content"])
        corrected = audit_correction(original_messages=messages,
            raw_response="invalid", error="malformed_output")
        self.assertEqual(corrected[:2], messages)
        self.assertEqual(len(corrected), 3)

    def test_codec_shared_body_is_single_without_changing_reconstruction(self):
        before = deepcopy(self.after)
        after = deepcopy(before)
        before["B"]["G"]["specifications"][0]["interpretation"] = "long " * 1000
        after["B"]["G"]["specifications"][0]["interpretation"] = "long " * 1000
        after["state_version"] = before["state_version"] + 1
        view = AuditCodec().encode(before, after, binding={"cycle_id": "size"},
            sources=[], observations={"events": []}, operation_index=[],
            resolve_manifest=[])
        AuditCodec().verify(view, before, after)
        self.assertEqual(len(view["shared_objects"]), 2)
        self.assertLess(len(canonical(view)), len(canonical({
            "before": before, "candidate": after, "source_catalog": [],
            "observations": {"events": []}})))
        proxy = TokenProxy()
        deduplicated = proxy.measure(audit_messages(view))
        repeated = proxy.measure(audit_messages({"before": before,
            "candidate": after, "source_catalog": [],
            "observations": {"events": []}}))
        self.assertLess(deduplicated["proxy_tokens"], repeated["proxy_tokens"])
        self.assertLess(deduplicated["utf8_bytes"], repeated["utf8_bytes"])

    def test_archived_version_is_related_witness_not_candidate_target(self):
        before, ledger = rich_state()
        after = deepcopy(before)
        after["state_version"] += 1
        archived = deepcopy(before["B"]["W"]["states"][0])
        after["B"]["W"]["states"][0]["revision"] = 2
        after["B"]["W"]["states"][0]["supersedes"] = [{"type": "state",
            "record_id": "s", "revision": 1}]
        view = AuditCodec().encode(before, after, binding={"cycle_id": "archive"},
            sources=[], observations={"events": []}, operation_index=[],
            resolve_manifest=[], contextual_objects=[{"kind": "archived_state",
                "record_ref": {"type": "state", "record_id": "s", "revision": 1},
                "body": archived}])
        catalog = SourceCatalog(ledger, "window")
        historical_field = {"snapshot": "archive", "target": {"kind": "state",
            "id": "s", "revision": 1}, "field_path": "claim.text"}
        result = {"protocol": "audit-result/2", "binding": view["binding"],
            "outcome": "issues",
            "issues": [{"issue_id": "i", "kind": "observation_conflict",
                "target": {"snapshot": "candidate", "target": {"kind": "state",
                    "id": "s", "revision": 2}, "field_path": "claim.text"},
                "related_targets": [historical_field], "explanation": "synthetic",
                "witnesses": [{"kind": "field", "field": historical_field,
                               "exact_value": "feature absent"}],
                "repair_constraint": "retain evidence"}],
            "closure_assessments": [], "unusable_reason": None}
        self.assertEqual(validate_audit_result(result, view=view,
            catalog=catalog, archive={("state", "s", 1): archived})["outcome"],
            "issues")
        with self.assertRaisesRegex(ContractError, "unknown_target_id"):
            validate_audit_result(result, view=view, catalog=catalog, archive={})


if __name__ == "__main__":
    unittest.main()
