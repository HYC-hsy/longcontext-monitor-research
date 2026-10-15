"""Generate offline-only, readable evidence for the S2/R2 coordinate repair."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "vendor/pma_89e5c0d/src"))
sys.path.insert(0, str(HERE / "vendor/pma_89e5c0d/external/harbor/src"))

from harbor.llms.base import LLMResponse

from episode import construct_upstream
from test_source_candidate_v2 import Script, call
from test_source_coordinate_diagnostics_v2 import FAILURES, archived_stage


ROOT = HERE.parents[2]
OUT = HERE / "source_coordinate_diagnostics_offline_20261015"
ARCHIVE = (HERE / "source_memory_v3_single_r2_archive_20261015" / "raw" /
           "source-v2-59f53dcd1a87-01-r2")


def run(name: str, argv: list[str], env: dict[str, str] | None = None) -> int:
    result = subprocess.run(argv, cwd=HERE, env=env, capture_output=True, timeout=180)
    (OUT / f"{name}.stdout.txt").write_bytes(result.stdout)
    (OUT / f"{name}.stderr.txt").write_bytes(result.stderr)
    (OUT / f"{name}.command.txt").write_text(
        "argv=" + json.dumps(argv, ensure_ascii=False) +
        f"\nexit_code={result.returncode}\n", encoding="utf-8")
    return result.returncode


def samples() -> None:
    payloads = []
    with TemporaryDirectory() as temp:
        for variant in ("S2", "R2"):
            agent = construct_upstream(Path(temp) / variant, research_candidate=variant)
            bank = agent.memory
            wrapper = json.dumps({"status": "ok", "stdout": "first\nsecond"})
            parent = bank.register_leaf("public", "tool_observation", wrapper, 1,
                "observation/tool_results/0/content", "a" * 64)
            child = bank.register_leaf("public", "tool_observation", "first\nsecond", 1,
                "observation/tool_results/0/content/stdout", "a" * 64)
            script = Script([
                LLMResponse(content="", tool_calls=[call("memory_save_knowledge",
                    content="coordinate mistake", statement_type="tool_observation",
                    source_refs=[{"source_handle": parent, "start_line": 2, "end_line": 2}])]),
                LLMResponse(content="<no_intervention/>"),
                LLMResponse(content="", tool_calls=[call("memory_save_procedural",
                    content="role mistake", statement_type="agent_report",
                    source_refs=[{"source_handle": child, "start_line": 1, "end_line": 1}])]),
                LLMResponse(content="<no_intervention/>"),
                LLMResponse(content="", tool_calls=[]),
                LLMResponse(content="<no_intervention/>")])
            agent._memory_llm.call = script
            for step in range(1, 4):
                asyncio.run(agent._memory_agent.process("public", step))
            payloads.append({"variant": variant, "requests": script.requests,
                             "final_transaction": agent._memory_agent.last_transaction,
                             "source_handles": {"wrapper": parent, "stdout": child}})
    (OUT / "FAKE_REQUESTS_AND_RECEIPTS.json").write_text(
        json.dumps(payloads, ensure_ascii=False, indent=2), encoding="utf-8")


def original_cases() -> None:
    rows = []
    for logical_call, failures in FAILURES.items():
        bank, _, calls = archived_stage(logical_call)
        for call_index, expected in failures.items():
            operation = calls[call_index - 1].function
            sources = []
            for key in ("source_refs", "evidence_refs"):
                for ref in operation.arguments.get(key, []):
                    source = next((bank.sources[source_id] for source_id in bank.current_source_ids
                                   if bank.sources[source_id]["handle"] == ref["source_handle"]), None)
                    sources.append({"argument_path": key, "selection": ref,
                        "actual_role": source["role"] if source else None,
                        "source_field_path": source["field_path"] if source else None,
                        "actual_total_lines": len(bank._line_spans(source["text"])) if source else None})
            rows.append({"public_event_sequence": logical_call, "logical_call": logical_call,
                         "phase": "phase1", "call_index_1_based": call_index,
                         "tool_name": operation.name, "original_arguments": operation.arguments,
                         "original_error": "unknown_source" if logical_call == 27 else "invalid_range",
                         "new_error": expected, "resolved_sources": sources,
                         "fixture_correction": "synthetic_corrected_only; original payload is unchanged"})
    (OUT / "EIGHT_ORIGINAL_CASES.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    OUT.mkdir(exist_ok=True)
    python = sys.executable
    suites = ["test_source_candidate", "test_source_candidate_v2",
              "test_source_coordinate_diagnostics_v2", "test_static_source_screen",
              "test_static_source_live", "test_static_source_live_v2",
              "test_archive_source_v2_batch"]
    first = run("affected", [python, "-m", "unittest", "-q", *suites])
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT), str(ROOT / "GenericAgent-main"),
        str(HERE), str(HERE / "vendor/pma_89e5c0d/src"),
        str(HERE / "vendor/pma_89e5c0d/external/harbor/src")])
    command = ("import importlib,sys,unittest; "
        "sys.modules['offline_launcher']=importlib.import_module("
        "'method_discovery.curator_supervisor_convergence_v0."
        "pma_full_upstream_ga_v1_20261013.offline_launcher'); "
        "unittest.main(module='test_episode',verbosity=1)")
    second = run("episode", [python, "-c", command], env)
    original_cases()
    samples()
    (OUT / "AUDIT.txt").write_text(
        "S2/R2 coordinate and safe receipt offline audit\n"
        "baseline=657aa0eefe0652a9b6ce8be7eae899ca076fde79\n"
        "real Task/PMA/provider/evaluator/training/scoring calls=0\n"
        "fake transport requests=12 (six per variant across three process calls)\n"
        f"affected_exit={first}; episode_exit={second}\n"
        "Historical: six failed Phase 1 stages, eight direct rejects (seven invalid_range, "
        "one previously mislabeled unknown_source), 65 collateral aborts. The original "
        "arguments remain in EIGHT_ORIGINAL_CASES.json and the prior immutable archive. "
        "All original stages still abort; synthetic_corrected operations are separate.\n"
        "Model-visible: each handle's own 1-based total_lines, verified wrapper/stdout "
        "relationship, bounded argument_path and typed diagnostic. Full old bank/history "
        "remain audit-only. call_index is 1-based; ref indexes are 0-based.\n"
        "Semantic limitation: event 35's in-range old-code citation is not validated "
        "as supporting a current-code claim. This repair does not test model behavior.\n"
        "FILE_HASHES.tsv records read_bytes of this checkout and archive files, not Git blob "
        "byte hashes; the pushed commit SHA and Git blobs are separate identities.\n"
        "Exploratory pre-fix test failures were observed in console and corrected by "
        "using the archived public-event sequence as the bank-state key; full early "
        "console bytes were not retained and are not represented as final test output.\n",
        encoding="utf-8")
    diff = subprocess.run(["git", "diff", "--cached", "--binary", "--",
        str(HERE / "source_memory_v2.py"), str(HERE / "source_agent_v2.py"),
        str(HERE / "source_protocol_v2.py"),
        str(HERE / "test_source_coordinate_diagnostics_v2.py"),
        str(HERE / "capture_source_coordinate_audit_v2.py")], cwd=ROOT,
        capture_output=True, check=True)
    (OUT / "FULL_DIFF.txt").write_bytes(diff.stdout)
    sections = ("AUDIT.txt", "EIGHT_ORIGINAL_CASES.json",
                "FAKE_REQUESTS_AND_RECEIPTS.json", "affected.command.txt",
                "affected.stdout.txt", "affected.stderr.txt", "episode.command.txt",
                "episode.stdout.txt", "episode.stderr.txt", "FULL_DIFF.txt")
    (OUT / "AUDIT_COMPLETE.txt").write_text("".join(
        f"\n\n===== {name} =====\n" + (OUT / name).read_text(encoding="utf-8")
        for name in sections), encoding="utf-8")
    files = sorted(p for p in OUT.iterdir() if p.is_file() and p.name != "FILE_HASHES.tsv")
    files += [HERE / name for name in ("source_memory_v2.py", "source_agent_v2.py",
        "source_protocol_v2.py", "test_source_coordinate_diagnostics_v2.py",
        "capture_source_coordinate_audit_v2.py")]
    files += [ARCHIVE / name for name in ("requests.jsonl", "responses.jsonl",
                                        "bank_states.jsonl")]
    (OUT / "FILE_HASHES.tsv").write_text("repo_relative_path\tsha256\tbytes\n" + "".join(
        f"{p.relative_to(ROOT).as_posix()}\t{hashlib.sha256(p.read_bytes()).hexdigest()}\t{p.stat().st_size}\n"
        for p in files), encoding="utf-8")
    return first or second


if __name__ == "__main__":
    raise SystemExit(main())
