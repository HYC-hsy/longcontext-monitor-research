"""Offline-only checks for a non-executable UC-R5 preregistration freeze."""

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "method_discovery/runs/uc_r5_cmp_readiness_20261003"
PRIVATE = Path(r"E:\uc_r5_cmp_private_20261003")
MODULE = ROOT / "method_discovery/uc_r5_freeze_comparison.py"
SPEC = importlib.util.spec_from_file_location("uc_r5_freeze_comparison", MODULE)
FREEZE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FREEZE)


def test_freeze_keeps_exact_allocation_and_is_not_runner_manifest(tmp_path):
    output = tmp_path / "prereg"
    result = FREEZE.freeze(PREP, output, PRIVATE, "a" * 40)
    assert result["slot_count"] == 30
    assert result["prereg_sha256"] == FREEZE.sha(output / "PREREGISTRATION.json")
    draft = json.loads((PREP / "SLOT_DRAFT.json").read_text(encoding="utf-8"))["slots"]
    checklist = json.loads((output / "SLOT_EXECUTION_CHECKLIST.json").read_text(encoding="utf-8"))
    rows = checklist["proposed_slots"]
    assert [(r["run_id"], r["task"], r["condition"], r["repetition"], r["block"], r["position"])
            for r in rows] == [
        (r["run_id"], r["task"], r["condition"], r["repetition"], r["block"], r["position"])
        for r in draft]
    assert "runs" not in checklist  # incompatible with existing runner's executable manifest format
    assert checklist["execution_authorized"] is False
    assert all(not row["launchable_now"] and row["status"] == "not_started" for row in rows)
    assert len({row["run_id"] for row in rows}) == 30


def test_profiles_and_budget_differ_only_as_frozen(tmp_path):
    output = tmp_path / "prereg"
    FREEZE.freeze(PREP, output, PRIVATE, "b" * 40)
    prereg = json.loads((output / "PREREGISTRATION.json").read_text(encoding="utf-8"))
    assert prereg["execution_authorized"] is False
    assert prereg["planned_conditions"] == {
        group: {"view": view, "intent": intent}
        for group, (view, intent) in FREEZE.CONDITIONS.items()}
    assert prereg["resources"]["task_max_turns"] == 180
    assert prereg["resources"]["max_agent_seconds"] == 10000
    assert prereg["resources"]["working_view_chars"] == 4000
    assert prereg["resources"]["intent_window_requests"] == 4
    assert prereg["unit"] == "complete fresh session; reviews are not independent samples"
    assert prereg["analysis"]["contrasts"]["interaction"] == "AB-AP-RB+RP"
    assert prereg["post_run_unknown"]["observed_model_identity"] is None
    assert prereg["post_run_unknown"]["final_scored_workspace_sha256"] is None
    for group, record in prereg["launch_profiles"].items():
        assert record["monitor_profile_sha256"] == FREEZE.sha(
            PRIVATE / f"launch_{group}/monitor_config/models.local.json")
        assert record["ga_source_tree_hash_runner_scope"] == FREEZE.LAUNCH_SOURCE_SHA256


def test_all_ledger_rows_start_unknown_not_false(tmp_path):
    output = tmp_path / "prereg"
    FREEZE.freeze(PREP, output, PRIVATE, "c" * 40)
    ledger = json.loads((output / "RESULT_LEDGER_INITIAL.json").read_text(encoding="utf-8"))
    assert ledger["execution_authorized"] is False
    assert len(ledger["records"]) == 30
    assert all(row["status"] == "not_started" and row["valid"] is None
               and row["final_allow_observed"] is None and row["false_allow"] is None
               for row in ledger["records"])


def test_existing_output_cannot_be_overwritten(tmp_path):
    output = tmp_path / "prereg"
    output.mkdir()
    with pytest.raises(FileExistsError):
        FREEZE.freeze(PREP, output, PRIVATE, "d" * 40)


def test_generator_has_no_launch_or_model_client():
    body = MODULE.read_text(encoding="utf-8")
    assert "import subprocess" not in body
    assert "import requests" not in body
    assert "harbor jobs start" not in body
    assert "MonitorRuntime" not in body
    assert "run_proof(" not in body
