"""No-model regression for fixed official bytes and fail-closed live evaluation."""

import json
import os
from pathlib import Path

import pytest

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.live_launcher import (
    _require_evaluation_state_contract, _stage_verifier)
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.posthoc_artifact_eval import (
    classify_native_result, inspect_reports)


STAGE = Path(__file__).resolve().parent
MANIFEST = STAGE / "FOUR_RUN_MANIFEST_OFFICIAL_EVALUATOR_V2_DRAFT.json"
OFFICIAL = STAGE / "posthoc_official_20261014"
REPORTS = OFFICIAL / "runs_v2"


@pytest.fixture
def source_git():
    source = os.environ.get("PMA_OFFICIAL_SOURCE_GIT")
    if not source:
        pytest.fail("PMA_OFFICIAL_SOURCE_GIT must point to fixed upstream Git objects")
    return Path(source).resolve(strict=True)


@pytest.mark.parametrize("task", ("db-wal-recovery", "fix-code-vulnerability"))
def test_stage_uses_fixed_git_blobs(tmp_path, source_git, task):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    tests = tmp_path / "public_task" / "tests"
    tests.mkdir(parents=True)
    identity = _stage_verifier(tmp_path, task, manifest, source_git)
    assert identity["native_tests_tree_sha256"] == manifest["assets"][task][
        "native_tests_tree_sha256"]
    assert {p.name for p in tests.iterdir()} == {"test.sh", "test_outputs.py"}
    for member in manifest["assets"][task]["official_evaluator_members"]:
        assert (tests / Path(member["path"]).name).stat().st_size == member["bytes"]
    assert b"\r\n" not in (tests / "test.sh").read_bytes()
    with pytest.raises(RuntimeError):
        _stage_verifier(tmp_path, task, manifest, source_git)
    manifest["assets"][task]["official_evaluator_members"][0]["sha256"] = "0" * 64
    other = tmp_path / "another" / "public_task" / "tests"
    other.mkdir(parents=True)
    with pytest.raises(RuntimeError):
        _stage_verifier(tmp_path / "another", task, manifest, source_git)
    assert not list(other.iterdir())


def test_new_live_evaluation_cannot_silently_use_old_shared_path():
    with pytest.raises(RuntimeError, match="not certified"):
        _require_evaluation_state_contract(json.loads(MANIFEST.read_text()))


def test_original_posthoc_reports_remain_mechanical_inputs():
    baseline = json.loads((REPORTS / "code_b/verifier/original-repo-ctrf.json").read_text())
    baseline_ids = {item["name"] for item in baseline["results"]["tests"]}
    for arm, task in (("db_a", "db-wal-recovery"), ("db_b", "db-wal-recovery"),
                      ("code_a", "fix-code-vulnerability"),
                      ("code_b", "fix-code-vulnerability")):
        logs = REPORTS / arm / "verifier"
        complete, details = inspect_reports(task, logs, official_tests=OFFICIAL / task / "tests",
                                            required_original_ids=baseline_ids)
        assert complete, details
        classified = classify_native_result(
            task, logs, official_tests=OFFICIAL / task / "tests",
            required_original_ids=baseline_ids, native_exit=0, timed_out=False,
            cleanup_confirmed=True)
        assert classified["classification"] in ("native_pass", "native_assertion_failure")


def test_report_mismatch_is_not_zero(tmp_path):
    import shutil
    shutil.copytree(REPORTS / "db_a/verifier", tmp_path / "verifier", dirs_exist_ok=True)
    logs = tmp_path / "verifier"
    (logs / "reward.txt").write_text("1\n", encoding="utf-8")
    result = classify_native_result("db-wal-recovery", logs,
        official_tests=OFFICIAL / "db-wal-recovery/tests", required_original_ids=None,
        native_exit=0, timed_out=False, cleanup_confirmed=True)
    assert result["classification"] == "evaluation_infrastructure_or_incomplete"
    assert result["reason"] == "reward_disagrees_with_official_script_rule"
    report = json.loads((logs / "ctrf.json").read_text())
    report["results"]["summary"]["passed"] = 1
    (logs / "ctrf.json").write_text(json.dumps(report), encoding="utf-8")
    complete, reason = inspect_reports("db-wal-recovery", logs,
                                       official_tests=OFFICIAL / "db-wal-recovery/tests")
    assert not complete and "summary_result_mismatch" in reason


@pytest.mark.parametrize("fault", ("missing_external", "unexpected_skip", "partial",
                                  "collection_missing", "timeout", "cleanup"))
def test_incomplete_or_infrastructure_result_is_not_normal_reward(tmp_path, fault):
    import shutil
    shutil.copytree(REPORTS / "db_b/verifier", tmp_path / "verifier")
    logs = tmp_path / "verifier"
    if fault == "missing_external":
        report = json.loads((logs / "ctrf.json").read_text())
        report["results"]["tests"].remove(next(
            item for item in report["results"]["tests"] if item["status"] == "passed"))
        report["results"]["summary"]["tests"] -= 1
        report["results"]["summary"]["passed"] -= 1
        (logs / "ctrf.json").write_text(json.dumps(report))
    elif fault == "unexpected_skip":
        report = json.loads((logs / "ctrf.json").read_text())
        next(item for item in report["results"]["tests"] if item["status"] == "passed")[
            "status"] = "skipped"
        report["results"]["summary"]["passed"] -= 1
        report["results"]["summary"]["skipped"] += 1
        (logs / "ctrf.json").write_text(json.dumps(report))
    elif fault in ("partial", "collection_missing"):
        (logs / "ctrf.json").unlink()
    result = classify_native_result("db-wal-recovery", logs,
        official_tests=OFFICIAL / "db-wal-recovery/tests", required_original_ids=None,
        native_exit=0, timed_out=fault == "timeout",
        cleanup_confirmed=fault != "cleanup")
    assert result["classification"] == "evaluation_infrastructure_or_incomplete"
