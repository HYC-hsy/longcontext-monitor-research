"""Mechanical input for one pending root handoff; no semantic verdicts."""

from __future__ import annotations

import json
import time
from pathlib import Path


ROOT_SYSTEM_PROMPT = """You are handling the Task Agent's current handoff for the full public task. Determine whether useful work should continue, a question or blocker needs an answer, or completion is adequately supported.

Start from the public requirements and current artifacts. Historical corrections, execution outcomes, and earlier judgments are evidence to interpret, not a whole-task verdict. A repaired local issue supports its own scope. Consider material integration effects and whether the observations actually distinguish the required behavior from an incomplete or incorrect implementation.

Use the existing tools directly. Inspect original requirements and actual code or execution results where they can change the decision. Reuse adequate evidence whose basis still applies. Do not require a coverage form, exhaustive testing, or investigation of every unknown.

Send a concrete correction or answer when warranted. An intervention ends this pending handoff and the Task can continue. Allow completion when the public task is adequately supported. Budget exhaustion does not establish completion."""

ROOT_NOTE_GUIDANCE = (
    "Current private root working note. This is your revisable interpretation, not verified truth "
    "or a replacement for public evidence. No fixed form or per-request rewrite is required."
)


def _complete_rows(path: Path):
    """Read complete JSONL rows only; report a partial trailing line explicitly."""
    if not path.is_file():
        return [], "missing"
    raw = path.read_bytes()
    complete = raw.endswith(b"\n") or not raw
    rows = []
    for line in raw.split(b"\n")[:-1] if not complete else raw.splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except (ValueError, UnicodeDecodeError):
            return rows, "invalid_complete_row"
    return rows, "complete" if complete else "partial_trailing_line_omitted"


def _excerpt(value, limit=700):
    text = json.dumps(value, ensure_ascii=False, default=str) if not isinstance(value, str) else value
    if len(text) <= limit:
        return text
    return text[:limit] + f" [excerpt; {len(text) - limit} characters omitted; read cited original]"


def root_input(workspace, handoff, *, remaining_seconds=None):
    """Build the same source-indexed root input for both modes."""
    task = workspace.resolve_read("task/original_task.txt").read_text(encoding="utf-8")
    cursor = handoff["cursor"]
    rows, event_status = _complete_rows(workspace.evidence_root / "public_events.jsonl")
    event = next((row for row in rows if row.get("archive_sequence") == cursor), None)
    if event is None:
        raise ValueError("Current handoff event is not present in complete public records")
    parts = [
        "Root decision input for the current pending handoff.",
        f"Handoff identity: generation={handoff['generation']}; request_id={handoff['request_id']}; "
        f"task/public_events.jsonl archive_sequence={cursor}; file_status={event_status}.",
        "Full public task (task/original_task.txt):\n" + task,
        "Current handoff original public event (task/public_events.jsonl):\n" +
        json.dumps(event, ensure_ascii=False, default=str),
        "Current live source: task/workspace/. Read actual files and execution evidence with existing tools.",
        "Original evidence locations: task/public_events.jsonl; task/synopsis.jsonl; "
        "monitor/audit/dialogue.jsonl; monitor/audit/provider_history.json; "
        "monitor/audit/root_frames/; monitor/root_working/; monitor/delivery_feedback.jsonl; "
        "monitor/audit/progress.jsonl; monitor/audit/request_attempts.jsonl. "
        "These records include observations and prior root investigations; use the originals when needed.",
    ]
    result_rows = [(index, row) for index, row in enumerate(rows, 1)
                   if row.get('tool_results')]
    parts.append(f"Public records with tool returns: {len(result_rows)}; "
                 "the two latest complete examples follow, with each event's calls and returns kept together.")
    for index, row in result_rows[-2:]:
        paired = {key: row.get(key) for key in (
            'archive_sequence', 'task_turn', 'boundary', 'tool_calls', 'tool_results')}
        parts.append(f"  task/public_events.jsonl row {index}: {_excerpt(paired, 1400)}")
    for label, path in (
        ("Actual interventions and delivery receipts", workspace.private_root / "delivery_feedback.jsonl"),
        ("Execution and control observations", workspace.private_root / "audit" / "dialogue.jsonl"),
        ("Provider attempts and failures", workspace.private_root / "audit" / "request_attempts.jsonl"),
    ):
        records, status = _complete_rows(path)
        parts.append(f"{label}: monitor/{path.relative_to(workspace.private_root).as_posix()}; "
                     f"complete_rows={len(records)}; status={status}.")
        for index, row in list(enumerate(records, 1))[-2:]:
            parts.append(f"  row {index}: {_excerpt(row)}")
    parts.append(
        "Excerpts above are not a complete history. Earlier rows and full results remain at the "
        "cited paths. A past correction or failure is not automatically a current defect; a successful "
        "exit code does not alone establish required behavior."
    )
    parts.append("Remaining shared run budget at frame entry: " +
                 (f"{max(0, int(remaining_seconds))} seconds." if remaining_seconds is not None else "unavailable."))
    return "\n\n".join(parts)
