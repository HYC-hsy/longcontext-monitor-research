"""Rebuild a scoped, public-only Fyne checkpoint from the recorded file tools.

No native verifier or solution files are copied. Unsupported mutations fail
closed; this is a fixture materializer, not a general task replay engine.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "method_discovery/artifacts/independent_verification_20260918/checkpoint_config.json"
RUN = ROOT / (
    "long_context_bench/output/clean_monitor_real_tasks/fyn-2.2.0-roadmap/jobs/"
    "clean-monitor-fyn-2.2.0-roadmap-root-simple-20260917-r2/fyn-2.2.0-roadmap__FEMZsvQ"
)
MUTATION_TOOLS = {"file_write", "file_patch", "file_delete", "file_move"}
SHELL_MUTATION = re.compile(
    r"(?:\bsed\s+-i\b|\bperl\s+-pi\b|\bgofmt\s+-w\b|"
    r"\b(?:cp|mv|rm|touch|tee|patch|apply_patch)\s|(?:^|\s)(?:>|>>))",
    re.I,
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def safe_relative(path: str) -> Path:
    if not path.startswith("/app/"):
        raise ValueError(f"not a task workspace path: {path}")
    parts = Path(path[5:]).parts
    if not parts or ".." in parts or "." in parts:
        raise ValueError(f"unsafe task workspace path: {path}")
    return Path(*parts)


def tool_ok(result: dict) -> bool:
    raw = result.get("content", "")
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        return False
    return isinstance(data, dict) and data.get("status") == "success"


def build(config_path: Path, output: Path) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if output.exists():
        raise FileExistsError(f"Output already exists; use a fresh destination: {output}")
    cases = config["cases"]
    cutoffs = {case["event_prefix"]["through_task_turn"] for case in cases}
    if cutoffs != {60}:
        raise ValueError(f"This fixture supports only the recorded turn-60 checkpoint: {cutoffs}")
    base = ROOT / config["fixture"]["workspace_base"]
    event_source = RUN / config["fixture"]["event_source"]
    task_source = RUN / config["fixture"]["original_task_ref"]
    if digest(event_source) != config["fixture"]["event_source_sha256"]:
        raise ValueError("public-event source digest changed")
    if digest(task_source) != config["fixture"]["original_task_sha256"]:
        raise ValueError("original-task source digest changed")

    wanted = set()
    for case in cases:
        for path in case["evidence_paths"]:
            if path.startswith("verifier/") or path.startswith("solution/"):
                raise ValueError(f"posthoc/hidden evidence in model paths: {path}")
            if path.startswith("task/workspace/"):
                wanted.add(Path(path.removeprefix("task/workspace/")))
            elif path not in {"task/public_events.jsonl", "task/build_observation.json"}:
                raise ValueError(f"unhandled evidence path: {path}")
    contents = {}
    for relative in wanted:
        source = base / relative
        contents[relative] = source.read_text(encoding="utf-8") if source.is_file() else None

    events = []
    operations = []
    suspicious_shell = []
    build_observation = None
    for line_no, line in enumerate(event_source.read_text(encoding="utf-8").splitlines(), 1):
        event = json.loads(line)
        turn = event.get("task_turn")
        if turn is not None and turn > 60:
            break
        events.append(line)
        if event.get("boundary") != "post_tool_pre_next_llm":
            continue
        results = {item.get("tool_use_id"): item for item in event.get("tool_results", [])}
        for call in event.get("tool_calls", []):
            name = call.get("name")
            args = call.get("args") or {}
            if name == "code_run":
                script = str(args.get("script", ""))
                if SHELL_MUTATION.search(script):
                    suspicious_shell.append({"turn": turn, "line": line_no, "script": script[:300]})
                if turn == 58 and script.startswith("go build -v ./..."):
                    raw = results.get(call.get("id"), {}).get("content", "")
                    observed = json.loads(raw)
                    build_observation = {
                        "task_turn": turn, "command": script,
                        "status": observed.get("status"),
                        "exit_code": observed.get("exit_code"),
                        "stdout": observed.get("stdout", ""),
                    }
                continue
            if name not in MUTATION_TOOLS:
                continue
            target = args.get("path")
            if not isinstance(target, str) or not target.startswith("/app/"):
                continue
            relative = safe_relative(target)
            if relative not in wanted:
                continue
            if not tool_ok(results.get(call.get("id"), {})):
                continue
            if name == "file_write":
                updated = args.get("content")
                if not isinstance(updated, str):
                    raise ValueError(f"missing file_write content at turn {turn}: {relative}")
            elif name == "file_patch":
                old, new = args.get("old_content"), args.get("new_content")
                current = contents[relative]
                if not isinstance(old, str) or not isinstance(new, str) or current is None:
                    raise ValueError(f"unreplayable file_patch at turn {turn}: {relative}")
                if old.startswith("{{file:"):
                    raise ValueError(f"locator-based patch requires separate replay at turn {turn}: {relative}")
                if current.count(old) != 1:
                    raise ValueError(
                        f"patch mismatch at turn {turn}: {relative}, matches={current.count(old)}"
                    )
                updated = current.replace(old, new, 1)
            else:
                raise ValueError(f"unsupported successful {name} at turn {turn}: {relative}")
            contents[relative] = updated
            operations.append({"turn": turn, "tool": name, "path": relative.as_posix()})
    if suspicious_shell:
        raise ValueError(f"unmodeled shell mutation candidates: {suspicious_shell}")
    if any(value is None for value in contents.values()):
        raise ValueError(f"missing reconstructed files: {[str(k) for k, v in contents.items() if v is None]}")
    if build_observation is None or build_observation["exit_code"] != 0:
        raise ValueError("recorded successful turn-58 build observation is unavailable")

    evidence = output / "task_evidence"
    workspace = output / "workspace"
    parent = output / "parent_context"
    evidence.mkdir(parents=True)
    workspace.mkdir()
    parent.mkdir()
    shutil.copyfile(task_source, evidence / "original_task.txt")
    (evidence / "public_events.jsonl").write_text("\n".join(events) + "\n", encoding="utf-8")
    (evidence / "build_observation.json").write_text(
        json.dumps(build_observation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for relative, value in sorted(contents.items()):
        destination = workspace / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(value, encoding="utf-8")
    for name, source in {
        "pma_memory.json": RUN / config["fixture"]["parent_state_ref"],
        "provider_history.json": RUN / "agent/monitor/monitor_private/audit/provider_history.json",
    }.items():
        shutil.copyfile(source, parent / name)
    artifact_paths = [
        evidence / "original_task.txt", evidence / "public_events.jsonl",
        evidence / "build_observation.json", parent / "pma_memory.json",
        parent / "provider_history.json",
    ] + [workspace / relative for relative in sorted(contents)]
    manifest = {
        "checkpoint": "turn-60-root-completion",
        "source_run": config["fixture"]["parent_run_id"],
        "config_sha256": digest(config_path).lower(),
        "public_event_lines": len(events),
        "replayed_operations": operations,
        "files": {path.as_posix(): digest(workspace / path).lower()
                  for path in sorted(contents)},
        "artifact_sha256": {
            path.relative_to(output).as_posix(): digest(path).lower()
            for path in artifact_paths
        },
        "evaluator_only": "Native verifier output remains outside this materialization.",
    }
    (output / "materialization.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.config, args.output), ensure_ascii=False, indent=2))
