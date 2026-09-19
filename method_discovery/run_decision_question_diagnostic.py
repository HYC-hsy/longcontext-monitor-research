"""CLI for the three-way decision-question diagnostic.

The command intentionally refuses to run against the legacy turn-60 fixture;
the manifest must declare model-visible prefixes independently of the full
research archive.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "GenericAgent-main"))

from monitor_agent_core.provider import MonitorProviderClient  # noqa: E402
from monitor_agent_core.workspace import MonitorWorkspace  # noqa: E402
from monitor_agent_core.configuration import load_profile  # noqa: E402

from decision_question_diagnostic import (  # noqa: E402
    DiagnosticConfig, run_three_way_case, validate_checkpoint_fixture,
    materialize_model_view,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--profile-file", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", default=["all"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Use a fresh output directory: {args.output}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    parent_history = validate_checkpoint_fixture(config, args.fixture, args.config)
    cases = config.get("cases", [])
    if args.cases != ["all"]:
        wanted = set(args.cases)
        cases = [case for case in cases if case.get("id") in wanted]
        if len(cases) != len(wanted):
            raise ValueError("unknown or duplicate case id")
    if args.dry_run:
        print(json.dumps({
            "checkpoint": config["checkpoint"].get("id"),
            "cases": [case["id"] for case in cases],
            "branches": ["ordinary", "parent_direct", "isolated_c"],
            "model_visible": config["checkpoint"]["model_visible"],
            "research_archive": config["checkpoint"]["research_archive"],
        }, ensure_ascii=False, indent=2))
        return

    args.output.mkdir(parents=True)
    # Materialize and resolve every selected view before the first model call.
    prepared = {}
    for case in cases:
        case_root = args.output / case["id"]
        private = case_root / "private"
        private.mkdir(parents=True)
        model_view, allowed = materialize_model_view(
            config, args.fixture, case, case_root / "model_visible")
        workspace = MonitorWorkspace(model_view, private)
        for virtual_path in sorted(allowed):
            workspace.resolve_read(virtual_path)
        prepared[case["id"]] = (private, workspace)
    (args.output / "preflight.json").write_text(json.dumps({
        "checkpoint": config["checkpoint"]["id"],
        "cases": [case["id"] for case in cases],
        "status": "passed",
        "history_source_kind": config["checkpoint"]["model_visible"]["history_source_kind"],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    provider = load_profile(args.profile, args.profile_file)
    diagnostic = config.get("diagnostic", {})
    run_config = DiagnosticConfig(
        total_calls=int(diagnostic.get("total_calls", 6)),
        question_turns=int(diagnostic.get("question_turns", 3)),
        investigation_turns=int(diagnostic.get("investigation_turns", 4)),
        final_turns=int(diagnostic.get("final_turns", 1)),
    )
    results = []
    for case in cases:
        case_id = case["id"]
        private, workspace = prepared[case_id]
        audit_path = private.parent / "audit.jsonl"
        transport_path = private.parent / "transport.jsonl"
        clients = {}

        def append_json(path, item):
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
                stream.flush()

        def audit(event, **fields):
            append_json(audit_path, {"event": event, "case": case_id,
                                     "recorded_at": datetime.now(timezone.utc).isoformat(),
                                     **fields})

        def transport(branch, event, **fields):
            allowed = {"request_id", "attempt", "started_at", "duration_seconds",
                       "purpose", "transaction_id", "outcome", "error_type",
                       "error_chain", "retry_delay_seconds", "status_code", "lines",
                       "bytes_or_characters", "seconds", "next_batch", "reason",
                       "source", "usage", "provider_message_id", "metadata"}
            item = {key: value for key, value in fields.items() if key in allowed}
            append_json(transport_path, {
                "event": "transport_" + event, "case": case_id, "branch": branch,
                "recorded_at": datetime.now(timezone.utc).isoformat(), **item,
            })

        def parent_factory(branch):
            client = MonitorProviderClient(
                f"decision_question::{case_id}::{branch}", dict(provider)
            )
            client.progress_callback = lambda event, **fields: transport(branch, event, **fields)
            clients[branch] = client
            return client

        def child_factory(branch):
            client = MonitorProviderClient(
                f"decision_question::{case_id}::{branch}", dict(provider)
            )
            client.progress_callback = lambda event, **fields: transport(branch, event, **fields)
            clients[branch] = client
            return client

        def usage_snapshot():
            snapshot = {}
            for branch, client in clients.items():
                snapshot[branch] = {
                    "logical_calls": len(client.usage_records),
                    "request_attempts": len(client.request_attempts),
                    "input_tokens": sum(int(x.get("input_tokens") or 0)
                                        for x in client.usage_records),
                    "output_tokens": sum(int(x.get("output_tokens") or 0)
                                         for x in client.usage_records),
                    "total_tokens": sum(sum(int(x.get(key) or 0) for key in
                                              ("input_tokens", "output_tokens",
                                               "cache_creation_input_tokens",
                                               "cache_read_input_tokens"))
                                        for x in client.usage_records),
                }
            return snapshot

        def branch_sink(branch, branch_result):
            entry = {"case": case_id, "branch": branch,
                     "recorded_at": datetime.now(timezone.utc).isoformat(),
                     "result": branch_result, "usage_by_client": usage_snapshot()}
            branch_dir = private.parent / "branches"
            branch_dir.mkdir(exist_ok=True)
            (branch_dir / f"{branch}.json").write_text(
                json.dumps(entry, ensure_ascii=False, indent=2, default=str) + "\n",
                encoding="utf-8")
            append_json(private.parent / "branch_results.jsonl", entry)

        try:
            result = run_three_way_case(
                parent_factory, child_factory, workspace,
                case["acceptance_question"], tuple(case["source_paths"]),
                tuple(case["evidence_paths"]), parent_history, run_config,
                audit=audit, branch_sink=branch_sink,
            )
        except Exception as exc:
            result = {"status": "error", "error_type": type(exc).__name__,
                      "error": str(exc)}
            append_json(audit_path, {"event": "case_exception", "case": case_id,
                                     "recorded_at": datetime.now(timezone.utc).isoformat(),
                                     "error_type": type(exc).__name__, "error": str(exc)})
        usage = usage_snapshot()
        actual_total_tokens = sum(item["total_tokens"] for item in usage.values())
        shared_tokens = usage.get("question", {}).get("total_tokens", 0)
        record = {"case": case_id, "result": result,
                  "model_visible_checkpoint": config["checkpoint"]["id"],
                  "usage_by_branch": usage,
                  "actual_unique_total_tokens": actual_total_tokens,
                  "shared_question_tokens_counted_per_comparison_branch": shared_tokens,
                  "shared_question_branch_accounting": ["parent_direct", "isolated_c"],
                  "transport_log": "transport.jsonl", "audit_log": "audit.jsonl"}
        (private.parent / "result.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        results.append(record)
        (args.output / "results.json").write_text(
            json.dumps({"items": results}, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        print(f"{case_id}: {result.get('status')}", flush=True)


if __name__ == "__main__":
    main()
