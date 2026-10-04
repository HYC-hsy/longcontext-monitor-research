"""Mechanical inter-review navigation for one persistent Supervisor.

No test, requirement, relevance, or completion classification is performed here.
"""

from __future__ import annotations

import json
from pathlib import Path

from .root_scope_v1 import task_budget_view


LIMIT = 3400
HEADING = ("Supervisory Situation — mechanical navigation only; statements, file changes "
           "and command results are not correctness verdicts.\n")


def _clip(value, limit):
    value = str(value).replace("\r", "\\r").replace("\n", "\\n")
    if len(value) <= limit:
        return value
    marker = f" ... [{len(value) - limit} chars omitted; read cited original]"
    return value[:max(0, limit - len(marker))] + marker[:limit]


def _result(result):
    content = result.get("content")
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except ValueError:
            return {"raw_result": content}
        return parsed if isinstance(parsed, dict) else {"raw_result": content}
    return {"raw_result": content}


def code_run_outcomes(events):
    """Pair calls and returns by tool identity across the observation interval."""
    by_id = {}
    for event in events:
        locator = f"task/public_events.jsonl#{event.get('archive_sequence')}"
        for call in event.get("tool_calls") or []:
            if not isinstance(call, dict) or call.get("name") != "code_run":
                continue
            args = call.get("args")
            identity = call.get("id")
            if not isinstance(args, dict) or not isinstance(identity, str):
                continue
            if identity not in by_id:
                by_id[identity] = {
                    "task_turn": event.get("task_turn"),
                    "call_event_locator": locator, "result_event_locator": None,
                    "tool_use_id": identity, "command": args.get("script"),
                    "call_args": args, "call_conflicts": [],
                    "result_present": False, "status": "no_return_in_interval",
                    "exit_code": None, "stdout": None, "stderr": None, "raw_result": None,
                }
            elif args != by_id[identity]["call_args"]:
                by_id[identity]["call_conflicts"].append({"event_locator": locator, "args": args})
    for event in events:
        locator = f"task/public_events.jsonl#{event.get('archive_sequence')}"
        for result in event.get("tool_results") or []:
            if not isinstance(result, dict) or not isinstance(result.get("tool_use_id"), str):
                continue
            row = by_id.get(result.get("tool_use_id"))
            if row is None or row["result_present"]:
                continue
            payload = _result(result)
            row.update({"result_event_locator": locator, "result_present": True,
                        "status": payload.get("status", "unknown"),
                        "exit_code": payload.get("exit_code"),
                        "stdout": payload.get("stdout"), "stderr": payload.get("stderr"),
                        "raw_result": payload.get("raw_result")})
    return list(by_id.values())


