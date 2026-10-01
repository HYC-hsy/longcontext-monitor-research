"""Mechanical locators and counts for two archived runs; no semantic adoption verdict."""

import collections
from datetime import datetime
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2] / "method_discovery/runs/dynamic_observer_v0c_adoption_20261001"
PATTERNS = {
    "possible_pre_result_measurement_text": re.compile(
        r"\b(if|would|versus|vs\.?|distinguish|different result|both states|alternative|contrast)\b", re.I),
    "possible_proxy_or_substitution_text": re.compile(
        r"\b(proxy|insufficient|does not prove|doesn't prove|not enough|unavailable|instead|substitut|cannot run|can't run|build|grep)\b", re.I),
    "possible_ground_transport_text": re.compile(
        r"\b(previous|earlier|still valid|still applies|unchanged|changed|recheck|requalif|reopen|carry|basis|wiring)\b", re.I),
    "possible_root_or_relax_text": re.compile(
        r"\b(complet|overall|whole.task|root|relax|wait|interven|recover)\b", re.I),
    "possible_protocol_creep_text": re.compile(
        r"(?im)^\s*(contrast|measurement|basis|reach|anchor|transport)\s*:"),
}


def numbered(path):
    with path.open(encoding="utf-8") as stream:
        for line, raw in enumerate(stream, 1):
            yield line, json.loads(raw)


def count_usage(rows):
    keys = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
            "cached_input_tokens")
    return {key: sum((row.get(key) or 0) for row in rows) for key in keys}


