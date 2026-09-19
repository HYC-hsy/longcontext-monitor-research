"""Run the fixed local-recovery versus root-completion scope diagnostic."""

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
from monitor_agent_core.provider import MonitorProviderClient  # noqa: E402
from monitor_agent_core.workspace import MonitorWorkspace  # noqa: E402

from decision_question_diagnostic import materialize_live_parent_state  # noqa: E402
from direct_evidence_diagnostic import FrozenEvidenceIndex  # noqa: E402
from run_direct_evidence_diagnostic import validate_direct_profile_contract  # noqa: E402
from monitor_agent_core.experiment_contract import load_contract  # noqa: E402
from recovery_scope_diagnostic import (  # noqa: E402
    CONDITIONS, PROTOCOL_ID, REPAIR_FILES, UPDATE_PATH, run_recovery_condition,
)


def append_json(path: Path, item: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
        stream.flush()


def file_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def validate_derivation(source: dict, derived: dict) -> dict:
    source_version = source["complete"]["manifest_sha256"]
    if derived["identity"].get("derived_from_manifest_sha256") != source_version:
        raise ValueError("derived checkpoint does not name the supplied source checkpoint")
    update_path = derived["root"] / UPDATE_PATH
    if not update_path.is_file():
        raise ValueError("derived checkpoint has no explicit local-repair update")
    update = json.loads(update_path.read_text(encoding="utf-8"))
    if update.get("nature") != "researcher_constructed_post_checkpoint_update":
        raise ValueError("derived material is not explicitly marked as research-constructed")
    source_files = file_hashes(source["root"] / "task" / "workspace")
    derived_files = file_hashes(derived["root"] / "task" / "workspace")
    changed = sorted(
        "task/workspace/" + path for path in set(source_files) | set(derived_files)
        if source_files.get(path) != derived_files.get(path)
    )
    if changed != sorted(REPAIR_FILES):
        raise ValueError(f"derived workspace differs outside declared local repair: {changed}")
    if [item.get("path") for item in update.get("changed_task_files", ())] != changed:
        raise ValueError("derived update does not exactly describe the workspace diff")
    check = update.get("limited_check", {})
    if check.get("exit_code") != 0 or not check.get("does_not_support"):
        raise ValueError("derived update has no bounded successful local check")
    return {
        "source_version": source_version,
        "derived_version": derived["complete"]["manifest_sha256"],
        "changed_task_files": changed,
        "update_sha256": hashlib.sha256(update_path.read_bytes()).hexdigest(),
        "limited_check": check,
    }


def prepare(config: dict, derived: dict, root: Path):
    root.mkdir(parents=True, exist_ok=True)
    index = FrozenEvidenceIndex(derived)
    seed, state_paths = materialize_live_parent_state(derived, root / "parent_state_seed")
    branches = root / "parent_branches"
    branches.mkdir()
    workspace = MonitorWorkspace(derived["root"] / "task", seed)
    for path in tuple(config["initial_paths"]):
        normalized = str(path).replace("\\", "/")
        if normalized not in derived["manifest"]["files"]:
            raise ValueError(f"initial evidence is not derived-manifest-listed: {path}")
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
    parser.add_argument("--source-checkpoint", type=Path, required=True)
    parser.add_argument("--derived-checkpoint", type=Path, required=True)
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
        raise ValueError("wrong recovery-scope protocol identity")
    if tuple(config.get("conditions", ())) != CONDITIONS:
        raise ValueError(f"conditions must be exactly {CONDITIONS}")
    if int(config.get("total_calls", 0)) != 6:
        raise ValueError("recovery-scope diagnostic budget must remain six calls")
    source = load_root_checkpoint(args.source_checkpoint)
    derived = load_root_checkpoint(args.derived_checkpoint)
    derivation = validate_derivation(source, derived)
    exact_request = restored_request(args.derived_checkpoint)
    if exact_request != restored_request(args.source_checkpoint):
        raise ValueError("derived checkpoint changed the captured parent request")

    if args.dry_run:
        with tempfile.TemporaryDirectory(prefix="recovery-scope-preflight-") as temp:
            index, workspace, branches, state_paths = prepare(config, derived, Path(temp))
            descriptor = index.descriptor()
        print(json.dumps({
            "status": "passed", "provider_created": False,
            "protocol": PROTOCOL_ID, "conditions": list(CONDITIONS),
            "derivation": derivation, "query_scope": descriptor,
            "parent_state_paths": list(state_paths),
        }, ensure_ascii=False, indent=2))
        return

    args.output.mkdir(parents=True)
    index, workspace, branches, state_paths = prepare(config, derived, args.output)
    provider = load_profile(args.profile, args.profile_file)
    contract_resolution = validate_direct_profile_contract(
        load_contract(args.model_contract), args.profile, provider)
    if derived["identity"].get("config_name") != args.profile:
        raise ValueError("derived checkpoint supervisor profile does not match requested profile")
    MonitorProviderClient("recovery_scope_restore_validation", dict(provider)).restore_request_snapshot(
        exact_request)
    (args.output / "preflight.json").write_text(json.dumps({
        "status": "passed", "protocol": PROTOCOL_ID,
        "source_checkpoint": source["identity"].get("checkpoint_id", args.source_checkpoint.name),
        "derived_checkpoint": derived["identity"].get("checkpoint_id", args.derived_checkpoint.name),
        "request_sha256": hashlib.sha256(json.dumps(
            exact_request, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode("utf-8")).hexdigest(),
        "conditions": list(CONDITIONS), "derivation": derivation,
        "query_scope": index.descriptor(), "parent_state_paths": list(state_paths),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "resolved_model_config.json").write_text(json.dumps({
        "profile": args.profile, "source": contract_resolution["source"],
        "resolved": contract_resolution["runtime"], "fallback_allowed": False,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    results = []
    for condition in CONDITIONS:
        condition_root = args.output / condition
        condition_root.mkdir()
        audit_path = condition_root / "audit.jsonl"
        transport_path = condition_root / "transport.jsonl"
        client = MonitorProviderClient(f"recovery_scope::{condition}", dict(provider))

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
            result = run_recovery_condition(
                condition=condition, parent_client=client, seed_workspace=workspace,
                branch_private_root=branches, index=index,
                initial_paths=tuple(config["initial_paths"]),
                parent_history=exact_request["messages"],
                parent_system=exact_request["system"],
                total_calls=6, audit=audit,
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
        (args.output / "results.json").write_text(json.dumps({
            "protocol": PROTOCOL_ID, "items": results,
        }, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        print(f"{condition}: {result.get('status')}", flush=True)


if __name__ == "__main__":
    main()
