"""Fail-closed, research-only launcher around the existing M12 runner.

The command is deliberately unusable with the frozen prereg's
execution_authorized=false.  A future main-thread authorization must provide
an independent exact-hash authorization and runner manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from method_discovery.uc_r5_execution_bridge import (
    FROZEN_CANDIDATE, FROZEN_PREREG_SHA256, file_sha, save_json,
)


HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PREREG = HERE / "runs" / "uc_r5_comparison_v1_20261003" / "PREREGISTRATION.json"
CHECKLIST = HERE / "runs" / "uc_r5_comparison_v1_20261003" / "SLOT_EXECUTION_CHECKLIST.json"
ADDENDUM = HERE / "runs" / "uc_r5_comparison_v1_20261003" / "EXECUTION_ADDENDUM.json"


def bridge_source_hash() -> str:
    """Hash source content canonically across Windows Git LF/CRLF checkout modes."""
    paths = [HERE / name for name in (
        "uc_r5_bridge_gateway.py", "uc_r5_execution_bridge.py",
        "uc_r5_execution_entry.py", "uc_r5_bridge_harbor_cli.py",
    )]
    digest = hashlib.sha256()
    for path in paths:
        relative = path.relative_to(HERE).as_posix().encode()
        content = path.read_bytes().replace(b"\r\n", b"\n")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def require_frozen_source_and_harbor() -> dict:
    diff = subprocess.run(
        ["git", "diff", "--quiet", FROZEN_CANDIDATE, "--",
         "GenericAgent-main", "long_context_bench"],
        cwd=REPO, capture_output=True, text=True)
    if diff.returncode:
        raise RuntimeError("Frozen candidate/runner source has changed")
    harbor = Path(r"E:\LongContext\bench_runtime\m4\harbor-src")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=harbor,
                          capture_output=True, text=True, check=True).stdout.strip()
    if head != "459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc":
        raise RuntimeError("Installed Harbor base mismatch")
    changed = subprocess.run(["git", "diff", "--name-only"], cwd=harbor,
                             capture_output=True, text=True, check=True).stdout.splitlines()
    expected = {
        "src/harbor/environments/docker/harbor-docker-egress-control-sidecar/Dockerfile",
        "src/harbor/models/task/config.py",
        "src/harbor/trial/single_step.py",
    }
    if set(changed) != expected:
        raise RuntimeError("Installed Harbor patch set mismatch")
    return {"harbor_base": head, "harbor_patch_files": sorted(changed),
            "candidate_and_runner_diff_empty": True}


def load_authorized_slot(run_id: str, authorization_path: Path) -> tuple[dict, dict]:
    if file_sha(PREREG) != FROZEN_PREREG_SHA256:
        raise RuntimeError("Frozen preregistration changed")
    checklist = json.loads(CHECKLIST.read_text(encoding="utf-8"))
    slots = [row for row in checklist["proposed_slots"] if row["run_id"] == run_id]
    if len(slots) != 1 or slots[0]["status"] != "not_started":
        raise RuntimeError("Unknown or already-started slot")
    slot = slots[0]
    if slot["candidate_commit"] != FROZEN_CANDIDATE:
        raise RuntimeError("Candidate mismatch")
    authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
    if not ADDENDUM.exists():
        raise RuntimeError("Bridge implementation has no frozen addendum")
    addendum = json.loads(ADDENDUM.read_text(encoding="utf-8"))
    if addendum.get("execution_authorized") is not False:
        raise RuntimeError("Frozen addendum must not itself authorize execution")
    if addendum.get("bridge_source_sha256") != bridge_source_hash():
        raise RuntimeError("Bridge source differs from frozen addendum")
    required = {
        "execution_authorized": True,
        "preregistration_sha256": FROZEN_PREREG_SHA256,
        "slot_checklist_sha256": file_sha(CHECKLIST),
        "run_id": run_id,
        "candidate_commit": FROZEN_CANDIDATE,
        "bridge_implementation_commit": addendum["bridge_implementation_commit"],
        "bridge_source_sha256": addendum["bridge_source_sha256"],
    }
    if any(authorization.get(key) != value for key, value in required.items()):
        raise RuntimeError("Missing or mismatched independent authorization")
    if authorization.get("task_model") != "claude-opus-4-8":
        raise RuntimeError("Task model differs from frozen profile")
    manifest = Path(authorization["runner_manifest"])
    if not manifest.is_absolute():
        raise RuntimeError("Authorized runner manifest must use an absolute path")
    if file_sha(manifest) != authorization.get("runner_manifest_sha256"):
        raise RuntimeError("Authorized runner manifest hash mismatch")
    return slot, authorization


def overlay_bundle(original_build, bridge_script: Path, control_dir: Path,
                   slot: dict, bridge_spec_path: Path):
    def build(*args, **kwargs):
        source, compose_path = original_build(*args, **kwargs)
        bundle_identity = json.loads((compose_path.parent / "isolation_identity.json").read_text(encoding="utf-8"))
        if bundle_identity.get("snapshot_sha256") != slot["deployment"]["bundle_snapshot_sha256"]:
            raise RuntimeError("Actual generated source bundle differs from preregistration")
        deployed_profile = source / "monitor_agent_core" / "models.local.json"
        if file_sha(deployed_profile) != slot["deployment"]["bundle_deployed_profile_sha256"]:
            raise RuntimeError("Actual deployed Monitor profile differs from preregistration")
        spec = json.loads(bridge_spec_path.read_text(encoding="utf-8"))
        spec["generated_bundle_source"] = str(source)
        spec["generated_bundle_source_sha256"] = bundle_identity["snapshot_sha256"]
        spec["generated_monitor_profile_sha256"] = file_sha(deployed_profile)
        save_json(bridge_spec_path, spec)
        compose = json.loads(compose_path.read_text(encoding="utf-8"))
        gateway = compose["services"]["model-gateway"]
        python_bin = gateway["entrypoint"][0]
        gateway["volumes"].extend([
            f"{bridge_script.resolve().as_posix()}:/bridge/bridge.py:ro",
            f"{control_dir.resolve().as_posix()}:/bridge/control",
        ])
        gateway["entrypoint"] = [
            python_bin, "/bridge/bridge.py", "--transport", "/gateway/transport.py",
            "--config", "/gateway/config.json", "--control-dir", "/bridge/control",
            "--slot-id", slot["run_id"], "--timeout-sec", "120",
        ]
        compose_path.write_text(json.dumps(compose, indent=2), encoding="utf-8")
        save_json(compose_path.parent / "uc_r5_bridge_overlay_identity.json", {
            "slot_id": slot["run_id"],
            "frozen_transport_sha256": file_sha(compose_path.parent / "gateway" / "transport.py"),
            "bridge_gateway_sha256": file_sha(bridge_script),
            "overlaid_compose_sha256": file_sha(compose_path),
            "allowed_change": "gateway-only research first-send wrapper and IPC mount",
        })
        return source, compose_path
    return build


def launch(run_id: str, authorization_path: Path) -> dict:
    slot, authorization = load_authorized_slot(run_id, authorization_path)
    frozen_identity = require_frozen_source_and_harbor()
    if Path(slot["live_root"]).exists():
        raise RuntimeError("Slot live root already used")
    campaign = Path(slot["output"]["campaign_root"])
    if (campaign / "jobs" / run_id).exists() or (campaign / "runs" / run_id).exists():
        raise RuntimeError("Slot output already used")
    control_dir = campaign / "bridge" / run_id / "control"
    archive_dir = campaign / "bridge" / run_id / "evidence"
    control_dir.mkdir(parents=True, exist_ok=False)
    archive_dir.mkdir(parents=True, exist_ok=False)
    bridge_spec_path = campaign / "bridge" / run_id / "bridge_spec.private.json"
    save_json(bridge_spec_path, {
        "execution_authorized": True, "slot": slot,
        "task_model": authorization["task_model"],
        "control_dir": str(control_dir), "archive_dir": str(archive_dir),
        "authorization_path": str(authorization_path.resolve()),
        "authorization_sha256": file_sha(authorization_path),
        "preregistration_sha256": FROZEN_PREREG_SHA256,
        "frozen_source_and_harbor": frozen_identity,
    })

    # Import and delegate to the unchanged runner. Its build_bundle call is
    # wrapped only to attach the research gateway sidecar overlay.
    bench = REPO / "long_context_bench"
    sys.path.insert(0, str(bench))
    from scripts import run_ultralong_m12_proofs as runner
    from scripts import run_harbor_tb2_m4 as m4

    runner.apply_experiment_manifest(authorization["runner_manifest"], run_id)
    expected_environment = json.loads((HERE / "runs" / "uc_r5_cmp_readiness_20261003"
                                       / "ENVIRONMENT_DRAFT.json").read_text(encoding="utf-8"))["common"]
    for name, value in expected_environment.items():
        if os.environ.get(name) != value:
            raise RuntimeError(f"Effective frozen runtime configuration mismatch: {name}")
    if Path(os.environ.get("BENCHMARK_CAMPAIGN_ROOT", "")).resolve() != campaign.resolve():
        raise RuntimeError("Effective campaign output root mismatch")
    if Path(os.environ["GA_HOST_ROOT"]).resolve() != Path(slot["deployment"]["ga_host_root"]).resolve():
        raise RuntimeError("Authorized source root mismatch")
    if file_sha(Path(slot["deployment"]["monitor_profile_path"])) != slot["deployment"]["monitor_profile_sha256"]:
        raise RuntimeError("Private Monitor profile mismatch")
    if os.environ.get("GA_RUN_ISOLATION") != "no-network-unix-inference-v1":
        raise RuntimeError("Isolation profile mismatch")
    m4.GA_ROOT = Path(os.environ["GA_HOST_ROOT"])
    control_dir.mkdir(parents=True, exist_ok=True)
    runner.build_bundle = overlay_bundle(
        runner.build_bundle, HERE / "uc_r5_bridge_gateway.py", control_dir,
        slot, bridge_spec_path)
    os.environ["UC_R5_BRIDGE_SPEC"] = str(bridge_spec_path)
    os.environ["PYTHONPATH"] = os.pathsep.join([str(REPO), os.environ.get("PYTHONPATH", "")])
    original_run = m4.run
    harbor_exe = str(m4.HARBOR_EXE)

    def run_with_hooks(command, *args, **kwargs):
        if (len(command) < 3 or command[0] != harbor_exe
                or command[1:3] != ["jobs", "start"]):
            return original_run(command, *args, **kwargs)
        harbor_python = str(Path(harbor_exe).with_name("python.exe"))
        guarded = [harbor_python, str(HERE / "uc_r5_bridge_harbor_cli.py"), *command[1:]]
        return original_run(guarded, *args, **kwargs)

    m4.run = run_with_hooks
    try:
        return runner.run_proof(
            source=slot["runner"]["source"], run_id=run_id,
            llm_no=slot["runner"]["llm_no"],
            max_agent_seconds=slot["runner"]["max_agent_seconds"],
            task_id=slot["runner"]["task_id"],
        )
    finally:
        m4.run = original_run
        os.environ.pop("UC_R5_BRIDGE_SPEC", None)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    args = parser.parse_args()
    result = launch(args.run_id, args.authorization)
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
