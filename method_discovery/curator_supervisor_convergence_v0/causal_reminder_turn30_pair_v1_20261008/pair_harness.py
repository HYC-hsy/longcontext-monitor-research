"""Frozen zero-model C/T construction at the certified Task turn-30 boundary.

This module does not run an Agent, provider, or evaluator. In particular, its
production request dry-runs stop at the deployed pre-network transport hook.
"""

from __future__ import annotations

import copy
from contextlib import contextmanager
from datetime import datetime
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from method_discovery.curator_supervisor_convergence_v0.causal_reminder_turn30_20261007 import (
    materialize as checkpoint_materialize,
)
from method_discovery.curator_supervisor_convergence_v0.causal_reminder_turn30_20261007 import (
    freeze as checkpoint_freeze,
)
from method_discovery.curator_supervisor_convergence_v0.causal_reminder_turn30_20261007.git_state import (
    certify_git_state,
)
from method_discovery.curator_supervisor_convergence_v0.causal_reminder_turn30_20261007.runtime_checkpoint import (
    certify as certify_runtime,
    dry_run_before_network,
    DEPLOYED_SOURCE,
)
from method_discovery.curator_supervisor_convergence_v0.causal_reminder_turn30_20261007.reconstruct_next_request import (
    NEXT_SHA256, canonical, raw_request, sha,
)


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CHECKPOINT = checkpoint_freeze.HERE
AUTHORITY_COMMIT = "b818b8f0d3b57eff0977e93e33af8594c8b04d17"
SOURCE_ARCHIVE_COMMIT = "ca3648a925eb709deb09603e36e0f4981a03743a"
LOCAL_PAIR_ROOT = Path(r"E:\fyne_turn30_causal_pair_v1_20261008_counter_certified")
REMINDER = (
    "Reminder from the original task: Target 4's Refresh requirement is behavioral, "
    "not merely structural. Menu.Refresh() must make all windows currently displaying "
    "that Menu re-render updated menu state and refresh the system tray menu when "
    "applicable; MainMenu.Refresh() must likewise re-render all windows using that "
    "MainMenu."
)
EXPECTED = {
    "workspace_file_count": 2472,
    "workspace_tree_sha256": "994ed5f372f0ee6fecda6a600dc970ce4c5fbbb1a8c09acfa9ab3748ce323c60",
    "historical_git_head": "7229e889d49c81a83b0b7e09400837f67f6ddad5",
    "provider_history_sha256": "95737650e2f053901b01db20f9db9729e911cba395895d94713926cf2353556b",
    "working_state_sha256": "bb0590c60c8033c9ba1e11e701cceae0e4429adcccd73d5ee7bbe912fd6c7d64",
    "runtime_backend_history_sha256": "17ec23f7b7c78eb8274afd9e874d25a857983d62ac4f78db14a7ebff3c90d5e4",
    "runtime_history_info_sha256": "b22518a3c66b6985bd9718d0bf11efbf9933997eade9b49cf822d2648d435cf9",
    "historical_raw_request_sha256": NEXT_SHA256,
    "control_model_visible_sha256": "c00732acd4553c7aaf2b38078e4d4c4271ad9071b0389320a65cc19d895598f1",
}
REQUEST_FIELDS = ("context_management", "max_tokens", "messages", "metadata",
                  "model", "stream", "system", "thinking", "tools")
BOUND_ARTIFACTS = (
    "CHECKPOINT_IDENTITY.json", "CHECKPOINT_WORKSPACE_MANIFEST.json",
    "GIT_STATE_CERTIFICATION.json", "RUNTIME_CHECKPOINT_STATE.json",
    "RUNTIME_NEXT_REQUEST_COMPARISON.json", "ORIGINAL_NEXT_REQUEST.json",
    "LEAKAGE_AUDIT.json", "WORKING_CHECKPOINT.json",
)


def sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: object) -> None:
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def frozen_reminder() -> str:
    raw = (HERE / "FROZEN_REMINDER.txt").read_bytes()
    if raw != (REMINDER + "\n").encode("ascii"):
        raise RuntimeError("Frozen reminder file differs from exact ASCII text + one LF")
    return REMINDER


