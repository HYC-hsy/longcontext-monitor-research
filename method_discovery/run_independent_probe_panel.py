"""Run bounded A/B/C/D local reviews over one materialized public checkpoint.

This is offline analysis of an archived task, not an online monitor hook.
Scoring data never enters the model prompt or readable workspace.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "GenericAgent-main"))
from monitor_agent_core.configuration import load_profile  # noqa: E402
from monitor_agent_core.probe import IndependentVerifier, ProbeConfig  # noqa: E402
from monitor_agent_core.provider import MonitorProviderClient  # noqa: E402
from monitor_agent_core.workspace import MonitorWorkspace  # noqa: E402


PANEL = ROOT / "method_discovery/artifacts/independent_verification_20260918"
DEFAULT_CONFIG = PANEL / "checkpoint_config.json"
DEFAULT_FIXTURE = PANEL / "materialized_r3"
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


def ensure_fixture(config: dict, fixture: Path) -> list[dict]:
    manifest = json.loads((fixture / "materialization.json").read_text(encoding="utf-8"))
    if manifest["checkpoint"] != "turn-60-root-completion":
        raise ValueError("wrong materialized checkpoint")
    if manifest["source_run"] != config["fixture"]["parent_run_id"]:
        raise ValueError("wrong parent run")
    if manifest["public_event_lines"] != 117:
        raise ValueError("public event prefix is incomplete")
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


def run_case_group(case: dict, group_name: str, group: dict, fixture: Path,
                   output: Path, provider_config: dict | None,
                   parent_history: list[dict]) -> dict:
    expected = VERDICT[case["scoring"]["expected_label"]]
    if group_name == "A_current":
        # Root approval implies support; it is not a recorded local probe.
        return {
            "case": case["id"], "group": group_name,
            "outcome": "supported_in_scope", "basis": "implied_by_archived_root_approval",
            "correct": expected == "supported_in_scope",
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
            "outcome": result.outcome, "expectation": result.expectation,
            "expectation_revision": result.expectation_revision,
            "conclusion": result.conclusion, "limitation": result.limitation,
            "phases": result.phases, "requests": result.requests,
            "history_before": result.history_before,
            "history_after": result.history_after,
            "correct": result.outcome == expected,
        }
    except Exception as exc:
        item = {
            "case": case["id"], "group": group_name,
            "outcome": "execution_error",
            "error_type": type(exc).__name__,
            "correct": False,
            "requests": len(client.usage_records),
        }
    item["seconds"] = round(time.monotonic() - started, 3)
    item["usage"] = usage_total(client.usage_records)
    item["history_transforms"] = client.history_transforms
    item["request_attempts"] = client.request_attempts
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
    parser.add_argument("--groups", nargs="+", default=["A_current", "B_same_context",
                                                        "C_isolated_direct",
                                                        "D_expectation_first_isolated"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Use a fresh output directory: {args.output}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    parent_history = ensure_fixture(config, args.fixture)
    cases = config["cases"] if args.cases == ["all"] else [
        case for case in config["cases"] if case["id"] in args.cases
    ]
    if len(cases) != len(config["cases"]) and len(cases) != len(set(args.cases)):
        raise ValueError("Unknown or duplicate case ID")
    groups = config["groups"]
    if not cases or any(name not in groups for name in args.groups):
        raise ValueError("No cases or unknown group")
    pending = [case["id"] for case in cases
               if case["scoring"].get("label_status") == "pending_user_decision"]
    if pending and not args.dry_run:
        raise ValueError(f"Scoring label requires user decision before further comparison: {pending}")
    if args.dry_run:
        print(json.dumps({
            "cases": [case["id"] for case in cases], "groups": args.groups,
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
            print(f"{case['id']} {name}: {item['outcome']} "
                  f"requests={item['requests']} tokens={item['usage']['total_tokens']}", flush=True)


if __name__ == "__main__":
    main()
