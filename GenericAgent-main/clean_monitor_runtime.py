"""Process-isolated C3 wiring for the clean Monitor Agent."""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import queue
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

from monitor_agent import MonitorAction


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(dict(value), ensure_ascii=False, default=str) + "\n")


def _intent_synopsis(packet: Mapping[str, Any]) -> str:
    content = str(packet.get("response_content") or "")
    matches = re.findall(r"<summary[^>]*>(.*?)</summary>", content, re.I | re.S)
    text = matches[-1].strip() if matches else content.strip()
    return text[:600]


def _monitor_process(config: dict, commands, outputs) -> None:
    from agent_loop import exhaust
    from llmcore import resolve_client
    from monitor_agent import MonitorAgent
    from monitor_agent_workspace import MonitorWorkspace

    client = resolve_client(config["config_name"])
    if client is None:
        outputs.put({"kind": "failure", "error": "Monitor model configuration is unavailable"})
        return
    workspace = MonitorWorkspace(
        config["evidence_root"], config["private_root"],
        task_mounts={"workspace": config["task_workspace"]},
    )
    monitor = MonitorAgent(client, workspace, max_review_turns=config["max_review_turns"])
    next_wake_turn = 1
    close_watch = False

    def review(context: str, completion: bool = False):
        nonlocal next_wake_turn, close_watch
        try:
            action = exhaust(monitor.review(context, completion_pending=completion))
        except Exception as exc:
            outputs.put({"kind": "failure", "error": repr(exc), "completion": completion})
            return
        if action.kind == "wait":
            close_watch = False
            next_wake_turn = int(context_turn) + max(1, int(action.payload["after_turns"]))
        elif action.kind == "intervene":
            close_watch = True
            next_wake_turn = int(context_turn) + 1
            if not completion:
                outputs.put({
                    "kind": "intervention", "message": action.payload["message"],
                    "cursor": int(context_cursor), "request_id": uuid.uuid4().hex,
                })
        elif action.kind == "allow_complete":
            outputs.put({"kind": "completion", "decision": "allow", "cursor": int(context_cursor)})
        if completion and action.kind != "allow_complete":
            outputs.put({
                "kind": "completion", "decision": "continue", "cursor": int(context_cursor),
                "message": action.payload.get("message", "Continue the task; completion is not yet supported."),
            })

    context_cursor = 0
    context_turn = 0
    review(
        "Turn-zero initialization. Read task/original_task.txt. The chronological navigation stream is "
        "task/synopsis.jsonl; original public events are task/public_events.jsonl; the live workspace, "
        "including tests and artifacts, is task/workspace/. Orient yourself, then choose wait(after_turns)."
    )
    outputs.put({"kind": "ready"})

    while True:
        command = commands.get()
        kind = command.get("kind")
        if kind == "close":
            return
        context_cursor = int(command.get("cursor") or context_cursor)
        context_turn = int(command.get("task_turn") or context_turn)
        if kind == "boundary":
            if close_watch or context_turn >= next_wake_turn:
                review(
                    f"Public task cursor advanced through {context_cursor}. Inspect task/synopsis.jsonl "
                    "from your last position and autonomously retrieve any original evidence needed."
                )
        elif kind == "completion":
            review(
                f"The Task Agent proposes root completion at cursor {context_cursor}. Reconstruct root-task "
                "coverage from the original task and public evidence, then intervene or allow_complete.",
                completion=True,
            )