def history_compression_counter_certificate() -> dict:
    """Recover deployed llmcore's process-local counter from bound public telemetry."""
    events = checkpoint_materialize.jsonl(checkpoint_materialize.RESEARCH_EVENTS)
    public = checkpoint_materialize.jsonl(checkpoint_materialize.PUBLIC_EVENTS)
    boundary = next(row for row in public if row["archive_sequence"] == 58)
    boundary_time = boundary["archived_at"]
    transforms = [row for row in events if row.get("event_type") == "history_transform_started"]
    before = [row for row in transforms
              if datetime.fromisoformat(row["timestamp"]).timestamp() <= boundary_time]
    if (len(before) != 30 or len(transforms) < 31 or before[-1] != transforms[29]
            or datetime.fromisoformat(transforms[30]["timestamp"]).timestamp() <= boundary_time):
        raise RuntimeError("Task history-compression call counter is not recoverable")
    return {"deployed_function": "llmcore.compress_history_tags",
            "call_count_after_turn30_before_turn31": 30,
            "source_research_events_sha256": checkpoint_materialize.sha_file(
                checkpoint_materialize.RESEARCH_EVENTS),
            "turn30_transform_event_id": transforms[29]["event_id"],
            "turn31_transform_event_id": transforms[30]["event_id"],
            "request_local_not_model_visible": True}


@contextmanager
def restored_compression_counter(value: int):
    if str(DEPLOYED_SOURCE) not in sys.path:
        sys.path.insert(0, str(DEPLOYED_SOURCE))
    llmcore = importlib.import_module("llmcore")
    function = llmcore.compress_history_tags
    previous = getattr(function, "_cd", None)
    function._cd = value
    try:
        yield
    finally:
        if previous is None:
            del function._cd
        else:
            function._cd = previous


def checkpoint_binding() -> dict:
    if subprocess.check_output(["git", "cat-file", "-t", AUTHORITY_COMMIT], cwd=REPO,
                               text=True).strip() != "commit":
        raise RuntimeError("Checkpoint authority commit unavailable")
    bound_hashes = {}
    for name in BOUND_ARTIFACTS:
        path = CHECKPOINT / name
        relative = path.relative_to(REPO).as_posix()
        committed = subprocess.check_output(["git", "show", f"{AUTHORITY_COMMIT}:{relative}"], cwd=REPO)
        local = path.read_bytes()
        if local != committed:
            raise RuntimeError(f"Certified checkpoint artifact changed: {name}")
        bound_hashes[name] = sha_bytes(local)
    identity = _read_json(CHECKPOINT / "CHECKPOINT_IDENTITY.json")
    workspace = _read_json(CHECKPOINT / "CHECKPOINT_WORKSPACE_MANIFEST.json")
    runtime = _read_json(CHECKPOINT / "RUNTIME_CHECKPOINT_STATE.json")
    working = _read_json(CHECKPOINT / "WORKING_CHECKPOINT.json")
    leakage = _read_json(CHECKPOINT / "LEAKAGE_AUDIT.json")
    git_saved = _read_json(CHECKPOINT / "GIT_STATE_CERTIFICATION.json")
    checks = {
        "workspace_file_count": workspace["file_count"],
        "workspace_tree_sha256": workspace["workspace_tree_sha256"],
        "historical_git_head": git_saved["turn30_head"],
        "provider_history_sha256": identity["task_agent_provider_history_sha256"],
        "working_state_sha256": working["checkpoint_relevant_state_sha256"],
        "runtime_backend_history_sha256": runtime["backend_history_sha256"],
        "runtime_history_info_sha256": runtime["history_info_sha256"],
        "historical_raw_request_sha256": sha_bytes((CHECKPOINT / "ORIGINAL_NEXT_REQUEST.json").read_bytes()),
        "control_model_visible_sha256": identity["original_next_request_model_visible_sha256"],
    }
    if (checks != EXPECTED or identity["validity"] != "eligible_exact"
            or identity["source_commit"] != SOURCE_ARCHIVE_COMMIT
            or not identity["model_visible_equal"]
            or not identity["git_state_certified"]
            or not identity["runtime_state_certified"]
            or not leakage["future_information_excluded"]
            or identity["boundary_intervention"]):
        raise RuntimeError("Exact checkpoint binding failed")
    local_tree, local_files = checkpoint_materialize.source_tree(
        checkpoint_freeze.MATERIALIZED, exclude_git=True)
    if local_tree != EXPECTED["workspace_tree_sha256"] or len(local_files) != 2472:
        raise RuntimeError("Local materialized workspace differs")
    if certify_git_state(checkpoint_freeze.MATERIALIZED) != git_saved:
        raise RuntimeError("Local materialized Git state differs")
    counter = history_compression_counter_certificate()
    with restored_compression_counter(counter["call_count_after_turn30_before_turn31"]):
        state, generated, report = certify_runtime()
    if (state != runtime or not report["model_visible_equal"]
            or report["ignored_transport_fields"]
            or sha(generated) != EXPECTED["control_model_visible_sha256"]):
        raise RuntimeError("Recovered runtime differs from checkpoint certification")
    return {"authority_commit": AUTHORITY_COMMIT,
            "historical_source_archive_commit": SOURCE_ARCHIVE_COMMIT,
            "task_id": "fyn-2.2.0-roadmap",
            "boundary": identity["boundary"],
            "identities": checks,
            "bound_artifact_sha256": bound_hashes,
            "git_index_tree": git_saved["turn30_index_tree"],
            "git_status": git_saved["turn30_status_porcelain_v1_untracked_all"],
            "runtime_history_compression_counter": counter,
            "model_visible_equal": True,
            "future_information_excluded": True}


