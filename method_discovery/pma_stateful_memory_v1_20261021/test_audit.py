"""Audit codec reconstruction and whole-output rejection controls."""

from copy import deepcopy
import unittest

from .audit import AuditCodec, validate_audit_result
from .source import ContractError, SourceCatalog, digest
from .test_contracts import empty_snapshot, leaf


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
        return {"protocol": "audit-result/1", "binding": self.view["binding"],
                "coverage": self.view["required_coverage"], "outcome": "clean",
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
        issues["issues"] = [self.issue(), {**self.issue(), "issue_id": "i2",
                                               "witnesses": []}]
        self.assertEqual(validate_audit_result(issues, view=self.view,
                         catalog=self.catalog)["outcome"], "issues")
        issues["issues"][1]["target"]["field_path"] = "does_not_exist"
        with self.assertRaisesRegex(ContractError, "invalid_field_path"):
            validate_audit_result(issues, view=self.view, catalog=self.catalog)
        issues["issues"] = [self.issue("TASK")]
        with self.assertRaisesRegex(ContractError, "quote_mismatch"):
            validate_audit_result(issues, view=self.view, catalog=self.catalog)

    def test_coverage_and_outcome_not_filtered(self):
        result = self.clean()
        result["coverage"] = []
        with self.assertRaisesRegex(ContractError, "coverage_mismatch"):
            validate_audit_result(result, view=self.view, catalog=self.catalog)
        result = self.clean()
        result["issues"] = [self.issue()]
        with self.assertRaisesRegex(ContractError, "contradictory_audit_outcome"):
            validate_audit_result(result, view=self.view, catalog=self.catalog)


if __name__ == "__main__":
    unittest.main()