def record(label):
    directory = ROOT / label
    audit = directory / "agent/monitor/monitor_private/audit"
    dialogue = list(numbered(audit / "dialogue.jsonl"))
    progress = list(numbered(audit / "progress.jsonl"))
    task = list(numbered(directory / "agent/research_events.jsonl"))
    public = list(numbered(directory / "agent/monitor/task_evidence/public_events.jsonl"))
    review_rows = [row for _, row in numbered(audit / "reviews.jsonl")]
    supervisor_attempts = [row for _, row in numbered(audit / "request_attempts.jsonl")]
    supervisor_usage = [row for _, row in numbered(audit / "provider_usage.jsonl")]
    task_usage = [row["payload"] for _, row in task if row["event_type"] == "provider_usage"]
    tools = [(line, row) for line, row in dialogue if row.get("event") == "tool_call"]
    mutations = [(line, row) for line, row in progress if row.get("event") == "dcec_state_mutation"]
    output_lines = [(line, row) for line, row in dialogue if row.get("event") == "model_output"]
    checkpoint_lines = [(line, row) for line, row in progress if row.get("event") == "root_checkpoint_created"]
    proposals = [(line, row) for line, row in task if row.get("event_type") == "completion_proposal"]
    feedback = list(numbered(directory / "agent/monitor/monitor_private/delivery_feedback.jsonl"))
    controls = [(line, row) for line, row in dialogue if row.get("event") == "control_result"]
    results = {row.get("tool_id"): (line, row) for line, row in dialogue if row.get("event") == "tool_result"}

    wording = {kind: [] for kind in PATTERNS}
    for line, row in output_lines:
        body = row.get("content") or ""
        for kind, pattern in PATTERNS.items():
            if pattern.search(body):
                wording[kind].append({"dialogue_line": line, "review_id": row.get("review_id"),
                                      "parent_turn": row.get("turn"), "text": body})

    observations = []
    for line, row in tools:
        if row.get("name") not in ("file_read", "code_run"):
            continue
        try:
            arguments = json.loads(row.get("arguments") or "{}")
        except json.JSONDecodeError:
            arguments = {}
        result = results.get(row.get("tool_id"))
        previous = next(((n, v) for n, v in reversed(output_lines)
                         if v.get("review_id") == row.get("review_id") and v.get("turn") == row.get("turn")
                         and n < line), None)
        observations.append({"call_line": line, "review_id": row.get("review_id"),
                             "parent_turn": row.get("turn"), "tool_use_id": row.get("tool_id"),
                             "tool": row.get("name"), "path": arguments.get("path"),
                             "script": arguments.get("script") if row.get("name") == "code_run" else None,
                             "preceding_model_output_line": previous[0] if previous else None,
                             "result_line": result[0] if result else None})

    task_changes = []
    for line, row in public:
        for call in row.get("tool_calls") or []:
            if call.get("name") not in ("file_write", "file_patch", "code_run"):
                continue
            args = call.get("args") or {}
            task_changes.append({"public_event_line": line, "archive_sequence": row.get("archive_sequence"),
                                 "task_turn": row.get("task_turn"), "tool": call.get("name"),
                                 "path": args.get("path"), "tool_id": call.get("id")})

    heading_hits = []
    for line, row in tools:
        if row.get("name") not in ("file_write", "file_patch"):
            continue
        try:
            args = json.loads(row.get("arguments") or "{}")
        except json.JSONDecodeError:
            continue
        if args.get("path") != "monitor/working.md":
            continue
        body = json.dumps(args, ensure_ascii=False)
        if PATTERNS["possible_protocol_creep_text"].search(body.replace("\\n", "\n")):
            heading_hits.append({"dialogue_line": line, "tool_use_id": row.get("tool_id")})

    result_status = collections.Counter()
    for _, row in dialogue:
        if row.get("event") == "tool_result" and isinstance(row.get("data"), dict):
            status = row["data"].get("status")
            if status:
                result_status[status] += 1
    task_events = collections.Counter(row.get("event_type") for _, row in task)
    tool_counts = collections.Counter(row.get("name") for _, row in tools)
    follow_modes = collections.Counter((row.get("action") or {}).get("payload", {}).get("mode")
                                       for row in review_rows if (row.get("action") or {}).get("kind") == "wait")
    proof = json.loads((directory / "proof/manifest.json").read_text(encoding="utf-8"))
    source = json.loads((directory / "source_identity/source_identity.json").read_text(encoding="utf-8"))
    task_times = [datetime.fromisoformat(row["timestamp"]) for _, row in task if row.get("timestamp")]

    facts = {
        "run_id": proof["run_id"], "task": proof["agent_protocol"]["task_id"],
        "source_commit": source["commit"], "source_tree": source["source_tree"],
        "source_archive_sha256": source["git_archive_sha256"],
        "task_tree_sha256": proof["source_identity"]["task_tree_sha256"],
        "image_id": proof["source_identity"]["image"]["image_id"],
        "task_profile_sha256": source["task_profile_sha256"],
        "supervisor_profile_sha256": source["monitor_profile_sha256"],
        "task_requests_ready": task_events["provider_request_ready"],
        "task_provider_attempts": task_events["provider_request_attempt"],
        "task_usage": count_usage(task_usage),
        "supervisor_requests": len(supervisor_usage),
        "supervisor_attempts": len(supervisor_attempts),
        "supervisor_attempt_outcomes": dict(collections.Counter(r.get("outcome") for r in supervisor_attempts)),
        "supervisor_usage": count_usage(supervisor_usage),
        "supervisor_tool_calls": dict(tool_counts),
        "interventions": tool_counts["intervene"],
        "completion_proposals": len(proposals),
        "working_mutations": len(mutations),
        "working_mutation_chars": [row.get("characters") for _, row in mutations],
        "working_max_chars": max((row.get("characters") or 0 for _, row in mutations), default=0),
        "review_count": len(review_rows), "wait_modes": dict(follow_modes),
        "tool_result_statuses": dict(result_status),
        "online_task_event_span_seconds": (max(task_times) - min(task_times)).total_seconds() if task_times else None,
        "trial_outcome": proof["trial_outcome"], "infra_validation_errors": proof["validation_errors"],
        "terminal_reward_separate": proof.get("rewards"),
    }
    index = {
        "record": label,
        "raw_roots": {"dialogue": str(audit / "dialogue.jsonl"),
                      "progress": str(audit / "progress.jsonl"),
                      "public_events": str(directory / "agent/monitor/task_evidence/public_events.jsonl")},
        "wording_search_hits_not_adoption_verdicts": wording,
        "all_observation_calls_with_preceding_output_and_result": observations,
        "task_mutating_or_code_calls_to_inspect_for_world_transitions": task_changes,
        "working_mutations": [{"progress_line": line, "review_id": row.get("review_id"),
                               "operation": row.get("operation"), "characters": row.get("characters"),
                               "sha256": row.get("sha256")} for line, row in mutations],
        "fixed_heading_candidates_in_working_tool_arguments": heading_hits,
        "completion_proposals": [{"research_event_line": line, "event_id": row.get("event_id"),
                                  "payload": row.get("payload")} for line, row in proposals],
        "root_checkpoints": [{"progress_line": line, "review_id": row.get("review_id"),
                              "request_id": row.get("request_id"), "cursor": row.get("cursor")}
                             for line, row in checkpoint_lines],
        "control_results": [{"dialogue_line": line, "review_id": row.get("review_id"),
                             "turn": row.get("turn"), "results": row.get("results")} for line, row in controls],
        "delivery_feedback": [{"line": line, **row} for line, row in feedback],
    }
    return facts, index


def main():
    all_facts, all_indices = {}, {}
    for label in ("r1", "r2"):
        all_facts[label], all_indices[label] = record(label)
    (ROOT / "RUN_FACTS.json").write_text(json.dumps(all_facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "ADOPTION_LOCATOR_INDEX.json").write_text(
        json.dumps(all_indices, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: {"supervisor_requests": row["supervisor_requests"],
                            "working_mutations": row["working_mutations"]}
                      for key, row in all_facts.items()}))


if __name__ == "__main__":
    main()