def _differences(left: object, right: object, path: tuple = ()) -> list[dict]:
    if type(left) is not type(right):
        return [{"path": list(path), "kind": "type_or_value"}]
    if isinstance(left, dict):
        if set(left) != set(right):
            return [{"path": list(path), "kind": "keys"}]
        return [item for key in sorted(left) for item in _differences(left[key], right[key], path + (key,))]
    if isinstance(left, list):
        if len(left) != len(right):
            return [{"path": list(path), "kind": "length"}]
        return [item for index in range(len(left))
                for item in _differences(left[index], right[index], path + (index,))]
    return [] if left == right else [{"path": list(path), "kind": "value"}]


def build_pair_requests() -> tuple[dict, dict, dict, dict]:
    frozen_reminder()
    counter = history_compression_counter_certificate()["call_count_after_turn30_before_turn31"]
    with restored_compression_counter(counter):
        state, control, control_report = certify_runtime()
    state = copy.deepcopy(state)
    state["history_compression_call_count"] = counter
    historical = raw_request(
        "f2bc63a1d6a842ffad4f831b1715690f", NEXT_SHA256)
    if (control != historical or tuple(sorted(control)) != tuple(sorted(REQUEST_FIELDS))
            or sha(control) != EXPECTED["control_model_visible_sha256"]
            or not control_report["model_visible_equal"]
            or control_report["ignored_transport_fields"]):
        raise RuntimeError("Control first request is not the historical turn-31 request")
    treated_state = copy.deepcopy(state)
    treated_state["turn30_next_prompt"] += "\n\n" + REMINDER
    with restored_compression_counter(counter):
        treatment, treatment_report = dry_run_before_network(treated_state)
    if treatment_report["network_send_attempted"]:
        raise RuntimeError("Treatment dry-run reached provider send")
    last = len(control["messages"]) - 1
    last_block = len(control["messages"][last]["content"]) - 1
    expected_path = ["messages", last, "content", last_block, "text"]
    expected_treatment = copy.deepcopy(control)
    expected_treatment["messages"][last]["content"][last_block]["text"] += "\n\n" + REMINDER
    differences = _differences(control, treatment)
    if treatment != expected_treatment or differences != [{"path": expected_path, "kind": "value"}]:
        raise RuntimeError("Treatment request has a model-visible difference beyond frozen suffix")
    if not (control["messages"][last]["content"][0] ==
            treatment["messages"][last]["content"][0]):
        raise RuntimeError("Turn-30 tool result changed")
    diff = {
        "control_canonical_sha256": sha(control),
        "treatment_canonical_sha256": sha(treatment),
        "reminder_injected_utf8_sha256": sha_bytes(REMINDER.encode("utf-8")),
        "control_equals_historical_nine_fields": True,
        "ignored_transport_fields": [],
        "non_message_top_level_fields_equal": [k for k in REQUEST_FIELDS if k != "messages"],
        "message_count_both": len(control["messages"]),
        "role_sequence_equal": True,
        "content_block_structure_equal": True,
        "turn30_tool_result_equal": True,
        "cache_control_positions_equal": True,
        "structural_differences": differences,
        "other_differences": 0,
        "treatment_last_text_equals_control_plus_two_lf_plus_frozen_reminder": True,
        "provider_send_count": 0,
    }
    return state, control, treatment, diff


