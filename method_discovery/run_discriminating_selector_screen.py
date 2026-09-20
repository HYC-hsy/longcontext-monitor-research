"""Run the frozen O/G/E discriminating-selector screen (six new G/E records)."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "GenericAgent-main"))

from monitor_agent_core.checkpoint import load_root_checkpoint, restored_request  # noqa: E402
from monitor_agent_core.configuration import load_profile  # noqa: E402
from monitor_agent_core.experiment_contract import load_contract  # noqa: E402
from monitor_agent_core.provider import MonitorProviderClient  # noqa: E402

from discriminating_selector_candidates import (  # noqa: E402
    MODES, PROTOCOL_ID as CANDIDATE_PROTOCOL, run_candidate, selector_spec,
)
from run_direct_evidence_diagnostic import validate_direct_profile_contract  # noqa: E402
from run_scoped_decision_diagnostic import prepare_case, usage  # noqa: E402
from scoped_decision_diagnostic import case_question  # noqa: E402


PROTOCOL_ID = "discriminating-selector-screen-v1"


def branch_identity(case: str, repeat: int, condition: str) -> str:
    """Bind private cognition to the complete experimental record identity."""
    if not case or type(repeat) is not int or repeat < 1 or condition not in MODES:
        raise ValueError("invalid discriminating-selector branch identity")
    return f"{case}-r{repeat}-{condition}"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().lower()


def append_json(path: Path, item: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
        stream.flush()


def combined_usage(*clients) -> dict:
    values = [usage(client) for client in clients]
    keys = {key for value in values for key in value}
    return {key: sum(int(value.get(key) or 0) for value in values) for key in keys}


def validate_config(config: dict) -> None:
    protocol = config.get("protocol", {})
    if protocol.get("id") != PROTOCOL_ID:
        raise ValueError("wrong discriminating-selector screen protocol")
    if (protocol.get("total_calls_per_record"), protocol.get("ordinary_calls"),
            protocol.get("selector_calls"), protocol.get("selected_parent_calls")) != (6, 6, 1, 5):
        raise ValueError("the frozen 6 versus 1+5 budget changed")
    if protocol.get("ordinary_policy") != "reuse_frozen_r11_before_new_results":
        raise ValueError("ordinary-control reuse was not preregistered")
    if any(protocol.get(name) for name in ("independent_c", "coverage_frontier_f",
                                           "code_execution")):
        raise ValueError("a forbidden mechanism was enabled")
    expected_new = {
        ("r7_root_completion", mode, repeat)
        for mode in MODES for repeat in (1, 2)
    } | {("synthetic_root_complete", mode, 1) for mode in MODES}
    actual_new = {(item.get("case"), item.get("condition"), item.get("repeat"))
                  for item in config.get("new_run_order", ())}
    if len(config.get("new_run_order", ())) != 6 or actual_new != expected_new:
        raise ValueError("new_run_order must contain the frozen six G/E records")
    ordinary = {(item.get("case"), item.get("condition"), item.get("repeat"))
                for item in config.get("historical_ordinary", ())}
    expected_o = {("r7_root_completion", "ordinary", 1),
                  ("r7_root_completion", "ordinary", 2),
                  ("synthetic_root_complete", "ordinary", 1)}
    if ordinary != expected_o:
        raise ValueError("historical ordinary controls changed")
    comparison = [(item.get("case"), item.get("condition"), item.get("repeat"))
                  for item in config.get("comparison_order", ())]
    if len(comparison) != len(set(comparison)) or set(comparison) != expected_new | expected_o:
        raise ValueError("comparison_order must contain the frozen nine records")


def load_historical_controls(config: dict) -> list[dict]:
    records = []
    for item in config["historical_ordinary"]:
        path = ROOT / item["path"]
        if not path.is_file() or digest(path) != item["sha256"]:
            raise ValueError(f"frozen R11 ordinary result changed: {item['path']}")
        record = json.loads(path.read_text(encoding="utf-8"))
        identity = (record.get("case"), record.get("condition"), record.get("repeat"))
        expected = (item["case"], item["condition"], item["repeat"])
        if identity != expected:
            raise ValueError(f"frozen R11 ordinary identity changed: {item['path']}")
        records.append({**record, "comparison_source": "reused_frozen_r11"})
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--repaired-checkpoint", type=Path, required=True)
    parser.add_argument("--synthetic-checkpoint", type=Path, required=True)
    parser.add_argument("--profile-file", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--model-contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Use a fresh output directory: {args.output}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    validate_config(config)
    historical = load_historical_controls(config)

    checkpoints = {
        "repaired": load_root_checkpoint(args.repaired_checkpoint),
        "synthetic": load_root_checkpoint(args.synthetic_checkpoint),
    }
    provider = load_profile(args.profile, args.profile_file)
    contract = validate_direct_profile_contract(
        load_contract(args.model_contract), args.profile, provider)
    for label, checkpoint in checkpoints.items():
        if checkpoint["identity"].get("config_name") != args.profile:
            raise ValueError(f"{label} checkpoint profile mismatch")
        MonitorProviderClient(
            f"discriminating_screen_restore::{label}", dict(provider)
        ).restore_request_snapshot(restored_request(checkpoint["root"]))

    with tempfile.TemporaryDirectory(prefix="discriminating-screen-preflight-") as temp:
        prepared, requests = {}, {}
        for case, definition in config["cases"].items():
            checkpoint = checkpoints[definition["checkpoint"]]
            local = {"cases": {case: {"initial_paths": definition["initial_paths"]}}}
            prepared[case] = prepare_case(case, local, checkpoint, Path(temp) / case)
            requests[case] = restored_request(checkpoint["root"])
        index = prepared["r7_root_completion"][0]
        original = (checkpoints["repaired"]["root"] / "task/original_task.txt").read_text(
            encoding="utf-8")
        specs = {mode: selector_spec(
            mode=mode, parent_system=requests["r7_root_completion"]["system"],
            original_task=original, decision_scope="root_completion", index=index,
            remaining_calls=6) for mode in MODES}
        if specs[MODES[0]]["tools"] != specs[MODES[1]]["tools"]:
            raise ValueError("G/E selector tools differ")
        if specs[MODES[0]]["prompt"] != specs[MODES[1]]["prompt"]:
            raise ValueError("G/E selector material views differ")
        preflight = {
            "status": "passed", "protocol": PROTOCOL_ID,
            "candidate_protocol": CANDIDATE_PROTOCOL, "provider_requests_sent": 0,
            "profile": args.profile, "resolved_model": contract["runtime"],
            "ordinary_policy": "reuse three hash-frozen R11 O records",
            "shared": {
                "total_call_limit": 6, "ordinary_allocation": "6",
                "selected_allocation": "1+5", "complete_parent_history": True,
                "same_selector_material_view": True, "selector_tools_identical": True,
                "nested_tools": ["file_read", "file_list", "text_search"],
                "research_metadata_hidden_from_parent": True,
                "independent_c": False, "coverage_frontier_f": False,
                "code_execution": False,
            },
            "frozen_new_run_order": config["new_run_order"],
            "frozen_comparison_order": config["comparison_order"],
        }
    if args.dry_run:
        print(json.dumps(preflight, ensure_ascii=False, indent=2))
        return

    args.output.mkdir(parents=True)
    (args.output / "preflight.json").write_text(
        json.dumps(preflight, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "resolved_model_config.json").write_text(json.dumps({
        "profile": args.profile, "source": contract["source"],
        "resolved": contract["runtime"], "fallback_allowed": False,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "historical_controls.json").write_text(json.dumps({
        "policy": "selected before G/E results", "items": historical,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    prepared, requests = {}, {}
    for case, definition in config["cases"].items():
        checkpoint = checkpoints[definition["checkpoint"]]
        local = {"cases": {case: {"initial_paths": definition["initial_paths"]}}}
        prepared[case] = prepare_case(
            case, local, checkpoint, args.output / "materials" / case)
        requests[case] = restored_request(checkpoint["root"])

    results = []
    for sequence, item in enumerate(config["new_run_order"], start=1):
        case, condition, repeat = item["case"], item["condition"], item["repeat"]
        index, workspace, branches, _, initial = prepared[case]
        request = requests[case]
        record_name = f"{sequence:02d}-{case}-{condition}-r{repeat}"
        record_root = args.output / "records" / record_name
        record_root.mkdir(parents=True)
        audit_path = record_root / "audit.jsonl"
        transport_path = record_root / "transport.jsonl"

        def audit(event, **fields):
            append_json(audit_path, {
                "event": event, "record": record_name,
                "recorded_at": datetime.now(timezone.utc).isoformat(), **fields,
            })

        def attach_transport(client, role):
            def transport(event, **fields):
                allowed = {"request_id", "attempt", "started_at", "duration_seconds",
                           "purpose", "transaction_id", "outcome", "error_type",
                           "error_chain", "retry_delay_seconds", "status_code", "lines",
                           "bytes_or_characters", "seconds", "next_batch", "reason",
                           "source", "usage", "provider_message_id", "metadata"}
                append_json(transport_path, {
                    "event": "transport_" + event, "record": record_name, "role": role,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    **{key: value for key, value in fields.items() if key in allowed},
                })
            client.progress_callback = transport

        selector = MonitorProviderClient(
            f"discriminating_screen::{record_name}::selector", dict(provider))
        parent = MonitorProviderClient(
            f"discriminating_screen::{record_name}::parent", dict(provider))
        attach_transport(selector, "selector")
        attach_transport(parent, "parent")
        try:
            original_task = (checkpoints[config["cases"][case]["checkpoint"]]["root"] /
                             "task/original_task.txt").read_text(encoding="utf-8")
            expected_scope, question = case_question(case)
            result = run_candidate(
                mode=condition, research_condition=condition,
                selector_client=selector, parent_client=parent,
                branch_identity=branch_identity(case, repeat, condition),
                seed_workspace=workspace, branch_private_root=branches, index=index,
                initial_paths=initial, parent_history=request["messages"],
                parent_system=request["system"], original_task=original_task,
                decision_scope=expected_scope, acceptance_question=question,
                total_calls=6, audit=audit)
        except Exception as exc:
            result = {"protocol": PROTOCOL_ID, "condition": condition, "status": "error",
                      "error_type": type(exc).__name__, "error": str(exc)}
            append_json(audit_path, {"event": "record_exception",
                                     "error_type": type(exc).__name__, "error": str(exc)})
        result["screen_protocol"] = PROTOCOL_ID
        record = {
            "sequence": sequence, "case": case, "condition": condition, "repeat": repeat,
            "result": result, "usage": combined_usage(selector, parent),
            "audit_log": f"records/{record_name}/audit.jsonl",
            "transport_log": f"records/{record_name}/transport.jsonl",
        }
        (record_root / "result.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8")
        results.append(record)
        (args.output / "results.json").write_text(json.dumps({
            "protocol": PROTOCOL_ID,
            "historical_ordinary": historical,
            "new_items": results,
        }, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        print(f"{sequence:02d}/6 {case}/{condition}/r{repeat}: "
              f"{result.get('status')}", flush=True)


if __name__ == "__main__":
    main()
