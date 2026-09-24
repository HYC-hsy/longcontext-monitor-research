"""Offline-only D1 materializer and contract tests.

This module deliberately has no provider imports or network entry point.  It
constructs deterministic model-visible envelopes from frozen source
references, keeping research condition identity outside those envelopes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MANIFEST = HERE / "manifest.json"
SEMANTIC_CONTRACT = (
    "current decision scope; local evidence does not automatically promote to whole task; "
    "observation outcomes must distinguish different control actions; observation boundary "
    "must reach the relevant behavior; unfinished or unavailable observation is not positive "
    "evidence; re-evaluate the same root anchor; relax after adequate evidence"
)
TOOLS = ["file_read", "file_list", "text_search", "code_run"]


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _case_material(case: dict) -> dict:
    """Return only task/evidence identity; no research labels or expected outcomes."""
    files = case["source_files"]
    return {
        "task_id": case["task_id"],
        "source_references": {
            key: {"path": value["path"], "sha256": value["sha256"]}
            for key, value in sorted(files.items())
        },
        "cutoff": case.get("cutoff"),
        "checkpoint_identity": case.get("checkpoint_identity"),
        "tools": TOOLS,
    }


def build_request(manifest: dict, case_key: str, condition: str) -> dict:
    """Build one deterministic model-visible request envelope."""
    case = manifest["cases"][case_key]
    material = _case_material(case)
    # This hash is the shared parent/evidence identity.  It is identical across
    # FREE and PROTOCOL for a case and contains no treatment or result label.
    shared = {
        "decision_scope": "consequential root decision",
        "semantic_guidance": SEMANTIC_CONTRACT,
        "parent_context_sha256": digest(material),
        "task_and_evidence": material,
        "tools": TOOLS,
        "budget": {"max_logical_calls": manifest["shared"]["logical_call_limit"]},
    }
    if condition == "PROTOCOL":
        shared["control_representation_contract"] = {
            "purpose": "model-owned decision-critical observation lifecycle",
            "operations": ["create", "retain", "replace", "discharge"],
            "statuses": ["requested", "running", "interrupted", "unavailable", "completed"],
            "receipt_rule": "reference only deterministic receipts observed by this run",
        }
    elif condition != "FREE":
        raise ValueError(f"unknown condition: {condition}")
    return shared


def build_all(manifest: dict) -> dict:
    records = []
    for run_id in manifest["run_order"]:
        case_key, condition, repeat = run_id.split("-")
        records.append({
            "run_id": run_id,
            "case_key": case_key,
            "condition": condition,
            "repeat": int(repeat[1:]),
            "model_visible_request": build_request(manifest, case_key, condition),
        })
    return {"schema_version": "d1-materialized-request-set/1", "records": records}


def materialize(out: Path) -> None:
    manifest = load_manifest()
    out.mkdir(parents=True, exist_ok=False)
    payload = build_all(manifest)
    (out / "requests.json").write_bytes(canonical(payload))
    diffs = {}
    for key in manifest["cases"]:
        free = build_request(manifest, key, "FREE")
        protocol = build_request(manifest, key, "PROTOCOL")
        diffs[key] = {
            "shared_sha256": digest(free),
            "protocol_sha256": digest(protocol),
            "added_top_level_keys": sorted(set(protocol) - set(free)),
            "removed_top_level_keys": sorted(set(free) - set(protocol)),
        }
    (out / "treatment_diffs.json").write_bytes(canonical(diffs))


class D1PreparationTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_manifest()

    def test_fixed_identities_and_budget(self):
        self.assertEqual(self.manifest["status"], "prepared_not_executed")
        self.assertEqual(len(self.manifest["run_order"]), 12)
        self.assertTrue(all("-r1" in r or "-r2" in r for r in self.manifest["run_order"]))
        self.assertEqual(self.manifest["shared"]["logical_call_limit"], 6)
        self.assertFalse(self.manifest["execution_authorized"])

    def test_source_case_contracts(self):
        self.assertEqual(self.manifest["cases"]["F"]["checkpoint_identity"]["task_turn"], 86)
        cutoff = self.manifest["cases"]["S"]["cutoff"]
        self.assertEqual(cutoff["internal_turn"], 52)
        self.assertTrue(cutoff["excludes_later_events"])
        self.assertEqual(self.manifest["cases"]["C"]["source_run"], "r12_discriminating_selector_screen")

    def test_treatment_only_diff(self):
        for case_key in self.manifest["cases"]:
            free = build_request(self.manifest, case_key, "FREE")
            protocol = build_request(self.manifest, case_key, "PROTOCOL")
            self.assertEqual({k: v for k, v in free.items()}, {
                k: v for k, v in protocol.items() if k != "control_representation_contract"
            })
            self.assertEqual(set(protocol) - set(free), {"control_representation_contract"})
            self.assertEqual(free["parent_context_sha256"], protocol["parent_context_sha256"])

    def test_no_research_metadata_leak(self):
        forbidden = ("expected_result", "candidate_winner", "research_only", "FREE", "PROTOCOL")
        for case_key in self.manifest["cases"]:
            for condition in ("FREE", "PROTOCOL"):
                blob = canonical(build_request(self.manifest, case_key, condition)).decode()
                self.assertFalse(any(token in blob for token in forbidden))

    def test_materialization_is_local_and_deterministic(self):
        first = build_all(self.manifest)
        second = build_all(self.manifest)
        self.assertEqual(canonical(first), canonical(second))
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "requests"
            materialize(out)
            self.assertTrue((out / "requests.json").exists())
            self.assertTrue((out / "treatment_diffs.json").exists())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--materialize", type=Path)
    args = parser.parse_args()
    if args.self_test:
        return 0 if unittest.main(module=__name__, argv=["d1_harness"], exit=False).result.wasSuccessful() else 1
    if args.materialize:
        materialize(args.materialize)
        return 0
    parser.error("preparation-only harness: use --self-test or --materialize")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
