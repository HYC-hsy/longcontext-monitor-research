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
    condition_spec, run_scope_prompt_condition, visible_supplement,
)


LEGACY_EVIDENCE_VISIBILITY_PROTOCOL = "visible-counterexample-consumption-v1"
EVIDENCE_VISIBILITY_PROTOCOL = "visible-counterexample-consumption-neutral-v2"


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


def _frozen_excerpt(checkpoint: dict, path: str, start: int, count: int) -> dict:
    normalized = path.replace("\\", "/")
    expected = checkpoint["manifest"]["files"].get(normalized)
    if not expected:
        raise ValueError(f"supplement source is not manifest-listed: {normalized}")
    source = checkpoint["root"] / normalized
    actual = hashlib.sha256(source.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f"supplement source hash mismatch: {normalized}")
    lines = source.read_text(encoding="utf-8").splitlines()
    if start < 1 or count < 1 or start > len(lines):
        raise ValueError(f"invalid supplement range: {normalized}:{start}+{count}")
    selected = lines[start - 1:start - 1 + count]
    return {
        "path": normalized, "file_sha256": actual, "start": start,
        "lines": len(selected), "total_lines": len(lines),
        "content": "\n".join(f"{start + index}: {line}" for index, line in enumerate(selected)),
    }


def _supplement(checkpoint: dict, material: str) -> dict:
    if material == "r7_local_support_visible":
        excerpts = [
            _frozen_excerpt(checkpoint, "task/original_task.txt", 145, 1),
            _frozen_excerpt(checkpoint, "task/workspace/data/validation/all.go", 1, 18),
            _frozen_excerpt(checkpoint, "task/research_derived_local_repair.json", 18, 11),
        ]
    elif material == "r7_json_counterexample_visible":
        excerpts = [
            _frozen_excerpt(checkpoint, "task/original_task.txt", 52, 9),
            _frozen_excerpt(checkpoint, "task/workspace/theme/json.go", 69, 14),
        ]
    elif material == "synthetic_complete_evidence_visible":
        excerpts = [
            _frozen_excerpt(checkpoint, "task/original_task.txt", 1, 10),
            _frozen_excerpt(checkpoint, "task/workspace/counter.go", 1, 17),
            _frozen_excerpt(checkpoint, "task/workspace/counter_test.go", 1, 27),
            _frozen_excerpt(checkpoint, "task/public_check.json", 1, 20),
        ]
    else:
        raise ValueError(f"unknown evidence-visibility material: {material}")
    return {
        "research_record": {
            "material_condition": material,
            "presentation": "research-side preselected frozen observations at current diagnostic turn",
            "source_mapping": [item["path"] for item in excerpts],
        },
        "model_visible": visible_supplement(excerpts),
    }


