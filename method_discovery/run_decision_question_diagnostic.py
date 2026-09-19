"""CLI for the three-way decision-question diagnostic.

The command intentionally refuses to run against the legacy turn-60 fixture;
the manifest must declare model-visible prefixes independently of the full
research archive.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "GenericAgent-main"))

from monitor_agent_core.provider import MonitorProviderClient  # noqa: E402
from monitor_agent_core.workspace import MonitorWorkspace  # noqa: E402
from monitor_agent_core.configuration import load_profile  # noqa: E402

from decision_question_diagnostic import (  # noqa: E402
    DiagnosticConfig, run_three_way_case, validate_checkpoint_fixture,
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

    provider = load_profile(args.profile, args.profile_file)
    args.output.mkdir(parents=True)
    diagnostic = config.get("diagnostic", {})
    run_config = DiagnosticConfig(
        total_calls=int(diagnostic.get("total_calls", 6)),
        question_turns=int(diagnostic.get("question_turns", 2)),
        investigation_turns=int(diagnostic.get("investigation_turns", 4)),
        final_turns=int(diagnostic.get("final_turns", 1)),
    )
    results = []
    for case in cases:
        case_id = case["id"]
        private = args.output / case_id / "private"
        private.mkdir(parents=True)
        workspace = MonitorWorkspace(
            args.fixture / "task_evidence", private,
            task_mounts={"workspace": args.fixture / "workspace"},
        )

        def parent_factory(branch):
            return MonitorProviderClient(
                f"decision_question::{case_id}::{branch}", dict(provider)
            )

        def child_factory(branch):
            return MonitorProviderClient(
                f"decision_question::{case_id}::{branch}", dict(provider)
            )

        audit = []
        result = run_three_way_case(
            parent_factory, child_factory, workspace,
            case["acceptance_question"], tuple(case["source_paths"]),
            tuple(case["evidence_paths"]), parent_history, run_config,
            audit=lambda event, **fields: audit.append({"event": event, **fields}),
        )
        record = {"case": case_id, "result": result,
                  "model_visible_checkpoint": config["checkpoint"]["id"]}
        (private.parent / "result.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        (private.parent / "audit.jsonl").write_text(
            "".join(json.dumps(item, ensure_ascii=False, default=str) + "\n" for item in audit),
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
