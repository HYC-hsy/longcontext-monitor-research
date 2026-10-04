"""Mechanical, opt-in navigation of Task-authored public validation activity."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


GUIDANCE = ("Task-authored tests and results are useful executable interpretations of the public task, "
            "not truth. When relevant to the current choice, inspect their assertion or oracle and exercised "
            "path before widening source investigation. Could a materially wrong implementation get the same "
            "favorable result, or bypass the intended behavior? Follow a discriminating failure that Task is "
            "reasonably repairing; for a weak check, return to the public requirement and relevant implementation "
            "before intervening. No new test is not itself a defect; a local pass supports only its actual reach.")
HEADING = ("Executable Interpretation Surface — Runtime observations only; "
           "candidate executable interpretations, not verdicts or coverage.\n")
INDEX_NAME = "candidate_validation_index.jsonl"
LATEST_NAME = "candidate_validation_latest.json"
SURFACE_LIMIT = 3000
_EXCERPT_LIMIT = 480
_TEST_RUNNER = re.compile(
    r"^(?:go\s+test|pytest(?:\s|$)|python(?:3)?\s+-m\s+pytest|cargo\s+test|"
    r"npm\s+(?:test|run\s+test)|pnpm\s+test|yarn\s+test|ctest(?:\s|$)|"
    r"mvn\s+test|(?:\./)?gradle\s+test)(?:\s|$)", re.I)


def _excerpt(value, limit=_EXCERPT_LIMIT):
    value = str(value).replace("\r", "\\r").replace("\n", "\\n")
    if len(value) <= limit:
        return value
    marker = f" ... [omitted {len(value) - limit} chars; read cited event]"
    return value[:max(0, limit - len(marker))] + marker


def _workspace_path(raw):
    if not isinstance(raw, str):
        return None
    path = raw.replace("\\", "/")
    if path.startswith("/app/"):
        path = path[5:]
    elif path.startswith("task/workspace/"):
        path = path[len("task/workspace/"):]
    elif path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        return None
    parts = path.split("/")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        return None
    return "task/workspace/" + "/".join(parts)


def _test_path(path):
    parts = path.lower().split("/")
    name = parts[-1]
    return ("test" in parts[:-1] or "tests" in parts[:-1] or
            name.endswith(("_test.go", "_test.py")) or name.startswith("test_") and name.endswith(".py") or
            re.search(r"\.(?:test|spec)\.[^.]+$", name) is not None)


def _test_command(script):
    if not isinstance(script, str):
        return False
    # These are shell command boundaries, not a semantic reading of the script.
    return any(_TEST_RUNNER.match(part.strip()) for part in re.split(r"&&|\|\||[;\n]", script))


def _result_payload(result):
    content = result.get("content")
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        return None
    try:
        payload = json.loads(content)
    except (ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def index_public_event(event):
    """Return only paired, mechanically identifiable validation rows from one event."""
    if event.get("boundary") != "post_tool_pre_next_llm":
        return []
    results = {}
    for result in event.get("tool_results") or []:
        if isinstance(result, dict) and isinstance(result.get("tool_use_id"), str):
            results[result["tool_use_id"]] = result
    rows = []
    for call in event.get("tool_calls") or []:
        if not isinstance(call, dict) or not isinstance(call.get("args"), dict):
            continue
        call_id = call.get("id")
        if not isinstance(call_id, str) or call_id not in results:
            continue
        payload = _result_payload(results[call_id])
        if payload is None:
            continue
        name, args = call.get("name"), call["args"]
        shared = {"task_turn": event.get("task_turn"),
                  "archive_sequence": event.get("archive_sequence"),
                  "event_locator": f"task/public_events.jsonl#{event.get('archive_sequence')}",
                  "tool": name, "tool_use_id": call_id}
        if name in {"file_write", "file_patch"} and payload.get("status") == "success":
            path = _workspace_path(args.get("path"))
            if path and _test_path(path):
                authored = args.get("content") if name == "file_write" else args.get("new_content")
                rows.append(dict(shared, kind="task_validation_artifact_change", path=path,
                                 status="success", authored_excerpt=_excerpt(authored or "")))
        elif name == "code_run":
            command = args.get("script")
            if not _test_command(command):
                continue
            # The exit status is for the complete Task command, not an inferred test verdict.
            rows.append(dict(shared, kind="task_validation_execution", command=command,
                             command_key=" ".join(command.split()),
                             status=payload.get("status", "unknown"),
                             exit_code=payload.get("exit_code"),
                             stdout_excerpt=_excerpt(payload.get("stdout") or ""),
                             stderr_excerpt=_excerpt(payload.get("stderr") or "")))
    return rows


def append_index(evidence_root: Path, event):
    rows = index_public_event(event)
    if rows:
        with (evidence_root / INDEX_NAME).open("a", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        # A constant-size pointer to each latest kind avoids a full index scan
        # during every Supervisor request, even after many Task turns.
        latest_path = evidence_root / LATEST_NAME
        try:
            latest = json.loads(latest_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            latest = {}
        for row in rows:
            key = "change" if row["kind"] == "task_validation_artifact_change" else "execution"
            latest[key] = row
        temporary = latest_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(latest, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        os.replace(temporary, latest_path)
    return len(rows)


def _recent_rows(path, cap=128):
    """Read a bounded tail; no full public-event or index scan per review."""
    try:
        with path.open("rb") as stream:
            stream.seek(0, 2)
            end = stream.tell()
            stream.seek(max(0, end - 131072))
            if stream.tell():
                stream.readline()  # discard one potentially partial row
            data = stream.readlines()
    except FileNotFoundError:
        return [], "index_missing"
    except OSError as exc:
        return [], f"index_unavailable:{type(exc).__name__}"
    rows = []
    for raw in data[-cap:]:
        if not raw.endswith(b"\n"):
            continue
        try:
            row = json.loads(raw)
        except (UnicodeError, ValueError):
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows, "complete_index_tail"


def _render_row(label, row, allowance):
    if row["kind"] == "task_validation_artifact_change":
        body = (f"{label}: turn={row['task_turn']} event={row['event_locator']} "
                f"tool={row['tool']} path={row['path']} write_status={row['status']}\n"
                f"authored_excerpt: {row['authored_excerpt']}\n")
    else:
        body = (f"{label}: turn={row['task_turn']} event={row['event_locator']} "
                f"tool={row['tool']} command={_excerpt(row['command'], 600)} "
                f"execution_status={row['status']} exit_code={row['exit_code']}\n"
                f"stdout_excerpt: {row['stdout_excerpt']}\n"
                f"stderr_excerpt: {row['stderr_excerpt']}\n")
    return _excerpt(body, allowance).replace("\\n", "\n")


def executable_interpretation_surface(workspace):
    rows, boundary = _recent_rows(workspace.evidence_root / INDEX_NAME)
    try:
        latest = json.loads((workspace.evidence_root / LATEST_NAME).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        latest = {}
    def newest(key, kind):
        recent = next((row for row in reversed(rows) if row.get("kind") == kind), None)
        saved = latest.get(key)
        if not isinstance(saved, dict):
            return recent
        if recent and (recent.get("archive_sequence") or 0) > (saved.get("archive_sequence") or 0):
            return recent
        return saved

    latest_change = newest("change", "task_validation_artifact_change")
    latest_run = newest("execution", "task_validation_execution")
    selected = [("Latest artifact change", latest_change), ("Latest execution", latest_run)]
    selected = [(label, row) for label, row in selected if row]
    prior_artifact = None
    for _, current in tuple(selected):
        key = "path" if current["kind"] == "task_validation_artifact_change" else "command_key"
        previous = next((row for row in reversed(rows) if row.get("tool_use_id") != current.get("tool_use_id") and
                         row.get("kind") == current["kind"] and row.get(key) == current.get(key) and
                         row.get("archive_sequence") != current.get("archive_sequence")), None)
        if previous:
            selected.append(("Earlier same path/command", previous))
            if current["kind"] == "task_validation_artifact_change":
                prior_artifact = previous
    block = HEADING
    locators = []
    if not selected:
        block += ("No candidate validation activity is recorded in the available index.\n" if boundary == "complete_index_tail"
                  else f"Candidate validation index: {boundary}; original public events remain readable.\n")
    for label, row in selected:
        allowance = min(920, SURFACE_LIMIT - len(block) - 120)
        if allowance <= 0:
            break
        block += _render_row(label, row, allowance)
        locators.append(row["event_locator"])
    if latest_change and prior_artifact:
        block += ("This candidate validation artifact changed again after an earlier recorded version/execution; "
                  "inspect cited events if the semantic change matters.\n")
    block += "Full originals: " + (", ".join(dict.fromkeys(locators)) if locators else "task/public_events.jsonl") + ".\n"
    if len(block) > SURFACE_LIMIT:
        block = block[:SURFACE_LIMIT - 58] + "\n[Surface truncated; read cited original events.]\n"
    return block, {"source": f"task/{INDEX_NAME}", "source_boundary": boundary,
                   "event_locators": list(dict.fromkeys(locators)), "injected_characters": len(block)}
