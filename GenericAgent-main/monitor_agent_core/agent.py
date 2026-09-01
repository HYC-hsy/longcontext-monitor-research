"""Independent persistent Monitor Agent."""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict

from .actions import MonitorAction, ToolOutcome
from .loop import run_review
from .process_runner import run_analysis
from .workspace import MonitorWorkspace


def _tool(name, description, properties, required):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties,
                       "required": required, "additionalProperties": False},
    }}


MONITOR_TOOLS = [
    _tool("file_read", "Read a bounded range from task/ evidence or monitor/ private files.", {
        "path": {"type": "string"}, "start": {"type": "integer", "minimum": 1, "default": 1},
        "count": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 200},
    }, ["path"]),
    _tool("file_write", "Write only a monitor/ private file.", {
        "path": {"type": "string"}, "content": {"type": "string"},
        "mode": {"type": "string", "enum": ["replace", "append", "prepend"], "default": "replace"},
    }, ["path", "content"]),
    _tool("file_patch", "Replace one exact text span in a monitor/ private file.", {
        "path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"},
    }, ["path", "old_text", "new_text"]),
    _tool("code_run", "Run general analysis in monitor/. A disposable task copy is available at .task_view/.", {
        "code": {"type": "string"},
        "type": {"type": "string", "enum": ["python", "powershell"] if os.name == "nt" else ["python", "bash"], "default": "python"},
        "timeout": {"type": "integer", "minimum": 1, "maximum": 300, "default": 60},
    }, ["code"]),
    _tool("wait", "Remain silent and wake after more public Task Agent turns.", {
        "after_turns": {"type": "integer", "minimum": 1},
    }, ["after_turns"]),
    _tool("intervene", "Interrupt the Task Agent with one natural user-like correction.", {
        "message": {"type": "string", "minLength": 1},
    }, ["message"]),
    _tool("allow_complete", "Allow only the currently pending root completion.", {}, []),
]


MONITOR_SYSTEM_PROMPT = """You are the persistent Monitor Agent for a long-running Task Agent.
Detect material task drift from public evidence, especially omitted requirements and completion claims based
on inadequate evidence. Tests and Agent statements are provisional evidence, never ground truth. At
initialization, read the original task and form your own durable working understanding; use natural private
notes when helpful, without forcing a fixed schema.

On an ordinary wake, continue from your existing history, use the chronological synopsis as navigation, and
retrieve original evidence where it can change the decision. A synopsis is not proof. Pay particular
attention to causal intent, changed tests as executable interpretations of the contract, and local success
being mistaken for root completion. Intervene only for a concrete material discrepancy supported by public
evidence. Explain the conflicting requirement or evidence and what should be re-checked; do not take over the
whole task.

After intervening, remain engaged across the next understanding, intent, action, and result. Intervene again
if the correction is misunderstood or evidence still cannot support the decision. Return to patrol once the
local issue is reasonably resolved; local release is not root completion. Do not verify every unknown, react
to harmless exploration, or impose code-review perfectionism.

Task evidence is read-only under task/. Private cognition is writable under monitor/. Broad analysis starts
in monitor/ and sees a disposable .task_view/. Every review must end by calling exactly one control action:
wait, intervene, or allow_complete (only for a pending root completion). Calling wait is normal silence."""


class MonitorAgent:
    def __init__(self, client, workspace: MonitorWorkspace, max_review_turns=20):
        self.client = client
        self.workspace = workspace
        self.max_review_turns = int(max_review_turns)
        self.completion_pending = False
        self.stop_event = threading.Event()

    def dispatch(self, name: str, arguments: dict) -> ToolOutcome:
        try:
            if name == "file_read":
                data = self.workspace.read_text(
                    arguments["path"], arguments.get("start", 1), arguments.get("count", 200)
                )
            elif name == "file_write":
                data = self.workspace.write_text(
                    arguments["path"], arguments["content"], arguments.get("mode", "replace")
                )
            elif name == "file_patch":
                data = self.workspace.patch_text(
                    arguments["path"], arguments["old_text"], arguments["new_text"]
                )
            elif name == "code_run":
                self.workspace.refresh_snapshot()
                data = run_analysis(
                    arguments["code"], arguments.get("type", "python"),
                    min(300, max(1, int(arguments.get("timeout", 60)))),
                    str(self.workspace.private_root), self.stop_event,
                )
            elif name == "wait":
                return ToolOutcome(None, False, MonitorAction(
                    "wait", {"after_turns": max(1, int(arguments["after_turns"]))}
                ))
            elif name == "intervene":
                message = str(arguments.get("message", "")).strip()
                if not message: raise ValueError("message must not be empty")
                return ToolOutcome(None, False, MonitorAction("intervene", {"message": message}))
            elif name == "allow_complete":
                if not self.completion_pending: raise ValueError("No root completion is pending")
                return ToolOutcome(None, False, MonitorAction("allow_complete", {}))
            else:
                data = {"status": "error", "error": f"Unknown tool: {name}"}
        except Exception as exc:
            data = {"status": "error", "error": str(exc)}
        return ToolOutcome(data)

    def review(self, wake_context: str, completion_pending=False) -> MonitorAction:
        started = time.time()
        before = self.client.history_measure()
        self.completion_pending = bool(completion_pending)
        action = None
        try:
            action = run_review(
                self.client, MONITOR_SYSTEM_PROMPT, wake_context, MONITOR_TOOLS,
                self.dispatch, self.max_review_turns,
            )
            return action
        finally:
            self.workspace.write_text(
                "monitor/audit/reviews.jsonl",
                json.dumps({
                    "started_at": started, "duration_seconds": time.time() - started,
                    "history_before": before, "history_after": self.client.history_measure(),
                    "action": asdict(action) if action else None,
                }, ensure_ascii=False) + "\n", mode="append",
            )
            self.workspace.write_text(
                "monitor/audit/provider_history.json",
                json.dumps(self.client.export_history(), ensure_ascii=False), mode="replace",
            )