def render_surface(*, baseline, from_cursor, to_cursor, events, changed, sample_complete,
                   sample_errors, current_event, root_handoff, control, used_turns,
                   max_turns, remaining_seconds, manifest_locator, visible_boundary="complete"):
    """Render a fixed-allocation excerpt; full mechanical facts stay in the manifest."""
    turns = [row.get("task_turn") for row in events if type(row.get("task_turn")) is int]
    turn_range = f"{min(turns)}..{max(turns)}" if turns else "none in interval"
    parts = [HEADING,
             f"Observed baseline={baseline}; interval=({from_cursor}, {to_cursor}]; "
             f"Task turns={turn_range}; public boundary={visible_boundary}.\n",
             task_budget_view(used_turns, max_turns, remaining_seconds) + "\n",
             f"Full mechanical delta: {manifest_locator}; originals: task/public_events.jsonl "
             "and task/workspace/.\n"]
    if current_event is None:
        parts.append("Task statement: no complete public event available.\n")
    else:
        locator = f"task/public_events.jsonl#{current_event.get('archive_sequence')}"
        statement = current_event.get("synopsis") or current_event.get("text") or ""
        parts.append(f"Task statement ({locator}, turn={current_event.get('task_turn')}, "
                     f"boundary={current_event.get('boundary')}): {_clip(statement, 430)}\n")
    if root_handoff:
        parts.append(f"Pending root handoff: generation={root_handoff.get('generation')} "
                     f"request={root_handoff.get('request_id')} "
                     f"event=task/public_events.jsonl#{root_handoff.get('cursor')}.\n")
    else:
        parts.append("Pending root handoff: none at assembly.\n")
    if not sample_complete:
        parts.append("Workspace sample incomplete; path delta unavailable; no unchanged inference. "
                     f"Errors: {_clip(sample_errors, 160)}.\n")
    else:
        total = sum(len(changed.get(kind, [])) for kind in ("added", "modified", "deleted"))
        parts.append(f"Workspace path delta: {total} changed; mechanical facts only.\n")
        shown = 0
        for kind in ("added", "modified", "deleted"):
            for path in changed.get(kind, []):
                if shown >= 12:
                    break
                parts.append(f"{kind}: {_clip(path, 125)}\n")
                shown += 1
        if total > shown:
            parts.append(f"Path view truncated: showing {shown}/{total}; full list in manifest.\n")
    outcomes = code_run_outcomes(events)
    parts.append(f"Task code_run calls in interval: {len(outcomes)} unique tool identities; "
                 "latest up to 3 below. A call without a return in this interval has no "
                 "established outcome here.\n")
    for row in outcomes[-3:]:
        parts.append(f"turn={row['task_turn']} call={row['call_event_locator']} "
                     f"result={row['result_event_locator']} id={row['tool_use_id']} "
                     f"command={_clip(row['command'], 220)} "
                     f"status={row['status']} exit_code={row['exit_code']}\n")
        if row["call_conflicts"]:
            parts.append(f"Conflicting call arguments for this identity: "
                         f"{len(row['call_conflicts'])}; inspect manifest.\n")
        if row["result_present"]:
            parts.append(f"stdout={_clip(row['stdout'] or '', 180)} "
                         f"stderr={_clip(row['stderr'] or '', 140)}\n")
    if len(outcomes) > 3:
        parts.append(f"Command view truncated: showing 3/{len(outcomes)}; full list in manifest.\n")
    if control:
        parts.append(f"Previous supervisory control (mechanical): {_clip(control, 290)}\n")
    else:
        parts.append("Previous supervisory control: none recorded.\n")
    text = "".join(parts)
    if len(text) > LIMIT:
        # Fixed priority preserves interval, budget, original/manifest locators,
        # then clips lower-priority excerpts without changing the underlying facts.
        prefix = "".join(parts[:4])
        tail = "".join(parts[4:])
        allowance = max(0, LIMIT - len(prefix))
        marker = "\n[Surface excerpt truncated; use the cited delta manifest.]"
        text = prefix + tail[:max(0, allowance - len(marker))] + marker[:allowance]
    return text[:LIMIT], outcomes


