"""Run six frozen records for the matched scoped-decision interface diagnostic."""

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
from monitor_agent_core.workspace import MonitorWorkspace  # noqa: E402

from decision_question_diagnostic import materialize_live_parent_state  # noqa: E402
from direct_evidence_diagnostic import FrozenEvidenceIndex  # noqa: E402
from recovery_scope_diagnostic import UPDATE_PATH  # noqa: E402
from run_direct_evidence_diagnostic import validate_direct_profile_contract  # noqa: E402
from run_recovery_scope_diagnostic import validate_derivation  # noqa: E402
from scoped_decision_diagnostic import (  # noqa: E402
    CASES, CONDITIONS, PROTOCOL_ID, run_scoped_decision_condition,
)


def append_json(path: Path, item: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
        stream.flush()


def usage(client: MonitorProviderClient) -> dict:
    records = client.usage_records
    return {
        "complete_calls": int(getattr(client, "complete_calls", len(records))),
        "successful_responses": len(records),
        "request_attempts": len(client.request_attempts),
        "input_tokens": sum(int(item.get("input_tokens") or 0) for item in records),
        "output_tokens": sum(int(item.get("output_tokens") or 0) for item in records),
        "total_tokens": sum(sum(int(item.get(key) or 0) for key in (
            "input_tokens", "output_tokens", "cache_creation_input_tokens",
            "cache_read_input_tokens")) for item in records),
        "history_transforms": list(getattr(client, "history_transforms", ())),
    }


def prepare_case(case: str, config: dict, checkpoint: dict, root: Path):
    root.mkdir(parents=True, exist_ok=True)
    index = FrozenEvidenceIndex(checkpoint)
    seed, state_paths = materialize_live_parent_state(checkpoint, root / "parent_state_seed")
    branches = root / "parent_branches"
    branches.mkdir()
    workspace = MonitorWorkspace(checkpoint["root"] / "task", seed)
    initial_paths = tuple(config["cases"][case]["initial_paths"])
    for path in initial_paths:
        if path not in checkpoint["manifest"]["files"]:
            raise ValueError(f"{case}: initial evidence is not manifest-listed: {path}")
        workspace.resolve_read(path)
    for path in state_paths:
        workspace.resolve_read(path)
    return index, workspace, branches, state_paths, initial_paths


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
        raise ValueError("wrong scoped-decision protocol identity")
    if tuple(config.get("conditions", ())) != CONDITIONS:
        raise ValueError(f"conditions must be exactly {CONDITIONS}")
    if tuple(config.get("cases", {}).keys()) != CASES:
        raise ValueError(f"cases must be exactly {CASES}")
    source = load_root_checkpoint(args.source_checkpoint)
    repaired = load_root_checkpoint(args.repaired_checkpoint)
    synthetic = load_root_checkpoint(args.synthetic_checkpoint)
    derivation = validate_derivation(source, repaired)
    if synthetic["identity"].get("source") != "research_synthetic_complete_control":
        raise ValueError("synthetic checkpoint identity is invalid")
    checkpoints = {"repaired": repaired, "synthetic": synthetic}

    if args.dry_run:
        prepared = {}
        with tempfile.TemporaryDirectory(prefix="scoped-decision-preflight-") as temp:
            for case in CASES:
                checkpoint = checkpoints[config["cases"][case]["checkpoint"]]
                index, workspace, branches, state_paths, initial = prepare_case(
                    case, config, checkpoint, Path(temp) / case)
                prepared[case] = {
                    "checkpoint_version": checkpoint["complete"]["manifest_sha256"],
                    "query_scope": index.descriptor(),
                    "parent_state_paths": sorted(state_paths),
                    "initial_paths": list(initial),
                    "request_sha256": hashlib.sha256(json.dumps(
                        restored_request(checkpoint["root"]), ensure_ascii=False,
                        sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
                }
        print(json.dumps({
            "status": "passed", "provider_created": False,
            "protocol": PROTOCOL_ID, "conditions": list(CONDITIONS),
            "cases": prepared, "repaired_derivation": derivation,
        }, ensure_ascii=False, indent=2))
        return

    args.output.mkdir(parents=True)
    provider = load_profile(args.profile, args.profile_file)
    contract_resolution = validate_direct_profile_contract(
        load_contract(args.model_contract), args.profile, provider)
    for label, checkpoint in checkpoints.items():
        if checkpoint["identity"].get("config_name") != args.profile:
            raise ValueError(f"{label} checkpoint profile does not match requested profile")
        MonitorProviderClient(f"scoped_restore::{label}", dict(provider)).restore_request_snapshot(
            restored_request(checkpoint["root"]))
    (args.output / "resolved_model_config.json").write_text(json.dumps({
        "profile": args.profile, "source": contract_resolution["source"],
        "resolved": contract_resolution["runtime"], "fallback_allowed": False,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    prepared = {}
    prepared_objects = {}
    for case in CASES:
        checkpoint = checkpoints[config["cases"][case]["checkpoint"]]
        case_root = args.output / case
        case_root.mkdir()
        index, workspace, branches, state_paths, initial = prepare_case(
            case, config, checkpoint, case_root)
        request = restored_request(checkpoint["root"])
        prepared[case] = {
            "checkpoint_version": checkpoint["complete"]["manifest_sha256"],
            "query_scope": index.descriptor(), "parent_state_paths": sorted(state_paths),
            "initial_paths": list(initial),
            "request_sha256": hashlib.sha256(json.dumps(
                request, ensure_ascii=False, sort_keys=True,
                separators=(",", ":")).encode("utf-8")).hexdigest(),
        }
        prepared_objects[case] = (index, workspace, branches, initial, request)
    (args.output / "preflight.json").write_text(json.dumps({
        "status": "passed", "protocol": PROTOCOL_ID,
        "conditions": list(CONDITIONS), "cases": prepared,
        "repaired_derivation": derivation,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    results = []
    for case in CASES:
        index, workspace, branches, initial, request = prepared_objects[case]
        for condition in CONDITIONS:
            record_root = args.output / case / condition
            record_root.mkdir()
            audit_path = record_root / "audit.jsonl"
            transport_path = record_root / "transport.jsonl"
            client = MonitorProviderClient(f"scoped::{case}::{condition}", dict(provider))

            def transport(event, **fields):
                allowed = {"request_id", "attempt", "started_at", "duration_seconds",
                           "purpose", "transaction_id", "outcome", "error_type",
                           "error_chain", "retry_delay_seconds", "status_code", "lines",
                           "bytes_or_characters", "seconds", "next_batch", "reason",
                           "source", "usage", "provider_message_id", "metadata"}
                append_json(transport_path, {
                    "event": "transport_" + event, "case": case, "condition": condition,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    **{key: value for key, value in fields.items() if key in allowed},
                })
            client.progress_callback = transport

            def audit(event, **fields):
                append_json(audit_path, {
                    "event": event, "case": case, "condition": condition,
                    "recorded_at": datetime.now(timezone.utc).isoformat(), **fields,
                })

            try:
                result = run_scoped_decision_condition(
                    case=case, condition=condition, parent_client=client,
                    seed_workspace=workspace, branch_private_root=branches, index=index,
                    initial_paths=initial, parent_history=request["messages"],
                    parent_system=request["system"], total_calls=6, audit=audit,
                )
            except Exception as exc:
                result = {"case": case, "condition": condition,
                          "protocol": PROTOCOL_ID, "status": "error",
                          "error_type": type(exc).__name__, "error": str(exc)}
                append_json(audit_path, {"event": "record_exception", "case": case,
                                         "condition": condition,
                                         "error_type": type(exc).__name__,
                                         "error": str(exc)})
            record = {"case": case, "condition": condition, "result": result,
                      "usage": usage(client),
                      "audit_log": f"{case}/{condition}/audit.jsonl",
                      "transport_log": f"{case}/{condition}/transport.jsonl"}
            (record_root / "result.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2, default=str) + "\n",
                encoding="utf-8")
            results.append(record)
            (args.output / "results.json").write_text(json.dumps({
                "protocol": PROTOCOL_ID, "items": results,
            }, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
            print(f"{case}/{condition}: {result.get('status')}", flush=True)


if __name__ == "__main__":
    main()
