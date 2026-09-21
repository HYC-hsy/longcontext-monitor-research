"""Materialize and run the frozen DCEC-v0 four-record discrimination screen.

Dry-run is network-free. Execution remains locked by the versioned manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
GA_ROOT = ROOT / "GenericAgent-main"
sys.path.insert(0, str(GA_ROOT))
sys.path.insert(0, str(ROOT / "method_discovery"))

from monitor_agent_core.agent import DCEC_SYSTEM_PROMPT  # noqa: E402
from monitor_agent_core.provider import MonitorProviderClient  # noqa: E402
from dcec_record_isolation import (  # noqa: E402
    filesystem_probe as isolated_filesystem_probe,
    prepare_runtime as prepare_isolated_runtime,
    provider_deadline_probe as isolated_provider_deadline_probe,
    request_probe as isolated_request_probe,
    run_record as run_isolated_record,
    watchdog_probe as isolated_watchdog_probe,
)


DEFAULT_MANIFEST = ROOT / "method_discovery/artifacts/dcec_v0_20260921/discriminating_manifest.json"
DEFAULT_PREFLIGHT_OUTPUT = ROOT / "method_discovery/runs/dcec_v0_final_preflight_wall_r1_20260921"
RUNNER_RELATIVE = "method_discovery/run_dcec_v0_discrimination.py"
MODEL_CONTRACT = ROOT / "method_discovery/runs/dual_opus_20260919/dual_opus_model_contract.json"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_jsonl(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, default=str) + "\n")
        stream.flush()


def jsonl_rows(path: Path) -> list[dict]:
    return ([json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            if path.is_file() else [])


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", *args], cwd=ROOT, text=True
    ).strip()


def _checked_inside(root: Path, target: Path) -> Path:
    root, target = root.resolve(), target.resolve()
    target.relative_to(root)
    return target


def reset_directory(root: Path, target: Path) -> Path:
    target = _checked_inside(root, target)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    return target


def file_manifest(root: Path) -> list[dict]:
    records = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        records.append({
            "path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    return records


def tree_sha256(records: list[dict]) -> str:
    encoded = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(encoded)


def model_visible_projection(spec: dict, variant: str) -> dict:
    """Explicit whitelist; never serialize the research specification itself."""
    visible = spec["model_visible"]
    selected = spec["sequence_variants"][variant]
    return {
        "original_task": visible["original_task"],
        "initial_task_agent_message": visible["initial_task_agent_message"],
        "initial_files": dict(selected["initial_files"]),
        "repair_task_agent_message": visible["repair_event"]["task_agent_message"],
        "post_repair_files": dict(selected["post_repair_files"]),
        "root_completion_message": visible["root_completion_message"],
    }


def _public_event(sequence: int, turn: int, boundary: str, text: str) -> dict:
    return {
        "archive_sequence": sequence, "archived_at": float(sequence),
        "task_turn": turn, "boundary": boundary, "text": text, "synopsis": text,
        "tool_calls": [], "tool_results": [],
    }


def append_public_event(evidence: Path, turn: int, boundary: str, text: str) -> dict:
    events = evidence / "public_events.jsonl"
    sequence = len(events.read_text(encoding="utf-8").splitlines()) + 1 if events.exists() else 1
    event = _public_event(sequence, turn, boundary, text)
    append_jsonl(events, event)
    append_jsonl(evidence / "synopsis.jsonl", {
        "cursor": sequence, "task_turn": turn, "boundary": boundary, "intent": text,
        "tool_names": [], "outcome_available": False,
        "raw_event": f"public_events.jsonl#{sequence}",
    })
    return event


def materialize_visible(root: Path, projection: dict) -> dict:
    evidence = root / "task"
    workspace = evidence / "workspace"
    private = root / "monitor"
    for path in (evidence, workspace, private):
        path.mkdir(parents=True, exist_ok=True)
    (evidence / "original_task.txt").write_text(projection["original_task"], encoding="utf-8")
    for relative, content in projection["initial_files"].items():
        path = workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    append_public_event(evidence, 1, "task_agent_message", projection["initial_task_agent_message"])
    # workspace is deliberately nested below task so the container can expose one
    # read-only task mount.  Scanning task already includes workspace exactly once.
    visible = file_manifest(evidence)
    return {
        "evidence_root": str(evidence), "workspace_root": str(workspace),
        "private_root": str(private), "visible_files": visible,
        "visible_tree_sha256": tree_sha256(visible),
        "private_initial_files": file_manifest(private),
    }


def apply_repair(root: Path, projection: dict, intervention: str) -> dict:
    """Any real intervention triggers the frozen transition; semantics are audited later."""
    workspace, evidence = root / "task/workspace", root / "task"
    before = file_manifest(workspace)
    for relative, content in projection["post_repair_files"].items():
        path = workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    event = append_public_event(
        evidence, 2, "task_agent_repair_claim", projection["repair_task_agent_message"])
    return {
        "trigger": "first_intervention_any_semantics", "intervention": intervention,
        "before": before, "after": file_manifest(workspace), "public_event": event,
        "semantic_validity": "not_judged_online",
    }


def resolved_configs(manifest: dict, monitor_config: Path) -> dict:
    contract = load_json(MODEL_CONTRACT)
    task = dict(contract["roles"]["task_agent"]["resolved"])
    profiles = load_json(monitor_config)
    profile_name = manifest["shared_contract"]["supervisor_profile"]
    raw = profiles[profile_name]
    client = MonitorProviderClient(profile_name, raw)
    supervisor = {
        "profile": profile_name, "model": client.model,
        "provider": client.provider, "api_mode": client.api_mode,
        "thinking_type": client.thinking_type, "reasoning_effort": client.reasoning_effort,
        "temperature": client.temperature, "max_tokens": client.max_tokens,
        "context_win": client.context_window, "timeout": client.connect_timeout,
        "read_timeout": client.read_timeout, "max_retries": client.max_retries,
        "transport_route": raw.get("transport_route"), "stream": True,
        "endpoint_host": urlparse(client.api_base).hostname,
    }
    expected = manifest["resolved_models"]
    for role, actual in (("task_agent", task), ("supervisor", supervisor)):
        for field, value in expected[role].items():
            if actual.get(field) != value:
                raise ValueError(
                    f"resolved model mismatch: role={role} field={field} "
                    f"expected={value!r} actual={actual.get(field)!r}")
    return {
        "task_agent": task, "supervisor": supervisor, "model_fallback": False,
        "task_agent_execution": "scripted_frozen_fixture_no_model_call",
    }


def validate_identity(manifest_path: Path, manifest: dict) -> dict:
    if sha256_file(ROOT / RUNNER_RELATIVE) != manifest["runner_sha256"]:
        raise ValueError("runner SHA256 does not match the frozen manifest")
    fixture_path = ROOT / manifest["fixture_spec"]
    if sha256_file(fixture_path) != manifest["fixture_spec_sha256"]:
        raise ValueError("fixture SHA256 does not match the frozen manifest")
    launch_sources = {}
    for relative, expected in manifest["launch_source_sha256"].items():
        actual = sha256_file(ROOT / relative)
        if actual != expected:
            raise ValueError(f"launch source mismatch: {relative}")
        launch_sources[relative] = actual
    implementation = manifest["implementation_commit"]
    subprocess.check_call(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", "merge-base", "--is-ancestor",
         implementation, "HEAD"], cwd=ROOT)
    hashes = {}
    for relative, expected in manifest["mechanism_source_sha256"].items():
        path = ROOT / relative
        actual = sha256_file(path)
        if actual != expected:
            raise ValueError(f"mechanism source mismatch: {relative}")
        baseline = subprocess.check_output(
            ["git", "-c", f"safe.directory={ROOT.as_posix()}", "show",
             f"{implementation}:{relative}"], cwd=ROOT)
        if sha256_bytes(baseline) != actual:
            raise ValueError(f"mechanism source differs from implementation commit: {relative}")
        hashes[relative] = actual
    return {
        "implementation_commit": implementation, "current_git_head": _git("rev-parse", "HEAD"),
        "runner_path": RUNNER_RELATIVE, "runner_sha256": manifest["runner_sha256"],
        "manifest_path": manifest_path.relative_to(ROOT).as_posix(),
        "manifest_sha256": sha256_file(manifest_path),
        "fixture_path": manifest["fixture_spec"], "fixture_sha256": manifest["fixture_spec_sha256"],
        "mechanism_source_sha256": hashes, "launch_source_sha256": launch_sources,
    }


def readable_snapshot(root: Path) -> dict:
    records = []
    for namespace in ("task",):
        base = root / namespace
        for item in file_manifest(base):
            content = (base / item["path"]).read_text(encoding="utf-8", errors="replace")
            records.append({"path": namespace + "/" + item["path"], "content": content,
                            "sha256": item["sha256"]})
    return {"files": records}


def strip_dcec_difference(request: dict) -> dict:
    value = json.loads(json.dumps(request))
    value["system"] = value["system"].replace("\n\n" + DCEC_SYSTEM_PROMPT, "", 1)
    value["messages"] = [message for message in value["messages"] if not any(
        block.get("type") == "text" and "<dcec_working_state>" in str(block.get("text") or "")
        for block in message.get("content") or [])]
    return value


def anti_leakage_audit(manifest: dict, spec: dict, scratch: Path, source: Path) -> dict:
    projection = model_visible_projection(spec, "latent_defect")
    slot = reset_directory(scratch, scratch / "execution-slot")
    materialize_visible(slot, projection)
    first = isolated_request_probe(source, slot, False)
    slot = reset_directory(scratch, scratch / "execution-slot")
    materialize_visible(slot, projection)
    # Research identity is deliberately not passed into either container.
    renamed = isolated_request_probe(source, slot, False)
    rename_equal = first == renamed
    slot = reset_directory(scratch, scratch / "execution-slot")
    materialize_visible(slot, projection)
    treatment = isolated_request_probe(source, slot, True)
    treatment_only = strip_dcec_difference(treatment) == first
    visible = readable_snapshot(slot)
    searchable = json.dumps({"request": treatment, "readable": visible}, ensure_ascii=False).lower()
    forbidden = [
        "research_only", "latent_defect", "correct_control", "expected_scope",
        "bounded_increment exceeds limit when value equals limit",
        manifest["experiment_id"].lower(),
    ]
    hits = [term for term in forbidden if term in searchable]
    if not rename_equal or not treatment_only or hits:
        raise ValueError(
            f"production request anti-leakage failed: rename={rename_equal} "
            f"treatment={treatment_only} hits={hits}")
    return {
        "metadata_rename_model_request_deep_equal": rename_equal,
        "hidden_research_terms_absent": not hits, "forbidden_hits": hits,
        "ordinary_vs_dcec_only_registered_mechanism_difference": treatment_only,
        "ordinary_request_sha256": sha256_bytes(json.dumps(first, sort_keys=True).encode()),
        "dcec_request_sha256": sha256_bytes(json.dumps(treatment, sort_keys=True).encode()),
        "task_readable_files": [{"path": item["path"], "sha256": item["sha256"]}
                                for item in visible["files"]],
        "offline_request_assemblies": 3, "os_isolated_request_assemblies": 3,
        "api_requests_sent": 0,
    }


def preflight(manifest_path: Path, output: Path, monitor_config: Path) -> dict:
    manifest, spec = load_json(manifest_path), load_json(ROOT / load_json(manifest_path)["fixture_spec"])
    if output.exists():
        raise FileExistsError(f"preflight output already exists: {output}")
    output.mkdir(parents=True)
    identity = validate_identity(manifest_path, manifest)
    models = resolved_configs(manifest, monitor_config)
    profiles = load_json(monitor_config)
    isolation = prepare_isolated_runtime(
        output / "isolated_runtime",
        profiles[manifest["shared_contract"]["supervisor_profile"]],
        manifest["historical_candidate_config_keys"],
    )
    records = []
    for run in manifest["runs"]:
        record_id = f"record-{int(run['order']):02d}"
        projection = model_visible_projection(spec, run["sequence"])
        record_root = output / "materialized" / record_id
        materialized = materialize_visible(record_root, projection)
        record = {
            "record_id": record_id, "order": run["order"], "research_sequence": run["sequence"],
            "research_condition": run["condition"], "physical_path_is_opaque": True,
            "projection_sha256": sha256_bytes(json.dumps(
                projection, sort_keys=True, ensure_ascii=False).encode("utf-8")),
            **materialized,
        }
        write_json(output / "records" / record_id / "materialization.json", record)
        records.append(record)
    by_sequence = {}
    for record in records:
        by_sequence.setdefault(record["research_sequence"], []).append(record)
    parity = {}
    for sequence, group in by_sequence.items():
        hashes = {item["visible_tree_sha256"] for item in group}
        parity[sequence] = {"records": [item["record_id"] for item in group],
                            "initial_visible_tree_equal": len(hashes) == 1, "hashes": sorted(hashes)}
        if len(hashes) != 1:
            raise ValueError(f"same-variant initial materialization mismatch: {sequence}")
    with tempfile.TemporaryDirectory(prefix="dcec-preflight-", dir=output) as temporary:
        scratch = Path(temporary)
        anti_leakage = anti_leakage_audit(
            manifest, spec, scratch, output / "isolated_runtime")
        probe_root = scratch / "filesystem-slot"
        materialize_visible(probe_root, model_visible_projection(spec, "latent_defect"))
        filesystem = isolated_filesystem_probe(output / "isolated_runtime", probe_root)
        wall_seconds = manifest["execution_constraints"]["record_wall_seconds"]
        provider_deadline = isolated_provider_deadline_probe(
            output / "isolated_runtime", probe_root, wall_seconds)
        host_watchdog = isolated_watchdog_probe(
            output / "isolated_runtime", probe_root)
    required_filesystem = {
        "forbidden_name_hits": [], "forbidden_content_hits": [], "other_record_paths": [],
        "original_task_readable": True, "workspace_readable": True,
        "monitor_write_succeeded": True, "file_read_original_succeeded": True,
        "file_read_workspace_succeeded": True, "file_write_monitor_succeeded": True,
        "task_workspace_write_blocked": True, "host_repo_candidates_visible": [],
        "docker_socket_visible": False,
    }
    for field, expected in required_filesystem.items():
        if filesystem.get(field) != expected:
            raise ValueError(
                f"code_run filesystem isolation failed: {field} expected={expected!r} "
                f"actual={filesystem.get(field)!r}")
    if (provider_deadline.get("budget_seconds") != wall_seconds
            or not provider_deadline.get("recovery_deadline_configured")
            or not provider_deadline.get("recovery_stop_configured")
            or not 0 < provider_deadline.get("remaining_seconds", 0) <= wall_seconds):
        raise ValueError(f"provider deadline propagation failed: {provider_deadline}")
    if (host_watchdog.get("status") != "timeout"
            or host_watchdog.get("stop_reason") != "record_wall_deadline_exceeded"
            or not host_watchdog.get("deadline_exceeded")):
        raise ValueError(f"host watchdog probe failed: {host_watchdog}")
    execution_output = (ROOT / manifest["execution_output"]).resolve()
    if execution_output.exists():
        raise FileExistsError(f"frozen execution output already exists: {execution_output}")
    result = {
        "schema_version": "dcec-v0-preflight/1", "status": "passed_not_executed",
        "identity": identity, "records": [{
            "record_id": item["record_id"], "order": item["order"],
            "research_sequence": item["research_sequence"],
            "research_condition": item["research_condition"],
            "visible_tree_sha256": item["visible_tree_sha256"],
            "private_initial_files": item["private_initial_files"],
        } for item in records],
        "same_variant_parity": parity, "research_metadata_isolation": anti_leakage,
        "code_run_filesystem_isolation": filesystem,
        "record_wall_deadline_enforcement": {
            "manifest_budget_seconds": wall_seconds,
            "provider": provider_deadline,
            "host_watchdog": host_watchdog,
            "same_budget_for_all_records": all(
                wall_seconds == manifest["execution_constraints"]["record_wall_seconds"]
                for _ in manifest["runs"]),
        },
        "isolation_runtime": isolation,
        "resolved_models": models, "historical_candidate_switches": manifest["historical_candidate_switches"],
        "constraints": manifest["execution_constraints"],
        "formal_execution_output": {
            "path": manifest["execution_output"], "exists": False,
            "must_not_exist_before_launch": True,
        },
        "execution_authorized": manifest["execution_authorized"],
        "api_requests_sent": 0, "model_api_calls": 0,
    }
    write_json(output / "preflight.json", result)
    return result


def state_audit(private: Path) -> dict:
    timeline = jsonl_rows(private / "audit/runner_state_timeline.jsonl")
    progress = jsonl_rows(private / "audit/progress.jsonl")
    dialogue = jsonl_rows(private / "audit/dialogue.jsonl")
    continuations = jsonl_rows(private / "audit/runner_continuation_state.jsonl")
    known = {event.get("sha256") for event in progress if event.get("event") == "dcec_state_mutation"}
    known.update(item.get("after", {}).get("sha256") for item in continuations)
    tool_operations = [event for event in dialogue if event.get("event") == "tool_call"
                       and event.get("name") in {"file_write", "file_patch"}
                       and "monitor/working.md" in str(event.get("arguments") or "")]
    working_calls = {event.get("tool_id") for event in tool_operations}
    for event in dialogue:
        if event.get("event") != "tool_result" or event.get("tool_id") not in working_calls:
            continue
        data = event.get("data")
        if isinstance(data, dict) and data.get("status") != "error" and data.get("sha256"):
            known.add(data["sha256"])
    out_of_band = []
    for previous, current in zip(timeline, timeline[1:]):
        if previous.get("sha256") != current.get("sha256") and current.get("sha256") not in known:
            out_of_band.append({"before": previous.get("sha256"), "after": current.get("sha256"),
                                "classification": "out_of_band_state_change"})
    return {"request_state_timeline": timeline, "mutation_events": [event for event in progress
            if event.get("event") in {"dcec_state_mutation", "dcec_state_mutation_failed"}],
            "working_file_tool_operations": tool_operations, "continuation_transitions": continuations,
            "out_of_band_state_changes": out_of_band}


def execute_record(slot: Path, source: Path, manifest: dict, spec: dict, run: dict,
                   profile: dict) -> dict:
    projection = model_visible_projection(spec, run["sequence"])
    materialize_visible(slot, projection)
    evidence, task_workspace, private = slot / "task", slot / "task/workspace", slot / "monitor"
    dcec = run["condition"] == "dcec_v0"
    interventions, repair = [], None

    def deliver(message):
        nonlocal repair
        interventions.append({"timestamp": time.time(), "message": message})
        if repair is None:
            repair = apply_repair(slot, projection, message)
        return repair

    def root_ready():
        if repair is None:
            raise RuntimeError("worker requested root phase without a repair transition")
        append_public_event(
            evidence, 3, "root_completion_proposal", projection["root_completion_message"])

    result = run_isolated_record(
        source, slot, profile, dcec,
        manifest["execution_constraints"]["max_review_turns_per_review"],
        manifest["execution_constraints"]["record_wall_seconds"],
        deliver, root_ready)
    usage_rows = jsonl_rows(private / "audit/provider_usage.jsonl")
    attempt_rows = jsonl_rows(private / "audit/request_attempts.jsonl")
    result.update(
        interventions=interventions, repair=repair,
        successful_usage_responses=len(usage_rows), usage_records=usage_rows,
        transport_attempts=len(attempt_rows), state_audit=state_audit(private),
        final_workspace=file_manifest(task_workspace),
    )
    progress = private / "audit/progress.jsonl"
    if progress.is_file():
        transport_events = [event for event in jsonl_rows(progress) if event.get("event") in {
            "request_started", "response_headers", "request_retry_wait", "request_finished",
            "request_usage", "response_metadata"}]
        for event in transport_events:
            append_jsonl(private / "audit/transport.jsonl", event)
    return result


def execute(manifest_path: Path, output: Path, monitor_config: Path) -> dict:
    manifest, spec = load_json(manifest_path), load_json(ROOT / load_json(manifest_path)["fixture_spec"])
    if not manifest.get("execution_authorized"):
        raise PermissionError("manifest execution_authorized=false; final launch audit has not approved API use")
    validate_identity(manifest_path, manifest)
    resolved_configs(manifest, monitor_config)
    frozen_output = (ROOT / manifest["execution_output"]).resolve()
    if output.resolve() != frozen_output:
        raise ValueError(f"execution output must equal frozen path: {frozen_output}")
    if output.exists():
        raise FileExistsError(f"execution output already exists: {output}")
    output.mkdir(parents=True)
    profiles = load_json(monitor_config)
    profile = profiles[manifest["shared_contract"]["supervisor_profile"]]
    source = output / "isolated_runtime"
    prepare_isolated_runtime(source, profile, manifest["historical_candidate_config_keys"])
    results = []
    for run in manifest["runs"]:
        record_id = f"record-{int(run['order']):02d}"
        slot = output / "records" / record_id / "artifacts"
        try:
            result = execute_record(slot, source, manifest, spec, run, profile)
        except Exception as exc:
            result = {"status": "runner_error", "error_type": type(exc).__name__, "error": str(exc)}
            write_json(output / "records" / record_id / "result.json", result)
        else:
            write_json(output / "records" / record_id / "result.json", result)
        results.append({"record_id": record_id, "research_sequence": run["sequence"],
                        "research_condition": run["condition"], "result": result})
    summary = {"status": "finished_once_no_retries", "records": results}
    write_json(output / "results.json", summary)
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--monitor-config", type=Path,
                        default=ROOT / "monitor_config/models.local.json")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    manifest = load_json(args.manifest.resolve())
    if args.execute:
        output = args.output.resolve() if args.output else (ROOT / manifest["execution_output"]).resolve()
        execute(args.manifest.resolve(), output, args.monitor_config.resolve())
    else:
        output = args.output.resolve() if args.output else DEFAULT_PREFLIGHT_OUTPUT.resolve()
        preflight(args.manifest.resolve(), output, args.monitor_config.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
