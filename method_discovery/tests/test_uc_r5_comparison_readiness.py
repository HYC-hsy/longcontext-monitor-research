"""Deterministic checks for the non-executable UC-R5 readiness artifacts."""

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "method_discovery/runs/uc_r5_cmp_readiness_20261003"
MODULE = ROOT / "method_discovery/prepare_uc_r5_comparison_readiness.py"
spec = importlib.util.spec_from_file_location("uc_r5_readiness", MODULE)
readiness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readiness)


def read(name):
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def test_frozen_allocation_and_fresh_opaque_slots():
    rows = read("SLOT_DRAFT.json")["slots"]
    assert len(rows) == 30
    assert [row["condition"] for row in rows] == [
        value for _, _, sequence in readiness.ORDER for value in sequence]
    assert len({row["run_id"] for row in rows}) == len(rows)
    assert len({row["live_root"] for row in rows}) == len(rows)
    assert all(len(row["run_id"]) == 24 and row["status"] == "not_started" for row in rows)


def test_all_five_profile_variants_differ_only_in_two_treatment_keys():
    profiles = read("CONFIG_PROPAGATION.json")["profile_variants"]
    assert set(profiles) == set(readiness.CONDITIONS)
    for condition, (view, intent) in readiness.CONDITIONS.items():
        row = profiles[condition]
        for layer in ("source", "bundled"):
            assert row[layer]["monitor_research_view"] == view
            assert row[layer]["monitor_research_intent"] == intent
            assert row[layer]["monitor_research_intent_window_requests"] == 4
            assert row[layer]["monitor_dcec"] is True
            assert row[layer]["monitor_dcec_working_chars"] == 4000
        assert row["worker"] is None and row["observed_model"] is None
    for layer in ("source", "bundled"):
        common = [{k: v for k, v in row[layer].items()
                   if k not in ("monitor_research_view", "monitor_research_intent")}
                  for row in profiles.values()]
        assert all(row == common[0] for row in common)


def test_task_input_transformation_and_asset_boundaries():
    tasks = read("TASK_ASSETS.json")["tasks"]
    assert set(tasks) == {"ktx-0.13.0-roadmap", "fyn-2.2.0-roadmap"}
    for task, row in tasks.items():
        root = OUTPUT / "public_task_inputs" / task
        original = (root / "original_instruction.txt").read_bytes()
        actual = (root / "actual_task_input.txt").read_bytes()
        monitor = (root / "monitor_original_task.txt").read_bytes()
        assert actual.startswith(original) and len(actual) > len(original)
        assert monitor == actual
        assert readiness.sha(original) == row["instruction"]["sha256"]
        assert readiness.sha(actual) == row["actual_task_input_sha256"]
        assert row["hidden_tests_identity_only"]["file_count"] > 0
        assert row["solution_identity_only"]["file_count"] > 0
        assert row["actual_image_id"] is None and row["repo_digest"] is None


def test_draft_is_not_executable_and_public_proof_contains_no_secrets():
    draft = read("PREREGISTRATION_DRAFT.json")
    assert draft["execution_authorized"] is False
    assert draft["comparison_approved"] is None
    assert draft["worker_provider_ready_identity"] is None
    assert draft["scientific_record_count"] == 0
    for name in ("CONFIG_PROPAGATION.json", "PREREGISTRATION_DRAFT.json"):
        raw = (OUTPUT / name).read_text(encoding="utf-8").lower()
        assert all(secret not in raw for secret in
                   ('"apikey"', '"apibase"', '"authorization"', 'sk-ant-', 'bearer '))
    environment = read("ENVIRONMENT_DRAFT.json")
    assert environment["execution_authorized"] is False
    assert environment["common"]["GA_MONITOR_DCEC"] == "1"
    assert environment["common"]["GA_MONITOR_INDEPENDENT_C"] == "0"
    assert environment["common"]["GA_PMA_ENABLED"] == "0"
    assert all(not key.startswith("GA_MONITOR_RESEARCH_")
               for key in environment["common"])


def test_no_model_or_verifier_entry_point_in_preparation_tool():
    text = MODULE.read_text(encoding="utf-8")
    assert "build_bundle(" in text and "load_profile(" in text
    assert all(call not in text for call in
               ("run_proof(", "run_trial(", "request_completion(", "verify_checkpoint("))


def test_copied_scripted_requests_are_complete_but_not_l2_proof():
    sample_root = OUTPUT / "SCRIPTED_PROVIDER_READY_SAMPLES"
    manifest = json.loads((sample_root / "MANIFEST.json").read_text(encoding="utf-8"))
    assert set(manifest["samples"]) == {
        "off_frozen", "off_candidate", "R_flat", "A_framed", "P_note",
        "B_routed", "combined_budget", "return_boundary"}
    for row in manifest["samples"].values():
        data = (sample_root / row["file"]).read_bytes()
        assert readiness.sha(data) == row["sha256"]
        assert set(json.loads(data)) >= {"system", "messages", "tools", "model_parameters"}
    assert read("PREREGISTRATION_DRAFT.json")["L2"] == "blocked_docker_unavailable"