class CleanMonitorRuntime:
    """Task-side archive, IPC, and immediate interruption delivery."""

    def __init__(self, *, public_task: str, task_workspace: str, artifact_dir: str,
                 config_name: str, interrupt_callback, max_review_turns: int = 20,
                 completion_timeout: float = 300, process_factory=None, worker_target=None):
        self.artifact_dir = Path(artifact_dir).resolve()
        task_workspace = Path(task_workspace).resolve()
        if self.artifact_dir == task_workspace or task_workspace in self.artifact_dir.parents:
            raise ValueError("Monitor artifacts must be outside the supervised task workspace")
        self.evidence_root = self.artifact_dir / "task_evidence"
        self.private_root = self.artifact_dir / "monitor_private"
        self.evidence_root.mkdir(parents=True, exist_ok=True)
        self.private_root.mkdir(parents=True, exist_ok=True)
        (self.evidence_root / "original_task.txt").write_text(public_task, encoding="utf-8")
        self.synopsis_path = self.evidence_root / "synopsis.jsonl"
        self.events_path = self.evidence_root / "public_events.jsonl"
        self._archive_lock = threading.Lock()
        self._sequence = 0
        self._interrupt_callback = interrupt_callback
        self._completion_timeout = max(1.0, float(completion_timeout))
        self._commands = mp.Queue()
        self._outputs = mp.Queue()
        self._completion = queue.Queue()
        self._closed = threading.Event()
        process = process_factory or mp.Process
        self._process = process(target=worker_target or _monitor_process, args=({
            "config_name": config_name,
            "evidence_root": str(self.evidence_root),
            "private_root": str(self.private_root),
            "task_workspace": str(task_workspace),
            "max_review_turns": int(max_review_turns),
        }, self._commands, self._outputs), daemon=True)
        self._process.start()
        self._pump = threading.Thread(target=self._pump_outputs, name="clean-monitor-output", daemon=True)
        self._pump.start()

    def archive_boundary(self, packet: Mapping[str, Any]) -> bool:
        with self._archive_lock:
            self._sequence += 1
            sequence = self._sequence
            raw = dict(packet)
            raw["archive_sequence"] = sequence
            _append_jsonl(self.events_path, raw)
            tool_calls = raw.get("tool_calls") or []
            synopsis = {
                "cursor": sequence,
                "task_turn": raw.get("internal_turn"),
                "boundary": raw.get("boundary"),
                "intent": _intent_synopsis(raw),
                "tool_names": [str(call.get("tool_name") or "") for call in tool_calls],
                "outcome_available": bool(raw.get("tool_results")),
                "raw_event": f"public_events.jsonl#{sequence}",
            }
            _append_jsonl(self.synopsis_path, synopsis)
        self._commands.put({
            "kind": "boundary", "cursor": sequence,
            "task_turn": int(packet.get("internal_turn") or 0),
        })
        return True

    def _pump_outputs(self) -> None:
        while not self._closed.is_set():
            try:
                value = self._outputs.get(timeout=0.1)
            except queue.Empty:
                continue
            kind = value.get("kind")
            if kind == "intervention":
                self._interrupt_callback(value["message"])
            elif kind == "completion" or (kind == "failure" and value.get("completion") is True):
                self._completion.put(value)
            _append_jsonl(self.artifact_dir / "runtime_receipts.jsonl", value)

    def consume_interventions(self) -> list[dict]:
        """Corrections are delivered immediately through the resumable mailbox."""
        return []

    def review_completion(self, proposal, turn, provider_link=None, response_content=None):
        from research_runtime import CompletionDecision

        if not self._process.is_alive():
            return CompletionDecision(
                decision="CONTINUE", reason_codes=("MONITOR_UNAVAILABLE",),
                next_prompt="The completion monitor is unavailable. Continue the task.",
            )
        self._commands.put({"kind": "completion", "cursor": self._sequence})
        try:
            value = self._completion.get(timeout=self._completion_timeout)
        except queue.Empty:
            return CompletionDecision(
                decision="CONTINUE", reason_codes=("MONITOR_TIMEOUT",),
                next_prompt="The completion audit timed out. Continue the task.",
            )
        if value.get("decision") == "allow":
            return CompletionDecision(decision="ALLOW_COMPLETE", reason_codes=("MONITOR_ALLOWED",))
        return CompletionDecision(
            decision="CONTINUE", reason_codes=("MONITOR_CORRECTION",),
            next_prompt=value.get("message") or "Continue the task; completion is not yet supported.",
        )

    def close(self) -> None:
        self._closed.set()
        self._commands.put({"kind": "close"})
        self._process.join(timeout=3)
        if self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=1)
