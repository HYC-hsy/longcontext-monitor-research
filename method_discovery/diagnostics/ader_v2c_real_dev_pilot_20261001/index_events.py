"""Read-only mechanical event locator for the two ADER-v2c development records.

Prints JSON to stdout. It does not classify evidence quality or write to the
scientific archive.
"""

import argparse
import collections
import json
from pathlib import Path


def numbered_jsonl(path):
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            yield line_number, json.loads(line)


def record_index(record):
    audit = record / "agent/monitor/monitor_private/audit"
    dialogue = list(numbered_jsonl(audit / "dialogue.jsonl"))
    progress = list(numbered_jsonl(audit / "progress.jsonl"))
    feedback_path = record / "agent/monitor/monitor_private/delivery_feedback.jsonl"
    feedback = list(numbered_jsonl(feedback_path)) if feedback_path.exists() else []
    calls = {entry[1].get("tool_id"): entry for entry in dialogue if entry[1].get("event") == "tool_call"}
    review_ids = [entry[1]["review_id"] for entry in progress if entry[1].get("event") == "review_started"]
    reviews = []
    for review_id in review_ids:
        pe = [(line, event) for line, event in progress if event.get("review_id") == review_id]
        de = [(line, event) for line, event in dialogue if event.get("review_id") == review_id]
        started = next(({"line": line, **event} for line, event in pe if event.get("event") == "review_started"), None)
        finished = next(({"line": line, **event} for line, event in pe if event.get("event") == "review_finished"), None)
        checkpoints = [
            {"line": line, "request_id": event.get("request_id"), "cursor": event.get("cursor")}
            for line, event in pe if event.get("event") == "root_checkpoint_created"
        ]
        mutations = [
            {"line": line, "operation": event.get("operation"), "sha256": event.get("sha256")}
            for line, event in pe if event.get("event") == "dcec_state_mutation"
        ]
        working_views = [
            {"line": line, "source_sha256": event.get("source_sha256"),
             "visible_characters": event.get("visible_characters"),
             "truncated": event.get("truncated")}
            for line, event in pe if event.get("event") == "dcec_working_view"
        ]
        tool_calls = []
        for line, event in de:
            if event.get("event") != "tool_call":
                continue
            try:
                arguments = json.loads(event.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {"unparsed": event.get("arguments")}
            tool_calls.append({
                "line": line,
                "turn": event.get("turn"),
                "tool_id": event.get("tool_id"),
                "name": event.get("name"),
                "path": arguments.get("path"),
                "start": arguments.get("start"),
                "count": arguments.get("count"),
                "offset": arguments.get("offset"),
                "tail": arguments.get("tail"),
                "code_type": arguments.get("type"),
                "code_script": arguments.get("script") if event.get("name") == "code_run" else None,
            })
        tool_results = []
        for line, event in de:
            if event.get("event") != "tool_result":
                continue
            data = event.get("data") or {}
            if not isinstance(data, dict):
                data = {}
            if data.get("status") == "error" or data.get("exit_code") not in (None, 0):
                prior = calls.get(event.get("tool_id"))
                tool_results.append({
                    "line": line,
                    "call_line": prior[0] if prior else None,
                    "tool_id": event.get("tool_id"),
                    "name": prior[1].get("name") if prior else None,
                    "status": data.get("status"),
                    "exit_code": data.get("exit_code"),
                    "error": data.get("error"),
                })
        runtime_updates = [
            {"line": line, "turn": event.get("turn"), "text": msg.get("content")}
            for line, event in de if event.get("event") == "model_input"
            for msg in event.get("messages", [])
            if isinstance(msg, dict) and "Runtime update:" in str(msg.get("content"))
        ]
        controls = []
        for line, event in de:
            if event.get("event") != "control_result":
                continue
            for result in event.get("results", []):
                try:
                    content = json.loads(result.get("content") or "{}")
                except json.JSONDecodeError:
                    content = {"raw": result.get("content")}
                controls.append({"line": line, "turn": event.get("turn"),
                                 "tool_use_id": result.get("tool_use_id"),
                                 "result": content})
        reviews.append({
            "review_id": review_id,
            "progress_start": started,
            "progress_finish": finished,
            "dialogue_lines": [de[0][0], de[-1][0]] if de else None,
            "model_input_lines": [line for line, event in de if event.get("event") == "model_input"],
            "review_context_lines": [line for line, event in de if event.get("event") == "review_context"],
            "checkpoints": checkpoints,
            "working_mutations": mutations,
            "working_views": working_views,
            "tool_calls": tool_calls,
            "tool_errors": tool_results,
            "runtime_updates": runtime_updates,
            "controls": controls,
        })
    repeated = collections.defaultdict(list)
    for review in reviews:
        for call in review["tool_calls"]:
            if call["name"] == "file_read":
                key = (call["path"], call["start"], call["count"], call["offset"], call["tail"])
                repeated[key].append(call["line"])
    repeated_reads = [
        {"path": key[0], "start": key[1], "count": key[2], "offset": key[3], "tail": key[4], "lines": lines}
        for key, lines in repeated.items() if len(lines) > 1
    ]
    repeated_code = collections.defaultdict(list)
    for review in reviews:
        for call in review["tool_calls"]:
            if call["name"] == "code_run" and call["code_script"]:
                repeated_code[(call["code_type"], call["code_script"])].append(call["line"])
    repeated_scripts = [
        {"type": key[0], "script": key[1], "lines": lines}
        for key, lines in repeated_code.items() if len(lines) > 1
    ]
    return {
        "record": record.name,
        "reviews": reviews,
        "delivery_feedback": [
            {"line": line, "kind": event.get("kind"), "cursor": event.get("cursor"),
             "request_id": event.get("request_id"), "delivery": event.get("delivery"),
             "resumed_completion_requests": event.get("resumed_completion_requests")}
            for line, event in feedback
        ],
        "repeated_exact_file_reads": repeated_reads,
        "repeated_exact_code_scripts": repeated_scripts,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive_root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = json.dumps([record_index(args.archive_root / name) for name in ("r1", "r2")], ensure_ascii=True, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
