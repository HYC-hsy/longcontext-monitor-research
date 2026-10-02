"""Freeze non-executable UC-R5 comparison allocation and identities.

Research metadata generator only. It has no model, Task Agent, Harbor launch,
verifier, subprocess execution, or scientific-run entry point.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


CANDIDATE = "232281d650d062bdc6a6030f40ccb904c1ac0851"
BASELINE = "6c72477fce3350c82baf74a9ca8a96c87742be5b"
SLOT_SHA256 = "ae7b7e93f79886be1e7801e358e0bcafbaa160071b33afe03dc67de25ee842fa"
LAUNCH_SOURCE_SHA256 = "21bca97c077317d11467a28405ecd2abdb4aa8a0f3c97b74574626cba5be30c4"
HARNESS_SHA256 = "1c2256113d5fc8ab43e307a9edf29b16c6defeb1d5f5e69d954784cea1618bd6"
ORDER = (
    ("b01", "ktx-0.13.0-roadmap", 2, ("RP", "C0", "RB", "AB", "AP")),
    ("b02", "ktx-0.13.0-roadmap", 1, ("RB", "RP", "AB", "C0", "AP")),
    ("b03", "ktx-0.13.0-roadmap", 3, ("RP", "C0", "RB", "AP", "AB")),
    ("b04", "fyn-2.2.0-roadmap", 1, ("AB", "RB", "RP", "AP", "C0")),
    ("b05", "fyn-2.2.0-roadmap", 2, ("RP", "RB", "AB", "C0", "AP")),
    ("b06", "fyn-2.2.0-roadmap", 3, ("C0", "RB", "AP", "AB", "RP")),
)
CONDITIONS = {"C0": ("off", "off"), "RP": ("flat", "note"),
              "AP": ("framed", "note"), "RB": ("flat", "routed"),
              "AB": ("framed", "routed")}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runner_scoped_source_hash(root: Path) -> str:
    """Recompute the existing runner's deterministic GA source identity."""
    digest = hashlib.sha256()
    files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in {".git", "__pycache__", ".pytest_cache", "temp"} for part in rel.parts):
            continue
        if rel == Path("memory/file_access_stats.json"):
            continue
        files.append(path)
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(rel).to_bytes(4, "big"))
        digest.update(rel)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def freeze(prep: Path, output: Path, private: Path, implementation_commit: str):
    if output.exists():
        raise FileExistsError(output)
    slot_path = prep / "SLOT_DRAFT.json"
    if sha(slot_path) != SLOT_SHA256:
        raise ValueError("frozen slot bytes changed")
    slots = read(slot_path)["slots"]
    expected = [(block, task, rep, pos, group)
                for block, task, rep, groups in ORDER
                for pos, group in enumerate(groups, 1)]
    actual = [(s["block"], s["task"].split(":", 1)[1], s["repetition"],
               s["position"], s["condition"]) for s in slots]
    if len(slots) != 30 or actual != expected or len({s["run_id"] for s in slots}) != 30:
        raise ValueError("allocation differs from the accepted draft")
    if any(s["status"] != "not_started" or Path(s["live_root"]).exists() for s in slots):
        raise ValueError("slot status or live-root freshness changed")
    assets = read(prep / "TASK_ASSETS.json")["tasks"]
    images = read(prep / "IMAGE_AND_DEPLOYMENT.json")["images"]
    profiles = read(prep / "CONFIG_PROPAGATION.json")
    common = read(prep / "ENVIRONMENT_DRAFT.json")["common"]
    budget = read(prep / "BUDGET_AND_COST.json")
    if not all(read(prep / "L2_EVIDENCE" / g / "research_l2_summary.json")["input_readback_equal"]
               for g in CONDITIONS):
        raise ValueError("deployed task input readback failed")
    if not read(prep / "L2_EVIDENCE/C0_BASELINE_COMPARISON.json")["all_equal"]:
        raise ValueError("frozen C0 provider-ready comparison failed")
    if not read(prep / "IMAGE_AND_DEPLOYMENT.json")["all_images_match_proposals"]:
        raise ValueError("actual image mismatch")
    if not read(prep / "IMAGE_AND_DEPLOYMENT.json")["all_deployed_code_matches_candidate"]:
        raise ValueError("deployed code mismatch")

    launch = {}
    for group, (view, intent) in CONDITIONS.items():
        root = private / f"launch_{group}"
        profile = root / "monitor_config/models.local.json"
        source = root / "GenericAgent-main"
        variant = profiles["profile_variants"][group]
        if not source.is_dir() or not profile.is_file():
            raise FileNotFoundError(f"private launch layout missing for {group}")
        if sha(profile) != variant["source_profile_sha256"]:
            raise ValueError(f"private profile identity mismatch for {group}")
        if runner_scoped_source_hash(source) != LAUNCH_SOURCE_SHA256:
            raise ValueError(f"private GA source identity mismatch for {group}")
        if (variant["bundled"]["monitor_research_view"],
                variant["bundled"]["monitor_research_intent"]) != (view, intent):
            raise ValueError(f"treatment mapping mismatch for {group}")
        launch[group] = {"ga_host_root": str(source), "monitor_profile_path": str(profile),
                         "monitor_profile_sha256": sha(profile),
                         "configured_monitor_model": variant["bundled"]["model"],
                         "bundle_source": profiles["private_bundle_roots"][group],
                         "bundle_snapshot_sha256": variant["bundle_snapshot_sha256"],
                         "bundle_deployed_profile_sha256": variant["deployed_profile_sha256"],
                         "ga_source_tree_hash_runner_scope": LAUNCH_SOURCE_SHA256,
                         "view": view, "intent": intent, "intent_window": 4}

    output.mkdir(parents=True)
    checklist = []
    ledger = []
    for ordinal, slot in enumerate(slots, 1):
        group = slot["condition"]
        short_task = slot["task"].split(":", 1)[1]
        asset = assets[short_task]
        image = images[short_task]
        task_input = prep / "public_task_inputs" / short_task / "actual_task_input.txt"
        monitor_input = prep / "public_task_inputs" / short_task / "monitor_original_task.txt"
        if sha(task_input) != asset["actual_task_input_sha256"] or sha(monitor_input) != sha(task_input):
            raise ValueError(f"task input bytes differ for {short_task}")
        row = dict(slot)
        row.update({"ordinal": ordinal, "launchable_now": False,
                    "candidate_commit": CANDIDATE, "production_baseline": BASELINE,
                    "deployment": launch[group],
                    "task_identity": {"proposal_row_sha256": asset["proposal_row_sha256"],
                                      "task_tree_sha256": asset["task_tree"]["sha256"],
                                      "instruction_sha256": asset["instruction"]["sha256"],
                                      "task_toml_sha256": asset["task_toml"]["sha256"],
                                      "actual_task_input_path": str(task_input),
                                      "actual_task_input_sha256": sha(task_input),
                                      "monitor_original_task_path": str(monitor_input),
                                      "monitor_original_task_sha256": sha(monitor_input),
                                      "proposal_source_revision_not_assumed_image_head": asset["source_revision"]},
                    "image": {"tag": image["tag"], "id": image["image_id"],
                              "repo_digests": image["repo_digests"], "architecture": image["architecture"]},
                    "runner": {"source_file": "long_context_bench/scripts/run_ultralong_m12_proofs.py",
                               "source": "roadmapbench", "task_id": short_task,
                               "run_id_argument": slot["run_id"], "llm_no": 0,
                               "max_agent_seconds": 10000,
                               "requires_separate_main_thread_authorization": True,
                               "authorized_experiment_manifest": None,
                               "execution_harness_sha256": HARNESS_SHA256},
                    "output": {"campaign_root": r"E:\LongContext\long_context_bench\output\uc_r5_comparison_v1_20261003",
                               "jobs_subdir": f"jobs/{slot['run_id']}",
                               "runs_subdir": f"runs/{slot['run_id']}"},
                    "isolation": {"profile": "no-network-unix-inference-v1",
                                  "task_network": "none", "gateway": "separate Unix socket",
                                  "mounts_must_be_recaptured_pre_request": True}})
        checklist.append(row)
        ledger.append({"run_id": slot["run_id"], "ordinal": ordinal,
                       "task": slot["task"], "repetition": slot["repetition"],
                       "condition": group, "status": "not_started", "valid": None,
                       "validation_errors": None, "exception_info": None,
                       "observed_model": None, "actual_usage": None,
                       "final_allow_observed": None, "final_allow_valid": None,
                       "scored_artifact_sha256": None, "evaluator_invocation": None,
                       "native_reward": None, "native_all_phases_passed": None,
                       "false_allow": None, "failure_category": None})
    write(output / "SLOT_EXECUTION_CHECKLIST.json", {"execution_authorized": False,
                                                      "proposed_slots": checklist})
    write(output / "RESULT_LEDGER_INITIAL.json", {"execution_authorized": False,
                                                    "records": ledger})
    prereg = {
        "schema_version": "uc-r5-comparison-v1-prereg/1", "execution_authorized": False,
        "status": "frozen_for_main_review_not_started", "scientific_records": 0,
        "implementation_freeze_commit": implementation_commit,
        "candidate_commit": CANDIDATE, "production_baseline_commit": BASELINE,
        "slot_draft": {"path": str(slot_path), "sha256": SLOT_SHA256,
                       "all_status": "not_started", "count": 30},
        "slot_execution_checklist": "SLOT_EXECUTION_CHECKLIST.json",
        "planned_conditions": {k: {"view": v[0], "intent": v[1]} for k, v in CONDITIONS.items()},
        "task_ids": ["roadmapbench:ktx-0.13.0-roadmap", "roadmapbench:fyn-2.2.0-roadmap"],
        "allocation_order": [s["run_id"] for s in slots],
        "unit": "complete fresh session; reviews are not independent samples",
        "all_assigned_slots_in_ledger": True, "non_adoption_and_incomplete_retained": True,
        "resources": {"task_max_turns": 180, "max_agent_seconds": 10000,
                      "dcec": True, "working_view_chars": 4000, "intent_window_requests": 4,
                      "source_body_chars": 6000, "per_source_chars": 1500,
                      "additional_block_chars": 14000,
                      "monitor_max_review_turns": budget["monitor_max_review_turns_default"],
                      "monitor_completion_timeout_seconds": budget["monitor_completion_timeout_seconds_default"],
                      "monitor_runtime_deadline_seconds": budget["monitor_runtime_deadline_seconds_default"],
                      "task_toml_agent_timeout_seconds": budget["task_toml_agent_timeout_seconds"],
                      "harbor_agent_timeout_multiplier": budget["harbor_agent_timeout_multiplier_if_authorized"],
                      "launcher_timeout_seconds": budget["launcher_timeout_seconds_if_authorized"],
                      "provider_profile_retry_max": budget["monitor_profile_max_retries"],
                      "provider_connect_timeout_seconds": budget["monitor_request_connect_timeout_seconds"],
                      "provider_read_timeout_seconds": budget["monitor_request_read_timeout_seconds"],
                      "ceilings_not_expected_duration": True},
        "task_profile": profiles["task_profile"],
        "task_profile_sha256": profiles["task_profile_sha256"],
        "monitor_profile_name": profiles["profile_name"],
        "launch_profiles": launch,
        "common_environment": common,
        "runner_harness_sha256": HARNESS_SHA256,
        "analysis": {
            "reporting_order": ["within_task_and_repetition", "equal_weight_across_two_tasks"],
            "outcome_scales": ["native_weighted_completion_score", "valid_final_allow_and_native_all_pass",
                               "valid_final_allow_and_native_not_all_pass", "unfinished_budget_or_failure",
                               "task_and_supervisor_requests_attempts_tokens_cache_control_cost"],
            "contrasts": {"A": "((AP-RP)+(AB-RB))/2", "B": "((RB-RP)+(AB-AP))/2",
                          "interaction": "AB-AP-RB+RP", "shared_increment": "RP-C0",
                          "combined_increment": "AB-C0"},
            "compute_each_scale_separately": True,
            "no_arbitrary_weighted_winner_score": True,
            "native_pass_not_semantic_proof": True,
            "development_comparison_not_held_out_or_promotion": True,
            "audit_order": "public evidence and control basis before terminal evaluation",
            "adoption_chain": ["configured_available", "select_or_set", "block_in_later_ordinary_request",
                               "request_returned", "later_locatable_use"],
            "new_tool_call_alone_not_adoption": True,
            "scientific_semantic_classification_by_main_thread_only": True},
        "failure_policy": {"no_record_level_rerun": True, "no_score_based_early_stop": True,
                           "valid_false_alone_excludes": False,
                           "missing_allow_log_means_allow_false": False,
                           "binding_unknown_false_allow": "unknown",
                           "non_completed_infra_identity_or_isolation": "preserve_and_pause_no_skip",
                           "ordinary_low_score_non_adoption_invalid_tool_budget_or_test_failure": "retain_as_result"},
        "post_run_unknown": {"observed_model_identity": None, "tokens_cache": None,
                             "final_scored_workspace_sha256": None,
                             "evaluator_invocation": None, "native_result": None},
        "pre_request_gate_spec": "START_GATE.md", "terminal_binding_spec": "TERMINAL_BINDING.md",
        "result_index_spec": "EVENT_INDEX_SPEC.json", "historical_precheck_appendix": "PRECHECK_ERRATA.md",
    }
    write(output / "PREREGISTRATION.json", prereg)
    return {"slot_count": len(checklist), "prereg_sha256": sha(output / "PREREGISTRATION.json")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prep", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--implementation-commit", required=True)
    args = parser.parse_args()
    print(json.dumps(freeze(args.prep, args.output, args.private,
                            args.implementation_commit), sort_keys=True))


if __name__ == "__main__":
    main()
