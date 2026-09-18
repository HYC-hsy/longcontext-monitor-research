"""Run bounded A/B/C/D local reviews over one materialized public checkpoint.

This is offline analysis of an archived task, not an online monitor hook.
Scoring data never enters the model prompt or readable workspace.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "GenericAgent-main"))
from monitor_agent_core.configuration import load_profile  # noqa: E402
from monitor_agent_core.probe import IndependentVerifier, ProbeConfig, score_local_result  # noqa: E402
from monitor_agent_core.provider import MonitorProviderClient  # noqa: E402
from monitor_agent_core.workspace import MonitorWorkspace  # noqa: E402


PANEL = ROOT / "method_discovery/artifacts/independent_verification_20260918"
DEFAULT_CONFIG = PANEL / "checkpoint_config.json"
DEFAULT_FIXTURE = PANEL / "materialized_r4"
DEFAULT_PROFILE = ROOT / "monitor_config/models.local.json"
VERDICT = {
    "correct": "supported_in_scope",
    "incorrect": "contradicted",
    "insufficient": "unresolved",
}


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def parent_approved(history: list[dict]) -> bool:
    return any(
        item.get("type") == "tool_use" and item.get("name") == "allow_complete"
        for message in history if message.get("role") == "assistant"
        for item in message.get("content", [])
    )


def ensure_fixture(config: dict, fixture: Path, config_path: Path) -> list[dict]:
    manifest = json.loads((fixture / "materialization.json").read_text(encoding="utf-8"))
    if manifest["checkpoint"] != "turn-60-root-completion":
        raise ValueError("wrong materialized checkpoint")
    if manifest["source_run"] != config["fixture"]["parent_run_id"]:
        raise ValueError("wrong parent run")
    if manifest["public_event_lines"] != 117:
        raise ValueError("public event prefix is incomplete")
    config_digest = hashlib.sha256(config_path.read_bytes()).hexdigest()
    if manifest.get("config_sha256") != config_digest:
        raise ValueError("checkpoint configuration digest changed")
    expected_workspace = {path.removeprefix("task/workspace/")
                          for case in config["cases"] for path in case["evidence_paths"]
                          if path.startswith("task/workspace/")}
    expected_artifacts = {
        "task_evidence/original_task.txt", "task_evidence/public_events.jsonl",
        "task_evidence/build_observation.json", "parent_context/pma_memory.json",
        "parent_context/provider_history.json",
    } | {f"workspace/{path}" for path in expected_workspace}
    artifact_digests = manifest.get("artifact_sha256")
    if not isinstance(artifact_digests, dict) or set(artifact_digests) != expected_artifacts:
        raise ValueError("materialized artifact inventory does not match checkpoint")
    if set(manifest.get("files", {})) != expected_workspace:
        raise ValueError("materialized workspace inventory does not match checkpoint")
    for relative, expected_digest in artifact_digests.items():
        path = fixture / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected_digest:
            raise ValueError(f"materialized artifact digest changed: {relative}")
        if relative.startswith("workspace/") and (
            manifest["files"][relative.removeprefix("workspace/")] != expected_digest
        ):
            raise ValueError(f"workspace digest disagrees with inventory: {relative}")
    if len((fixture / "task_evidence/public_events.jsonl").read_text(encoding="utf-8").splitlines()) != 117:
        raise ValueError("public-event line count changed")
    history = json.loads((fixture / "parent_context/provider_history.json").read_text(encoding="utf-8"))
    if not parent_approved(history):
        raise ValueError("A baseline is not an archived allow_complete decision")
    return history


def usage_total(records: list[dict]) -> dict:
    totals = {
        key: sum(int(record.get(key) or 0) for record in records)
        for key in ("input_tokens", "output_tokens", "cache_creation_input_tokens",
                    "cache_read_input_tokens")
    }
    totals["total_tokens"] = sum(totals.values())
    return totals


def transport_audit_callback(records: list[dict], case_id: str, group_name: str):
    """Keep provider lifecycle diagnostics without response bodies or secrets."""
    allowed = {
        "request_id", "attempt", "started_at", "duration_seconds", "purpose",
        "transaction_id", "outcome", "error_type", "error_chain", "retry_delay_seconds",
        "status_code", "lines", "bytes_or_characters", "seconds", "next_batch",
        "reason", "source", "delta_characters", "final_characters", "mismatch",
        "reasoning_echo", "final_item_types", "usage", "provider_message_id", "metadata",
    }
    def callback(event, **fields):
        item = {key: value for key, value in fields.items() if key in allowed}
        metadata = item.get("metadata")
        if isinstance(metadata, dict):
            item["metadata"] = {key: metadata[key] for key in (
                "provider", "stream_complete", "stop_reason", "provider_message_id"
            ) if key in metadata}
        records.append({"event": "transport_" + event, "case": case_id,
                        "group": group_name, **item})
    return callback


def run_case_group(case: dict, group_name: str, group: dict, fixture: Path,
                   output: Path, provider_config: dict | None,
                   parent_history: list[dict]) -> dict:
    if group_name in case.get("incompatible_groups", []):
        raise ValueError(f"{group_name} can see evidence beyond this scoped question")
    expected = VERDICT[case["scoring"]["expected_label"]]
    if group_name == "A_current":
        # Historical root approval is not a local answer to this question.
        return {
            "case": case["id"], "group": group_name,
            "status": "historical_reference", "outcome": None,
            "basis": "archived_root_approval_only", "parent_root_approved": True,
            "comparison_role": "historical_reference", "score_eligible": False,
            "correct": None,
            "requests": 0, "usage": usage_total([]), "seconds": 0,
        }
    if provider_config is None:
        raise ValueError("provider configuration required for B/C/D")
    mode = group["mode"]
    if mode == "same_context_review":
        mode = "direct"
    if mode not in ("direct", "expectation_first"):
        raise ValueError(f"unsupported group mode: {mode}")
    private = output / case["id"] / group_name / "private"
    private.mkdir(parents=True)
    workspace = MonitorWorkspace(
        fixture / "task_evidence", private,
        task_mounts={"workspace": fixture / "workspace"},
    )
    profile = dict(provider_config)
    client = MonitorProviderClient(f"independent_probe::{group_name}", profile)
    if group_name == "B_same_context":
        # A copy in a fresh client; archived parent file itself is never mutated.
        client.restore_history(parent_history)
    records = []
    client.progress_callback = transport_audit_callback(records, case["id"], group_name)
    probe = IndependentVerifier(
        client, workspace,
        ProbeConfig(
            mode=mode,
            source_paths=tuple(case["source_paths"]),
            evidence_paths=tuple(case["evidence_paths"]),
            max_requests=int(group["max_requests"]),
            max_turns=int(group["max_turns"]),
            allow_code_run=False,
        ),
        audit=lambda event, **fields: records.append({"event": event, **fields}),
    )
    started = time.monotonic()
    try:
        result = probe.run(case["question"])
        item = {
            "case": case["id"], "group": group_name,
            "status": result.status,
            "outcome": result.outcome, "expectation": result.expectation,
            "expectation_revision": result.expectation_revision,
            "conclusion": result.conclusion, "limitation": result.limitation,
            "phases": result.phases, "requests": result.requests,
            "history_before": result.history_before,
            "history_after": result.history_after,
            **score_local_result(result, expected),
            "comparison_role": "supplemental_history" if group_name == "B_same_context"
                               else "primary_isolated",
        }
    except Exception as exc:
        item = {
            "case": case["id"], "group": group_name,
            "outcome": "execution_error",
            "status": "execution_error", "score_eligible": False,
            "error_type": type(exc).__name__,
            "correct": None,
            "requests": probe.logical_calls,
            "successful_responses": len(client.usage_records),
        }
    item["seconds"] = round(time.monotonic() - started, 3)
    item["usage"] = usage_total(client.usage_records)
    item["history_transforms"] = client.history_transforms
    item["request_attempts"] = client.request_attempts
    item["transport_attempts"] = len(client.request_attempts)
    group_dir = private.parent
    write_json(group_dir / "result.json", item)
    (group_dir / "audit.jsonl").write_text(
        "".join(json.dumps(record, ensure_ascii=False, default=str) + "\n" for record in records),
        encoding="utf-8",
    )
    return item


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--profile-file", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--profile", default="claude_monitor_opus48")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", default=["all"])
    parser.add_argument("--groups", nargs="+", default=["C_isolated_direct",
                                                        "D_expectation_first_isolated"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Use a fresh output directory: {args.output}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    parent_history = ensure_fixture(config, args.fixture, args.config)
    cases = config["cases"] if args.cases == ["all"] else [
        case for case in config["cases"] if case["id"] in args.cases
    ]
    if len(cases) != len(config["cases"]) and len(cases) != len(set(args.cases)):
        raise ValueError("Unknown or duplicate case ID")
    groups = config["groups"]
    if not cases or any(name not in groups for name in args.groups):
        raise ValueError("No cases or unknown group")
    disputed = [case["id"] for case in cases
                if case["scoring"].get("label_status", "confirmed") != "confirmed"]
    if disputed and args.cases != ["all"] and not args.dry_run:
        raise ValueError(f"Scoring label is not confirmed; exclude these cases: {disputed}")
    if args.cases == ["all"]:
        cases = [case for case in cases if case["id"] not in disputed]
    incompatible = [(case["id"], name) for case in cases for name in args.groups
                    if name in case.get("incompatible_groups", [])]
    if incompatible and not args.dry_run:
        raise ValueError(f"Incomparable case/group context: {incompatible}")
    if args.dry_run:
        print(json.dumps({
            "cases": [case["id"] for case in cases], "groups": args.groups,
            "excluded_unconfirmed_labels": disputed,
            "incompatible_case_groups": incompatible,
            "fixture": str(args.fixture), "model_input_fields":
            ["question", "source_paths", "evidence_paths"],
            "evaluator_only_fields": ["scoring", "native_verifier"],
        }, ensure_ascii=False, indent=2))
        return
    provider = None
    if any(name != "A_current" for name in args.groups):
        provider = load_profile(args.profile, args.profile_file)
    args.output.mkdir(parents=True)
    results = []
    for case in cases:
        for name in args.groups:
            item = run_case_group(case, name, groups[name], args.fixture,
                                  args.output, provider, parent_history)
            results.append(item)
            write_json(args.output / "results.json", {"items": results})
            print(f"{case['id']} {name}: {item['status']} / {item['outcome']} "
                  f"logical_calls={item['requests']} "
                  f"transport_attempts={item.get('transport_attempts', 0)} "
                  f"tokens={item['usage']['total_tokens']}", flush=True)


if __name__ == "__main__":
    main()
