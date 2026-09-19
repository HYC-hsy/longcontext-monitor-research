"""Run the two-condition direct frozen-evidence diagnostic."""

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
from monitor_agent_core.experiment_contract import (  # noqa: E402
    load_contract, resolved_monitor_config, validate_inherited_child, validate_role,
    validate_source_upstream,
)
from monitor_agent_core.provider import MonitorProviderClient  # noqa: E402
from monitor_agent_core.workspace import MonitorWorkspace  # noqa: E402

from decision_question_diagnostic import materialize_live_parent_state  # noqa: E402
from direct_evidence_diagnostic import (  # noqa: E402
    CONDITIONS, FrozenEvidenceIndex, PROTOCOL_ID, run_direct_condition,
)


def append_json(path: Path, item: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
        stream.flush()


def validate_direct_profile_contract(contract, profile, provider):
    source = resolved_monitor_config(profile, provider)
    validate_source_upstream(contract, "supervisor", source)
    runtime = dict(source, endpoint_host="127.0.0.1")
    validate_role(contract, "supervisor", runtime)
    validate_inherited_child(contract, runtime)
    return {"source": source, "runtime": runtime}


def prepare(config: dict, checkpoint: dict, root: Path):
    root.mkdir(parents=True, exist_ok=True)
    index = FrozenEvidenceIndex(checkpoint)
    seed, state_paths = materialize_live_parent_state(checkpoint, root / "parent_state_seed")
    branches = root / "parent_branches"
    branches.mkdir()
    workspace = MonitorWorkspace(checkpoint["root"] / "task", seed)
    initial_paths = tuple(config["initial_paths"])
    for path in initial_paths:
        normalized = str(path).replace("\\", "/")
        relative = normalized.removeprefix("task/")
        declared_name = "task/" + relative
        if declared_name not in checkpoint["manifest"]["files"]:
            raise ValueError(f"initial evidence is not checkpoint-manifest-listed: {path}")
        workspace.resolve_read(normalized)
    for path in state_paths:
        workspace.resolve_read(path)
    return index, workspace, branches, tuple(sorted(state_paths))


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--live-checkpoint", type=Path, required=True)
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
        raise ValueError("wrong direct-evidence protocol identity")
    conditions = tuple(config.get("conditions", ()))
    if conditions != CONDITIONS:
        raise ValueError(f"conditions must be exactly {CONDITIONS}")
    checkpoint = load_root_checkpoint(args.live_checkpoint)
    exact_request = restored_request(args.live_checkpoint)

    if args.dry_run:
        with tempfile.TemporaryDirectory(prefix="direct-evidence-preflight-") as temp:
            index, workspace, branches, state_paths = prepare(
                config, checkpoint, Path(temp))
            descriptor = index.descriptor()
        print(json.dumps({
            "status": "passed", "provider_created": False,
            "protocol": PROTOCOL_ID, "conditions": conditions,
            "query_scope": descriptor, "parent_state_paths": list(state_paths),
        }, ensure_ascii=False, indent=2))
        return

    args.output.mkdir(parents=True)
    index, workspace, branches, state_paths = prepare(config, checkpoint, args.output)
    provider = load_profile(args.profile, args.profile_file)
    contract_resolution = validate_direct_profile_contract(
        load_contract(args.model_contract), args.profile, provider)
    if checkpoint["identity"].get("config_name") != args.profile:
        raise ValueError("checkpoint supervisor profile does not match requested profile")
    MonitorProviderClient("direct_evidence_restore_validation", dict(provider)).restore_request_snapshot(
        exact_request)
    (args.output / "preflight.json").write_text(json.dumps({
        "status": "passed", "protocol": PROTOCOL_ID,
        "checkpoint": checkpoint["identity"].get("checkpoint_id", args.live_checkpoint.name),
        "request_sha256": hashlib.sha256(json.dumps(
            exact_request, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode("utf-8")).hexdigest(),
        "conditions": list(conditions), "query_scope": index.descriptor(),
        "parent_state_paths": list(state_paths),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "resolved_model_config.json").write_text(json.dumps({
        "profile": args.profile, "source": contract_resolution["source"],
        "resolved": contract_resolution["runtime"], "fallback_allowed": False,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    results = []
    for condition in conditions:
        condition_root = args.output / condition
        condition_root.mkdir()
        audit_path = condition_root / "audit.jsonl"
        transport_path = condition_root / "transport.jsonl"
        client = MonitorProviderClient(
            f"direct_evidence::{condition}", dict(provider))

        def transport(event, **fields):
            allowed = {"request_id", "attempt", "started_at", "duration_seconds",
                       "purpose", "transaction_id", "outcome", "error_type",
                       "error_chain", "retry_delay_seconds", "status_code", "lines",
                       "bytes_or_characters", "seconds", "next_batch", "reason",
                       "source", "usage", "provider_message_id", "metadata"}
            append_json(transport_path, {
                "event": "transport_" + event, "condition": condition,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                **{key: value for key, value in fields.items() if key in allowed},
            })
        client.progress_callback = transport

        def audit(event, **fields):
            append_json(audit_path, {
                "event": event, "condition": condition,
                "recorded_at": datetime.now(timezone.utc).isoformat(), **fields,
            })

        try:
            result = run_direct_condition(
                condition=condition, parent_client=client, seed_workspace=workspace,
                branch_private_root=branches, index=index,
                acceptance_question=config["acceptance_question"],
                initial_paths=tuple(config["initial_paths"]),
                parent_history=exact_request["messages"],
                parent_system=exact_request["system"],
                total_calls=int(config.get("total_calls", 6)), audit=audit,
            )
        except Exception as exc:
            result = {"condition": condition, "protocol": PROTOCOL_ID,
                      "status": "error", "error_type": type(exc).__name__,
                      "error": str(exc)}
            append_json(audit_path, {"event": "condition_exception",
                                     "condition": condition,
                                     "error_type": type(exc).__name__,
                                     "error": str(exc)})
        record = {"condition": condition, "result": result, "usage": usage(client),
                  "audit_log": f"{condition}/audit.jsonl",
                  "transport_log": f"{condition}/transport.jsonl"}
        (condition_root / "result.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8")
        results.append(record)
        (args.output / "results.json").write_text(
            json.dumps({"protocol": PROTOCOL_ID, "items": results},
                       ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8")
        print(f"{condition}: {result.get('status')}", flush=True)


if __name__ == "__main__":
    main()
