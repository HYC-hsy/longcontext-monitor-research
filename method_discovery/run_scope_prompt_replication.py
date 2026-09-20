"""Run the twelve frozen R8 natural-language scope-guidance replications."""

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

from run_direct_evidence_diagnostic import validate_direct_profile_contract  # noqa: E402
from run_recovery_scope_diagnostic import validate_derivation  # noqa: E402
from run_scoped_decision_diagnostic import prepare_case, usage  # noqa: E402
from scope_prompt_replication import (  # noqa: E402
    CASES, CONDITIONS, PROTOCOL_ID, R8_NATURAL_ORGANIZATION, R8_SCOPE_GUIDANCE,
    condition_spec, run_scope_prompt_condition,
)


def append_json(path: Path, item: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
        stream.flush()


def _sha(value) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        default=str).encode("utf-8")).hexdigest()


def _difference_summary(config: dict, prepared: dict, requests: dict,
                        profile: str, resolved: dict) -> dict:
    cases = {}
    for case in CASES:
        index, _, _, _, initial = prepared[case]
        specs = {condition: condition_spec(
            case=case, condition=condition,
            parent_system=requests[case]["system"], initial_paths=initial,
            descriptor=index.descriptor(), total_calls=6)
                 for condition in CONDITIONS}
        ordinary, candidate = (specs["ordinary_investigation"],
                               specs["scope_prompt_candidate"])
        if ordinary["tools"] != candidate["tools"]:
            raise ValueError(f"{case}: tool definitions differ")
        cases[case] = {
            "parent_request_sha256": _sha(requests[case]),
            "checkpoint_version": index.descriptor()["checkpoint_version"],
            "query_scope": index.descriptor(),
            "initial_paths": list(initial),
            "tool_definitions_identical": True,
            "tool_definitions_sha256": _sha(ordinary["tools"]),
            "budget_identical": True,
            "logical_call_limit": 6,
            "ordinary_effective_system_sha256": _sha(ordinary["effective_system"]),
            "candidate_effective_system_sha256": _sha(candidate["effective_system"]),
            "ordinary_prompt_sha256": _sha(ordinary["prompt"]),
            "candidate_prompt_sha256": _sha(candidate["prompt"]),
        }
    return {
        "status": "passed",
        "protocol": PROTOCOL_ID,
        "profile": profile,
        "resolved_model": resolved,
        "shared": {
            "same_parent_history_and_private_state_seed": True,
            "same_evidence_registry_and_receipts": True,
            "same_query_and_read_dispatch": True,
            "same_finish_tool": "finish_parent_decision",
            "same_budget": 6,
        },
        "only_declared_difference": {
            "candidate_system_and_prompt_addition": R8_SCOPE_GUIDANCE,
            "candidate_prompt_organization_addition": R8_NATURAL_ORGANIZATION,
            "ordinary_removes_only_these_r8_additions": True,
        },
        "cases": cases,
        "frozen_run_order": config["run_order"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source-checkpoint", type=Path, required=True)
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
    if config.get("protocol", {}).get("id") != PROTOCOL_ID:
        raise ValueError("wrong replication protocol")
    if tuple(config.get("conditions", ())) != CONDITIONS:
        raise ValueError("condition order changed")
    order = config.get("run_order")
    expected = {(case, condition, repeat) for case in CASES
                for condition in CONDITIONS for repeat in (1, 2)}
    actual = {(item.get("case"), item.get("condition"), item.get("repeat")) for item in order}
    if len(order) != 12 or actual != expected:
        raise ValueError("run_order must contain each case/condition/repeat exactly once")

    source = load_root_checkpoint(args.source_checkpoint)
    repaired = load_root_checkpoint(args.repaired_checkpoint)
    synthetic = load_root_checkpoint(args.synthetic_checkpoint)
    derivation = validate_derivation(source, repaired)
    checkpoints = {"repaired": repaired, "synthetic": synthetic}
    provider = load_profile(args.profile, args.profile_file)
    contract = validate_direct_profile_contract(
        load_contract(args.model_contract), args.profile, provider)
    for label, checkpoint in checkpoints.items():
        if checkpoint["identity"].get("config_name") != args.profile:
            raise ValueError(f"{label} checkpoint profile mismatch")
        MonitorProviderClient(f"scope_replication_restore::{label}", dict(provider)).restore_request_snapshot(
            restored_request(checkpoint["root"]))

    with tempfile.TemporaryDirectory(prefix="scope-prompt-replication-preflight-") as temp:
        prepared = {}
        requests = {}
        for case in CASES:
            checkpoint = checkpoints[config["cases"][case]["checkpoint"]]
            prepared[case] = prepare_case(
                case, config, checkpoint, Path(temp) / case)
            requests[case] = restored_request(checkpoint["root"])
        summary = _difference_summary(
            config, prepared, requests, args.profile, contract["runtime"])
    if args.dry_run:
        print(json.dumps({**summary, "provider_requests_sent": 0}, ensure_ascii=False, indent=2))
        return

    args.output.mkdir(parents=True)
    (args.output / "condition_difference.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "resolved_model_config.json").write_text(json.dumps({
        "profile": args.profile, "source": contract["source"],
        "resolved": contract["runtime"], "fallback_allowed": False,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    prepared = {}
    requests = {}
    for case in CASES:
        checkpoint = checkpoints[config["cases"][case]["checkpoint"]]
        prepared[case] = prepare_case(
            case, config, checkpoint, args.output / "materials" / case)
        requests[case] = restored_request(checkpoint["root"])
    results = []
    for sequence, item in enumerate(order, start=1):
        case, condition, repeat = item["case"], item["condition"], item["repeat"]
        index, workspace, branches, _, initial = prepared[case]
        request = requests[case]
        run_key = f"repeat-{repeat}"
        record_name = f"{sequence:02d}-{case}-{condition}-r{repeat}"
        record_root = args.output / "records" / record_name
        record_root.mkdir(parents=True)
        audit_path, transport_path = record_root / "audit.jsonl", record_root / "transport.jsonl"
        client = MonitorProviderClient(f"scope_replication::{record_name}", dict(provider))

        def transport(event, **fields):
            allowed_fields = {"request_id", "attempt", "started_at", "duration_seconds",
                              "purpose", "transaction_id", "outcome", "error_type",
                              "error_chain", "retry_delay_seconds", "status_code", "lines",
                              "bytes_or_characters", "seconds", "next_batch", "reason",
                              "source", "usage", "provider_message_id", "metadata"}
            append_json(transport_path, {
                "event": "transport_" + event, "record": record_name,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                **{key: value for key, value in fields.items() if key in allowed_fields},
            })
        client.progress_callback = transport

        def audit(event, **fields):
            append_json(audit_path, {
                "event": event, "record": record_name,
                "recorded_at": datetime.now(timezone.utc).isoformat(), **fields,
            })

        try:
            result = run_scope_prompt_condition(
                case=case, condition=condition, run_key=run_key,
                parent_client=client, seed_workspace=workspace,
                branch_private_root=branches, index=index, initial_paths=initial,
                parent_history=request["messages"], parent_system=request["system"],
                total_calls=6, audit=audit)
        except Exception as exc:
            result = {"case": case, "condition": condition, "repeat": repeat,
                      "protocol": PROTOCOL_ID, "status": "error",
                      "error_type": type(exc).__name__, "error": str(exc)}
            append_json(audit_path, {"event": "record_exception",
                                     "error_type": type(exc).__name__, "error": str(exc)})
        record = {"sequence": sequence, "repeat": repeat, "case": case,
                  "condition": condition, "result": result, "usage": usage(client),
                  "audit_log": f"records/{record_name}/audit.jsonl",
                  "transport_log": f"records/{record_name}/transport.jsonl"}
        (record_root / "result.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8")
        results.append(record)
        (args.output / "results.json").write_text(json.dumps({
            "protocol": PROTOCOL_ID, "items": results,
        }, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        print(f"{sequence:02d}/12 {case}/{condition}/r{repeat}: {result.get('status')}", flush=True)

    (args.output / "preflight.json").write_text(json.dumps({
        "status": "passed", "protocol": PROTOCOL_ID,
        "derivation": derivation, "condition_difference": summary,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
