"""Finite FakeTask/FakeProvider scenarios; no transport or benchmark imports."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .engine import CycleEngine
from .reminder import attach_once
from .source import ContractError, digest
from .store import MemoryStore
from .test_contracts import empty_snapshot, leaf
from .test_engine import ScriptedProvider, event


def scenario(name: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="stateful-memory-fake-") as directory:
        store = MemoryStore(Path(directory) / "method.sqlite3")
        try:
            store.initialize(empty_snapshot(), leaf("task"))
            task_events = 0
            first, leaves = event(1, "synthetic tool observation")
            store.append_event(first, leaves)
            task_events += 1
            options = {}
            if name in {"clean_remind", "goal_epoch_stale"}:
                options = {"create_requirement": True, "remind": True}
            elif name == "issues_repair_clean":
                options = {"create_requirement": True, "outcomes": ["issues"]}
            elif name == "audit_correction_exhausted":
                options = {"outcomes": ["malformed", "malformed"]}
            elif name == "failed_then_replayed":
                options = {"fail_role": "audit"}
            elif name == "prefix_backlog":
                long_text = " ".join(str(number) for number in range(40000))
                second, second_leaves = event(2, long_text)
                store.append_event(second, second_leaves)
                task_events += 1
            provider = ScriptedProvider(**options)
            first_result = CycleEngine(store, provider, task_text="task").run(
                "trigger-first")
            replay_result = None
            if name == "failed_then_replayed":
                replay_provider = ScriptedProvider()
                replay_result = CycleEngine(store, replay_provider,
                                            task_text="task").run("trigger-second")
                provider.calls.extend(replay_provider.calls)
            task_delivery = "not_prepared"
            task_request_hash = None
            if first_result["status"] == "committed_reminder_ready":
                reminder = first_result["reminder"]
                messages = [{"role": "system", "content": "synthetic Task"},
                            {"role": "user", "content": "task"}]
                if name == "goal_epoch_stale":
                    revision = leaf("changed goal", source_id="user-new")
                    revision.update(event_id="user-message-2", event_seq=2, ga_turn=2)
                    store.append_event({"event_id": "user-message-2",
                        "event_seq": 2, "kind": "user_message", "occurred_at_step": 2,
                        "source_ids": ["user-new"], "payload": {}}, [revision])
                    task_events += 1
                def fake_task_send(payload):
                    nonlocal task_request_hash
                    task_request_hash = digest(payload)
                    return {"accepted": True, "public_text": "synthetic continuation"}
                try:
                    attach_once(store=store, reminder=reminder,
                        task_messages=messages, request_id="fake-task-request-1",
                        cycle_id=first_result["cycle_id"], send=fake_task_send)
                    task_delivery = "included_in_accepted_request"
                except ContractError as error:
                    task_delivery = error.code
            return {"scenario": name, "first_status": first_result["status"],
                "replay_status": replay_result["status"] if replay_result else None,
                "committed_frontier": store.snapshot()["committed_event_seq"],
                "state_version": store.snapshot()["state_version"],
                "fake_role_calls": len(provider.calls),
                "roles": [call["role"] for call in provider.calls],
                "fake_task_events": task_events,
                "task_delivery": task_delivery,
                "task_request_sha256": task_request_hash,
                "real_model_calls": 0, "official_evaluator_calls": 0}
        finally:
            store.close()


SCENARIOS = ("clean_remind", "clean_silent", "issues_repair_clean",
             "audit_correction_exhausted", "failed_then_replayed",
             "prefix_backlog", "goal_epoch_stale")


def main() -> None:
    for name in SCENARIOS:
        print(json.dumps(scenario(name), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