def _run_evidence_visibility(args, config: dict) -> None:
    materials = config.get("materials") or {}
    order = config.get("run_order") or []
    expected_materials = {
        "r7_local_support_visible", "r7_json_counterexample_visible",
        "synthetic_complete_evidence_visible",
    }
    if set(materials) != expected_materials:
        raise ValueError("evidence visibility materials changed")
    expected_runs = {(material, repeat) for material in expected_materials for repeat in (1, 2)}
    actual_runs = {(item.get("material"), item.get("repeat")) for item in order}
    if len(order) != 6 or actual_runs != expected_runs:
        raise ValueError("run_order must contain each material/repeat exactly once")

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
        MonitorProviderClient(f"visible_evidence_restore::{label}", dict(provider)).restore_request_snapshot(
            restored_request(checkpoint["root"]))

    prepared, requests, supplements = {}, {}, {}
    temp_context = tempfile.TemporaryDirectory(prefix="visible-evidence-preflight-")
    try:
        for material, item in materials.items():
            checkpoint = checkpoints[item["checkpoint"]]
            base_case = item["base_case"]
            local_config = {"cases": {base_case: {"initial_paths": item["initial_paths"]}}}
            prepared[material] = prepare_case(
                base_case, local_config, checkpoint, Path(temp_context.name) / material)
            requests[material] = restored_request(checkpoint["root"])
            supplements[material] = _supplement(checkpoint, material)
        first = requests["r7_local_support_visible"]
        second = requests["r7_json_counterexample_visible"]
        if _sha(first) != _sha(second):
            raise ValueError("the two R7 materials do not share the same parent request")
        first_item, second_item = (materials["r7_local_support_visible"],
                                   materials["r7_json_counterexample_visible"])
        if first_item["initial_paths"] != second_item["initial_paths"]:
            raise ValueError("the two R7 materials do not share the same initial evidence access")
        preflight = {
            "status": "passed", "protocol": EVIDENCE_VISIBILITY_PROTOCOL,
            "provider_requests_sent": 0,
            "profile": args.profile, "resolved_model": contract["runtime"],
            "shared": {
                "condition": "ordinary_investigation",
                "finish_tool": "finish_parent_decision", "logical_call_limit": 6,
                "r7_parent_request_sha256": _sha(first),
                "r7_parent_state_and_workspace_identical": True,
                "neutral_instruction_identical": True,
                "query_capability_unchanged": True,
            },
            "materials": supplements, "frozen_run_order": order,
            "derivation": derivation,
        }
        if args.dry_run:
            print(json.dumps(preflight, ensure_ascii=False, indent=2))
            return
    finally:
        temp_context.cleanup()

    args.output.mkdir(parents=True)
    (args.output / "preflight.json").write_text(
        json.dumps(preflight, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "supplement_sources.json").write_text(json.dumps({
        "protocol": EVIDENCE_VISIBILITY_PROTOCOL, "materials": supplements,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "resolved_model_config.json").write_text(json.dumps({
        "profile": args.profile, "source": contract["source"],
        "resolved": contract["runtime"], "fallback_allowed": False,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    prepared, requests = {}, {}
    for material, item in materials.items():
        checkpoint = checkpoints[item["checkpoint"]]
        base_case = item["base_case"]
        local_config = {"cases": {base_case: {"initial_paths": item["initial_paths"]}}}
        prepared[material] = prepare_case(
            base_case, local_config, checkpoint, args.output / "materials" / material)
        requests[material] = restored_request(checkpoint["root"])

    results = []
    for sequence, item in enumerate(order, start=1):
        material, repeat = item["material"], item["repeat"]
        definition = materials[material]
        base_case = definition["base_case"]
        index, workspace, branches, _, initial = prepared[material]
        request = requests[material]
        record_name = f"{sequence:02d}-{material}-r{repeat}"
        record_root = args.output / "records" / record_name
        record_root.mkdir(parents=True)
        audit_path, transport_path = record_root / "audit.jsonl", record_root / "transport.jsonl"
        client = MonitorProviderClient(f"visible_evidence::{record_name}", dict(provider))

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
                case=base_case, condition="ordinary_investigation",
                run_key=f"{material}-repeat-{repeat}", parent_client=client,
                seed_workspace=workspace, branch_private_root=branches, index=index,
                initial_paths=initial, parent_history=request["messages"],
                parent_system=request["system"], total_calls=6,
                supplemental_observation=supplements[material]["model_visible"], audit=audit)
        except Exception as exc:
            result = {"case": base_case, "condition": "ordinary_investigation",
                      "material": material, "repeat": repeat,
                      "protocol": EVIDENCE_VISIBILITY_PROTOCOL, "status": "error",
                      "error_type": type(exc).__name__, "error": str(exc)}
            append_json(audit_path, {"event": "record_exception",
                                     "error_type": type(exc).__name__, "error": str(exc)})
        result["material_condition"] = material
        result["protocol"] = EVIDENCE_VISIBILITY_PROTOCOL
        record = {"sequence": sequence, "repeat": repeat, "material": material,
                  "result": result, "usage": usage(client),
                  "audit_log": f"records/{record_name}/audit.jsonl",
                  "transport_log": f"records/{record_name}/transport.jsonl"}
        (record_root / "result.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8")
        results.append(record)
        (args.output / "results.json").write_text(json.dumps({
            "protocol": EVIDENCE_VISIBILITY_PROTOCOL, "items": results,
        }, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        print(f"{sequence:02d}/6 {material}/r{repeat}: {result.get('status')}", flush=True)


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
    protocol = config.get("protocol", {}).get("id")
    if protocol == LEGACY_EVIDENCE_VISIBILITY_PROTOCOL:
        raise ValueError(
            "R10 V1 is frozen because research condition metadata was model-visible; "
            "use the neutral-v2 calibration manifest instead")
    if protocol == EVIDENCE_VISIBILITY_PROTOCOL:
        _run_evidence_visibility(args, config)
        return
    if protocol != PROTOCOL_ID:
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
