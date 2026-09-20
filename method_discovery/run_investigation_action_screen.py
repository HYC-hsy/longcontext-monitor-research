"""Run the frozen nine-record O/A/B investigation-action screen."""

from __future__ import annotations

import argparse
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

from investigation_action_candidates import (  # noqa: E402
    CANDIDATES, PROTOCOL_ID as CANDIDATE_PROTOCOL, run_investigation_candidate,
    selector_spec,
)
from run_direct_evidence_diagnostic import validate_direct_profile_contract  # noqa: E402
from run_scoped_decision_diagnostic import prepare_case, usage  # noqa: E402
from scope_prompt_replication import run_scope_prompt_condition  # noqa: E402
from scoped_decision_diagnostic import case_question  # noqa: E402


PROTOCOL_ID = "investigation-action-screen-v1"
CONDITIONS = ("ordinary",) + CANDIDATES


def append_json(path: Path, item: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
        stream.flush()


def combined_usage(*clients) -> dict:
    values = [usage(client) for client in clients]
    keys = {key for value in values for key in value}
    return {key: sum(int(value.get(key) or 0) for value in values) for key in keys}


def validate_config(config: dict) -> None:
    if config.get("protocol", {}).get("id") != PROTOCOL_ID:
        raise ValueError("wrong investigation-action screen protocol")
    if tuple(config.get("conditions", ())) != CONDITIONS:
        raise ValueError("condition set or order changed")
    order = config.get("run_order") or []
    expected = {
        ("r7_root_completion", condition, repeat)
        for condition in CONDITIONS for repeat in (1, 2)
    } | {("synthetic_root_complete", condition, 1) for condition in CONDITIONS}
    actual = {(item.get("case"), item.get("condition"), item.get("repeat")) for item in order}
    if len(order) != 9 or actual != expected:
        raise ValueError("run_order must contain the frozen nine unique records")
    protocol = config["protocol"]
    if (protocol.get("total_calls_per_record"), protocol.get("ordinary_calls"),
            protocol.get("selector_calls"), protocol.get("selected_parent_calls")) != (6, 6, 1, 5):
        raise ValueError("the frozen 6 versus 1+5 budget changed")


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
        MonitorProviderClient(f"action_screen_restore::{label}", dict(provider)).restore_request_snapshot(
            restored_request(checkpoint["root"]))

    with tempfile.TemporaryDirectory(prefix="action-screen-preflight-") as temp:
        prepared, requests = {}, {}
        for case, definition in config["cases"].items():
            checkpoint = checkpoints[definition["checkpoint"]]
            local = {"cases": {case: {"initial_paths": definition["initial_paths"]}}}
            prepared[case] = prepare_case(case, local, checkpoint, Path(temp) / case)
            requests[case] = restored_request(checkpoint["root"])
        r7_index = prepared["r7_root_completion"][0]
        original_task = (checkpoints["repaired"]["root"] / "task/original_task.txt").read_text(
            encoding="utf-8")
        selector_tools = {}
        for candidate in CANDIDATES:
            spec = selector_spec(
                candidate=candidate,
                parent_system=requests["r7_root_completion"]["system"],
                original_task=original_task, decision_scope="root_completion",
                index=r7_index, remaining_calls=6)
            selector_tools[candidate] = spec["tools"]
        if selector_tools[CANDIDATES[0]] != selector_tools[CANDIDATES[1]]:
            raise ValueError("A/B selector tools differ")
        preflight = {
            "status": "passed", "protocol": PROTOCOL_ID, "provider_requests_sent": 0,
            "profile": args.profile, "resolved_model": contract["runtime"],
            "shared": {
                "total_call_limit": 6, "ordinary_allocation": "6",
                "selected_allocation": "1+5", "same_parent_state_per_case": True,
                "same_parent_tools_after_selection": True, "selector_tools_identical": True,
                "candidate_observation_metadata_hidden_from_parent": True,
                "independent_c": False,
            },
            "conditions": {
                "ordinary": "original parent investigates directly",
                "full_parent_action": "one action selected with complete parent History",
                "requirement_side_action": "one action selected without completion summaries",
            },
            "frozen_run_order": config["run_order"],
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

    prepared, requests = {}, {}
    for case, definition in config["cases"].items():
        checkpoint = checkpoints[definition["checkpoint"]]
        local = {"cases": {case: {"initial_paths": definition["initial_paths"]}}}
        prepared[case] = prepare_case(
            case, local, checkpoint, args.output / "materials" / case)
        requests[case] = restored_request(checkpoint["root"])

    results = []
    for sequence, item in enumerate(config["run_order"], start=1):
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

        parent = MonitorProviderClient(f"action_screen::{record_name}::parent", dict(provider))
        attach_transport(parent, "parent")
        try:
            if condition == "ordinary":
                result = run_scope_prompt_condition(
                    case=case, condition="ordinary_investigation",
                    run_key=f"ordinary-r{repeat}", parent_client=parent,
                    seed_workspace=workspace, branch_private_root=branches, index=index,
                    initial_paths=initial, parent_history=request["messages"],
                    parent_system=request["system"], total_calls=6, audit=audit)
                clients = (parent,)
            else:
                selector = MonitorProviderClient(
                    f"action_screen::{record_name}::selector", dict(provider))
                attach_transport(selector, "selector")
                original_task = (checkpoints[config["cases"][case]["checkpoint"]]["root"] /
                                 "task/original_task.txt").read_text(encoding="utf-8")
                expected_scope, question = case_question(case)
                result = run_investigation_candidate(
                    candidate=condition, selector_client=selector, parent_client=parent,
                    seed_workspace=workspace, branch_private_root=branches, index=index,
                    initial_paths=initial, parent_history=request["messages"],
                    parent_system=request["system"], original_task=original_task,
                    decision_scope=expected_scope, acceptance_question=question,
                    total_calls=6, audit=audit)
                clients = (selector, parent)
        except Exception as exc:
            result = {"protocol": PROTOCOL_ID, "condition": condition, "status": "error",
                      "error_type": type(exc).__name__, "error": str(exc)}
            clients = (parent,)
            append_json(audit_path, {"event": "record_exception",
                                     "error_type": type(exc).__name__, "error": str(exc)})
        result["screen_protocol"] = PROTOCOL_ID
        record = {
            "sequence": sequence, "case": case, "condition": condition, "repeat": repeat,
            "result": result, "usage": combined_usage(*clients),
            "audit_log": f"records/{record_name}/audit.jsonl",
            "transport_log": f"records/{record_name}/transport.jsonl",
        }
        (record_root / "result.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8")
        results.append(record)
        (args.output / "results.json").write_text(json.dumps({
            "protocol": PROTOCOL_ID, "items": results,
        }, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        print(f"{sequence:02d}/9 {case}/{condition}/r{repeat}: {result.get('status')}", flush=True)


if __name__ == "__main__":
    main()
