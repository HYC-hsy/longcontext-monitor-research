"""Fail-closed future execution entry for the frozen causal pair.

There is deliberately no authorization file or bound provider/evaluator adapter
in this zero-model commit. --validate is offline; --live cannot send by default.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable, Optional

from .execution_control import ArmResult, PairController
from .pair_harness import (AUTHORITY_COMMIT, EXPECTED, HERE, REQUEST_FIELDS,
                           _read_json, build_pair_requests, checkpoint_binding,
                           frozen_reminder, sha, sha_bytes)
from method_discovery.curator_supervisor_convergence_v0.causal_reminder_turn30_20261007 import (
    materialize as checkpoint_materialize,
)
from method_discovery.curator_supervisor_convergence_v0.causal_reminder_turn30_20261007.git_state import (
    certify_git_state,
)


DEFAULT_AUTHORIZATION = HERE / "AUTHORIZATION.json"  # deliberately absent
TASK_SOURCE = Path(r"E:\LongContext\long_context_bench\.cache\m12_roadmap_tasks\fyn-2.2.0-roadmap")


def validate_offline() -> dict:
    binding = checkpoint_binding()
    _, control, treatment, diff = build_pair_requests()
    artifacts = {
        "CONTROL_REQUEST.json": control,
        "TREATMENT_REQUEST.json": treatment,
        "CONTROL_VS_TREATMENT_DIFF.json": diff,
    }
    for name, expected in artifacts.items():
        if _read_json(HERE / name) != expected:
            raise RuntimeError(f"Frozen causal artifact differs: {name}")
    protocol = _read_json(HERE / "FROZEN_PROTOCOL.json")
    plan = _read_json(HERE / "EXECUTION_PLAN.json")
    clones = _read_json(HERE / "CLONE_MANIFEST.json")
    if (protocol["reminder_exact_text"] != frozen_reminder()
            or protocol["reminder_injected_utf8_sha256"] != sha_bytes(frozen_reminder().encode("utf-8"))
            or plan["arm_order"] != ["control", "treatment"]
            or plan["max_additional_task_turns_per_arm"] != 270
            or plan["history_compression_call_count_at_checkpoint"] != 30
            or binding["runtime_history_compression_counter"]["call_count_after_turn30_before_turn31"] != 30
            or plan["total_task_turn_ceiling"] != 300
            or plan["max_agent_seconds"] != 10000
            or plan["isolation"] != "no-network-unix-inference-v1"
            or plan["model"] != "claude-opus-4-8"
            or any(value is not True for value in plan["mechanisms_disabled"].values())
            or sha_bytes((TASK_SOURCE / "tests/test.sh").read_bytes()) != plan["future_native_evaluator_sha256"]
            or sha_bytes((TASK_SOURCE / "task.toml").read_bytes()) != plan["future_native_task_toml_sha256"]
            or plan["live_execution_authorized"]
            or plan["native_evaluator_enabled_now"]
            or not clones["initial_runtime_states_identical"]
            or not clones["workspaces_independent"]):
        raise RuntimeError("Frozen causal protocol/plan/clone metadata differs")
    for arm in ("control", "treatment"):
        info = clones["arms"][arm]
        workspace = Path(info["workspace_path"])
        runtime_file = Path(info["runtime_state_path"])
        tree, files = checkpoint_materialize.source_tree(workspace, exclude_git=True)
        git_state = certify_git_state(workspace)
        if (tree != EXPECTED["workspace_tree_sha256"] or len(files) != 2472
                or git_state["turn30_head"] != EXPECTED["historical_git_head"]
                or git_state["turn30_index_tree"] != binding["git_index_tree"]
                or sha_bytes(runtime_file.read_bytes()) != info["runtime_state_file_sha256"]
                or _read_json(runtime_file)["backend_history_sha256"] !=
                EXPECTED["runtime_backend_history_sha256"]
                or _read_json(runtime_file)["history_compression_call_count"] != 30
                or info["history_compression_call_count"] != 30):
            raise RuntimeError(f"{arm} clone identity differs")
    if clones["arms"]["control"]["workspace_path"] == clones["arms"]["treatment"]["workspace_path"]:
        raise RuntimeError("Arms share workspace")
    if control["model"] != "claude-opus-4-8" or treatment["model"] != control["model"]:
        raise RuntimeError("Task model mismatch")
    return {"status": "CAUSAL_PAIR_ZERO_MODEL_READY",
            "checkpoint_authority_commit": AUTHORITY_COMMIT,
            "control_request_sha256": sha(control), "treatment_request_sha256": sha(treatment),
            "request_fields": list(REQUEST_FIELDS), "ignored_fields": [],
            "arm_order": ["control", "treatment"],
            "remaining_task_turns_per_arm": 270,
            "provider_send_count": 0, "task_agent_accepted_response_count": 0,
            "supervisor_reviewer_pma_model_calls": 0, "native_evaluator_execution_count": 0}


def require_live_authorization(path: Path = DEFAULT_AUTHORIZATION) -> dict:
    if not path.is_file():
        raise RuntimeError("Live causal pair is not authorized; no provider send permitted")
    auth = _read_json(path)
    required = {
        "execution_authorized": True,
        "checkpoint_authority_commit": AUTHORITY_COMMIT,
        "frozen_protocol_sha256": sha_bytes((HERE / "FROZEN_PROTOCOL.json").read_bytes()),
        "execution_plan_sha256": sha_bytes((HERE / "EXECUTION_PLAN.json").read_bytes()),
        "control_request_canonical_sha256": sha(_read_json(HERE / "CONTROL_REQUEST.json")),
        "treatment_request_canonical_sha256": sha(_read_json(HERE / "TREATMENT_REQUEST.json")),
        "approved_order": ["control", "treatment"],
    }
    if auth != required:
        raise RuntimeError("Live causal authorization fields/identities mismatch")
    return auth


def run_authorized_pair(*, authorization: Path,
                        execute_arm: Optional[Callable[[str], ArmResult]] = None,
                        evaluate_workspace: Optional[Callable[[str], object]] = None) -> dict:
    # Authorization, full zero-model identity, and both adapters are required
    # before the first possible external action. No adapter ships by default.
    require_live_authorization(authorization)
    validate_offline()
    if execute_arm is None or evaluate_workspace is None:
        raise RuntimeError("No audited live continuation/evaluator adapters bound; no send permitted")
    return PairController().run(execute_arm, evaluate_workspace)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--authorization", type=Path, default=DEFAULT_AUTHORIZATION)
    args = parser.parse_args()
    if args.validate == args.live:
        parser.error("choose exactly one of --validate or --live")
    if args.validate:
        print(json.dumps(validate_offline(), ensure_ascii=False))
    else:
        # CLI does not bind an execution adapter in this zero-model freeze.
        print(json.dumps(run_authorized_pair(authorization=args.authorization), ensure_ascii=False))


if __name__ == "__main__":
    main()