def prepare_independent_clones(root: Path, state: dict) -> dict:
    if root.exists():
        raise RuntimeError("Pair clone root already exists; refusing reuse/overwrite")
    root.mkdir(parents=True, exist_ok=False)
    arms = {}
    for arm in ("control", "treatment"):
        arm_root = root / arm
        arm_root.mkdir()
        workspace = arm_root / "workspace"
        shutil.copytree(checkpoint_freeze.MATERIALIZED, workspace)
        tree, files = checkpoint_materialize.source_tree(workspace, exclude_git=True)
        if tree != EXPECTED["workspace_tree_sha256"] or len(files) != 2472:
            raise RuntimeError(f"{arm} workspace clone identity mismatch")
        git_identity = certify_git_state(workspace)
        state_path = arm_root / "runtime_checkpoint.json"
        _write_json(state_path, copy.deepcopy(state))
        if _read_json(state_path) != state:
            raise RuntimeError(f"{arm} runtime clone mismatch")
        arms[arm] = {
            "workspace_path": str(workspace), "workspace_tree_sha256": tree,
            "workspace_file_count": len(files),
            "git_head": git_identity["turn30_head"],
            "git_index_tree": git_identity["turn30_index_tree"],
            "runtime_state_path": str(state_path),
            "runtime_state_file_sha256": sha_bytes(state_path.read_bytes()),
            "runtime_backend_history_sha256": state["backend_history_sha256"],
            "history_compression_call_count": state["history_compression_call_count"],
        }
    if arms["control"]["workspace_path"] == arms["treatment"]["workspace_path"]:
        raise RuntimeError("Arms share a workspace")
    if arms["control"]["runtime_state_path"] == arms["treatment"]["runtime_state_path"]:
        raise RuntimeError("Arms share a runtime-state file")
    if arms["control"]["runtime_state_file_sha256"] != arms["treatment"]["runtime_state_file_sha256"]:
        raise RuntimeError("Pre-injection runtime clones differ")
    return {"local_root": str(root), "arms": arms,
            "source_workspace": str(checkpoint_freeze.MATERIALIZED),
            "initial_runtime_states_identical": True,
            "workspaces_independent": True}


def validate_existing_clones(root: Path, state: dict) -> dict:
    manifest = _read_json(HERE / "CLONE_MANIFEST.json")
    if manifest["local_root"] != str(root) or not manifest["initial_runtime_states_identical"]:
        raise RuntimeError("Existing pair clone manifest differs")
    seen = set()
    for arm in ("control", "treatment"):
        info = manifest["arms"][arm]
        workspace = Path(info["workspace_path"])
        runtime_path = Path(info["runtime_state_path"])
        if (workspace.parent != root / arm or runtime_path.parent != root / arm
                or workspace in seen or runtime_path in seen):
            raise RuntimeError("Existing pair clones are not independent")
        seen.update((workspace, runtime_path))
        tree, files = checkpoint_materialize.source_tree(workspace, exclude_git=True)
        git_identity = certify_git_state(workspace)
        if (tree != EXPECTED["workspace_tree_sha256"] or len(files) != 2472
                or git_identity["turn30_head"] != EXPECTED["historical_git_head"]
                or git_identity["turn30_index_tree"] != manifest["arms"][arm]["git_index_tree"]
                or _read_json(runtime_path) != state
                or info["history_compression_call_count"] != state["history_compression_call_count"]
                or sha_bytes(runtime_path.read_bytes()) != info["runtime_state_file_sha256"]):
            raise RuntimeError(f"Existing {arm} clone differs")
    return manifest


