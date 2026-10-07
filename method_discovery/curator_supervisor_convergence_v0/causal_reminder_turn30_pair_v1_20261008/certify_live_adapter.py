"""Zero-model, task-image certification; never runs an Agent or evaluator."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from . import container_launcher as launcher
from . import pair_harness as frozen
from .continuation_adapter import canonical_sha, digest
from .live_runner import DEFAULT_AUTHORIZATION, adapter_source_sha256, validate_offline


FROZEN_FILES = (
    "FROZEN_REMINDER.txt", "CONTROL_REQUEST.json", "TREATMENT_REQUEST.json",
    "FROZEN_PROTOCOL.json", "EXECUTION_PLAN.json", "OUTCOME_SCHEMA.json",
    "INVALIDATION_POLICY.json",
)


def git_show_bytes(revision: str, path: Path) -> bytes:
    return subprocess.check_output(["git", "show", f"{revision}:{path.relative_to(frozen.REPO).as_posix()}"],
                                   cwd=frozen.REPO)


def certify() -> dict:
    frozen.checkpoint_binding()
    offline = validate_offline()
    if DEFAULT_AUTHORIZATION.exists():
        raise RuntimeError("Unexpected live authorization file")
    frozen_hashes = {}
    for name in FROZEN_FILES:
        path = frozen.HERE / name
        raw = path.read_bytes()
        if raw != git_show_bytes("e784da69bb604a130c8d02a85a35d47c9a0de362", path):
            raise RuntimeError(f"Frozen causal artifact changed: {name}")
        frozen_hashes[name] = digest(raw)
    tree = subprocess.check_output(["git", "rev-parse", "HEAD:GenericAgent-main"],
                                   cwd=frozen.REPO, text=True).strip()
    original_tree = subprocess.check_output(["git", "rev-parse",
        "e784da69bb604a130c8d02a85a35d47c9a0de362:GenericAgent-main"],
        cwd=frozen.REPO, text=True).strip()
    if tree != original_tree:
        raise RuntimeError("Production source tree changed")
    if subprocess.check_output(["git", "diff", "--name-only", "--", "GenericAgent-main"],
                               cwd=frozen.REPO, text=True).strip():
        raise RuntimeError("Production tracked working tree changed")
    state, control, treatment, _ = frozen.build_pair_requests()
    image_reports = {}
    with tempfile.TemporaryDirectory(prefix="causal_live_cert_") as temporary:
        temp = Path(temporary)
        for arm, expected in (("control", control), ("treatment", treatment)):
            stage = temp / arm / "stage"
            launcher.prepare_arm_stage(arm, stage, state, control, treatment)
            source_workspace = Path(frozen._read_json(frozen.HERE / "CLONE_MANIFEST.json")
                ["arms"][arm]["workspace_path"])
            workspace = temp / arm / "workspace"
            shutil.copytree(source_workspace, workspace)
            source = temp / arm / "production_source"
            shutil.copytree(launcher.FROZEN_BUNDLE / "source", source,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "temp"))
            command = launcher.zero_model_container_command(workspace, stage, source)
            completed = subprocess.run(command, capture_output=True, text=True,
                                       timeout=180, check=False)
            if completed.returncode:
                raise RuntimeError(f"{arm} task-image zero-model bootstrap failed: {completed.stderr[-1000:]}")
            lines = [line for line in completed.stdout.splitlines() if line.startswith("{")]
            report = json.loads(lines[-1])
            if (report["request_sha256"] != canonical_sha(expected)
                    or report["network_send_count"] != 0
                    or report["task_agent_loop_run_count"] != 0
                    or report["checkpoint_identity"]["compression_counter"] != 30
                    or report["compression_counter_after_build"] != 31):
                raise RuntimeError(f"{arm} live-time pre-send dry-run identity mismatch")
            image_reports[arm] = report
    template = {"execution_authorized": False,
                "checkpoint_authority_commit": frozen.AUTHORITY_COMMIT,
                "frozen_protocol_sha256": frozen_hashes["FROZEN_PROTOCOL.json"],
                "execution_plan_sha256": frozen_hashes["EXECUTION_PLAN.json"],
                "control_request_canonical_sha256": canonical_sha(control),
                "treatment_request_canonical_sha256": canonical_sha(treatment),
                "live_adapter_source_sha256": adapter_source_sha256(),
                "approved_order": ["control", "treatment"]}
    (frozen.HERE / "AUTHORIZATION_TEMPLATE.json").write_bytes(
        (json.dumps(template, indent=2) + "\n").encode("utf-8"))
    result = {
        "status": "CAUSAL_PAIR_LIVE_ADAPTER_READY_NOT_AUTHORIZED",
        "authority_causal_protocol_commit": "e784da69bb604a130c8d02a85a35d47c9a0de362",
        "checkpoint_authority_commit": frozen.AUTHORITY_COMMIT,
        "frozen_artifact_sha256": frozen_hashes,
        "production_tree_sha": tree,
        "deployed_task_source_snapshot_sha256": launcher.FROZEN_SOURCE_SNAPSHOT,
        "live_adapter_source_sha256": adapter_source_sha256(),
        "gateway_config_sha256": launcher.FROZEN_GATEWAY_CONFIG_SHA,
        "task_image": launcher.TASK_IMAGE,
        "control_pre_send_sha256": image_reports["control"]["request_sha256"],
        "treatment_pre_send_sha256": image_reports["treatment"]["request_sha256"],
        "per_arm_zero_model_task_image_reports": image_reports,
        "separate_task_processes": True,
        "shared_writable_workspace": False,
        "task_code_root": "/app", "task_network_mode": "none",
        "bootstrap_calls_per_arm": 1, "subsequent_calls": "production NativeToolClient.chat pass-through",
        "production_loop": "agent_loop.agent_runner_loop",
        "turn_offset": 30, "max_additional_turns": 270,
        "evaluator_barrier": "both legal continuations terminate before either evaluator invocation",
        "authorization_file_absent": True,
        "actual_provider_api_calls": 0, "actual_task_agent_calls": 0,
        "actual_supervisor_calls": 0, "actual_native_evaluator_calls": 0,
        "production_changes": 0,
        "offline_base_gate": offline["status"],
    }
    (frozen.HERE / "LIVE_ADAPTER_CERTIFICATION.json").write_bytes(
        (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return result


if __name__ == "__main__":
    print(json.dumps(certify(), ensure_ascii=False))
