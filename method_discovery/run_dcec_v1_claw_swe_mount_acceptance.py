"""Zero-model acceptance for the CLAW-SWE nested mount repair.

This starts the pinned task container through CLAW-SWE's production workspace
and the production DCEC isolation adapter, but deliberately does not start the
Task Agent, Supervisor, inference gateway, or verifier.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "long_context_bench"
GA_ROOT = ROOT / "GenericAgent-main"
RUNTIME_LINUX = ROOT / "bench_runtime" / "m2" / "linux"
OUTPUT = (
    ROOT / "method_discovery" / "runs"
    / "dcec_v1_claw_swe_mount_acceptance_20260921" / "acceptance.json"
)
RUN_ID = "dcec-v1-claw-swe-mount-acceptance-20260921"
INSTANCE_ID = "sphinx-doc__sphinx-8551"
EXPECTED_IMAGE_ID = "sha256:77f476927410992943a8d2744aea86b3e0c50d8773b61e56ebba9dd0fd4b9db1"


def _check(workspace, command: str) -> str:
    result = workspace.run_in_container(command, timeout=60)
    if result.exit_code:
        raise RuntimeError(
            f"container acceptance command failed ({result.exit_code}): "
            f"{command}: {(result.stderr or result.stdout).strip()}"
        )
    return result.stdout.strip()


def execute() -> dict:
    if OUTPUT.exists():
        raise RuntimeError(f"immutable acceptance output already exists: {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(BENCH))
    from scripts import run_claw_swe_m3 as m3
    from scripts.isolated_run_bundle import build_bundle
    from method_discovery import run_dcec_v1_claw_swe_generalization as launch

    for relative, expected in launch.MECHANISM_HASHES.items():
        if launch.sha256(GA_ROOT / relative) != expected:
            raise RuntimeError(f"frozen DCEC-v1 mechanism changed: {relative}")

    acceptance_root = BENCH / "output" / "dcec_v1_claw_swe_mount_acceptance_20260921"
    locks_path = acceptance_root / "locks.jsonl"
    m3.M3_ROOT = acceptance_root / "claw_swe"
    m3.LOCKS = locks_path
    m3.READINESS = m3.M3_ROOT / "readiness.jsonl"
    os.environ["GA_METHOD_EXPECTED_SOURCE_SHA256"] = launch.EXPECTED_GA_HASH
    readiness = m3.scan("all", False, False, [INSTANCE_ID])
    if len(readiness) != 1 or readiness[0]["status"] != "ready":
        raise RuntimeError(f"pinned task is not ready: {readiness}")
    lock = m3.load_locks()[INSTANCE_ID]
    if lock["image"]["image_id"] != EXPECTED_IMAGE_ID:
        raise RuntimeError("pinned task image identity changed")

    volume = "dcec-v1-claw-swe-mount-acceptance-" + hashlib.sha256(
        RUN_ID.encode()
    ).hexdigest()[:12]
    workspace = None
    container_name = None
    cleaned_up = False
    with tempfile.TemporaryDirectory(prefix="dcec-claw-mount-accept-") as temp_root:
        bundle_root = Path(temp_root) / "bundle"
        source_snapshot, _ = build_bundle(
            bundle_root, GA_ROOT, RUNTIME_LINUX, launch.python_home(),
            "native_claude_cc_vibe", "claude_monitor_opus48", 15328,
            monitor_profile_path=ROOT / "monitor_config" / "models.local.json",
        )
        mountpoints = launch.prepare_source_snapshot_mountpoints(source_snapshot)
        launch.docker("volume", "create", volume)
        try:
            launch.install_isolated_adapter(m3, source_snapshot, volume)
            module = m3.configure_m2_for_lock(lock)
            module.pin_workspace_image()
            adapter = module.M2GenericAgentAdapter(
                RUN_ID,
                {"model": "claude-opus-4-6", "effective_llm_no": 0},
                timeout=60,
            )
            # This acceptance validates container topology only.  Starting the
            # inference relay would broaden it beyond the audited mount defect.
            adapter.post_container_start = lambda _workspace: None
            workspace = module.SWEBenchWorkspace(INSTANCE_ID, adapter)
            container_name = workspace.start()

            source_read_only = _check(
                workspace,
                "! touch /opt/genericagent/.mount_acceptance_forbidden 2>/dev/null",
            ) == ""
            temp_write = _check(
                workspace,
                "p=/opt/genericagent/temp/.mount_acceptance; "
                "printf ok > $p; cat $p; rm -f $p",
            )
            memory_write = _check(
                workspace,
                "p=/opt/genericagent/memory/.mount_acceptance; "
                "printf ok > $p; cat $p; rm -f $p",
            )
            testbed_git = _check(
                workspace, "git -C /testbed rev-parse --is-inside-work-tree",
            )
            testbed_head = _check(workspace, "git -C /testbed rev-parse HEAD")
            interfaces = _check(workspace, "ls /sys/class/net | sort | tr '\\n' ' '").strip()
            cap_eff = _check(
                workspace, "awk '/^CapEff:/{print $2}' /proc/1/status",
            )
            no_new_privs = _check(
                workspace, "awk '/^NoNewPrivs:/{print $2}' /proc/1/status",
            )
            result = {
                "schema_version": "dcec-v1-claw-swe-mount-acceptance/1",
                "classification": "NOT A SCIENTIFIC RUN",
                "run_id": RUN_ID,
                "instance_id": INSTANCE_ID,
                "image_id": lock["image"]["image_id"],
                "container_started": True,
                "source_snapshot_read_only": source_read_only,
                "temp_mountpoint_materialized_before_mount": Path(mountpoints["temp"]).is_dir(),
                "temp_nested_mount_writable": temp_write == "ok",
                "memory_nested_mount_writable": memory_write == "ok",
                "testbed_is_git_worktree": testbed_git == "true",
                "testbed_head": testbed_head,
                "network_interfaces": interfaces.split(),
                "capabilities_effective_hex": cap_eff,
                "no_new_privileges": no_new_privs == "1",
                "task_agent_started": False,
                "supervisor_started": False,
                "task_model_requests": 0,
                "supervisor_model_requests": 0,
                "otel_model_traces": 0,
            }
            required = (
                result["container_started"]
                and result["source_snapshot_read_only"]
                and result["temp_mountpoint_materialized_before_mount"]
                and result["temp_nested_mount_writable"]
                and result["memory_nested_mount_writable"]
                and result["testbed_is_git_worktree"]
                and result["network_interfaces"] == ["lo"]
                and int(result["capabilities_effective_hex"], 16) == 0
                and result["no_new_privileges"]
            )
            result["passed"] = bool(required)
            if not result["passed"]:
                raise RuntimeError(f"mount acceptance failed: {result}")
        finally:
            if workspace is not None:
                workspace.cleanup()
            if container_name:
                inspected = launch.docker(
                    "container", "inspect", container_name, check=False, timeout=60
                )
                cleaned_up = inspected.returncode != 0
            launch.docker("volume", "rm", "-f", volume, check=False, timeout=60)

    result["container_cleaned_up"] = cleaned_up
    if not cleaned_up:
        raise RuntimeError("acceptance container was not cleaned up")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(execute(), ensure_ascii=False, indent=2))
