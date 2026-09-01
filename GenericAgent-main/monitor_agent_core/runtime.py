"""Process-isolated runtime owned by Monitor Agent."""

from __future__ import annotations

import json
import multiprocessing as mp
import queue
import re
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class CompletionOutcome:
    allow: bool
    message: str = ""
    reason: str = ""


def _append(path: Path, value: Mapping[str, Any]):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(dict(value), ensure_ascii=False, default=str) + "\n")


def _synopsis(packet):
    content = str(packet.get("response_content") or "")
    matches = re.findall(r"<summary[^>]*>(.*?)</summary>", content, re.I | re.S)
    return (matches[-1].strip() if matches else content.strip())[:600]


def _worker(config, commands, outputs):
    from .agent import MonitorAgent
    from .provider import MonitorProviderClient
    from .workspace import MonitorWorkspace

    try:
        client = MonitorProviderClient(config["config_name"], config["model_config"])
        workspace = MonitorWorkspace(
            config["evidence_root"], config["private_root"],
            task_mounts={"workspace": config["task_workspace"]},
        )
        history_path = Path(config["private_root"]) / "audit" / "provider_history.json"
        if history_path.is_file():
            client.restore_history(json.loads(history_path.read_text(encoding="utf-8")))
        monitor = MonitorAgent(client, workspace, config["max_review_turns"])
    except Exception as exc:
        outputs.put({"kind": "failure", "error": repr(exc), "phase": "startup"})
        return

    next_wake_turn = 1
    close_watch = False
    cursor = 0
    task_turn = 0

    def review(context, completion=False):
        nonlocal next_wake_turn, close_watch
        try:
            action = monitor.review(context, completion_pending=completion)
        except Exception as exc:
            outputs.put({"kind": "failure", "error": repr(exc), "completion": completion})
            return
        if action.kind == "wait":
            close_watch = False
            next_wake_turn = task_turn + max(1, int(action.payload["after_turns"]))
        elif action.kind == "intervene":
            close_watch = True
            next_wake_turn = task_turn + 1
            if not completion:
                outputs.put({
                    "kind": "intervention", "message": action.payload["message"],
                    "cursor": cursor, "request_id": uuid.uuid4().hex,
                })
        elif action.kind == "allow_complete":
            outputs.put({"kind": "completion", "decision": "allow", "cursor": cursor})
        if completion and action.kind != "allow_complete":
            outputs.put({
                "kind": "completion", "decision": "continue", "cursor": cursor,
                "message": action.payload.get("message", "Continue; completion is not yet supported."),
            })

    review(
        "Turn-zero initialization. Read task/original_task.txt. Use task/synopsis.jsonl for chronological "
        "navigation, task/public_events.jsonl for original public events, and task/workspace/ for live tests, "
        "code, diffs, and artifacts. Orient yourself, then choose wait(after_turns)."
    )
    outputs.put({"kind": "ready"})
    while True:
        command = commands.get()
        kind = command.get("kind")
        if kind == "close": return
        cursor = int(command.get("cursor") or cursor)
        task_turn = int(command.get("task_turn") or task_turn)
        if kind == "boundary" and (close_watch or task_turn >= next_wake_turn):
            review(
                f"Public task cursor advanced through {cursor}. Continue from your existing history, inspect "
                "new synopsis rows, and retrieve original evidence wherever it can change your decision."
            )
        elif kind == "completion":
            review(
                f"The Task Agent proposes root completion at cursor {cursor}. Reconstruct root coverage from "
                "the original task and public evidence, then intervene or allow_complete.", completion=True,
            )


class MonitorRuntime:
    def __init__(self, *, public_task, task_workspace, artifact_dir, config_name,
                 model_config, interrupt_callback, max_review_turns=20,
                 completion_timeout=300, process_factory=None, worker_target=None):
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
        self._context = mp.get_context("spawn")
        self._commands = self._context.Queue()
        self._outputs = self._context.Queue()
        self._completion = queue.Queue()
        self._closed = threading.Event()
        process = process_factory or self._context.Process
        self._process = process(target=worker_target or _worker, args=({
            "config_name": config_name, "model_config": dict(model_config),
            "evidence_root": str(self.evidence_root), "private_root": str(self.private_root),
            "task_workspace": str(task_workspace), "max_review_turns": int(max_review_turns),
        }, self._commands, self._outputs), daemon=True)
        self._process.start()
        self._pump = threading.Thread(target=self._pump_outputs, daemon=True, name="monitor-output")
        self._pump.start()

    def _archive(self, packet):
        with self._archive_lock:
            self._sequence += 1
            sequence = self._sequence
            raw = dict(packet, archive_sequence=sequence)
            _append(self.events_path, raw)
            calls = raw.get("tool_calls") or []
            _append(self.synopsis_path, {
                "cursor": sequence, "task_turn": raw.get("internal_turn"),
                "boundary": raw.get("boundary"), "intent": _synopsis(raw),
                "tool_names": [str(call.get("tool_name") or "") for call in calls],
                "outcome_available": bool(raw.get("tool_results")),
                "raw_event": f"public_events.jsonl#{sequence}",
            })
        return sequence

    def archive_boundary(self, packet):
        sequence = self._archive(packet)
        self._commands.put({
            "kind": "boundary", "cursor": sequence,
            "task_turn": int(packet.get("internal_turn") or 0),
        })
        return True

    def _pump_outputs(self):
        while not self._closed.is_set():
            try: value = self._outputs.get(timeout=0.1)
            except queue.Empty: continue
            kind = value.get("kind")
            if kind == "intervention": self._interrupt_callback(value["message"])
            elif kind == "completion" or (kind == "failure" and value.get("completion") is True):
                self._completion.put(value)
            _append(self.artifact_dir / "runtime_receipts.jsonl", value)

    def request_completion(self, public_event=None) -> CompletionOutcome:
        if not self._process.is_alive():
            return CompletionOutcome(False, "The completion monitor is unavailable. Continue the task.", "unavailable")
        cursor = self._archive(public_event) if public_event else self._sequence
        self._commands.put({"kind": "completion", "cursor": cursor})
        try: value = self._completion.get(timeout=self._completion_timeout)
        except queue.Empty:
            return CompletionOutcome(False, "The completion audit timed out. Continue the task.", "timeout")
        if value.get("decision") == "allow": return CompletionOutcome(True, reason="monitor_allowed")
        return CompletionOutcome(False, value.get("message") or "Continue the task.", "monitor_correction")

    def close(self):
        self._closed.set()
        self._commands.put({"kind": "close"})
        self._process.join(timeout=3)
        if self._process.is_alive():
            self._process.terminate(); self._process.join(timeout=1)
