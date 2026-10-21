"""Private stateful-memory worker on the existing Harbor event spool.

The Task process receives only reminder text and binding receipts. The bank,
candidate/audit records, auxiliary profile and raw role logs stay host-side.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import time

from event_spool import EventDispatcher


def _durable(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


class StatefulEpisode:
    def __init__(self, *, run_id: str, task_id: str, archive: Path,
                 private: Path, provider):
        self.run_id, self.task_id = run_id, task_id
        self.archive, self.private, self.provider = archive, private, provider
        self.bridge = None
        self.sequence = 0
        self.business = {}

    def _one_business_event(self, event: dict, identity: str, action):
        from method_discovery.pma_stateful_memory_v1_20261021.source import digest
        key = (event["kind"], identity)
        body = {key: value for key, value in event.items() if key not in
                {"schema", "run_id", "task_id", "sequence", "event_id"}}
        fingerprint = digest(body)
        prior = self.business.get(key)
        if prior is not None:
            if prior[0] != fingerprint:
                raise ValueError("stateful business identity conflict")
            return prior[1]
        result = action()
        self.business[key] = (fingerprint, result)
        return result

    def _initialize(self, task: str):
        from method_discovery.pma_stateful_memory_v1_20261021.store import MemoryStore
        from stateful_memory_bridge import StatefulMemoryBridge, StatefulBridgeError, _leaf
        if self.bridge is not None or not isinstance(task, str) or not task:
            raise ValueError("stateful episode initialization invalid")
        db = self.private / "memory.sqlite3"
        if db.exists():
            raise ValueError("stateful episode database already exists")
        store = MemoryStore(db)
        try:
            task_source = _leaf(task, "initial-task", "initial-task",
                "initial_user_content", "user_requirement", 0, 0)
            snapshot = {"schema_version": "stateful-proactive-memory/1",
                "task_id": self.task_id, "episode_id": self.run_id,
                "state_version": 0, "committed_event_seq": 0,
                "B": {"G": {"task_version": 1, "original_user_sources": [{
                    "source_id": "initial-task", "start": 0, "end": len(task),
                    "quote": task}], "specifications": [], "goal_deltas": []},
                    "W": {"entities": [], "states": [], "relations": []},
                    "DeltaE": [], "DeltaA": [], "F": None}}
            store.initialize(snapshot, task_source)
            bridge = StatefulMemoryBridge(store=store, provider=self.provider,
                task=task, episode_id=self.run_id)
            first = bridge.engine.run("initial")
            bridge.results.append(first)
            if not first["status"].startswith("committed_"):
                raise StatefulBridgeError("init_failed: " + first["status"])
            bridge._take_reminder(first)
            self.bridge = bridge
            return {"status": first["status"],
                    "pending_reminder": bridge.pending is not None,
                    "state_version": store.snapshot()["state_version"]}
        except BaseException:
            store.close()
            raise

    def _handle(self, event: dict) -> dict:
        kind = event["kind"]
        if kind == "initialize":
            return self._one_business_event(event, "initial", lambda:
                self._initialize(event.get("task")))
        bridge = self.bridge
        if bridge is None:
            raise ValueError("stateful episode not initialized")
        if kind == "action_batch":
            def complete():
                result = bridge.complete_batch(event["turn"], event["actions"],
                                               event["receipts"])
                if result["status"] == "runtime_failed":
                    raise RuntimeError("stateful update runtime failed: " +
                                       result.get("error_code", "unknown"))
                return {"status": result["status"], "cycle_id": result["cycle_id"],
                        "pending_reminder": bridge.pending is not None,
                        "state_version": bridge.store.snapshot()["state_version"]}
            return self._one_business_event(event, event["batch_id"], complete)
        if kind == "incomplete_batch":
            def record():
                bridge.record_incomplete(event["turn"], event["reason"],
                    event.get("actions", []), event.get("receipts", []),
                    started_unknown_ids=event.get("started_unknown_ids", []),
                    not_executed_ids=event.get("not_executed_ids", []),
                    terminal=event.get("terminal"),
                    error_type=event.get("error_type"))
                return {"recorded": True}
            return self._one_business_event(event, event["batch_id"], record)
        if kind == "agent_report":
            return self._one_business_event(event, str(event["turn"]), lambda:
                (bridge.record_report(event["turn"], event["content"]) or
                 {"recorded": True}))
        if kind == "prepare_task":
            if bridge.pending is None:
                return {"has_reminder": False}
            from method_discovery.pma_stateful_memory_v1_20261021.reminder import begin_delivery
            cycle_id, reminder = bridge.pending
            prepared = begin_delivery(store=bridge.store, reminder=reminder,
                task_messages=event["messages"], request_id=event["request_id"],
                cycle_id=cycle_id)
            return {"has_reminder": True, "cycle_id": cycle_id,
                    "messages": prepared["messages"],
                    "binding": prepared["binding"]}
        if kind == "confirm_task":
            from method_discovery.pma_stateful_memory_v1_20261021.reminder import confirm_delivery
            confirm_delivery(store=bridge.store, cycle_id=event["cycle_id"],
                binding=event["binding"], accepted=event["accepted"])
            bridge.pending = None
            return {"confirmed": True}
        if kind == "finish":
            return self._one_business_event(event, "terminal", lambda:
                self._finish(event["terminal"]))
        raise ValueError("unsupported stateful event kind")

    def _finish(self, terminal):
        self.bridge.finish(terminal)
        return {"closed": self.bridge.closed, "cycle_count": len(self.bridge.results)}

    async def handle(self, event: dict) -> dict:
        if event.get("sequence") != self.sequence + 1:
            raise ValueError("stateful spool sequence mismatch")
        self.sequence += 1
        _durable(self.archive / "events.jsonl", {"sequence": self.sequence,
            "event_id": event["event_id"], "kind": event["kind"],
            "business_id": event.get("batch_id", event.get("request_id"))})
        try:
            result = self._handle(event)
        except BaseException as error:
            _durable(self.archive / "failures.jsonl", {"sequence": self.sequence,
                "event_id": event["event_id"], "kind": event["kind"],
                "error_type": type(error).__name__})
            raise
        return result


async def serve(args) -> None:
    private = Path(args.private_root).resolve()
    requests = Path(args.requests).resolve(strict=True)
    responses = Path(args.responses).resolve(strict=True)
    if private.exists() or private.is_relative_to(requests.parent):
        raise RuntimeError("stateful host-private/spool boundary invalid")
    private.mkdir(parents=True)
    archive = private / "archive"
    archive.mkdir()
    if args.fake_replies:
        from method_discovery.pma_stateful_memory_v1_20261021.ga_fake_provider import FiniteGAFakeProvider
        provider = FiniteGAFakeProvider.from_file(args.fake_replies)
        mode = "fake-only"
    else:
        raise RuntimeError("live auxiliary provider is not yet configured")
    episode = StatefulEpisode(run_id=args.run_id, task_id=args.task_id,
        archive=archive, private=private, provider=provider)
    dispatcher = EventDispatcher(episode, requests, responses)
    (private / "worker_ready.json").write_text(json.dumps({
        "run_id": args.run_id, "task_id": args.task_id,
        "research_candidate": "pma_stateful_memory_v1", "mode": mode},
        sort_keys=True), encoding="utf-8")
    reason = "host_stop"
    try:
        while not (private / "stop.request").exists():
            await dispatcher.serve_once()
            await asyncio.sleep(.05)
    except BaseException:
        reason = "worker_exception"
        raise
    finally:
        (private / "worker_exit.json").write_text(json.dumps({
            "run_id": args.run_id, "task_id": args.task_id,
            "reason": reason, "last_sequence": episode.sequence},
            sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--requests", required=True)
    parser.add_argument("--responses", required=True)
    parser.add_argument("--fake-replies")
    asyncio.run(serve(parser.parse_args()))
