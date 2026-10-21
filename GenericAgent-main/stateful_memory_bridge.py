"""Fake-only GA host adapter for stateful proactive memory v1.

No provider or credential discovery exists here. The core and its SQLite
store remain in the method package; this module maps actual GA boundaries.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


class StatefulBridgeError(RuntimeError):
    pass


def _leaf(text, source_id, event_id, path, kind, turn, seq):
    return {"source_id": source_id, "event_id": event_id, "field_path": path,
        "source_kind": kind, "ga_turn": turn, "event_seq": seq,
        "truncated": False, "text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}


class StatefulMemoryBridge:
    def __init__(self, *, store, provider, task, episode_id):
        from method_discovery.pma_stateful_memory_v1_20261021.engine import CycleEngine
        self.store, self.provider = store, provider
        self.engine = CycleEngine(store, provider, task_text=task)
        self.episode_id = episode_id
        self.pending = None
        self.closed = False
        self.results = []

    @classmethod
    def from_environment(cls, task, *, turn_offset=0):
        from method_discovery.pma_stateful_memory_v1_20261021.ga_fake_provider import FiniteGAFakeProvider
        from method_discovery.pma_stateful_memory_v1_20261021.source import ContractError
        from method_discovery.pma_stateful_memory_v1_20261021.store import MemoryStore
        if turn_offset != 0:
            raise StatefulBridgeError("stateful memory requires a fresh GA episode")
        if (os.environ.get("GA_STATEFUL_MEMORY_MODE") != "fake-only" or
                os.environ.get("GA_STATEFUL_MEMORY_ENABLED") != "1"):
            raise StatefulBridgeError("stateful memory is fake-only in this stage")
        required = ("GA_STATEFUL_MEMORY_DB", "GA_STATEFUL_FAKE_REPLIES",
                    "GA_BENCH_RUN_ID", "GA_BENCH_TASK_ID")
        if any(not os.environ.get(name) for name in required):
            raise StatefulBridgeError("stateful fake identity or replies missing")
        db = Path(os.environ["GA_STATEFUL_MEMORY_DB"])
        if db.exists():
            raise StatefulBridgeError("stateful fake episode must use a new store")
        provider = FiniteGAFakeProvider.from_file(os.environ["GA_STATEFUL_FAKE_REPLIES"])
        store = MemoryStore(db)
        episode_id = os.environ["GA_BENCH_RUN_ID"]
        task_id = os.environ["GA_BENCH_TASK_ID"]
        try:
            task_source = _leaf(task, "initial-task", "initial-task",
                                "initial_user_content", "user_requirement", 0, 0)
            snapshot = {"schema_version": "stateful-proactive-memory/1",
                "task_id": task_id, "episode_id": episode_id,
                "state_version": 0, "committed_event_seq": 0,
                "B": {"G": {"task_version": 1, "original_user_sources": [{
                    "source_id": "initial-task", "start": 0, "end": len(task),
                    "quote": task}], "specifications": [], "goal_deltas": []},
                    "W": {"entities": [], "states": [], "relations": []},
                    "DeltaE": [], "DeltaA": [], "F": None}}
            store.initialize(snapshot, task_source)
            bridge = cls(store=store, provider=provider, task=task,
                         episode_id=episode_id)
            first = bridge.engine.run("initial")
            bridge.results.append(first)
            if not first["status"].startswith("committed_"):
                raise StatefulBridgeError("init_failed: " + first["status"])
            bridge._take_reminder(first)
            return bridge
        except BaseException:
            store.close()
            raise

    def _take_reminder(self, result):
        if result["status"] != "committed_reminder_ready":
            self.pending = None
            return
        reminder = result["reminder"]
        if (self.store.delivery_result(reminder["reminder_id"]) is not None or
                self.store.delivery_attempt_cycles(reminder["reminder_id"])):
            self.pending = None
            return
        self.pending = (result["cycle_id"], reminder)

    def record_incomplete(self, turn, reason, action_ids=()):
        self.store.journal("host-" + self.episode_id, "incomplete_batch",
            {"turn": turn, "reason": reason, "action_ids": list(action_ids)})

    def record_report(self, turn, content):
        if not content:
            return
        event_id = f"ga-agent-report-{self.episode_id}-{turn}"
        prior = next((row for row in self.store.events_after(0) if
                      row["event_id"] == event_id), None)
        seq = prior["event_seq"] if prior else len(self.store.events_after(0)) + 1
        source = _leaf(content, event_id + "/text", event_id,
                       "assistant.content", "agent_report", turn, seq)
        self.store.append_event({"event_id": event_id, "event_seq": seq,
            "kind": "agent_report", "occurred_at_step": turn,
            "source_ids": [source["source_id"]], "payload": {}}, [source])

    def complete_batch(self, turn, actions, receipts):
        from method_discovery.pma_stateful_memory_v1_20261021.source import canonical
        if not actions:
            return None
        if (len(actions) != len(receipts) or any(not action.get("id") for action in actions)
                or [action["id"] for action in actions] !=
                   [receipt["tool_use_id"] for receipt in receipts]):
            self.record_incomplete(turn, "missing_or_unpaired_result",
                                   [action.get("id", "") for action in actions])
            raise StatefulBridgeError("incomplete GA action batch")
        event_id = f"ga-action-batch-{self.episode_id}-{turn}"
        prior = next((row for row in self.store.events_after(0) if
                      row["event_id"] == event_id), None)
        seq = prior["event_seq"] if prior else len(self.store.events_after(0)) + 1
        leaves = []
        for action, receipt in zip(actions, receipts):
            tool_id = action["id"]
            source_event_id = f"{event_id}/{tool_id}"
            action_text = canonical({"name": action["name"],
                                     "arguments": action["arguments"]}).decode("utf-8")
            result_text = canonical({"status": receipt["status"],
                                     "result": receipt["result"]}).decode("utf-8")
            leaves.extend((_leaf(action_text, f"{event_id}/{tool_id}/action",
                                 source_event_id, f"tools.{tool_id}.arguments", "executed_action", turn, seq),
                           _leaf(result_text, f"{event_id}/{tool_id}/result",
                                 source_event_id, f"tools.{tool_id}.result", "tool_result", turn, seq)))
        event = {"event_id": event_id, "event_seq": seq, "kind": "action_batch",
            "occurred_at_step": turn,
            "source_ids": [leaf["source_id"] for leaf in leaves],
            "payload": {"actions": [{"tool_use_id": f"{event_id}/{action['id']}",
                                    "ga_tool_use_id": action["id"]}
                                    for action in actions]}}
        self.store.append_event(event, leaves)
        result = self.engine.run(event_id)
        self.results.append(result)
        self._take_reminder(result)
        if result.get("error_code") in {"fake_script_exhausted", "fake_role_mismatch",
                                        "fake_shape_mismatch", "fake_observation_missing"}:
            raise StatefulBridgeError(result["error_code"])
        return result

    def chat(self, client, messages, tools, turn):
        """Drive one GA chat generator; a prepared generator is not delivery."""
        if self.pending is None:
            return (yield from client.chat(messages=messages, tools=tools))
        from method_discovery.pma_stateful_memory_v1_20261021.reminder import attach_once
        cycle_id, reminder = self.pending
        request_id = f"task-{self.episode_id}-{turn}"
        chunks = []
        def send(payload):
            generator = client.chat(messages=payload, tools=tools)
            self.store.journal(cycle_id, "task_transport_attempt",
                               {"request_id": request_id})
            try:
                while True:
                    try:
                        chunks.append(next(generator))
                    except StopIteration as done:
                        response = done.value
                        break
            finally:
                generator.close()
            if not getattr(response, "complete_response_accepted", False):
                raise StatefulBridgeError("Task response not completely accepted")
            self.store.journal(cycle_id, "task_response_accepted",
                               {"request_id": request_id})
            return {"accepted": True, "response": response}
        receipt = attach_once(store=self.store, reminder=reminder,
            task_messages=messages, request_id=request_id, cycle_id=cycle_id,
            send=send)
        self.pending = None
        for chunk in chunks:
            yield chunk
        return receipt["response"]

    def finish(self, terminal):
        if self.closed:
            return
        try:
            pending = self.store.events_after(self.store.snapshot()["committed_event_seq"])
            self.store.journal("host-" + self.episode_id, "task_terminal", {
                "terminal": terminal, "pending_event_ids": [e["event_id"] for e in pending]})
        finally:
            self.closed = True
            self.store.close()
