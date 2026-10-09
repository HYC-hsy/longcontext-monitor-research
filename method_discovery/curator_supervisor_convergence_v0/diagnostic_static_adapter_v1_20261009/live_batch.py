"""One authorized static-diagnostic batch; no Task or native evaluator exists here."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

from . import adapter
from .docker_tool import IMAGE
from .protocol import Audit, RUN_BUDGET, run_static
from .freeze_run import HOST_PROFILE
from method_discovery.curator_supervisor_convergence_v0.diagnostic_flex_preflight_v0_20261009 import freeze_inputs


HERE = Path(__file__).resolve().parent
EXPECTED_PROFILE_SHA = "cc5f784b069034f44bc4527d15acd70191b1f7fc5810556c087b7b35e0ae00f1"
ARCHIVED_PROFILE_SHA = "74cbb71bdab7f6e690554ae6d6977e9522539ace6012a8dcbde5597725709dec"
STOP_TERMINALS = {"protocol_or_infrastructure_failure", "infrastructure_timeout", "child_failure"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_freeze(freeze: dict) -> dict:
    expected = {"source_commit", "stage1_commit", "profile_sha256", "archived_profile_sha256", "image",
                "docker_tool_sha256", "probe_sha256", "requests", "order", "limits",
                "provider_policy", "tool_policy", "visibility_manifests"}
    if set(freeze) != expected:
        raise RuntimeError("Incomplete or expanded frozen run identity")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=freeze_inputs.REPO,
                          text=True, capture_output=True, check=True).stdout.strip()
    if head != freeze["source_commit"] or freeze["stage1_commit"] != "d76d8a178e4268582f3d5b5a2c052c6cd85a18bf":
        raise RuntimeError("Code/phase identity mismatch")
    if (digest(HOST_PROFILE) != freeze["profile_sha256"] or freeze["profile_sha256"] != EXPECTED_PROFILE_SHA or
            digest(freeze_inputs.PROFILE) != freeze["archived_profile_sha256"] or
            freeze["archived_profile_sha256"] != ARCHIVED_PROFILE_SHA):
        raise RuntimeError("Private profile identity mismatch")
    if freeze["image"] != IMAGE or digest(HERE / "docker_tool.py") != freeze["docker_tool_sha256"] or \
            digest(HERE / "probe_isolation.py") != freeze["probe_sha256"]:
        raise RuntimeError("Certified tool execution identity changed")
    if freeze["order"] != [list(row) for row in adapter.ORDER] or freeze["limits"] != RUN_BUDGET:
        raise RuntimeError("Order/budget identity changed")
    certification = HERE / "ISOLATION_CERTIFICATION_V2.json"
    expected_tool = {"image": IMAGE, "network": "none", "app": "read_only",
                     "evidence": "read_only", "private": "per_attempt_writable",
                     "scratch": "per_attempt_persistent_home_tmp_build_cache_output",
                     "new_command_timeout_max_seconds": 300, "poll_wait_max_seconds": 5,
                     "total_tool_calls_ceiling": None, "cumulative_tool_wait_ceiling": None,
                     "certification_sha256": digest(certification) if certification.exists() else None}
    if not certification.exists() or freeze["tool_policy"] != expected_tool:
        raise RuntimeError("Amended Docker isolation identity changed")
    for scene in adapter.SCENES:
        if freeze["visibility_manifests"].get(scene) != digest(HERE / f"{scene}_VISIBILITY_MANIFEST.json"):
            raise RuntimeError("Cutoff visibility manifest changed")
    for scene in adapter.SCENES:
        adapter.request_checks(scene)
        for arm in ("B", "F"):
            if adapter.sha(adapter.canonical(adapter.request(scene, arm))) != freeze["requests"][f"{scene}_{arm}"]:
                raise RuntimeError("Frozen request identity changed")
    image = subprocess.run(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"],
                           text=True, capture_output=True, check=True).stdout.strip()
    if image != IMAGE:
        raise RuntimeError("Task image identity mismatch")
    profile = json.loads(HOST_PROFILE.read_text(encoding="utf-8"))["claude_monitor_opus48"]
    archived = json.loads(freeze_inputs.PROFILE.read_text(encoding="utf-8"))["claude_monitor_opus48"]
    keys = ("model", "provider", "max_tokens", "thinking_type", "reasoning_effort",
            "temperature", "transport_route", "timeout", "read_timeout")
    if any(profile.get(key) != archived.get(key) for key in keys):
        raise RuntimeError("Host transport profile is not the archived model configuration")
    if (profile.get("model") != "claude-opus-4-8" or profile.get("provider") != "anthropic" or
            profile.get("max_tokens") != 8192 or profile.get("thinking_type") != "adaptive" or
            profile.get("reasoning_effort") != "high" or profile.get("temperature") != 1 or
            not profile.get("apikey") or not profile.get("apibase")):
        raise RuntimeError("Frozen model/profile unavailable")
    expected_policy = {"model": "claude-opus-4-8", "provider": "anthropic", "max_tokens": 8192,
                       "thinking_type": "adaptive", "reasoning_effort": "high", "stream": True,
                       "temperature_sent": False,
                       "connect_timeout_seconds": max(1, int(profile.get("timeout", 10))),
                       "read_timeout_seconds": max(10, int(profile.get("read_timeout", 300))),
                       "automatic_retry_on_ambiguous_failure": False}
    if freeze["provider_policy"] != expected_policy:
        raise RuntimeError("Transport/model protection differs from freeze")
    return profile  # Secret-bearing: caller must never serialize this mapping.


def slots():
    for scene, repeat, first, second in adapter.ORDER:
        for arm in (first, second):
            yield f"{scene}-R{repeat}-{arm}_static", scene, arm


def cleanup_sessions(slot: Path):
    commands = slot / "fixture/monitor_private/audit/commands"
    if not commands.exists():
        return
    for directory in commands.iterdir():
        if directory.is_dir() and re.fullmatch(r"static-[0-9a-f]{32}", directory.name):
            subprocess.run(["docker", "rm", "-f", directory.name],
                           capture_output=True, timeout=10, check=False)


def file_manifest(root: Path) -> dict:
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rows.append({"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size,
                         "sha256": digest(path)})
    return {"file_count": len(rows), "files": rows}


def execute_slots(root: Path, launch):
    records = []
    for index, (name, scene, arm) in enumerate(slots(), 1):
        slot = root / name
        result = launch(slot, scene, arm)
        records.append({"slot": name, "scene": scene, "arm": arm, **result})
        adapter.save_json(root / "BATCH_PROGRESS.json", {"started": records,
                          "unstarted": [item[0] for item in list(slots())[index:]]})
        if index == 1:
            print("FIRST_CASE_COMPLETE " + json.dumps({"slot": name,
                  "terminal": result.get("terminal"), "requests": result.get("provider_requests")}), flush=True)
        if result.get("terminal") in STOP_TERMINALS:
            break
    return records


def real_child(slot: Path, scene: str, arm: str, freeze_path: Path):
    if slot.exists():
        raise RuntimeError("Attempt path already exists")
    started = time.monotonic()
    with (slot.parent / (slot.name + ".stdout")).open("wb") as stdout, \
         (slot.parent / (slot.name + ".stderr")).open("wb") as stderr:
        try:
            process = subprocess.run([sys.executable, "-m", __package__ + ".live_batch", "--child",
                                      "--freeze", str(freeze_path), "--slot", str(slot),
                                      "--scene", scene, "--arm", arm], cwd=freeze_inputs.REPO,
                                     stdout=stdout, stderr=stderr, check=False)
            exit_code = process.returncode
        except OSError:
            exit_code = None
    cleanup_sessions(slot)
    result_file = slot / "audit/result.json"
    if result_file.exists():
        result = json.loads(result_file.read_text(encoding="utf-8"))
    else:
        result = {"terminal": "infrastructure_timeout" if exit_code is None else "child_failure",
                  "provider_requests": None, "accepted_responses": None, "tool_calls": None}
    if result.get("terminal") not in STOP_TERMINALS:
        audit_root = slot / "audit"
        events = audit_root / "events.jsonl"
        requests = result.get("provider_requests")
        try:
            rows = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
            valid = (exit_code == 0 and isinstance(requests, int) and requests >= 1 and
                     len(list(audit_root.glob("request_*.json"))) == requests and
                     len(list(audit_root.glob("stream_*.sse"))) == requests and
                     sum(row.get("kind") == "provider_response" for row in rows) ==
                     result.get("accepted_responses") and
                     (slot / "fixture/RESEARCH_ONLY_MANIFEST.json").exists())
        except (OSError, ValueError, TypeError):
            valid = False
        if not valid:
            result["terminal"] = "protocol_or_infrastructure_failure"
            result["post_run_integrity_error"] = "request/stream/event/fixture identity incomplete"
    result["child_exit_code"] = exit_code
    result["parent_wall_seconds"] = time.monotonic() - started
    return result


def child_main(args):
    profile = validate_freeze(json.loads(args.freeze.read_text(encoding="utf-8")))
    args.slot.mkdir(parents=True, exist_ok=False)
    fixture = args.slot / "fixture"
    fixture_manifest = adapter.materialize(args.scene, fixture)
    audit = Audit(args.slot / "audit")
    audit.record("fixture_identity", scene=args.scene,
                 workspace_tree_sha256=fixture_manifest["workspace_tree_sha256"],
                 visible_file_count=len(fixture_manifest["visible_files"]))
    result = run_static(args.scene, args.arm, profile, fixture, audit)
    print(json.dumps({"terminal": result["terminal"], "provider_requests": result["provider_requests"]}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--slot", type=Path)
    parser.add_argument("--scene", choices=list(adapter.SCENES))
    parser.add_argument("--arm", choices=["B", "F"])
    args = parser.parse_args()
    if args.child:
        if not args.slot or not args.scene or not args.arm:
            raise RuntimeError("Incomplete child identity")
        child_main(args)
        return
    if not args.live or not args.output_root or args.output_root.exists():
        raise RuntimeError("Live batch requires explicit --live and fresh output root")
    validate_freeze(json.loads(args.freeze.read_text(encoding="utf-8")))
    args.output_root.mkdir(parents=True)
    (args.output_root / "FROZEN_RUN_IDENTITY.json").write_bytes(args.freeze.read_bytes())
    records = execute_slots(args.output_root, lambda slot, scene, arm:
                            real_child(slot, scene, arm, args.freeze.resolve(strict=True)))
    adapter.save_json(args.output_root / "BATCH_RESULT.json", {"slots": records,
                      "started_count": len(records), "planned_count": 12})
    adapter.save_json(args.output_root / "RAW_FILE_MANIFEST.json", file_manifest(args.output_root))


if __name__ == "__main__":
    main()
