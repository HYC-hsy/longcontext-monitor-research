"""Mechanical post-run copy/index. Never starts a trial or evaluates meaning."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from method_discovery.uc_path_control_entry import PLAN, PLAN_ROOT


CAMPAIGN = Path(r"E:\LongContext\long_context_bench\output\uc_path_control_v0_20261003")
RECORDS = PLAN_ROOT / "records"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def rows(path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def record_one(slot):
    run_id = slot["run_id"]
    destination = RECORDS / f"{slot['position']:02d}_{run_id}"
    if destination.exists():
        raise RuntimeError("Record destination exists; no overwrite")
    trials = [path for path in (CAMPAIGN / "jobs" / run_id).iterdir() if path.is_dir()]
    if len(trials) != 1:
        raise RuntimeError("Expected exactly one original trial")
    trial = trials[0]
    agent = trial / "agent"
    monitor = agent / "monitor"
    private = monitor / "monitor_private"
    audit = private / "audit"
    bridge = CAMPAIGN / "bridge" / run_id
    run = CAMPAIGN / "runs" / run_id
    file_records = []

    def copy(source, name):
        if not source.is_file():
            file_records.append({"source": str(source), "archive": name, "status": "missing"})
            return
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        file_records.append({"source": str(source), "archive": name,
                             "bytes": target.stat().st_size, "sha256": digest(target),
                             "status": "copied"})

    for name in ("manifest.json", "raw_trace.jsonl"):
        copy(run / name, "runner/" + name)
    for name in ("result.json", "trial.log"):
        copy(trial / name, "trial/" + name)
    for name in ("output.txt", "agent_stdout.log", "agent_stderr.log",
                 "research_events.jsonl", "m4_agent_identity.json", "otel_trace.json"):
        copy(agent / name, "agent/" + name)
    for name in ("original_task.txt", "public_events.jsonl", "synopsis.jsonl"):
        copy(monitor / "task_evidence" / name, "monitor/task_evidence/" + name)
    for name in ("runtime_receipts.jsonl", "task_identity.json"):
        copy(monitor / name, "monitor/" + name)
    for name in ("working.md", "delivery_feedback.jsonl"):
        copy(private / name, "monitor/private/" + name)
    for source in sorted(audit.glob("*.json*")):
        copy(source, "monitor/audit/" + source.name)
    for source in sorted((trial / "verifier").glob("*")):
        if source.is_file():
            copy(source, "verifier/" + source.name)
    for source in sorted((bridge / "evidence").glob("*.json")):
        copy(source, "bridge/evidence/" + source.name)
    for source in sorted((audit / "live_checkpoints").glob("checkpoint-*/*.json")):
        copy(source, "monitor/root_checkpoints/" + source.parent.name + "/" + source.name)
    for source in sorted((audit / "commands").glob("*/*")):
        if source.is_file():
            copy(source, "monitor/commands/" + source.parent.name + "/" + source.name)

    # Raw gateway bodies and receipts contain model-visible material but never
    # the private gateway header config. Check known private credentials before
    # packaging; do not print credential values.
    gateway_config = CAMPAIGN / "isolated_bundles" / run_id / "gateway" / "config.json"
    gateway = json.loads(gateway_config.read_text(encoding="utf-8"))
    secrets = [value.encode() for route in gateway["models"].values()
               for value in route["headers"].values() if value]
    control = bridge / "control"
    control_zip = destination / "bridge" / "gateway_control_raw.zip"
    control_zip.parent.mkdir(parents=True, exist_ok=True)
    control_files = sorted(path for path in control.iterdir() if path.is_file())
    with zipfile.ZipFile(control_zip, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in control_files:
            data = source.read_bytes()
            if any(secret in data for secret in secrets):
                raise RuntimeError("Private gateway credential found in control artifact")
            archive.writestr(source.name, data)
    file_records.append({"source": str(control), "archive": "bridge/gateway_control_raw.zip",
                         "bytes": control_zip.stat().st_size, "sha256": digest(control_zip),
                         "status": "copied", "file_count": len(control_files)})

    local_only = []
    for source in (bridge / "evidence" / "pre_verification_app.tar",
                   bridge / "evidence" / "verification_boundary_app.tar"):
        if source.is_file():
            local_only.append({"path": str(source), "bytes": source.stat().st_size,
                               "sha256": digest(source)})
    write(destination / "RAW_FILE_MANIFEST.json", {
        "copied": file_records, "local_only_large_artifacts": local_only})

    task_events = rows(agent / "research_events.jsonl")
    usage = []
    for event in task_events:
        if event.get("event_type") == "provider_usage":
            if isinstance(event.get("payload"), dict):
                usage.append(event["payload"])
    monitor_usage = rows(audit / "provider_usage.jsonl")
    dialogue = rows(audit / "dialogue.jsonl")
    progress = rows(audit / "progress.jsonl")
    attempts = rows(audit / "request_attempts.jsonl")
    reviews = rows(audit / "reviews.jsonl")
    windows = [(line, event) for line, event in enumerate(dialogue, 1)
               if event.get("event") == "path_control_public_window"]
    tool_calls = [(line, event) for line, event in enumerate(dialogue, 1)
                  if event.get("event") == "tool_call"]
    interventions = []
    for line, event in tool_calls:
        if event.get("name") != "intervene":
            continue
        timestamp = float(event["timestamp"])
        interventions.append({"dialogue_line": line, "review_id": event.get("review_id"),
                              "timestamp": timestamp,
                              "raw_arguments": event.get("arguments"),
                              "public_event_index": "monitor/task_evidence/public_events.jsonl"})
    write(destination / "EVENT_LOCATORS.json", {
        "review_rows": [{"line": i, "action": r.get("action")}
                        for i, r in enumerate(reviews, 1)],
        "path_window_rows": [{"dialogue_line": i, "review_id": e.get("review_id"),
                              "source_lines": e.get("source_lines"),
                              "characters": e.get("injected_characters")}
                             for i, e in windows],
        "interventions": interventions,
        "root_checkpoint_events": [{"progress_line": i, "review_id": e.get("review_id")}
                                   for i, e in enumerate(progress, 1)
                                   if e.get("event") == "root_checkpoint_created"],
        "tool_calls": [{"dialogue_line": i, "review_id": e.get("review_id"),
                        "name": e.get("name"), "arguments": e.get("arguments")}
                       for i, e in tool_calls],
    })

    control_counts = Counter()
    for source in control.glob("*.pending.json"):
        control_counts[json.loads(source.read_text(encoding="utf-8")).get("role", "unknown")] += 1
    result = json.loads((trial / "result.json").read_text(encoding="utf-8"))
    reward = result.get("verifier_result") or {}
    def token_sums(records):
        fields = ("input_tokens", "output_tokens", "cache_creation_input_tokens",
                  "cache_read_input_tokens", "cached_input_tokens")
        return {field: sum(r.get(field) or 0 for r in records) for field in fields}
    summary = {
        "run_id": run_id, "condition": slot["condition"], "task": slot["task"],
        "trial_dir": str(trial),
        "trial_outcome": json.loads((run / "manifest.json").read_text(encoding="utf-8")).get("trial_outcome"),
        "started_at": result.get("started_at"), "finished_at": result.get("finished_at"),
        "native_result": reward.get("rewards"),
        "task_provider_requests": Counter(e.get("event_type") for e in task_events).get("provider_request_ready", 0),
        "task_provider_attempts": Counter(e.get("event_type") for e in task_events).get("provider_request_attempt", 0),
        "task_usage_observations": len(usage), "task_tokens_observed": token_sums(usage),
        "monitor_requests": len(monitor_usage), "monitor_provider_attempts": len(attempts),
        "monitor_tokens_observed": token_sums(monitor_usage),
        "monitor_review_count": len(reviews), "monitor_tools": dict(Counter(e.get("name") for _, e in tool_calls)),
        "monitor_intervention_count": len(interventions),
        "monitor_working_mutation_count": Counter(e.get("event") for e in progress).get("dcec_state_mutation", 0),
        "monitor_path_window_count": len(windows),
        "gateway_requests_by_role": dict(control_counts),
        "bridge_capture_present": (bridge / "evidence" / "pre_verification_capture.json").is_file(),
        "verification_release_present": (bridge / "evidence" / "verification_release.json").is_file(),
        "trial_end_binding_present": (bridge / "evidence" / "trial_end_binding.json").is_file(),
    }
    write(destination / "MECHANICAL_SUMMARY.json", summary)
    return summary


def main():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    if len(plan["slots"]) != 4 or [s["run_id"] for s in plan["slots"]] != plan["run_order"]:
        raise RuntimeError("Frozen four-slot order mismatch")
    summaries = [record_one(slot) for slot in plan["slots"]]
    write(PLAN_ROOT / "BLOCK_MECHANICAL_SUMMARY.json", {"records": summaries})
    print(json.dumps({"archived_runs": [s["run_id"] for s in summaries],
                      "record_count": len(summaries)}, indent=2))


if __name__ == "__main__":
    main()
