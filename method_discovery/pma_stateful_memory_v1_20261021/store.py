"""Method-local SQLite transaction backend; never the benchmark environment."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .schema import validate_snapshot
from .source import ContractError, canonical, digest, fields, integer, nonempty, validate_leaf


def _decode(raw: bytes) -> dict:
    return json.loads(raw.decode("utf-8"))


class MemoryStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS singleton (
                key TEXT PRIMARY KEY, value BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS sources (
                source_id TEXT PRIMARY KEY, content_hash TEXT NOT NULL, body BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS events (
                event_seq INTEGER PRIMARY KEY, event_id TEXT UNIQUE NOT NULL,
                content_hash TEXT NOT NULL, body BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS archive (
                object_kind TEXT NOT NULL, object_id TEXT NOT NULL, revision INTEGER NOT NULL,
                body BLOB NOT NULL, PRIMARY KEY(object_kind,object_id,revision));
            CREATE TABLE IF NOT EXISTS commits (
                update_id TEXT PRIMARY KEY, cycle_id TEXT NOT NULL,
                base_hash TEXT NOT NULL, candidate_hash TEXT NOT NULL,
                event_seq INTEGER NOT NULL, result BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS journal (
                cycle_id TEXT NOT NULL, entry_seq INTEGER NOT NULL,
                phase TEXT NOT NULL, body BLOB NOT NULL,
                PRIMARY KEY(cycle_id,entry_seq));
            CREATE TABLE IF NOT EXISTS deliveries (
                reminder_id TEXT PRIMARY KEY, request_id TEXT NOT NULL,
                result BLOB NOT NULL);
        """)

    def close(self) -> None:
        self.db.close()

    @contextmanager
    def transaction(self):
        try:
            self.db.execute("BEGIN IMMEDIATE")
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def _set(self, key: str, value: object) -> None:
        self.db.execute("INSERT INTO singleton(key,value) VALUES(?,?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (key, canonical(value)))

    def _get(self, key: str) -> dict | None:
        row = self.db.execute("SELECT value FROM singleton WHERE key=?", (key,)).fetchone()
        return _decode(row[0]) if row else None

    def snapshot(self) -> dict | None:
        return self._get("snapshot")

    def goals(self) -> dict:
        return self._get("goal_ledger") or {"epoch": 1, "deltas": {}, "messages": []}

    def sources(self) -> dict[str, dict]:
        return {key: _decode(raw) for key, raw in self.db.execute(
            "SELECT source_id,body FROM sources")}

    def archive(self) -> dict:
        result = {}
        for kind, key, revision, raw in self.db.execute(
                "SELECT object_kind,object_id,revision,body FROM archive"):
            # Preserve the existing state lookup contract; non-state histories
            # use typed keys so equal object IDs cannot alias one another.
            result[(key, revision) if kind == "state" else
                   (kind, key, revision)] = _decode(raw)
        return result

    def initialize(self, snapshot: dict, task_leaf: dict) -> None:
        validate_leaf(task_leaf)
        if task_leaf["source_kind"] != "user_requirement" or task_leaf["event_seq"] != 0:
            raise ContractError("invalid_initial_source")
        validate_snapshot(snapshot, {task_leaf["source_id"]: task_leaf})
        if snapshot["state_version"] != 0 or snapshot["committed_event_seq"] != 0:
            raise ContractError("invalid_initial_snapshot")
        with self.transaction():
            existing = self.snapshot()
            if existing is not None:
                if canonical(existing) != canonical(snapshot):
                    raise ContractError("initial_snapshot_conflict")
                return
            self._append_source(task_leaf)
            self._set("snapshot", snapshot)
            self._set("goal_ledger", {"epoch": snapshot["B"]["G"]["task_version"],
                                      "deltas": {}, "messages": [task_leaf["source_id"]]})

    def _append_source(self, leaf: dict) -> None:
        validate_leaf(leaf)
        raw = canonical(leaf)
        source_hash = digest(leaf)
        prior = self.db.execute("SELECT content_hash FROM sources WHERE source_id=?",
                                (leaf["source_id"],)).fetchone()
        if prior is not None:
            if prior[0] != source_hash:
                raise ContractError("source_id_hash_conflict", leaf["source_id"])
            return
        self.db.execute("INSERT INTO sources VALUES(?,?,?)",
                        (leaf["source_id"], source_hash, raw))

    def append_event(self, event: dict, leaves: list[dict]) -> None:
        event = fields(event, {"event_id", "event_seq", "kind", "occurred_at_step",
                               "source_ids", "payload"})
        nonempty(event["event_id"], "event_id")
        seq = integer(event["event_seq"], "event_seq", 1)
        if event["kind"] not in {"action_batch", "user_message", "agent_report"}:
            raise ContractError("invalid_event_kind")
        integer(event["occurred_at_step"], "occurred_at_step")
        source_ids = event["source_ids"]
        if type(source_ids) is not list or len(source_ids) != len(set(source_ids)):
            raise ContractError("invalid_event_sources")
        if {leaf["source_id"] for leaf in leaves} != set(source_ids):
            raise ContractError("incomplete_atomic_event")
        for leaf in leaves:
            validate_leaf(leaf)
            # A leaf keeps its own tool_use/message identity; event_seq binds it
            # to the host's indivisible action batch.
            if leaf["event_seq"] != seq:
                raise ContractError("event_leaf_identity")
        if event["kind"] == "action_batch":
            by_call = {}
            for leaf in leaves:
                if leaf["source_kind"] not in {"executed_action", "tool_result"}:
                    raise ContractError("invalid_action_batch_source")
                by_call.setdefault(leaf["event_id"], set()).add(leaf["source_kind"])
            if not by_call or any(kinds != {"executed_action", "tool_result"}
                                  for kinds in by_call.values()):
                raise ContractError("incomplete_atomic_action_batch")
            payload = event["payload"]
            if type(payload) is not dict:
                raise ContractError("invalid_action_batch_payload")
            actions = payload.get("actions")
            if type(actions) is not list or any(type(item) is not dict or
                    type(item.get("tool_use_id")) is not str or
                    not item["tool_use_id"] for item in actions):
                raise ContractError("invalid_action_batch_payload")
            identifiers = [item["tool_use_id"] for item in actions]
            if len(identifiers) != len(set(identifiers)) or set(identifiers) != set(by_call):
                raise ContractError("action_result_identity_mismatch")
        elif event["kind"] == "user_message":
            if len(leaves) != 1 or leaves[0]["source_kind"] != "user_requirement":
                raise ContractError("user_message_source_role")
        elif not leaves or any(leaf["source_kind"] != "agent_report" for leaf in leaves):
            raise ContractError("agent_report_source_role")
        raw = canonical(event)
        event_hash = digest(event)
        with self.transaction():
            prior = self.db.execute("SELECT content_hash FROM events WHERE event_seq=? "
                                    "OR event_id=?", (seq, event["event_id"])).fetchone()
            if prior is not None:
                if prior[0] != event_hash:
                    raise ContractError("event_id_hash_conflict")
                for leaf in leaves:
                    self._append_source(leaf)
                return
            latest = self.db.execute("SELECT MAX(event_seq) FROM events").fetchone()[0]
            if seq != (latest or 0) + 1:
                raise ContractError("noncontiguous_event_seq")
            for leaf in leaves:
                self._append_source(leaf)
            self.db.execute("INSERT INTO events VALUES(?,?,?,?)",
                            (seq, event["event_id"], event_hash, raw))
            if event["kind"] == "user_message":
                user_leaves = [leaf for leaf in leaves if leaf["source_kind"] ==
                               "user_requirement"]
                if len(user_leaves) != 1:
                    raise ContractError("user_message_source_role")
                goals = self.goals()
                old_epoch = goals["epoch"]
                new_epoch = old_epoch + 1
                delta_id = f"goal-delta-{new_epoch}"
                goals["epoch"] = new_epoch
                goals["deltas"][delta_id] = {"type": "goal_delta",
                    "goal_delta_id": delta_id, "from_task_version": old_epoch,
                    "to_task_version": new_epoch}
                goals["messages"].append(user_leaves[0]["source_id"])
                self._set("goal_ledger", goals)

    def events_after(self, seq: int) -> list[dict]:
        return [_decode(row[0]) for row in self.db.execute(
            "SELECT body FROM events WHERE event_seq>? ORDER BY event_seq", (seq,))]

    def journal(self, cycle_id: str, phase: str, body: dict) -> None:
        nonempty(cycle_id, "cycle_id")
        nonempty(phase, "phase")
        with self.transaction():
            next_seq = self.db.execute("SELECT COALESCE(MAX(entry_seq),0)+1 FROM journal "
                                       "WHERE cycle_id=?", (cycle_id,)).fetchone()[0]
            self.db.execute("INSERT INTO journal VALUES(?,?,?,?)",
                            (cycle_id, next_seq, phase, canonical(body)))

    def journal_rows(self, cycle_id: str) -> list[dict]:
        return [{"phase": phase, "body": _decode(body)} for phase, body in
                self.db.execute("SELECT phase,body FROM journal WHERE cycle_id=? "
                                "ORDER BY entry_seq", (cycle_id,))]

    def failed_attempts_for(self, event_ids: set[str]) -> list[dict]:
        cycles = {}
        for cycle_id, phase, raw in self.db.execute(
                "SELECT cycle_id,phase,body FROM journal ORDER BY rowid"):
            body = _decode(raw)
            entry = cycles.setdefault(cycle_id, {})
            if phase == "workset_frozen":
                entry["event_ids"] = body["event_ids"]
            elif phase == "cycle_result" and body["status"] in {
                    "init_failed", "update_rejected", "update_unusable",
                    "runtime_failed"}:
                entry["failure_class"] = body["error_code"]
        return [{"attempt_id": cycle_id,
                 "event_ids": [event_id for event_id in entry["event_ids"] if
                               event_id in event_ids],
                 "failure_class": entry["failure_class"],
                 "detail": "prior cycle failed before commit",
                 "epistemic_status": "diagnostic_not_evidence"}
                for cycle_id, entry in cycles.items() if "event_ids" in entry and
                "failure_class" in entry and event_ids.intersection(entry["event_ids"])]

    def commit_result(self, update_id: str) -> dict | None:
        row = self.db.execute("SELECT result FROM commits WHERE update_id=?",
                              (update_id,)).fetchone()
        return _decode(row[0]) if row else None

    def commit_for_cycle(self, cycle_id: str) -> dict | None:
        row = self.db.execute("SELECT result FROM commits WHERE cycle_id=?",
                              (cycle_id,)).fetchone()
        return _decode(row[0]) if row else None

    def compare_and_swap(self, *, update_id: str, cycle_id: str,
                         base: dict, candidate: dict, archive_delta: list[tuple[str, str,
                         int, dict]]) -> dict:
        existing = self.commit_result(update_id)
        if existing is not None:
            if existing["candidate_hash"] != digest(candidate):
                raise ContractError("update_id_hash_conflict")
            return existing
        with self.transaction():
            current = self.snapshot()
            if current is None or digest(current) != digest(base):
                raise ContractError("stale_snapshot")
            if candidate["state_version"] != base["state_version"] + 1:
                raise ContractError("state_version_not_incremented")
            if candidate["committed_event_seq"] < base["committed_event_seq"]:
                raise ContractError("frontier_regression")
            if candidate["committed_event_seq"] > base["committed_event_seq"]:
                row = self.db.execute("SELECT event_seq FROM events WHERE event_seq=?",
                    (candidate["committed_event_seq"],)).fetchone()
                if row is None:
                    raise ContractError("frontier_missing_event")
            if candidate["B"]["G"]["task_version"] != self.goals()["epoch"]:
                raise ContractError("goal_epoch_mismatch")
            additions = {(kind, object_id, revision): body for kind, object_id,
                         revision, body in archive_delta}
            if len(additions) != len(archive_delta):
                raise ContractError("duplicate_archive_revision")
            for (kind, object_id, revision), body in additions.items():
                self.db.execute("INSERT INTO archive VALUES(?,?,?,?)",
                                (kind, object_id, revision, canonical(body)))
            validate_snapshot(candidate, self.sources(), self.archive(),
                              self.goals()["deltas"])
            result = {"update_id": update_id, "cycle_id": cycle_id,
                      "base_hash": digest(base), "candidate_hash": digest(candidate),
                      "event_seq": candidate["committed_event_seq"]}
            self._set("snapshot", candidate)
            self.db.execute("INSERT INTO commits VALUES(?,?,?,?,?,?)",
                            (update_id, cycle_id, result["base_hash"],
                             result["candidate_hash"], result["event_seq"],
                             canonical(result)))
            return result

    def delivery(self, reminder_id: str, request_id: str, result: dict) -> dict:
        raw = canonical(result)
        with self.transaction():
            old = self.db.execute("SELECT request_id,result FROM deliveries "
                                  "WHERE reminder_id=?", (reminder_id,)).fetchone()
            if old is not None:
                if old[0] != request_id or old[1] != raw:
                    raise ContractError("delivery_identity_conflict")
                return _decode(old[1])
            self.db.execute("INSERT INTO deliveries VALUES(?,?,?)",
                            (reminder_id, request_id, raw))
        return result

    def delivery_result(self, reminder_id: str) -> dict | None:
        row = self.db.execute("SELECT result FROM deliveries WHERE reminder_id=?",
                              (reminder_id,)).fetchone()
        return _decode(row[0]) if row else None

    def delivery_attempt_cycles(self, reminder_id: str) -> list[str]:
        return [cycle_id for cycle_id, raw in self.db.execute(
            "SELECT cycle_id,body FROM journal WHERE phase='delivery_attempt'")
            if _decode(raw).get("reminder_id") == reminder_id]
