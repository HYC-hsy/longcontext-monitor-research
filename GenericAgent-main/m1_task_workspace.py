"""Persistent open-semantic workspace for the M1 monitor increment.

This is a reconstructable projection over public task history.  It does not
replace the original task or raw trajectory and it makes no control decisions.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from m0_monitor_checkpoint import MonitorCheckpointStore


SCHEMA_VERSION = "m1-task-workspace/1"
EVENT_SCHEMA_VERSION = "m1-task-workspace-event/1"
_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class PersistentTaskWorkspace:
    """Maintain a compact semantic projection with links to public sources."""

    def __init__(self, artifact_dir: str | os.PathLike[str] | None,
                 public_task: str):
        self.artifact_dir = Path(artifact_dir).resolve() if artifact_dir else None
        self.public_task = public_task
        self.public_task_sha256 = hashlib.sha256(
            public_task.encode("utf-8", errors="replace")
        ).hexdigest()
        self.path = self.artifact_dir / "m1_workspace.json" if self.artifact_dir else None
        self.events_path = (
            self.artifact_dir / "m1_workspace_events.jsonl" if self.artifact_dir else None
        )
        self.objects: dict[str, dict[str, Any]] = {}
        self.relations: dict[str, dict[str, Any]] = {}
        self.update_count = 0
        self.last_internal_turn: int | None = None
        self._load_or_bootstrap()

    def _load_or_bootstrap(self) -> None:
        loaded = self._read_snapshot()
        if loaded is not None:
            self.objects = {
                str(row["id"]): dict(row)
                for row in loaded.get("objects", [])
                if isinstance(row, Mapping) and row.get("id")
            }
            self.relations = {
                self._relation_key(row): dict(row)
                for row in loaded.get("relations", [])
                if self._valid_relation(row)
            }
            self.update_count = int(loaded.get("update_count", 0))
            self.last_internal_turn = loaded.get("last_internal_turn")
            return
        self.objects["root:public-task"] = {
            "id": "root:public-task",
            "role": "root_contract",
            "summary": "Immutable original public task; retrieve the original text when detail matters.",
            "state": "active",
            "source_anchors": [f"public_task:sha256:{self.public_task_sha256}"],
            "root_links": [],
            "updated_turn": 0,
        }
        self._persist()
        if self.artifact_dir:
            task_path = self.artifact_dir / "original_public_task.txt"
            existing = task_path.read_text(encoding="utf-8-sig") if task_path.exists() else None
            if existing != self.public_task:
                temporary = task_path.with_name(task_path.name + ".tmp")
                temporary.write_text(self.public_task, encoding="utf-8")
                os.replace(temporary, task_path)

    def _read_snapshot(self) -> dict[str, Any] | None:
        if self.path is None or not self.path.exists():
            return None
        try:
            value = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(value, Mapping):
            return None
        if value.get("schema_version") != SCHEMA_VERSION:
            return None
        if value.get("public_task_sha256") != self.public_task_sha256:
            return None
        return dict(value)

    @staticmethod
    def _clean_text(value: Any, limit: int) -> str:
        return str(value or "").strip()[:limit]

    @classmethod
    def _clean_id(cls, value: Any) -> str:
        identifier = cls._clean_text(value, 128)
        return identifier if _ID_PATTERN.fullmatch(identifier) else ""

    @classmethod
    def _normalize_object(cls, value: Mapping[str, Any], turn: int) -> dict[str, Any] | None:
        identifier = cls._clean_id(value.get("id"))
        summary = cls._clean_text(value.get("summary"), 4000)
        if not identifier or not summary or identifier == "root:public-task":
            return None
        role = cls._clean_text(value.get("role"), 80) or "other"
        state = cls._clean_text(value.get("state"), 80) or "active"
        anchors = value.get("source_anchors", [])
        links = value.get("root_links", [])
        if not isinstance(anchors, list) or not isinstance(links, list):
            return None
        return {
            "id": identifier,
            "role": role,
            "summary": summary,
            "state": state,
            "source_anchors": [cls._clean_text(item, 500) for item in anchors[:20]
                               if cls._clean_text(item, 500)],
            "root_links": [cls._clean_id(item) for item in links[:20] if cls._clean_id(item)],
            "updated_turn": turn,
        }

    @classmethod
    def _valid_relation(cls, value: Any) -> bool:
        return (isinstance(value, Mapping)
                and bool(cls._clean_id(value.get("source")))
                and bool(cls._clean_id(value.get("target")))
                and bool(cls._clean_text(value.get("relation"), 80)))

    @classmethod
    def _normalize_relation(cls, value: Mapping[str, Any], turn: int) -> dict[str, Any] | None:
        if not cls._valid_relation(value):
            return None
        return {
            "source": cls._clean_id(value.get("source")),
            "relation": cls._clean_text(value.get("relation"), 80),
            "target": cls._clean_id(value.get("target")),
            "summary": cls._clean_text(value.get("summary"), 1000),
            "updated_turn": turn,
        }

    @staticmethod
    def _relation_key(value: Mapping[str, Any]) -> str:
        return "\x1f".join(str(value.get(key, "")) for key in ("source", "relation", "target"))

    @staticmethod
    def _semantic_equal(left: Mapping[str, Any] | None,
                        right: Mapping[str, Any]) -> bool:
        if left is None:
            return False
        return ({key: value for key, value in left.items() if key != "updated_turn"}
                == {key: value for key, value in right.items() if key != "updated_turn"})

    def sync_root_obligations(self, rows: list[dict[str, Any]], turn: int,
                              decision_index: int | None = None) -> int:
        """Project M0's existing root ledger without inventing new semantics."""
        changed = 0
        for index, row in enumerate(rows):
            obligation = self._clean_text(row.get("obligation"), 4000)
            if not obligation:
                continue
            digest = hashlib.sha256(obligation.encode("utf-8", errors="replace")).hexdigest()[:16]
            identifier = f"obligation:{digest}"
            anchors = row.get("public_evidence", [])
            projected = {
                "id": identifier,
                "role": "root_obligation",
                "summary": obligation,
                "state": self._clean_text(row.get("status"), 80) or "unknown",
                "source_anchors": ["public_task:explicit_obligation", *[
                    self._clean_text(item, 500) for item in anchors[:20]
                    if self._clean_text(item, 500)
                ]],
                "root_links": ["root:public-task"],
                "updated_turn": turn,
                "source_order": index,
            }
            previous = self.objects.get(identifier)
            if not self._semantic_equal(previous, projected):
                changed += 1
            elif previous is not None:
                projected["updated_turn"] = previous.get("updated_turn", turn)
            self.objects[identifier] = projected
            relation = {
                "source": identifier,
                "relation": "part_of",
                "target": "root:public-task",
                "summary": "Explicit obligation projected from the monitor-owned root audit.",
                "updated_turn": turn,
            }
            self.relations[self._relation_key(relation)] = relation
        if changed:
            self.last_internal_turn = turn
            self._append_event({
                "schema_version": EVENT_SCHEMA_VERSION,
                "internal_turn": turn,
                "decision_index": decision_index,
                "projection": "root_obligation_audit",
                "changed": changed,
            })
            self._persist()
        return changed

    def sync_repair_episode(self, episode: Mapping[str, Any] | None, *, turn: int,
                            decision_index: int) -> int:
        """Project M0's current repair scope without deciding whether it is resolved."""
        active_repairs = [identifier for identifier, row in self.objects.items()
                          if row.get("role") == "repair_episode"
                          and row.get("state") != "inactive"]
        changed = 0
        current_id = ""
        if episode:
            opened_turn = int(episode.get("opened_turn") or turn)
            current_id = f"repair:{opened_turn}"
            summary = self._clean_text(
                episode.get("current_residual") or episode.get("original_discrepancy"),
                4000,
            ) or "Open monitor repair episode"
            projected = {
                "id": current_id,
                "role": "repair_episode",
                "summary": summary,
                "state": "active",
                "source_anchors": [f"public_trajectory:turn:{opened_turn}"],
                "root_links": ["root:public-task"],
                "updated_turn": turn,
                "exit_condition": self._clean_text(
                    episode.get("current_exit_condition") or episode.get("original_exit_condition"),
                    2000,
                ),
            }
            previous = self.objects.get(current_id)
            if not self._semantic_equal(previous, projected):
                changed += 1
            elif previous is not None:
                projected["updated_turn"] = previous.get("updated_turn", turn)
            self.objects[current_id] = projected
            relation = {
                "source": current_id,
                "relation": "repairs",
                "target": "root:public-task",
                "summary": "Local repair remains subordinate to the root task.",
                "updated_turn": turn,
            }
            self.relations[self._relation_key(relation)] = relation
        for identifier in active_repairs:
            if identifier == current_id:
                continue
            self.objects[identifier] = {
                **self.objects[identifier], "state": "inactive", "updated_turn": turn,
            }
            changed += 1
        if changed:
            self.last_internal_turn = turn
            self._append_event({
                "schema_version": EVENT_SCHEMA_VERSION,
                "internal_turn": turn,
                "decision_index": decision_index,
                "projection": "open_repair_episode",
                "changed": changed,
            })
            self._persist()
        return changed

    def apply_delta(self, delta: Any, *, turn: int, decision_index: int) -> dict[str, Any]:
        """Apply one monitor-authored semantic delta; invalid rows are ignored and audited."""
        if not isinstance(delta, Mapping):
            return {"applied": False, "reason": "no_delta", "upserted": 0,
                    "deactivated": 0, "relations": 0, "invalid": 0}
        upserts = delta.get("upsert", [])
        deactivations = delta.get("deactivate", [])
        relations = delta.get("relations", [])
        if not isinstance(upserts, list) or not isinstance(deactivations, list) or not isinstance(relations, list):
            return {"applied": False, "reason": "invalid_collections", "upserted": 0,
                    "deactivated": 0, "relations": 0, "invalid": 1}
        result = {"applied": True, "upserted": 0, "deactivated": 0,
                  "relations": 0, "invalid": 0}
        for value in upserts[:100]:
            normalized = self._normalize_object(value, turn) if isinstance(value, Mapping) else None
            if normalized is None:
                result["invalid"] += 1
                continue
            previous = self.objects.get(normalized["id"])
            if self._semantic_equal(previous, normalized):
                normalized["updated_turn"] = previous.get("updated_turn", turn)
            else:
                result["upserted"] += 1
            self.objects[normalized["id"]] = normalized
        for value in deactivations[:100]:
            identifier = self._clean_id(value)
            if not identifier or identifier == "root:public-task" or identifier not in self.objects:
                result["invalid"] += 1
                continue
            self.objects[identifier] = {
                **self.objects[identifier], "state": "inactive", "updated_turn": turn,
            }
            result["deactivated"] += 1
        for value in relations[:200]:
            normalized = self._normalize_relation(value, turn) if isinstance(value, Mapping) else None
            if (normalized is None or normalized["source"] not in self.objects
                    or normalized["target"] not in self.objects):
                result["invalid"] += 1
                continue
            self.relations[self._relation_key(normalized)] = normalized
            result["relations"] += 1
        self.update_count += 1
        self.last_internal_turn = turn
        self._append_event({
            "schema_version": EVENT_SCHEMA_VERSION,
            "internal_turn": turn,
            "decision_index": decision_index,
            "delta": dict(delta),
            "result": result,
        })
        self._persist()
        return result

    def view(self, *, include_inactive: bool = False) -> dict[str, Any]:
        objects = [row for row in self.objects.values()
                   if include_inactive or row.get("state") != "inactive"]
        objects.sort(key=lambda row: (str(row.get("role", "")), str(row.get("id", ""))))
        relations = sorted(self.relations.values(), key=self._relation_key)
        active_ids = {row["id"] for row in objects}
        if not include_inactive:
            relations = [row for row in relations
                         if row["source"] in active_ids and row["target"] in active_ids]
        return {
            "schema_version": SCHEMA_VERSION,
            "public_task_sha256": self.public_task_sha256,
            "objects": objects,
            "relations": relations,
            "update_count": self.update_count,
            "last_internal_turn": self.last_internal_turn,
        }

    def search(self, pattern: str, *, limit: int = 30) -> dict[str, Any]:
        if not pattern:
            return {"ok": False, "error": "pattern is required"}
        try:
            expression = re.compile(pattern, re.I)
        except re.error as error:
            return {"ok": False, "error": f"invalid regex: {error}"}
        rows = [row for row in self.objects.values()
                if expression.search(json.dumps(row, ensure_ascii=False, default=str))]
        rows.sort(key=lambda row: (int(row.get("updated_turn") or 0), row["id"]), reverse=True)
        return {"ok": True, "objects": rows[:max(1, min(100, limit))],
                "matched": len(rows), "truncated": len(rows) > limit}

    def _persist(self) -> None:
        if self.path is not None:
            MonitorCheckpointStore.write_json(self.path, self.view(include_inactive=True))

    def _append_event(self, event: Mapping[str, Any]) -> None:
        if self.events_path is None:
            return
        with self.events_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
