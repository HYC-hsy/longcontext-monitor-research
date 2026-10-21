"""Finite FakeTask/FakeProvider scenarios; no transport or benchmark imports."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from .engine import CycleEngine
from .reminder import attach_once
from .source import ContractError, digest
from .store import MemoryStore
from .test_contracts import empty_snapshot, leaf
from .test_engine import ScriptedProvider, event


class FakeTask:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store
        self.tool_calls = 0

    def execute_synthetic_tool(self, output: str) -> None:
        self.tool_calls += 1
        action_batch, leaves = event(self.tool_calls, output)
        self.store.append_event(action_batch, leaves)


def scenario(name: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="stateful-memory-fake-") as directory:
        store = MemoryStore(Path(directory) / "method.sqlite3")
        try:
            store.initialize(empty_snapshot(), leaf("task"))
            task = FakeTask(store)
            user_events = 0
            if name != "initial_task":
                task.execute_synthetic_tool("synthetic tool observation")
            options = {}
            if name in {"clean_remind", "goal_epoch_stale"}:
                options = {"create_requirement": True, "remind": True}
            elif name == "initial_task":
                options = {"create_requirement": True}
            elif name == "issues_repair_clean":
                options = {"create_requirement": True, "outcomes": ["issues"]}
            elif name == "audit_correction_exhausted":
                options = {"outcomes": ["malformed", "malformed"]}
            elif name == "failed_then_replayed":
                options = {"fail_role": "audit"}
            elif name == "prefix_backlog":
                long_text = " ".join(str(number) for number in range(40000))
                task.execute_synthetic_tool(long_text)
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
                    user_events += 1
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
            cycle_ids = [first_result["cycle_id"]]
            if replay_result:
                cycle_ids.append(replay_result["cycle_id"])
            journal = [row for cycle_id in cycle_ids for row in
                       store.journal_rows(cycle_id)]
            measured = [row["body"]["input_size"] for row in journal if
                        row["phase"] == "call_prepared"]
            prepared_hashes = [row["body"]["messages_sha256"] for row in journal
                               if row["phase"] == "call_prepared"]
            returned_hashes = [row["body"]["public_response_sha256"] for row in
                               journal if row["phase"] == "call_returned"]
            return {"scenario": name, "first_status": first_result["status"],
                "replay_status": replay_result["status"] if replay_result else None,
                "committed_frontier": store.snapshot()["committed_event_seq"],
                "state_version": store.snapshot()["state_version"],
                "fake_role_calls": len(provider.calls),
                "observable_fake_attempts": sum(row["phase"] == "call_attempt"
                                                for row in journal),
                "roles": [call["role"] for call in provider.calls],
                "request_sha256": prepared_hashes,
                "response_sha256": returned_hashes,
                "request_sizes": measured,
                "fake_tool_calls": task.tool_calls,
                "fake_user_revision_events": user_events,
                "task_delivery": task_delivery,
                "task_request_sha256": task_request_hash,
                "real_model_calls": 0, "official_evaluator_calls": 0}
        finally:
            store.close()


SCENARIOS = ("initial_task", "clean_remind", "clean_silent", "issues_repair_clean",
             "audit_correction_exhausted", "failed_then_replayed",
             "prefix_backlog", "goal_epoch_stale")


def main() -> None:
    compact = "--compact" in sys.argv[1:]
    rows = []
    for name in SCENARIOS:
        result = scenario(name)
        if compact:
            result["request_sizes"] = [{key: item[key] for key in
                ("characters", "utf8_bytes", "proxy_tokens")} for item in
                result["request_sizes"]]
        rows.append(json.dumps(result, ensure_ascii=False, sort_keys=True))
    record_name = ("FAKE_CHAIN_POST_STALE.jsonl" if "--record-post-stale" in sys.argv[1:]
                   else "FAKE_CHAIN_STATUS_V1.jsonl" if "--record-status" in sys.argv[1:]
                   else "FAKE_CHAIN_FINAL.jsonl" if "--record-final" in sys.argv[1:]
                   else None)
    if record_name:
        target = Path(__file__).resolve().parent / "evidence" / record_name
        content = ("\n".join(rows) + "\n").encode("utf-8")
        if target.exists() and target.read_bytes() != content:
            raise RuntimeError("Refusing to overwrite a different fake evidence record")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(content)
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
