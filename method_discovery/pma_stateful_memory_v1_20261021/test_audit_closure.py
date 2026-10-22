"""Closure assessment uses bound before/after and real source roles."""

from copy import deepcopy
import unittest

from .audit import AuditCodec, validate_audit_result
from .source import ContractError, SourceCatalog
from .test_schema_advanced import rich_state


class AuditClosureTests(unittest.TestCase):
    def test_goal_changed_and_merged_into_basis_unions(self):
        for kind in ("goal_changed", "merged_into"):
            with self.subTest(kind=kind):
                before, ledger = rich_state()
                after = deepcopy(before)
                after["state_version"] += 1
                gap = after["B"]["DeltaE"][0]
                gap["revision"] = 2
                gap["status"] = "superseded"
                if kind == "goal_changed":
                    delta = {"type": "goal_delta", "goal_delta_id": "d2",
                        "from_task_version": 1, "to_task_version": 2}
                    after["B"]["G"]["goal_deltas"] = [delta]
                    basis = delta
                    gap["closure"] = {"kind": kind, "goal_delta_ref": delta}
                else:
                    basis = {"type": "gap", "gap_id": "ga", "revision": 1,
                             "task_version": 1}
                    gap["closure"] = {"kind": kind,
                                      "replacement_gap_ref": basis}
                catalog = SourceCatalog(ledger, "branch-" + kind)
                view = AuditCodec().encode(before, after, binding={"cycle_id": kind},
                    sources=[], observations={"events": []}, operation_index=[],
                    resolve_manifest=[{"resolution_id": "ge",
                        "gap_before": before["B"]["DeltaE"][0],
                        "gap_after": gap, "closure_kind": kind}])
                result = {"protocol": "audit-result/2", "binding": view["binding"],
                    "outcome": "clean",
                    "issues": [], "closure_assessments": [{"resolution_id": "ge",
                        "gap_before": {"type": "gap", "gap_id": "ge",
                            "revision": 1, "task_version": 1},
                        "gap_after": {"type": "gap", "gap_id": "ge",
                            "revision": 2, "task_version": 1},
                        "closure_kind": kind, "verdict": "supported",
                        "assessed_scope": {}, "explanation": "synthetic branch",
                        "basis_refs": [basis], "blocking_issue_ids": []}],
                    "unusable_reason": None}
                self.assertEqual(validate_audit_result(result, view=view,
                    catalog=catalog)["outcome"], "clean")
                invalid = deepcopy(result)
                invalid["closure_assessments"][0]["basis_refs"] = []
                with self.assertRaisesRegex(ContractError,
                                            "closure_basis_mismatch"):
                    validate_audit_result(invalid, view=view, catalog=catalog)

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
        return {"protocol": "audit-result/2", "binding": self.view["binding"],
            "outcome": "clean",
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
