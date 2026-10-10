"""One frozen 12-slot C02 H/R native-boundary diagnostic batch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import requests

from .bootstrap import HANDOFF, DIALOGUE_CUTOFF, certify_cutoff, candidate_config
from .freeze_inputs import HERE, build_requests, digest
from .native_runtime import run_native_slot, ROOT_CEILING
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009 import adapter
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.docker_tool import IMAGE
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.freeze_run import HOST_PROFILE
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.protocol import Audit
from method_discovery.curator_supervisor_convergence_v0.diagnostic_flex_preflight_v0_20261009.freeze_inputs import REPO


ORDER = [(1, "H", "R"), (2, "R", "H"), (3, "H", "R"),
         (4, "R", "H"), (5, "H", "R"), (6, "R", "H")]
FILES = {
    "research/freeze_inputs.py": HERE / "freeze_inputs.py",
    "research/bootstrap.py": HERE / "bootstrap.py",
    "research/payload_client.py": HERE / "payload_client.py",
    "research/ports.py": HERE / "ports.py",
    "research/native_runtime.py": HERE / "native_runtime.py",
    "research/run_batch.py": HERE / "run_batch.py",
    "research/archive_batch.py": HERE / "archive_batch.py",
    "research/BOOTSTRAP_STATE_TEMPLATE.json": HERE / "BOOTSTRAP_STATE_TEMPLATE.json",
    "research/EVALUATION_RECORD_TEMPLATE.json": HERE / "EVALUATION_RECORD_TEMPLATE.json",
    "research/docker_tool.py": adapter.HERE / "docker_tool.py",
    "research/adapter.py": adapter.HERE / "adapter.py",
    "production/agent.py": REPO / "GenericAgent-main/monitor_agent_core/agent.py",
    "production/ase_v0.py": REPO / "GenericAgent-main/monitor_agent_core/ase_v0.py",
    "production/crs_v0.py": REPO / "GenericAgent-main/monitor_agent_core/crs_v0.py",
    "production/cfs_v0.py": REPO / "GenericAgent-main/monitor_agent_core/cfs_v0.py",
    "production/dcm_v0.py": REPO / "GenericAgent-main/monitor_agent_core/dcm_v0.py",
    "production/provider.py": REPO / "GenericAgent-main/monitor_agent_core/provider.py",
    "production/loop.py": REPO / "GenericAgent-main/monitor_agent_core/loop.py",
    "production/runtime.py": REPO / "GenericAgent-main/monitor_agent_core/runtime.py",
    "production/workspace.py": REPO / "GenericAgent-main/monitor_agent_core/workspace.py",
}
CERT = adapter.HERE / "ISOLATION_CERTIFICATION_V3.json"


def head():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          check=True, capture_output=True, text=True).stdout.strip()


def code_hashes():
    return {name: digest(path.read_bytes()) for name, path in FILES.items()}


def native_source_identity():
    root = REPO / "GenericAgent-main/monitor_agent_core"
    rows = [(path.relative_to(root).as_posix(), digest(path.read_bytes()))
            for path in root.rglob("*.py")]
    return {"python_files": len(rows), "aggregate_sha256": digest(
        adapter.canonical(sorted(rows)))}


def cutoff_dialogue_prefix_sha256():
    source = adapter.ARCHIVE / "monitor/audit/dialogue.jsonl"
    return digest(b"".join(source.read_bytes().splitlines(keepends=True)[:DIALOGUE_CUTOFF]))


def direct_session():
    result = requests.Session()
    result.trust_env = False
    return result


def build_freeze():
    requests_by_arm, identities = build_requests()
    profile = candidate_config()
    source = json.loads(HOST_PROFILE.read_text(encoding="utf-8"))["claude_monitor_opus48"]
    if not profile.get("apikey") or not profile.get("apibase"):
        raise RuntimeError("Frozen private inference transport unavailable")
    if any(profile.get(key) != source.get(key) for key in
           ("model", "provider", "max_tokens", "thinking_type", "reasoning_effort",
            "temperature", "transport_route", "timeout", "read_timeout")):
        raise RuntimeError("Model/transport profile changed while enabling native control flags")
    if (profile["model"] != "claude-opus-4-8" or profile["max_tokens"] != 8192 or
            profile["thinking_type"] != "adaptive" or profile["reasoning_effort"] != "high" or
            profile.get("temperature", 1) != 1 or profile.get("proxy") or
            profile.get("verify", True) is not True):
        raise RuntimeError("Frozen model or direct verified transport mismatch")
    if not CERT.exists():
        raise RuntimeError("Certified static Docker isolation record missing")
    return {"source_commit": head(), "revision": "C02_H_R_native_BJI_static_v1",
            "source_request_identities": identities,
            "new_requests": {arm: digest(adapter.canonical(value))
                             for arm, value in requests_by_arm.items()},
            "new_request_file_sha256": {arm: digest((HERE / "frozen_requests" /
                                          f"{arm}_FULL_REQUEST.json").read_bytes())
                                         for arm in requests_by_arm},
            "code_hashes": code_hashes(), "native_source_identity": native_source_identity(),
            "private_profile_file_sha256": digest(HOST_PROFILE.read_bytes()),
            "isolation_certification_sha256": digest(CERT.read_bytes()),
            "C02_visibility_manifest_sha256": digest((adapter.HERE /
                "C02_VISIBILITY_MANIFEST.json").read_bytes()),
            "C02_dialogue_prefix_lines": DIALOGUE_CUTOFF,
            "C02_dialogue_prefix_sha256": cutoff_dialogue_prefix_sha256(),
            "image": IMAGE, "handoff": HANDOFF,
            "mechanisms": {"ASE": True, "CRS": True, "RHR": True, "RER": True},
            "root_outer_model_cycle_ceiling": ROOT_CEILING,
            "task_turn_at_cutoff": 83, "task_max_turns": 300,
            "order": [list(row) for row in ORDER], "planned_slots": 12,
            "provider": {"model": "claude-opus-4-8", "max_tokens": 8192,
                         "thinking_type": "adaptive", "reasoning_effort": "high",
                         "stream": True, "temperature_sent": False,
                         "connect_timeout_seconds": max(1, int(profile.get("timeout", 10))),
                         "read_timeout_seconds": max(10, int(profile.get("read_timeout", 300))),
                         "max_retries": 0, "recovery_deadline": None,
                         "proxy_policy": "direct_session_trust_env_false", "tls_verify": True},
            "tool": {"image": IMAGE, "network": "none", "app": "read_only",
                     "private_and_scratch": "fresh_per_slot", "code_run_default_timeout": 60,
                     "code_run_max_timeout": 300, "poll_wait_max_seconds": 5},
            "task_agent": "disabled", "native_evaluator": "disabled", "scoring_model": "disabled"}


def validate_freeze(frozen):
    if frozen != build_freeze():
        raise RuntimeError("Frozen code/config/request identity changed")
    image = subprocess.run(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"],
                           capture_output=True, text=True, check=True).stdout.strip()
    if image != IMAGE:
        raise RuntimeError("Frozen task image identity unavailable")
    return candidate_config()


def slots():
    for pair, first, second in ORDER:
        for arm in (first, second):
            yield f"C02-P{pair}-{arm}", arm


def run_child(slot: Path, arm: str, frozen):
    profile = validate_freeze(frozen)
    if slot.exists():
        raise RuntimeError("Slot output already exists")
    slot.mkdir(parents=True)
    fixture = slot / "fixture"
    material = adapter.materialize("C02", fixture)
    state = certify_cutoff(fixture, adapter.ARCHIVE / "monitor/audit/dialogue.jsonl")
    if state["dialogue_prefix_sha256"] != frozen["C02_dialogue_prefix_sha256"]:
        raise RuntimeError("C02 historical dialogue prefix changed after freeze")
    adapter.save_json(slot / "BOOTSTRAP_STATE.json", {
        "from_cutoff": state, "common_research_initialization": {
            "root_outer_model_cycle_budget": ROOT_CEILING,
            "static_task_no_progress": True, "fresh_provider_process": True,
            "fresh_CRS_RHR_RER_objects": True, "future_task_control": "record_only_noop"},
        "fixture_workspace_sha256": material["workspace_tree_sha256"]})
    audit = Audit(slot / "audit")
    audit.record("fixture_identity", workspace_sha256=material["workspace_tree_sha256"],
                 visible_files=len(material["visible_files"]))
    request = build_requests()[0][arm]
    with direct_session() as session:
        result = run_native_slot(fixture, request, profile, audit, session)
    print(json.dumps({"terminal": result["terminal"],
                      "provider_requests": result["provider_requests"]}), flush=True)


def launch_child(root: Path, name: str, arm: str, freeze_path: Path):
    slot = root / name
    if slot.exists():
        raise RuntimeError("Duplicate slot path")
    started = time.monotonic()
    with (root / f"{name}.stdout").open("wb") as out, (root / f"{name}.stderr").open("wb") as err:
        child = subprocess.run([sys.executable, "-m", __package__ + ".run_batch", "--child",
                                "--freeze", str(freeze_path), "--slot", str(slot), "--arm", arm],
                               cwd=REPO, stdout=out, stderr=err, check=False)
    result_file = slot / "audit/result.json"
    result = json.loads(result_file.read_text(encoding="utf-8")) if result_file.exists() else {
        "terminal": "infrastructure_or_protocol_failure", "error_type": "missing_result"}
    names = []
    commands = slot / "fixture/monitor_private/audit/commands"
    if commands.exists():
        names = [item.name for item in commands.iterdir() if item.is_dir()
                 and item.name.startswith("static-") and len(item.name) == 39]
    lingering = []
    cleanup_failures = []
    for name in names:
        try:
            inspect = subprocess.run(["docker", "container", "inspect", name],
                                     capture_output=True, timeout=15, check=False)
            if inspect.returncode == 0:
                lingering.append(name)
                removed = subprocess.run(["docker", "rm", "-f", name], capture_output=True,
                                         timeout=15, check=False)
                recheck = subprocess.run(["docker", "container", "inspect", name],
                                        capture_output=True, timeout=15, check=False)
                if removed.returncode != 0 or recheck.returncode == 0:
                    cleanup_failures.append({"container": name, "reason": "removal_not_confirmed"})
            elif inspect.returncode != 1:
                cleanup_failures.append({"container": name, "reason": "inspect_failed",
                                         "returncode": inspect.returncode})
        except (OSError, subprocess.TimeoutExpired) as exc:
            cleanup_failures.append({"container": name, "reason": type(exc).__name__})
    if lingering or cleanup_failures or child.returncode != 0 or not result_file.exists():
        result["primary_terminal"] = result.get("terminal")
        result["terminal"] = "infrastructure_or_protocol_failure"
        result["child_exit_code"] = child.returncode
        result["lingering_container_ids"] = lingering
        result["container_cleanup_unconfirmed"] = cleanup_failures
    result["parent_wall_seconds"] = time.monotonic() - started
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-freeze", type=Path)
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--slot", type=Path)
    parser.add_argument("--arm", choices=("H", "R"))
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    if args.write_freeze:
        if args.write_freeze.exists():
            raise RuntimeError("Freeze file exists")
        adapter.save_json(args.write_freeze, build_freeze())
        return
    if args.freeze is None:
        raise RuntimeError("Explicit frozen identity file required")
    freeze_path = args.freeze.resolve(strict=True)
    frozen = json.loads(freeze_path.read_text(encoding="utf-8"))
    validate_freeze(frozen)
    if args.child:
        if args.slot is None or args.arm is None:
            raise RuntimeError("Incomplete child arguments")
        run_child(args.slot, args.arm, frozen)
        return
    if not args.live or args.output_root is None or args.output_root.exists():
        raise RuntimeError("Explicit --live and a fresh output root are required")
    root = args.output_root
    root.mkdir(parents=True)
    (root / "FROZEN_RUN_IDENTITY.json").write_bytes(freeze_path.read_bytes())
    records = []
    planned = list(slots())
    for index, (name, arm) in enumerate(planned, 1):
        result = launch_child(root, name, arm, freeze_path)
        records.append({"slot": name, "arm": arm, **result})
        adapter.save_json(root / "BATCH_PROGRESS.json", {
            "started": records, "unstarted": [row[0] for row in planned[index:]]})
        print("SLOT_COMPLETE " + json.dumps({"slot": name, "terminal": result["terminal"],
                                             "provider_requests": result.get("provider_requests")}), flush=True)
        if result["terminal"] == "infrastructure_or_protocol_failure":
            break
    adapter.save_json(root / "BATCH_RESULT.json", {"slots": records,
                      "started_count": len(records), "planned_count": len(planned),
                      "unstarted": [row[0] for row in planned[len(records):]]})


if __name__ == "__main__":
    main()
