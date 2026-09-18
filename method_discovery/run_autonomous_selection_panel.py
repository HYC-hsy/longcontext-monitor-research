"""Run direct-C versus parent-selected-question+C on fixed checkpoints.

The panel is intentionally not wired into the online monitor. It is a small
diagnostic experiment with a shared logical-call budget per group.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(ROOT / "GenericAgent-main"))
sys.path.insert(0, str(ROOT / "method_discovery"))
from monitor_agent_core.probe import IndependentVerifier, ProbeConfig, score_local_result  # noqa: E402
from monitor_agent_core.provider import MonitorProviderClient  # noqa: E402
from monitor_agent_core.workspace import MonitorWorkspace  # noqa: E402
from monitor_agent_core.configuration import load_profile  # noqa: E402
from autonomous_selection_probe import SelectionConfig, run_autonomous_selection_case  # noqa: E402
from run_independent_probe_panel import transport_audit_callback  # noqa: E402


PANEL = ROOT / "method_discovery/artifacts/independent_verification_20260918"
DEFAULT_CONFIG = ROOT / "method_discovery/autonomous_selection_config.json"
DEFAULT_PROFILE = ROOT / "monitor_config/models.local.json"


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
                    encoding="utf-8")


def audit_writer(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)

    def write(event, **fields):
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"event": event, **fields},
                                    ensure_ascii=False, default=str) + "\n")
            stream.flush()
    return write


def usage_total(records: list[dict]) -> dict:
    keys = ("input_tokens", "output_tokens", "cache_creation_input_tokens",
            "cache_read_input_tokens")
    result = {key: sum(int(item.get(key) or 0) for item in records) for key in keys}
    result["total_tokens"] = sum(result.values())
    return result


def write_transport_config(path: Path, profile: dict) -> None:
    write_json(path, {
        "provider": profile.get("provider"), "model": profile.get("model"),
        "api_mode": profile.get("api_mode"), "timeout": profile.get("timeout"),
        "read_timeout": profile.get("read_timeout"),
        "max_retries": profile.get("max_retries"), "stream": True,
        "apikey": "[redacted]",
    })


def load_inputs(config_path: Path):
    experiment = json.loads(config_path.read_text(encoding="utf-8"))
    checkpoint_path = PANEL / "checkpoint_config.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    fixture = PANEL / "materialized_r4"
    manifest = json.loads((fixture / "materialization.json").read_text(encoding="utf-8"))
    if manifest.get("config_sha256") != hashlib.sha256(checkpoint_path.read_bytes()).hexdigest():
        raise ValueError("checkpoint configuration digest changed")
    cases = {case["id"]: case for case in checkpoint["cases"]}
    selected = [cases[case_id] for case_id in experiment["cases"]]
    if any(case["scoring"].get("label_status", "confirmed") != "confirmed" for case in selected):
        raise ValueError("selected cases must have confirmed labels")
    workspace_files = sorted(
        path.relative_to(fixture / "workspace").as_posix()
        for path in (fixture / "workspace").rglob("*") if path.is_file()
    )
    evidence = (
        "task/public_events.jsonl", "task/build_observation.json",
        *(f"task/workspace/{path}" for path in workspace_files),
    )
    evidence_by_case = {
        case["id"]: tuple(experiment.get("evidence_overrides", {}).get(
            case["id"], evidence)) for case in selected
    }
    return experiment, checkpoint, fixture, selected, evidence_by_case


def run_direct(case, fixture, evidence, profile, output):
    private = output / case["id"] / "direct_c" / "private"
    private.mkdir(parents=True)
    group_dir = private.parent
    write_transport_config(group_dir / "transport_config.json", profile)
    audit = audit_writer(group_dir / "audit.jsonl")
    workspace = MonitorWorkspace(fixture / "task_evidence", private,
                                 task_mounts={"workspace": fixture / "workspace"})
    client = MonitorProviderClient("autonomous-selection::direct-c", dict(profile))
    client.progress_callback = transport_audit_callback(
        [], case["id"], "direct_c", group_dir / "transport.jsonl")
    verifier = IndependentVerifier(
        client, workspace,
        ProbeConfig(mode="direct", source_paths=("task/original_task.txt",),
                    evidence_paths=evidence, max_requests=6, max_turns=8),
        audit=audit,
    )
    started = time.monotonic()
    result = verifier.run(case["question"])
    item = {
        "case": case["id"], "group": "direct_c", "status": result.status,
        "outcome": result.outcome, "conclusion": result.conclusion,
        **score_local_result(result, {"correct": "supported_in_scope",
                                      "incorrect": "contradicted",
                                      "insufficient": "unresolved"}[case["scoring"]["expected_label"]]),
        "requests": result.requests, "seconds": round(time.monotonic() - started, 3),
        "usage": usage_total(client.usage_records),
        "material_evidence_count": len(evidence),
    }
    write_json(private.parent / "result.json", item)
    return item


def run_panel(args):
    experiment, checkpoint, fixture, cases, evidence_by_case = load_inputs(args.config)
    profile = load_profile(args.profile, args.profile_file)
    output = args.output
    output.mkdir(parents=True)
    write_json(output / "manifest.json", {
        "schema": experiment["schema"], "checkpoint_sha256": hashlib.sha256(
            (PANEL / "checkpoint_config.json").read_bytes()).hexdigest(),
        "cases": [case["id"] for case in cases],
        "evidence_count_by_case": {case["id"]: len(evidence_by_case[case["id"]])
                                   for case in cases},
        "groups": ["direct_c", "autonomous_selection_c"],
        "total_calls": experiment["total_calls"],
    })
    for case in cases:
        evidence = evidence_by_case[case["id"]]
        direct = run_direct(case, fixture, evidence, profile, output)
        parent_client = MonitorProviderClient("autonomous-selection::parent", dict(profile))
        child_client = MonitorProviderClient("autonomous-selection::child-c", dict(profile))
        private = output / case["id"] / "autonomous_selection_c" / "private"
        private.mkdir(parents=True)
        group_dir = private.parent
        write_transport_config(group_dir / "transport_config.json", profile)
        audit = audit_writer(group_dir / "audit.jsonl")
        transport = group_dir / "transport.jsonl"
        workspace = MonitorWorkspace(fixture / "task_evidence", private,
                                     task_mounts={"workspace": fixture / "workspace"})
        parent_client.progress_callback = transport_audit_callback(
            [], case["id"], "autonomous_parent", transport)
        child_client.progress_callback = transport_audit_callback(
            [], case["id"], "autonomous_child_c", transport)
        started = time.monotonic()
        autonomous = run_autonomous_selection_case(
            parent_client, child_client, workspace, case["question"],
            ("task/original_task.txt",), evidence,
            SelectionConfig(total_calls=experiment["total_calls"],
                             selection_turns=experiment["selection_turns"],
                             child_turns=experiment["child_turns"],
                             final_turns=experiment["final_turns"]),
            audit=audit,
        )
        expected = {"correct": "supported_in_scope", "incorrect": "contradicted",
                    "insufficient": "unresolved"}[case["scoring"]["expected_label"]]
        if autonomous.get("status") == "completed":
            autonomous["correct"] = autonomous["final"]["outcome"] == expected
            autonomous["score_eligible"] = True
        else:
            autonomous["correct"] = None
            autonomous["score_eligible"] = False
        autonomous.update({"case": case["id"], "group": "autonomous_selection_c",
                           "seconds": round(time.monotonic() - started, 3),
                           "evidence_count": len(evidence),
                           "parent_calls": parent_client.request_attempts,
                           "child_calls": child_client.request_attempts})
        autonomous["parent_usage"] = usage_total(parent_client.usage_records)
        autonomous["child_usage"] = usage_total(child_client.usage_records)
        autonomous["transport_log"] = "transport.jsonl"
        write_json(private.parent / "result.json", autonomous)
        print(json.dumps({"direct": direct, "autonomous": autonomous},
                         ensure_ascii=False, default=str), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile-file", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--profile", default="claude_monitor_opus48")
    args = parser.parse_args()
    run_panel(args)


if __name__ == "__main__":
    main()
