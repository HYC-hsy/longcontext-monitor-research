"""Copy the one completed record and emit mechanical, non-semantic locators."""

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil


ROOT = Path(r"E:\LongContext")
RUN = "dynamic-observer-wtv-kitex-transfer-20261002-01"
OUTPUT = ROOT / "long_context_bench/output/dynamic_observer_wtv_kitex_transfer_20261002"
ARCHIVE = (Path(__file__).resolve().parents[3]
           / "method_discovery/runs/dynamic_observer_wtv_kitex_transfer_20261002/r1")
JOB = OUTPUT / "jobs" / RUN
TRIALS = [p for p in JOB.iterdir() if p.is_dir()]
if len(TRIALS) != 1:
    raise RuntimeError("expected exactly one completed trial")
TRIAL = TRIALS[0]
AGENT = TRIAL / "agent"
MONITOR = AGENT / "monitor"
AUDIT = MONITOR / "monitor_private/audit"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def copy_one(source, target):
    if not source.is_file():
        return
    if target.exists():
        if digest(source) != digest(target):
            raise RuntimeError("archive overwrite refused: " + str(target))
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    if digest(source) != digest(target):
        raise RuntimeError("archive copy hash mismatch: " + str(source))


def copy_tree(source, target):
    if not source.is_dir():
        return
    for path in source.rglob("*"):
        if path.is_file():
            copy_one(path, target / path.relative_to(source))


def read_jsonl(path):
    return [(number, json.loads(line)) for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if line.strip()]


def write_json(name, value):
    path = ARCHIVE / name
    content = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") == content:
            return
        if name not in ("WTV_REVIEW_INDEX.json", "GROUND_TRANSITION_REUSE_INDEX.json",
                        "MECHANICAL_FACTS.json", "LOCAL_LARGE_CHECKPOINTS.json", "RAW_FILE_MANIFEST.json"):
            raise RuntimeError("raw artifact overwrite refused: " + str(path))
    path.write_text(content, encoding="utf-8")


def tool_path(call):
    try:
        args = json.loads(call.get("arguments") or "{}")
    except json.JSONDecodeError:
        return None
    return args.get("path")