class SituationState:
    def __init__(self, workspace):
        self.workspace = workspace
        self.committed_cursor = 0
        self.shown_cursor = 0
        self.shown_this_review = False
        self.scan = None
        self.pending = None
        self.offset = 0
        self.events = {}
        self.visible_boundary = "missing"
        self.review_id = None
        self.sequence = 0
        self.last_control = None

    def begin_review(self, review_id):
        self.review_id = review_id
        self.shown_cursor = self.committed_cursor
        self.shown_this_review = False
        self.pending = None

    def end_review(self, action):
        self.committed_cursor = max(self.committed_cursor, self.shown_cursor)
        if action is not None:
            self.last_control = {"kind": action.kind, "payload": action.payload,
                                 "locator": "monitor/audit/reviews.jsonl (latest preceding row)"}
        self.pending = None

    def _read_complete_events(self):
        path = self.workspace.evidence_root / "public_events.jsonl"
        try:
            with path.open("rb") as stream:
                stream.seek(self.offset)
                self.visible_boundary = "complete"
                while True:
                    start = stream.tell()
                    line = stream.readline()
                    if not line:
                        break
                    if not line.endswith(b"\n"):
                        self.visible_boundary = "trailing_partial_line"
                        stream.seek(start)
                        break
                    self.offset = stream.tell()
                    try:
                        row = json.loads(line)
                    except (ValueError, UnicodeError):
                        self.visible_boundary = "unreadable_complete_line"
                        continue
                    if isinstance(row, dict) and type(row.get("archive_sequence")) is int:
                        self.events[row["archive_sequence"]] = row
        except FileNotFoundError:
            self.visible_boundary = "file_missing"
        except OSError as exc:
            self.visible_boundary = f"read_unavailable:{type(exc).__name__}"

    def build(self, *, handoff=None, used_turns=None, max_turns=None, remaining_seconds=None):
        from .runtime import WorkspaceTransitionSampler

        self._read_complete_events()
        current = max(self.events, default=0)
        files, errors = WorkspaceTransitionSampler._scan(self.workspace.task_mounts["workspace"])
        complete = not errors
        changed = {"added": [], "modified": [], "deleted": []}
        if complete and self.scan is not None:
            before = self.scan
            changed = {
                "added": [f"task/workspace/{p}" for p in sorted(files.keys() - before.keys())],
                "modified": [f"task/workspace/{p}" for p in sorted(files.keys() & before.keys())
                             if files[p] != before[p]],
                "deleted": [f"task/workspace/{p}" for p in sorted(before.keys() - files.keys())],
            }
        if self.shown_this_review and current <= self.shown_cursor and not any(changed.values()) and complete:
            self.pending = None
            return f"Situation unchanged through cursor {self.shown_cursor}.", {"unchanged": True}
        interval = [self.events[key] for key in sorted(self.events)
                    if self.shown_cursor < key <= current]
        selected = self.events.get(handoff.get("cursor")) if handoff else self.events.get(current)
        self.sequence += 1
        locator = f"monitor/audit/cfs_deltas/{self.review_id}-{self.sequence:04d}.json"
        control = self.last_control
        feedback = self.workspace.private_root / "delivery_feedback.jsonl"
        if feedback.is_file():
            try:
                lines = [line for line in feedback.read_bytes().splitlines() if line]
                if lines:
                    control = {"previous": control, "latest_delivery": json.loads(lines[-1]),
                               "locator": f"monitor/delivery_feedback.jsonl#{len(lines)}"}
            except (OSError, ValueError, UnicodeError):
                control = {"previous": control, "delivery_read": "unavailable"}
        text, outcomes = render_surface(
            baseline=self.committed_cursor, from_cursor=self.shown_cursor, to_cursor=current,
            events=interval, changed=changed, sample_complete=complete, sample_errors=errors,
            current_event=selected, root_handoff=handoff, control=control,
            used_turns=used_turns, max_turns=max_turns, remaining_seconds=remaining_seconds,
            manifest_locator=locator, visible_boundary=self.visible_boundary)
        manifest = {"review_id": self.review_id, "sequence": self.sequence,
                    "committed_baseline_cursor": self.committed_cursor,
                    "from_cursor": self.shown_cursor, "shown_through_cursor": current,
                    "event_locators": [f"task/public_events.jsonl#{e['archive_sequence']}" for e in interval],
                    "task_turns": [e.get("task_turn") for e in interval],
                    "current_event_locator": (f"task/public_events.jsonl#{selected['archive_sequence']}"
                                              if selected else None), "root_handoff": handoff,
                    "changed_paths": changed, "workspace_sample_complete": complete,
                    "workspace_sample_errors": errors, "code_run_outcomes": outcomes,
                    "control": control, "visible_boundary": self.visible_boundary,
                    "rendered_characters": len(text), "rendered_text": text}
        target = self.workspace.private_root / "audit" / "cfs_deltas" / Path(locator).name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        self.pending = {"cursor": current, "scan": files if complete else None,
                        "manifest_locator": locator, "text": text}
        return text, {"manifest_locator": locator, "shown_through_cursor": current,
                      "rendered_characters": len(text), "unchanged": False}

    def context_appended(self):
        """Called only after this request receives a successful provider response."""
        if self.pending is None:
            return None
        shown = self.pending
        self.shown_cursor = max(self.shown_cursor, shown["cursor"])
        self.shown_this_review = True
        if shown["scan"] is not None:
            self.scan = shown["scan"]
        self.pending = None
        return shown
