"""One frozen C02 H/R batch using the certified static tool and provider loop."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import requests as http_requests

from .projection import HERE, SOURCE, digest, project
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009 import adapter
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009 import live_batch as v2
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.docker_tool import IMAGE
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.protocol import Audit, RUN_BUDGET, run_static
from method_discovery.curator_supervisor_convergence_v0.diagnostic_flex_preflight_v0_20261009 import freeze_inputs


ORDER = [(1, "H", "R"), (2, "R", "H"), (3, "H", "R"),
         (4, "R", "H"), (5, "H", "R"), (6, "R", "H")]
REQUEST_DIR = HERE / "frozen_requests"
CERT = adapter.HERE / "ISOLATION_CERTIFICATION_V3.json"
PROFILE = v2.HOST_PROFILE
CODE = {
    "projection.py": HERE / "projection.py",
    "run_batch.py": HERE / "run_batch.py",
    "archive_batch.py": HERE / "archive_batch.py",
    "research/adapter.py": adapter.HERE / "adapter.py",
    "research/protocol.py": adapter.HERE / "protocol.py",
    "research/docker_tool.py": adapter.HERE / "docker_tool.py",
    "research/live_batch.py": adapter.HERE / "live_batch.py",
    "production/provider.py": freeze_inputs.REPO / "GenericAgent-main/monitor_agent_core/provider.py",
    "production/loop.py": freeze_inputs.REPO / "GenericAgent-main/monitor_agent_core/loop.py",
    "production/actions.py": freeze_inputs.REPO / "GenericAgent-main/monitor_agent_core/actions.py",
}


def head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=freeze_inputs.REPO,
                          text=True, capture_output=True, check=True).stdout.strip()


def requests() -> dict[str, dict]:
    h, r, _ = project()
    results = {"H": h, "R": r}
    for condition, value in results.items():
        frozen = json.loads((REQUEST_DIR / f"{condition}_REQUEST.json").read_text(encoding="utf-8"))
        if frozen != value:
            raise RuntimeError("Frozen projected request drift: " + condition)
    return results


def direct_session() -> http_requests.Session:
    """Use the configured HTTPS endpoint without inheriting Windows proxy settings."""
    session = http_requests.Session()
    session.trust_env = False
    return session


def build_freeze() -> dict:
    if not CERT.exists():
        raise RuntimeError("Certified isolation identity missing")
    cert = json.loads(CERT.read_text(encoding="utf-8"))
    if cert["tool_port_source_sha256"] != digest((adapter.HERE / "docker_tool.py").read_bytes()):
        raise RuntimeError("Tool port differs from isolation certification")
    values = requests()
    _, _, projection_manifest = project()
    archived = json.loads(freeze_inputs.PROFILE.read_text(encoding="utf-8"))["claude_monitor_opus48"]
    host = json.loads(PROFILE.read_text(encoding="utf-8"))["claude_monitor_opus48"]
    for key in ("model", "provider", "max_tokens", "thinking_type", "reasoning_effort",
                "temperature", "transport_route", "timeout", "read_timeout"):
        if host.get(key) != archived.get(key):
            raise RuntimeError("Host model profile differs from certified profile")
    if (host.get("model"), host.get("provider"), host.get("max_tokens"),
        host.get("thinking_type"), host.get("reasoning_effort")) != (
            "claude-opus-4-8", "anthropic", 8192, "adaptive", "high"):
        raise RuntimeError("Frozen model profile unavailable")
    if not host.get("apikey") or not host.get("apibase"):
        raise RuntimeError("Private inference transport unavailable")
    if host.get("proxy") or host.get("verify", True) is not True:
        raise RuntimeError("Direct transport requires no explicit proxy and certificate verification")
    return {
        "source_commit": head(), "research_revision": "C02_history_projection_H_R_v1",
        "v2_archive_commit": "adb12fb9fb2224619d1593d57baac8d0edebe227",
        "source_request_raw_sha256": digest(SOURCE.read_bytes()),
        "source_request_canonical_sha256": projection_manifest["H_canonical_sha256"],
        "request_sha256": {k: digest(adapter.canonical(v)) for k, v in values.items()},
        "request_file_sha256": {k: digest((REQUEST_DIR / f"{k}_REQUEST.json").read_bytes())
                                for k in values},
        "projection_manifest_sha256": digest((REQUEST_DIR / "PROJECTION_MANIFEST.json").read_bytes()),
        "evaluation_record_template_sha256": digest((HERE / "EVALUATION_RECORD_TEMPLATE.json").read_bytes()),
        "code_hashes": {name: digest(path.read_bytes()) for name, path in CODE.items()},
        "profile_file_sha256": digest(PROFILE.read_bytes()),
        "archived_profile_sha256": digest(freeze_inputs.PROFILE.read_bytes()),
        "isolation_certification_sha256": digest(CERT.read_bytes()),
        "image": IMAGE,
        "C02_visibility_manifest_sha256": digest((adapter.HERE / "C02_VISIBILITY_MANIFEST.json").read_bytes()),
        "order": [list(row) for row in ORDER], "planned_slots": 12,
        "limits": RUN_BUDGET,
        "provider": {"model": "claude-opus-4-8", "max_tokens": 8192,
                     "thinking_type": "adaptive", "reasoning_effort": "high",
                     "stream": True, "temperature_sent": False,
                     "connect_timeout_seconds": max(1, int(host.get("timeout", 10))),
                     "read_timeout_seconds": max(10, int(host.get("read_timeout", 300))),
                     "ambiguous_transport_retries": 0,
                     "proxy_policy": "direct_session_trust_env_false",
                     "certificate_verification": True},
        "tool": {"image": IMAGE, "network": "none", "task_source": "read_only",
                 "private_and_scratch": "fresh_per_slot", "new_code_run_timeout_default": 60,
                 "new_code_run_timeout_max": 300, "poll_wait_max_seconds": 5},
        "evaluator": "disabled", "task_agent": "disabled", "scoring_model": "disabled",
    }


def validate_freeze(frozen: dict) -> dict:
    expected = build_freeze()
    if frozen != expected:
        raise RuntimeError("Run freeze/source/config identity mismatch")
    image = subprocess.run(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"],
                           text=True, capture_output=True, check=True).stdout.strip()
    if image != IMAGE:
        raise RuntimeError("Task image identity mismatch")
    return json.loads(PROFILE.read_text(encoding="utf-8"))["claude_monitor_opus48"]


def slots():
    for pair, first, second in ORDER:
        for arm in (first, second):
            yield f"C02-P{pair}-{arm}", arm


def child(slot: Path, arm: str, freeze_path: Path) -> None:
    profile = validate_freeze(json.loads(freeze_path.read_text(encoding="utf-8")))
    if slot.exists():
        raise RuntimeError("Slot already exists")
    slot.mkdir(parents=True)
    fixture = slot / "fixture"
    material = adapter.materialize("C02", fixture)
    audit = Audit(slot / "audit")
    audit.record("fixture_identity", workspace_sha256=material["workspace_tree_sha256"],
                 visible_file_count=len(material["visible_files"]))
    request = requests()[arm]
    with direct_session() as session:
        result = run_static("C02", arm, profile, fixture, audit,
                            transport=session.post, frozen_request=request)
    print(json.dumps({"terminal": result["terminal"], "requests": result["provider_requests"]}), flush=True)


def launch_child(root: Path, name: str, arm: str, freeze_path: Path) -> dict:
    slot = root / name
    if slot.exists():
        raise RuntimeError("Slot already exists")
    started = time.monotonic()
    with (root / f"{name}.stdout").open("wb") as out, (root / f"{name}.stderr").open("wb") as err:
        process = subprocess.run([sys.executable, "-m", __package__ + ".run_batch", "--child",
                                  "--freeze", str(freeze_path), "--slot", str(slot), "--arm", arm],
                                 cwd=freeze_inputs.REPO, stdout=out, stderr=err, check=False)
    v2.cleanup_sessions(slot)
    result_path = slot / "audit/result.json"
    result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {
        "terminal": "child_failure", "provider_requests": None}
    if result["terminal"] not in v2.STOP_TERMINALS:
        try:
            events = [json.loads(line) for line in (slot / "audit/events.jsonl").read_text(encoding="utf-8").splitlines()]
            count = result["provider_requests"]
            complete = (process.returncode == 0 and isinstance(count, int) and count >= 1 and
                        len(list((slot / "audit").glob("request_*.json"))) == count and
                        len(list((slot / "audit").glob("stream_*.sse"))) == count and
                        sum(row.get("kind") == "provider_response" for row in events) == result["accepted_responses"] and
                        (slot / "fixture/RESEARCH_ONLY_MANIFEST.json").exists())
        except (OSError, ValueError, TypeError):
            complete = False
        if not complete:
            result["terminal"] = "protocol_or_infrastructure_failure"
            result["post_run_integrity_error"] = "request/response/fixture archive incomplete"
    result["child_exit_code"] = process.returncode
    result["parent_wall_seconds"] = time.monotonic() - started
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--slot", type=Path)
    parser.add_argument("--arm", choices=("H", "R"))
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--write-freeze", type=Path)
    args = parser.parse_args()
    if args.write_freeze:
        if args.write_freeze.exists():
            raise RuntimeError("Freeze output exists")
        adapter.save_json(args.write_freeze, build_freeze())
        return
    if not args.freeze:
        raise RuntimeError("Frozen identity required")
    freeze_path = args.freeze.resolve(strict=True)
    validate_freeze(json.loads(freeze_path.read_text(encoding="utf-8")))
    if args.child:
        if not args.slot or not args.arm:
            raise RuntimeError("Incomplete child arguments")
        child(args.slot, args.arm, freeze_path)
        return
    if not args.live or not args.output_root or args.output_root.exists():
        raise RuntimeError("Explicit --live and fresh output path required")
    root = args.output_root
    root.mkdir(parents=True)
    (root / "FROZEN_RUN_IDENTITY.json").write_bytes(freeze_path.read_bytes())
    records = []
    for index, (name, arm) in enumerate(slots(), 1):
        result = launch_child(root, name, arm, freeze_path)
        records.append({"slot": name, "arm": arm, **result})
        adapter.save_json(root / "BATCH_PROGRESS.json", {
            "started": records, "unstarted": [item[0] for item in list(slots())[index:]]})
        if index == 1:
            print("FIRST_CASE_COMPLETE " + json.dumps({"slot": name, "terminal": result["terminal"],
                                                       "requests": result["provider_requests"]}), flush=True)
        if result["terminal"] in v2.STOP_TERMINALS:
            break
    adapter.save_json(root / "BATCH_RESULT.json", {"slots": records, "started_count": len(records),
                                                   "planned_count": 12})
    adapter.save_json(root / "RAW_FILE_MANIFEST.json", v2.file_manifest(root))


if __name__ == "__main__":
    main()