def main():
    manifest = json.loads((OUTPUT / "runs" / RUN / "manifest.json").read_text(encoding="utf-8"))
    if manifest["run_id"] != RUN or manifest["trial_outcome"] != "agent_phase_completed":
        raise RuntimeError("record is not completed under the expected identity")
    if manifest["agent_protocol"]["ga_process_return_code"] not in (0, 143):
        raise RuntimeError("unexpected Agent process termination")
    # A failed archival pass may have copied immutable raw files already; each
    # repeat copy must byte-match and generated indexes still refuse overwrite.
    ARCHIVE.mkdir(parents=True, exist_ok=True)

    for name in ("config.json", "lock.json", "result.json", "trial.log"):
        copy_one(TRIAL / name, ARCHIVE / "trial" / name)
    for name in ("job.log", "job_config.json", "job_result.json", "launcher_stdout.log", "launcher_stderr.log",
                 "config.json", "lock.json", "result.json"):
        copy_one(JOB / name, ARCHIVE / "job" / name)
    for path in AGENT.iterdir():
        if path.is_file():
            copy_one(path, ARCHIVE / "agent" / path.name)
    for path in MONITOR.iterdir():
        if path.is_file():
            copy_one(path, ARCHIVE / "agent/monitor" / path.name)
    private = MONITOR / "monitor_private"
    for path in private.iterdir():
        if path.is_file():
            copy_one(path, ARCHIVE / "agent/monitor/monitor_private" / path.name)
    for path in AUDIT.iterdir():
        if path.is_file():
            copy_one(path, ARCHIVE / "agent/monitor/monitor_private/audit" / path.name)
    copy_tree(MONITOR / "task_evidence", ARCHIVE / "agent/monitor/task_evidence")
    copy_tree(AUDIT / "commands", ARCHIVE / "agent/monitor/monitor_private/audit/commands")
    for checkpoint in (AUDIT / "live_checkpoints").glob("checkpoint-*"):
        if not checkpoint.is_dir():
            continue
        for name in ("complete.json", "identity.json", "manifest.json", "request.json"):
            copy_one(checkpoint / name, ARCHIVE / "checkpoint_metadata" / checkpoint.name / name)
    for name in ("verifier", "artifacts"):
        copy_tree(TRIAL / name, ARCHIVE / name)
    copy_tree(OUTPUT / "runs" / RUN, ARCHIVE / "proof")
    for name in ("source_identity.json", "result.json"):
        copy_one(OUTPUT / "source_inputs" / RUN / name, ARCHIVE / "source_identity" / name)
    copy_one(OUTPUT / "isolated_bundles" / RUN / "isolation_identity.json",
             ARCHIVE / "source_identity/isolation_identity.json")

    dialogue_path = AUDIT / "dialogue.jsonl"
    rows = read_jsonl(dialogue_path)
    by_review = defaultdict(list)
    for line, row in rows:
        by_review[row["review_id"]].append((line, row))
    contexts = [(line, row) for line, row in rows if row["event"] == "review_context"]
    samples = read_jsonl(AUDIT / "workspace_transitions.jsonl")
    if len(samples) != len(contexts):
        raise RuntimeError("WTV sample/review count mismatch")

    review_index = []
    for (sample_line, sample), (context_line, context) in zip(samples, contexts):
        review_id = context["review_id"]
        events = by_review[review_id]
        outputs = [(line, row) for line, row in events if row["event"] == "model_output"]
        calls = [(line, row) for line, row in events if row["event"] == "tool_call"]
        wake = context.get("wake_context", "")
        start = wake.find("Workspace transition")
        end = wake.find("\nLive environment map", start) if start >= 0 else -1
        wtv_text = wake[start:end].strip() if start >= 0 and end >= 0 else (wake[start:].strip() if start >= 0 else None)
        changed_paths = sample["added"] + sample["modified"] + sample["deleted"]
        workspace_reads = [{"dialogue_line": line, "turn": row["turn"], "path": tool_path(row)}
                           for line, row in calls if row["name"] == "file_read"
                           and (tool_path(row) or "").startswith("task/workspace/")]
        entry = {
            "sample_sequence": sample["sample_sequence"], "sample_line": sample_line,
            "review_id": review_id, "review_context_line": context_line,
            "from_cursor": sample["from_cursor"], "to_cursor": sample["to_cursor"],
            "task_turn": sample["task_turn"], "initial_baseline": sample["initial_baseline"],
            "sample_complete": sample["sample_complete"], "truncated": sample["model_visible_truncated"],
            "added": sample["added"], "modified": sample["modified"], "deleted": sample["deleted"],
            "total_changed": sample["total_changed"], "errors": sample["errors"],
            "model_visible_wtv": wtv_text,
            "first_model_output_line": outputs[0][0] if outputs else None,
            "workspace_reads": workspace_reads,
            "reads_of_exact_changed_paths": [read for read in workspace_reads if read["path"] in changed_paths],
            "other_observations": [{"dialogue_line": line, "turn": row["turn"], "tool": row["name"]}
                                   for line, row in calls if row["name"] in ("code_run", "file_list")],
            "working_writes": [{"dialogue_line": line, "turn": row["turn"]}
                               for line, row in calls if row["name"] == "file_write"
                               and tool_path(row) == "monitor/working.md"],
            "controls": [{"dialogue_line": line, "turn": row["turn"], "tool": row["name"]}
                         for line, row in calls if row["name"] in ("wait", "intervene", "allow_complete")],
        }
        review_index.append(entry)
    write_json("WTV_REVIEW_INDEX.json", {
        "source_file": "agent/monitor/monitor_private/audit/workspace_transitions.jsonl",
        "dialogue_file": "agent/monitor/monitor_private/audit/dialogue.jsonl",
        "join": "sample sequence matched to chronological review_context; no semantic path ranking",
        "reviews": review_index,
    })

    working_writes = []
    for line, row in rows:
        if row["event"] != "tool_call" or row.get("name") != "file_write" or tool_path(row) != "monitor/working.md":
            continue
        args = json.loads(row["arguments"])
        content = args.get("content", "")
        working_writes.append({"dialogue_line": line, "review_id": row["review_id"],
                               "turn": row["turn"], "characters": len(content),
                               "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()})
    write_json("GROUND_TRANSITION_REUSE_INDEX.json", {
        "scope": "Mechanical navigation only. Working writes are candidate state locators, not semantic ground verdicts.",
        "working_writes": working_writes,
        "workspace_transition_reviews": [r for r in review_index if r["total_changed"]],
        "endpoint_path_transitions": [r["sample_sequence"] for r in review_index
                                      if any("pkg/endpoint/" in p for p in r["added"] + r["modified"] + r["deleted"])],
        "client_option_wiring_transitions": [r["sample_sequence"] for r in review_index
                                             if any(("client/option" in p or "internal/client/option" in p
                                                     or "callopt/streamcall" in p) for p in
                                                    r["added"] + r["modified"] + r["deleted"])],
        "root_controls": [{"dialogue_line": line, "review_id": row["review_id"], "turn": row["turn"],
                           "tool": row["name"]} for line, row in rows if row["event"] == "tool_call"
                          and row["name"] == "allow_complete"],
        "root_checkpoints": [{"progress_line": line, "review_id": row["review_id"],
                              "request_id": row["request_id"], "cursor": row["cursor"]}
                             for line, row in read_jsonl(AUDIT / "progress.jsonl")
                             if row.get("event") == "root_checkpoint_created"],
    })

    calls = [row for _, row in rows if row["event"] == "tool_call"]
    waits = [json.loads(row["arguments"]).get("mode") for row in calls if row["name"] == "wait"]
    tool_errors = [{"dialogue_line": line, "review_id": row["review_id"], "data": row["data"]}
                   for line, row in rows if row["event"] == "tool_result"
                   and isinstance(row.get("data"), dict) and row["data"].get("status") == "error"]
    usage = [row for _, row in read_jsonl(AUDIT / "provider_usage.jsonl")]
    usage_sum = {key: sum((row.get(key) or 0) for row in usage) for key in
                 ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")}
    model_input = [row for _, row in rows if row["event"] == "model_input"]
    request_attempts = read_jsonl(AUDIT / "request_attempts.jsonl")
    task_events = read_jsonl(AGENT / "research_events.jsonl")
    task_usage = [row["payload"] for _, row in task_events if row["event_type"] == "provider_usage"]
    task_usage_sum = {key: sum((row.get(key) or 0) for row in task_usage) for key in
                      ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")}
    trial_result = json.loads((TRIAL / "result.json").read_text(encoding="utf-8"))
    from datetime import datetime
    duration = (datetime.fromisoformat(trial_result["finished_at"].replace("Z", "+00:00"))
                - datetime.fromisoformat(trial_result["started_at"].replace("Z", "+00:00"))).total_seconds()
    public_events = MONITOR / "task_evidence/public_events.jsonl"
    events = read_jsonl(public_events) if public_events.exists() else []
    text_all = "\n".join(json.dumps(row, ensure_ascii=False) for _, row in rows)
    write_json("MECHANICAL_FACTS.json", {
        "run_id": RUN, "task_id": "roadmapbench:ktx-0.13.0-roadmap",
        "source_commit": "6c72477fce3350c82baf74a9ca8a96c87742be5b",
        "review_count": len(contexts), "wtv_sample_count": len(samples),
        "wtv_changed_path_count_distribution": dict(Counter(r["total_changed"] for r in review_index)),
        "wtv_incomplete_samples": [r["sample_sequence"] for r in review_index if not r["sample_complete"]],
        "supervisor_model_requests": len(model_input), "supervisor_provider_attempt_events": len(request_attempts),
        "task_agent_model_requests": sum(row["event_type"] == "provider_request_ready" for _, row in task_events),
        "task_agent_provider_attempt_events": sum(row["event_type"] == "provider_request_attempt" for _, row in task_events),
        "task_agent_usage": task_usage_sum,
        "supervisor_usage": usage_sum, "supervisor_tool_calls_by_type": dict(Counter(row["name"] for row in calls)),
        "wait_modes": dict(Counter(waits)), "supervisor_tool_errors": tool_errors,
        "supervisor_provider_attempt_outcomes": dict(Counter(row.get("outcome") for _, row in request_attempts)),
        "interventions": sum(row["name"] == "intervene" for row in calls),
        "completion_proposals_observed": sum(row["event_type"] == "completion_proposal" for _, row in task_events),
        "working_mutations": len(working_writes),
        "working_characters_per_write": [x["characters"] for x in working_writes],
        "working_max_characters": max((x["characters"] for x in working_writes), default=0),
        "fixed_heading_occurrences_in_dialogue": {name: text_all.count(name) for name in
                                                    ("Contrast:", "Measurement:", "Basis:", "Reach:",
                                                     "Anchor:", "Transport:")},
        "public_event_count": len(events),
        "duration_seconds_runner": duration,
        "terminal_verifier": manifest["rewards"],
        "note": "Counts are mechanical; headings counted over raw dialogue may include system/history repetition.",
    })

    skipped = []
    for path in (AUDIT / "live_checkpoints").glob("checkpoint-*.tar"):
        skipped.append({"local_path": str(path), "bytes": path.stat().st_size, "sha256": digest(path)})
    for checkpoint in (AUDIT / "live_checkpoints").glob("checkpoint-*"):
        if not checkpoint.is_dir():
            continue
        for path in checkpoint.iterdir():
            if path.is_file() and path.name not in ("complete.json", "identity.json", "manifest.json", "request.json"):
                skipped.append({"local_path": str(path), "bytes": path.stat().st_size, "sha256": digest(path)})
    write_json("LOCAL_LARGE_CHECKPOINTS.json", skipped)
    files = []
    for path in ARCHIVE.rglob("*"):
        if path.is_file() and path.name != "RAW_FILE_MANIFEST.json":
            files.append({"path": path.relative_to(ARCHIVE).as_posix(), "bytes": path.stat().st_size,
                          "sha256": digest(path)})
    files.sort(key=lambda item: item["path"])
    write_json("RAW_FILE_MANIFEST.json", files)
    print(json.dumps({"archive": str(ARCHIVE), "files": len(files), "reviews": len(contexts),
                      "wtv_samples": len(samples)}, indent=2))


if __name__ == "__main__":
    main()
