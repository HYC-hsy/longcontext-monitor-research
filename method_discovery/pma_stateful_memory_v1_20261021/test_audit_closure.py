"""Closure assessment uses bound before/after and real source roles."""

from copy import deepcopy
import unittest

from .audit import AuditCodec, validate_audit_result
from .source import ContractError, SourceCatalog
from .test_schema_advanced import rich_state


class AuditClosureTests(unittest.TestCase):
    def setUp(self):
        before, ledger = rich_state()
        after = deepcopy(before)
        after["state_version"] += 1
        after_gap = after["B"]["DeltaE"][0]
        after_gap["revision"] = 2
        after_gap["status"] = "supported"
        after_gap["closure"] = {"kind": "environment_supported",
            "conclusion": "feature absent", "evidence_refs": [{"source_id": "tool",
                "start": 0, "end": 14, "quote": "feature absent"}], "state_refs": []}
        self.before, self.after = before, after
        self.catalog = SourceCatalog(ledger, "window")
        self.tool = self.catalog.add("tool", 0, 14, "audit")
        self.user = self.catalog.add("u0", 0, 4, "audit")
        self.view = AuditCodec().encode(before, after, binding={"cycle_id": "c"},
            sources=[], observations={"events": []}, operation_index=[],
            resolve_manifest=[{"resolution_id": "ge",
                "gap_before": before["B"]["DeltaE"][0],
                "gap_after": after_gap, "closure_kind": "environment_supported"}])

    def result(self):
        return {"protocol": "audit-result/1", "binding": self.view["binding"],
            "coverage": self.view["required_coverage"], "outcome": "clean",
            "issues": [], "closure_assessments": [{"resolution_id": "ge",
                "gap_before": {"type": "gap", "gap_id": "ge", "revision": 1,
                               "task_version": 1},
                "gap_after": {"type": "gap", "gap_id": "ge", "revision": 2,
                              "task_version": 1},
                "closure_kind": "environment_supported", "verdict": "supported",
                "assessed_scope": {}, "explanation": "observed answer",
                "basis_refs": [{"evidence_id": self.tool.evidence_id,
                                "quote": "feature absent"}],
                "blocking_issue_ids": []}], "unusable_reason": None}

    def test_valid_closure_and_wrong_basis(self):
        good = self.result()
        self.assertEqual(validate_audit_result(good, view=self.view,
                         catalog=self.catalog)["outcome"], "clean")
        bad = self.result()
        bad["closure_assessments"][0]["basis_refs"] = [{
            "evidence_id": self.user.evidence_id, "quote": "task"}]
        with self.assertRaisesRegex(ContractError, "source_role_misuse"):
            validate_audit_result(bad, view=self.view, catalog=self.catalog)
        bad = self.result()
        bad["closure_assessments"][0]["gap_after"]["revision"] = 3
        with self.assertRaisesRegex(ContractError, "closure_assessment_mismatch"):
            validate_audit_result(bad, view=self.view, catalog=self.catalog)


if __name__ == "__main__":
    unittest.main()