def freeze() -> dict:
    binding = checkpoint_binding()
    state, control, treatment, diff = build_pair_requests()
    if EXPECTED["workspace_tree_sha256"][-1] != "0":
        raise RuntimeError("Pre-registered order nibble changed")
    clones = (validate_existing_clones(LOCAL_PAIR_ROOT, state) if LOCAL_PAIR_ROOT.exists()
              else prepare_independent_clones(LOCAL_PAIR_ROOT, state))
    protocol = {
        "schema": "turn30-minimal-reminder-causal-pair/1",
        "status": "zero_model_prepared_not_live_authorized",
        "scientific_question": "At the same long-horizon Task Agent checkpoint, does reactivating one original-task behavioral distinction cause the Task Agent to autonomously recover?",
        "candidate_failure_at_boundary": "Task Agent wrote Target 4 COMPLETE in its own working checkpoint while the public Refresh contract is behavioral.",
        "task_distinction": "Menu/MainMenu refresh must cause the specified current windows, and applicable tray menu, to re-render; API presence alone is not that behavior.",
        "checkpoint_authority_commit": AUTHORITY_COMMIT,
        "reminder_exact_text": REMINDER,
        "reminder_injected_utf8_bytes": len(REMINDER.encode("ascii")),
        "reminder_injected_utf8_sha256": diff["reminder_injected_utf8_sha256"],
        "reminder_file_sha256_including_final_lf": sha_bytes((HERE / "FROZEN_REMINDER.txt").read_bytes()),
        "reminder_file_final_lf_is_not_injected": True,
        "control_additional_text": None,
        "treatment_injection": "existing turn-30 next_prompt + two LF + exact reminder text",
        "no_second_reminder": True,
        "forbidden_treatment_additions": ["implementation verdict", "noop diagnosis",
            "measurement verdict", "file or API guidance", "native/hidden result",
            "implementation plan", "second reminder"],
        "no_supervisor_reviewer_pma_or_researcher_intervention": True,
        "no_native_feedback_during_continuations": True,
    }
    plan = {
        "schema": "turn30-causal-pair-execution-plan/1",
        "task": "fyn-2.2.0-roadmap", "model": "claude-opus-4-8",
        "checkpoint_task_turn": 30, "total_task_turn_ceiling": 300,
        "history_compression_call_count_at_checkpoint": state["history_compression_call_count"],
        "max_additional_task_turns_per_arm": 270,
        "max_agent_seconds": 10000,
        "isolation": "no-network-unix-inference-v1",
        "task_image": "sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1",
        "task_profile": "native_claude_cc_vibe_opus48",
        "task_profile_file_sha256": state["profile_file_sha256"],
        "mechanisms_disabled": {"supervisor": True, "reviewer": True, "pma": True,
                                "adaptive_monitor": True, "b_j_i": True,
                                "researcher_intervention": True},
        "order_rule": "last hex nibble of checkpoint workspace SHA: even Control first, odd Treatment first",
        "order_nibble": "0", "arm_order": ["control", "treatment"],
        "arms_share_workspace": False, "arms_share_provider_client_or_history": False,
        "passive_logging_only": True,
        "live_execution_authorized": False,
        "native_evaluator_enabled_now": False,
        "future_evaluator_order": "both continuations complete before either native evaluation",
        "future_evaluator_model_visibility": False,
        "future_native_evaluator_path": "/tests/test.sh",
        "future_native_evaluator_sha256": "77637bf7eb621697259e7fad7428ed4cc578b17aef171fc76f44cf5474b8bda2",
        "future_native_task_toml_sha256": "db81f4ee37e4f69e7ace0fa7b7cb6ab8b2cd3469463091b1bcf073da4237dd6d",
        "future_evaluator_input": "label-neutral isolated /app workspace only; no reminder/history/research mounts",
        "required_passive_raw_capture": ["provider_pre_send_requests", "provider_responses",
            "tool_calls_and_results", "task_trajectory", "usage_and_transport", "termination",
            "workspace_pre_post_manifest_and_diff"],
        "no_selective_rerun": True,
        "researcher_early_stop_for_semantic_behavior": False,
        "legal_natural_terminations": ["normal Task Agent completion", "original runner termination",
            "total Task turn 300", "recorded infrastructure/provider failure"],
    }
    invalidation = {
        "before_any_accepted_task_response_in_an_arm_infrastructure_failure": "pair invalid; preserve attempt; any authorized replacement restarts entire C→T pair",
        "after_accepted_response_semantic_failure": "outcome, not rerun criterion",
        "provider_transport_or_service_terminal_failure": "infrastructure_invalid; stop; research thread decides any replacement",
        "auto_retry_whole_pair": False, "selective_arm_rerun": False,
        "best_of_n": False,
    }
    outcomes = {
        "primary": ["native_phases_passed", "native_phases_total", "native_reward",
                    "whole_task_success", "termination_turn", "native_target4_phase_if_provided"],
        "secondary_public_trajectory_only": {
            "distinction_uptake": "Agent revisits Refresh as runtime window/tray behavior, reopens Target 4, or questions its COMPLETE state.",
            "measurement_selection": "Agent autonomously selects an investigation that could distinguish the behavioral contract; no researcher hint.",
            "measurement_completion": "Separate a planned check from a tool/test/probe that actually ran and returned.",
            "evidence_state_update": "After observation, Agent changes its Target-4 state, implementation hypothesis, or prior closure.",
            "autonomous_repair": "Without another reminder, Agent changes implementation, validates, and rejudges completion.",
            "first_target4_revisit_turn": "Task turn from 31 onward, or null.",
            "first_behavioral_measurement_turn": "Task turn from 31 onward, or null.",
            "first_target4_implementation_change_turn": "Task turn from 31 onward, or null.",
        },
        "interpretation_categories_frozen": {
            "strong_positive": "Control continues to miss the distinction while Treatment shows uptake, completed discriminating measurement, evidence-based state/implementation change, and better native Target-4 or whole-task outcome.",
            "mechanistic_positive_outcome_partial": "Treatment shows reminder→reactivation→autonomous repair but unrelated target failures prevent a whole-task score gain.",
            "null": "No meaningful behavior/outcome difference, or both arms naturally recover.",
            "detection_uptake_failure": "Treatment reminder does not alter later Task cognition or behavior.",
            "harm": "Treatment causes distraction/regression, lower native outcome, or breaks other behavior during Target-4 repair.",
        },
        "single_pair_not_statistical_significance": True,
        "no_extra_reviewer_model": True,
    }
    preflight = {
        "status": "CAUSAL_PAIR_ZERO_MODEL_READY",
        "checkpoint_binding_passed": True,
        "control_historical_equivalence_passed": True,
        "treatment_single_suffix_difference_passed": True,
        "clone_manifest": clones,
        "provider_send_count": 0,
        "accepted_task_response_count": 0,
        "supervisor_reviewer_pma_model_call_count": 0,
        "native_evaluator_execution_count": 0,
        "production_changes": 0,
    }
    values = {
        "FROZEN_PROTOCOL.json": protocol,
        "CHECKPOINT_BINDING.json": binding,
        "CONTROL_REQUEST.json": control,
        "TREATMENT_REQUEST.json": treatment,
        "CONTROL_VS_TREATMENT_DIFF.json": diff,
        "CLONE_MANIFEST.json": clones,
        "EXECUTION_PLAN.json": plan,
        "OUTCOME_SCHEMA.json": outcomes,
        "INVALIDATION_POLICY.json": invalidation,
        "ZERO_MODEL_PREFLIGHT.json": preflight,
    }
    for name, value in values.items():
        _write_json(HERE / name, value)
    return preflight
