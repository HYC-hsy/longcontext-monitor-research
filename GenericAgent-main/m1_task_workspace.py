"""Persistent open-semantic workspace for the M1 monitor increment.

This is a reconstructable projection over public task history.  It does not
replace the original task or raw trajectory and it makes no control decisions.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from m0_monitor_checkpoint import MonitorCheckpointStore


SCHEMA_VERSION = "m1-task-workspace/2"
EVENT_SCHEMA_VERSION = "m1-task-workspace-event/1"
_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class PersistentTaskWorkspace:
    """Maintain a compact semantic projection with links to public sources."""

    def __init__(self, artifact_dir: str | os.PathLike[str] | None,
                 public_task: str, versioned_revision_enabled: bool = False,
                 justification_invalidation_enabled: bool = False,
                 semantic_impact_enabled: bool = False):
        self.artifact_dir = Path(artifact_dir).resolve() if artifact_dir else None
        self.public_task = public_task
        self.public_task_sha256 = hashlib.sha256(
            public_task.encode("utf-8", errors="replace")
        ).hexdigest()
        self.versioned_revision_enabled = bool(versioned_revision_enabled)
        self.justification_invalidation_enabled = bool(
            justification_invalidation_enabled
        )
        self.semantic_impact_enabled = bool(semantic_impact_enabled)
        self.path = self.artifact_dir / "m1_workspace.json" if self.artifact_dir else None
        self.events_path = (
            self.artifact_dir / "m1_workspace_events.jsonl" if self.artifact_dir else None
        )
        self.objects: dict[str, dict[str, Any]] = {}
        self.relations: dict[str, dict[str, Any]] = {}
        self.update_count = 0
        self.last_internal_turn: int | None = None
        self.root_ledger_frozen = False
        self.rejected_root_mutations = 0
        self.revision_history: list[dict[str, Any]] = []
        self.invalidation_history: list[dict[str, Any]] = []
        self.pending_invalidations: dict[str, dict[str, Any]] = {}
        self.semantic_impact_history: list[dict[str, Any]] = []
        self.pending_semantic_impacts: dict[str, dict[str, Any]] = {}
        self.rejected_semantic_impacts = 0
        self.last_state_transaction_id = "decision:0000"
        self.transaction_backup_path = (
            self.artifact_dir / "m1_workspace_transaction_backup.json"
            if self.artifact_dir else None
        )
        self._load_or_bootstrap()

    def _load_or_bootstrap(self) -> None:
        loaded = self._read_snapshot()
        if loaded is not None:
            self.objects = {
                str(row["id"]): (
                    dict(row) if self.versioned_revision_enabled
                    else {key: item for key, item in row.items() if key != "object_version"}
                )
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
            self.root_ledger_frozen = bool(loaded.get("root_ledger_frozen", False))
            self.rejected_root_mutations = int(loaded.get("rejected_root_mutations", 0))
            self.revision_history = [
                dict(row) for row in loaded.get("revision_history", [])
                if isinstance(row, Mapping) and row.get("object_id")
            ] if self.versioned_revision_enabled else []
            self.invalidation_history = [
                dict(row) for row in loaded.get("invalidation_history", [])
                if isinstance(row, Mapping) and row.get("target_id")
            ] if self.justification_invalidation_enabled else []
            self.pending_invalidations = {
                str(row["target_id"]): dict(row)
                for row in loaded.get("pending_invalidations", [])
                if (self.justification_invalidation_enabled
                    and isinstance(row, Mapping) and row.get("target_id"))
            }
            self.semantic_impact_history = [
                dict(row) for row in loaded.get("semantic_impact_history", [])
                if (self.semantic_impact_enabled and isinstance(row, Mapping)
                    and row.get("target_id"))
            ]
            self.pending_semantic_impacts = {
                str(row["target_id"]): dict(row)
                for row in loaded.get("pending_semantic_impacts", [])
                if (self.semantic_impact_enabled and isinstance(row, Mapping)
                    and row.get("target_id"))
            }
            self.rejected_semantic_impacts = (
                int(loaded.get("rejected_semantic_impacts", 0))
                if self.semantic_impact_enabled else 0
            )
            self.last_state_transaction_id = str(
                loaded.get("last_state_transaction_id", "decision:0000")
            )
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
        ignored = {"updated_turn", "object_version"}
        return ({key: value for key, value in left.items() if key not in ignored}
                == {key: value for key, value in right.items() if key not in ignored})

    def _store_object(self, projected: Mapping[str, Any], *, turn: int,
                      decision_index: int | None, reason: str) -> bool:
        """Store the current projection, preserving replaced semantics only in M2.

        M1 behavior is byte-for-byte compatible when versioned revision is off.
        Versions describe monitor-owned semantic objects, not repository files or
        hidden ground truth.  A version advance therefore never implies success.
        """
        row = dict(projected)
        identifier = str(row["id"])
        previous = self.objects.get(identifier)
        changed = not self._semantic_equal(previous, row)
        if not self.versioned_revision_enabled:
            self.objects[identifier] = row
            return changed
        if previous is None:
            row["object_version"] = 1
        elif changed:
            previous_version = int(previous.get("object_version", 1))
            self.revision_history.append({
                "object_id": identifier,
                "previous_version": previous_version,
                "new_version": previous_version + 1,
                "superseded_turn": turn,
                "decision_index": decision_index,
                "reason": self._clean_text(reason, 160),
                "previous": dict(previous),
            })
            row["object_version"] = previous_version + 1
        else:
            row["object_version"] = int(previous.get("object_version", 1))
        self.objects[identifier] = row
        return changed

    @staticmethod
    def _evidence_withdrawn(previous: Mapping[str, Any] | None,
                            current: Mapping[str, Any]) -> bool:
        """Recognize an explicit support withdrawal, not ordinary wording drift."""
        if previous is None or previous.get("role") != "public_evidence":
            return False
        before = str(previous.get("state", "")).lower()
        after = str(current.get("state", "")).lower()
        negative = ("inactive", "contested", "invalid", "superseded", "withdrawn")
        return (not any(token in before for token in negative)
                and any(token in after for token in negative))

    def _invalidate_supported_dependents(
        self, evidence_id: str, previous: Mapping[str, Any],
        current: Mapping[str, Any], *, turn: int, decision_index: int,
    ) -> int:
        if not self.justification_invalidation_enabled:
            return 0
        targets = {
            str(row.get("target")) for row in self.relations.values()
            if (row.get("source") == evidence_id
                and str(row.get("relation", "")).lower()
                in {"supports", "justifies", "evidence_for"})
        }
        changed = 0
        for target_id in sorted(targets):
            target = self.objects.get(target_id)
            if target is None or target.get("role") != "root_obligation":
                continue
            record = {
                "target_id": target_id,
                "evidence_id": evidence_id,
                "turn": turn,
                "decision_index": decision_index,
                "reason": "previously linked public evidence was explicitly withdrawn",
                "previous_evidence_state": previous.get("state"),
                "current_evidence_state": current.get("state"),
            }
            self.pending_invalidations[target_id] = record
            self.invalidation_history.append(dict(record))
            changed += 1
        return changed

    def _apply_semantic_impacts(self, values: Any, *, turn: int,
                                decision_index: int) -> tuple[int, int, int]:
        """Validate monitor proposals structurally; never infer semantic truth."""
        if not self.semantic_impact_enabled or not isinstance(values, list):
            return 0, 0, 0
        accepted = rejected = revalidated = 0
        allowed_relations = {
            "supports", "partially_supports", "justifies", "evidence_for",
            "conflicts_with", "bears_on", "invalidates", "revalidates", "restores",
        }
        for value in values[:50]:
            if not isinstance(value, Mapping):
                rejected += 1
                continue
            target_id = self._clean_id(value.get("target_id"))
            cause_id = self._clean_id(value.get("cause_id"))
            effect = self._clean_text(value.get("effect"), 40).lower()
            reason = self._clean_text(value.get("reason"), 1000)
            anchors = value.get("public_anchors", [])
            target = self.objects.get(target_id)
            cause = self.objects.get(cause_id)
            clean_anchors = [self._clean_text(item, 500) for item in anchors[:20]
                             if self._clean_text(item, 500)] if isinstance(anchors, list) else []
            related = any(
                row.get("source") == cause_id and row.get("target") == target_id
                and str(row.get("relation", "")).lower() in allowed_relations
                for row in self.relations.values()
            )
            # Natural-language anchors are citations, not canonical keys. The
            # monitor may quote the same public event at different granularity;
            # deterministic validation checks that both records carry public
            # provenance while the explicit local relation constrains scope.
            anchored = bool(clean_anchors) and bool((cause or {}).get("source_anchors", []))
            valid = (
                target is not None and target.get("role") == "root_obligation"
                and cause is not None and cause.get("role") == "public_evidence"
                and effect in {"contest", "supersede", "withdraw_support", "revalidate"}
                and bool(reason) and anchored
                and (related or target_id in cause.get("root_links", []))
            )
            if not valid:
                rejected += 1
                continue
            record = {
                "target_id": target_id, "cause_id": cause_id, "effect": effect,
                "reason": reason, "public_anchors": clean_anchors,
                "turn": turn, "decision_index": decision_index,
            }
            if effect == "revalidate":
                if target_id not in self.pending_semantic_impacts:
                    rejected += 1
                    continue
                del self.pending_semantic_impacts[target_id]
                revalidated += 1
            else:
                previous = self.pending_semantic_impacts.get(target_id)
                semantic_keys = ("target_id", "cause_id", "effect", "reason", "public_anchors")
                if previous and all(previous.get(key) == record.get(key)
                                    for key in semantic_keys):
                    continue
                self.pending_semantic_impacts[target_id] = record
                self.semantic_impact_history.append(dict(record))
                accepted += 1
        self.rejected_semantic_impacts += rejected
        return accepted, rejected, revalidated

    def sync_root_obligations(self, rows: list[dict[str, Any]], turn: int,
                              decision_index: int | None = None) -> int:
        """Project the frozen root ledger using stable, source-ordered identities.

        Existing identities are immutable. Later audits may recover an omitted
        public-task obligation by appending it, but cannot delete, reorder, or
        paraphrase an existing obligation into a new object.
        """
        existing = sorted(
            (row for row in self.objects.values() if row.get("role") == "root_obligation"),
            key=lambda row: int(row.get("source_order", 0)),
        )
        if self.root_ledger_frozen and len(rows) < len(existing):
            self.rejected_root_mutations += len(existing) - len(rows)
        accepted_count = len(rows)
        changed = 0
        for index, row in enumerate(rows[:accepted_count]):
            obligation = self._clean_text(row.get("obligation"), 4000)
            if not obligation:
                continue
            if self.root_ledger_frozen and index < len(existing):
                identifier = str(existing[index]["id"])
                obligation = str(existing[index]["summary"])
            else:
                identifier = (
                    self._clean_id(row.get("obligation_id"))
                    or f"obligation:{index:04d}"
                )
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
            pending = (self.pending_invalidations.get(identifier)
                       or self.pending_semantic_impacts.get(identifier))
            if pending:
                projected["state"] = "contested"
                projected["source_anchors"].append(
                    "semantic_reopen:"
                    f"{pending.get('evidence_id') or pending.get('cause_id')}:turn:{pending['turn']}"
                )
            previous = self.objects.get(identifier)
            if not self._semantic_equal(previous, projected):
                changed += 1
            elif previous is not None:
                projected["updated_turn"] = previous.get("updated_turn", turn)
            self._store_object(
                projected, turn=turn, decision_index=decision_index,
                reason="root_obligation_projection_changed",
            )
            relation = {
                "source": identifier,
                "relation": "part_of",
                "target": "root:public-task",
                "summary": "Explicit obligation projected from the monitor-owned root audit.",
                "updated_turn": turn,
            }
            self.relations[self._relation_key(relation)] = relation
        if rows and not self.root_ledger_frozen:
            self.root_ledger_frozen = True
        if changed:
            self.last_internal_turn = turn
            self.last_state_transaction_id = f"decision:{int(decision_index or 0):04d}"
            event = {
                "schema_version": EVENT_SCHEMA_VERSION,
                "internal_turn": turn,
                "decision_index": decision_index,
                "projection": "root_obligation_audit",
                "changed": changed,
            }
            self._persist()
            self._append_event({
                **event, "workspace_snapshot_persisted": True,
            })
        return changed

    def archive_and_reset_root_projection(self) -> None:
        """Quarantine a pre-identity derived root projection before bootstrap."""
        root_ids = {
            identifier for identifier, row in self.objects.items()
            if row.get("role") == "root_obligation"
        }
        if not root_ids:
            self.root_ledger_frozen = False
            return
        if self.artifact_dir:
            archive = self.artifact_dir / "m1_workspace_pre_identity_migration.json"
            if not archive.exists():
                MonitorCheckpointStore.write_json(
                    archive, self.view(include_inactive=True)
                )
        self.objects = {
            identifier: row for identifier, row in self.objects.items()
            if identifier not in root_ids
        }
        self.relations = {
            key: row for key, row in self.relations.items()
            if row.get("source") not in root_ids and row.get("target") not in root_ids
        }
        self.pending_invalidations = {
            key: row for key, row in self.pending_invalidations.items()
            if key not in root_ids
        }
        self.pending_semantic_impacts = {
            key: row for key, row in self.pending_semantic_impacts.items()
            if key not in root_ids
        }
        self.root_ledger_frozen = False
        self._persist()

    def transaction_snapshot(self) -> dict[str, Any]:
        """Capture mutable projection state, excluding immutable paths/config."""
        fields = (
            "objects", "relations", "update_count", "last_internal_turn",
            "root_ledger_frozen", "rejected_root_mutations", "revision_history",
            "invalidation_history", "pending_invalidations",
            "semantic_impact_history", "pending_semantic_impacts",
            "rejected_semantic_impacts", "last_state_transaction_id",
        )
        return {name: copy.deepcopy(getattr(self, name)) for name in fields}

    def restore_transaction_snapshot(self, snapshot: Mapping[str, Any]) -> None:
        """Restore and persist the last committed in-memory projection."""
        for name, value in snapshot.items():
            setattr(self, name, copy.deepcopy(value))
        self._persist()
        self._append_event({
            "schema_version": EVENT_SCHEMA_VERSION,
            "event": "workspace_transaction_rollback",
            "workspace_snapshot_persisted": True,
            "update_count": self.update_count,
            "last_internal_turn": self.last_internal_turn,
        })
        if self.transaction_backup_path:
            self.transaction_backup_path.unlink(missing_ok=True)

    def begin_transaction(self, transaction_id: str) -> None:
        if self.transaction_backup_path is not None:
            MonitorCheckpointStore.write_json(self.transaction_backup_path, {
                "schema_version": "m1-workspace-transaction-backup/1",
                "pending_transaction_id": transaction_id,
                "workspace": self.view(include_inactive=True),
            })

    def finish_transaction(self) -> None:
        if self.transaction_backup_path:
            self.transaction_backup_path.unlink(missing_ok=True)

    def recover_incomplete_transaction(self, committed_transaction_id: str) -> bool:
        path = self.transaction_backup_path
        if path is None or not path.exists():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return False
        pending_id = str(payload.get("pending_transaction_id", ""))
        if pending_id and pending_id == committed_transaction_id:
            path.unlink(missing_ok=True)
            return False
        snapshot = payload.get("workspace")
        if not isinstance(snapshot, Mapping):
            return False
        self._restore_from_view(snapshot)
        self._persist()
        path.unlink(missing_ok=True)
        self._append_event({
            "schema_version": EVENT_SCHEMA_VERSION,
            "event": "workspace_crash_recovery",
            "abandoned_transaction_id": pending_id,
            "committed_transaction_id": committed_transaction_id,
        })
        return True

    def _restore_from_view(self, snapshot: Mapping[str, Any]) -> None:
        self.objects = {
            str(row["id"]): dict(row) for row in snapshot.get("objects", [])
            if isinstance(row, Mapping) and row.get("id")
        }
        self.relations = {
            self._relation_key(row): dict(row)
            for row in snapshot.get("relations", []) if self._valid_relation(row)
        }
        self.update_count = int(snapshot.get("update_count", 0) or 0)
        self.last_internal_turn = snapshot.get("last_internal_turn")
        self.root_ledger_frozen = bool(snapshot.get("root_ledger_frozen", False))
        self.rejected_root_mutations = int(snapshot.get("rejected_root_mutations", 0) or 0)
        self.revision_history = list(snapshot.get("revision_history", []))
        self.invalidation_history = list(snapshot.get("invalidation_history", []))
        self.pending_invalidations = {
            str(row["target_id"]): dict(row)
            for row in snapshot.get("pending_invalidations", [])
            if isinstance(row, Mapping) and row.get("target_id")
        }
        self.semantic_impact_history = list(snapshot.get("semantic_impact_history", []))
        self.pending_semantic_impacts = {
            str(row["target_id"]): dict(row)
            for row in snapshot.get("pending_semantic_impacts", [])
            if isinstance(row, Mapping) and row.get("target_id")
        }
        self.rejected_semantic_impacts = int(snapshot.get("rejected_semantic_impacts", 0) or 0)
        self.last_state_transaction_id = str(
            snapshot.get("last_state_transaction_id", "decision:0000")
        )

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
            self._store_object(
                projected, turn=turn, decision_index=decision_index,
                reason="repair_episode_changed",
            )
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
            self._store_object(
                {**self.objects[identifier], "state": "inactive", "updated_turn": turn},
                turn=turn, decision_index=decision_index,
                reason="repair_episode_deactivated",
            )
            changed += 1
        if changed:
            self.last_internal_turn = turn
            self.last_state_transaction_id = f"decision:{int(decision_index):04d}"
            event = {
                "schema_version": EVENT_SCHEMA_VERSION,
                "internal_turn": turn,
                "decision_index": decision_index,
                "projection": "open_repair_episode",
                "changed": changed,
            }
            self._persist()
            self._append_event({
                **event, "workspace_snapshot_persisted": True,
            })
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
        if self.justification_invalidation_enabled:
            result.update(dependency_invalidations=0, dependency_revalidations=0)
        if self.semantic_impact_enabled:
            result.update(semantic_impacts=0, rejected_semantic_impacts=0,
                          semantic_revalidations=0)
        for value in upserts[:100]:
            normalized = self._normalize_object(value, turn) if isinstance(value, Mapping) else None
            if normalized is None:
                result["invalid"] += 1
                continue
            if normalized["role"] in {"root_contract", "root_obligation"}:
                # Root authority is owned exclusively by sync_root_obligations.
                result["invalid"] += 1
                self.rejected_root_mutations += 1
                continue
            normalized["root_links"] = [
                identifier for identifier in normalized["root_links"]
                if identifier == "root:public-task"
                or (identifier in self.objects
                    and self.objects[identifier].get("role") == "root_obligation")
            ]
            previous = self.objects.get(normalized["id"])
            if self._semantic_equal(previous, normalized):
                normalized["updated_turn"] = previous.get("updated_turn", turn)
            else:
                result["upserted"] += 1
            self._store_object(
                normalized, turn=turn, decision_index=decision_index,
                reason="monitor_semantic_update",
            )
            if (self.justification_invalidation_enabled
                    and self._evidence_withdrawn(previous, normalized)):
                result["dependency_invalidations"] += self._invalidate_supported_dependents(
                    normalized["id"], previous, normalized,
                    turn=turn, decision_index=decision_index,
                )
        for value in deactivations[:100]:
            identifier = self._clean_id(value)
            if not identifier or identifier == "root:public-task" or identifier not in self.objects:
                result["invalid"] += 1
                continue
            previous = dict(self.objects[identifier])
            inactive = {**previous, "state": "inactive", "updated_turn": turn}
            self._store_object(
                inactive,
                turn=turn, decision_index=decision_index,
                reason="monitor_deactivation",
            )
            if self.justification_invalidation_enabled:
                result["dependency_invalidations"] += self._invalidate_supported_dependents(
                    identifier, previous, inactive,
                    turn=turn, decision_index=decision_index,
                )
            result["deactivated"] += 1
        for value in relations[:200]:
            normalized = self._normalize_relation(value, turn) if isinstance(value, Mapping) else None
            if (normalized is None or normalized["source"] not in self.objects
                    or normalized["target"] not in self.objects):
                result["invalid"] += 1
                continue
            self.relations[self._relation_key(normalized)] = normalized
            result["relations"] += 1
            if (self.justification_invalidation_enabled
                    and normalized["relation"].lower() in {"revalidates", "restores"}
                    and normalized["target"] in self.pending_invalidations):
                del self.pending_invalidations[normalized["target"]]
                result["dependency_revalidations"] += 1
        if self.semantic_impact_enabled:
            accepted, rejected, revalidated = self._apply_semantic_impacts(
                delta.get("semantic_impacts", []), turn=turn,
                decision_index=decision_index,
            )
            result["semantic_impacts"] = accepted
            result["rejected_semantic_impacts"] = rejected
            result["semantic_revalidations"] = revalidated
        self.update_count += 1
        self.last_internal_turn = turn
        self.last_state_transaction_id = f"decision:{int(decision_index):04d}"
        event = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "internal_turn": turn,
            "decision_index": decision_index,
            "delta": dict(delta),
            "result": result,
        }
        self._persist()
        self._append_event({
            **event, "workspace_snapshot_persisted": True,
        })
        return result

    def active_view(self, *, object_limit: int = 48, relation_limit: int = 64) -> dict[str, Any]:
        """Return a bounded, single-version projection for routine deliberation."""
        active = [row for row in self.objects.values() if row.get("state") != "inactive"]
        roots = sorted(
            (row for row in active if row.get("role") in {"root_contract", "root_obligation"}),
            key=lambda row: (int(row.get("source_order", -1)), str(row.get("id", ""))),
        )
        local = sorted(
            (row for row in active if row.get("role") not in {"root_contract", "root_obligation"}),
            key=lambda row: (int(row.get("updated_turn") or 0), str(row.get("id", ""))),
            reverse=True,
        )
        # Root obligations are the immutable task basis and are never displaced
        # by transient evidence. Local state receives the remaining bounded slots.
        selected = roots + local[:max(0, object_limit - len(roots))]
        selected_ids = {row["id"] for row in selected}
        relations = [row for row in self.relations.values()
                     if row["source"] in selected_ids and row["target"] in selected_ids]
        relations.sort(key=lambda row: int(row.get("updated_turn") or 0), reverse=True)
        return {
            "schema_version": SCHEMA_VERSION,
            "public_task_sha256": self.public_task_sha256,
            "objects": selected,
            "relations": relations[:relation_limit],
            "metrics": self.metrics(),
            **({"pending_invalidations": list(self.pending_invalidations.values())}
               if self.justification_invalidation_enabled else {}),
            **({"pending_semantic_impacts": list(self.pending_semantic_impacts.values())}
               if self.semantic_impact_enabled else {}),
            "truncated": len(selected) < len(active) or len(relations) > relation_limit,
        }

    def index_view(self, *, object_limit: int = 80) -> dict[str, Any]:
        """Return a cheap navigation index, leaving semantic detail on demand."""
        active = [row for row in self.objects.values()
                  if row.get("state") != "inactive"]
        active.sort(
            key=lambda row: (
                row.get("role") not in {"root_contract", "root_obligation", "repair_episode"},
                -int(row.get("updated_turn") or 0),
                str(row.get("id", "")),
            )
        )
        selected = active[:max(1, min(200, object_limit))]
        return {
            "schema_version": SCHEMA_VERSION,
            "public_task_sha256": self.public_task_sha256,
            "objects": [{
                "id": row.get("id"),
                "role": row.get("role"),
                "state": row.get("state"),
                "summary_hint": self._clean_text(row.get("summary"), 240),
                "updated_turn": row.get("updated_turn"),
                "root_links": list(row.get("root_links", []))[:8],
            } for row in selected],
            "metrics": self.metrics(),
            **({"pending_invalidations": list(self.pending_invalidations.values())}
               if self.justification_invalidation_enabled else {}),
            **({"pending_semantic_impacts": list(self.pending_semantic_impacts.values())}
               if self.semantic_impact_enabled else {}),
            "truncated": len(selected) < len(active),
            "retrieval_hint": (
                "Use read_semantic_object for an exact id or "
                "search_semantic_workspace for a semantic query."
            ),
        }

    def get_object(self, identifier: str) -> dict[str, Any]:
        """Retrieve one semantic object and its directly connected relations."""
        clean = self._clean_id(identifier)
        if not clean:
            return {"ok": False, "error": "valid object id is required"}
        row = self.objects.get(clean)
        if row is None:
            return {"ok": False, "error": "semantic object not found", "id": clean}
        relations = [value for value in self.relations.values()
                     if value.get("source") == clean or value.get("target") == clean]
        relations.sort(key=self._relation_key)
        result = {"ok": True, "object": dict(row), "relations": relations[:100],
                  "relations_truncated": len(relations) > 100}
        if self.versioned_revision_enabled:
            result["revision_history"] = [
                dict(value) for value in self.revision_history
                if value.get("object_id") == clean
            ][-50:]
        return result

    def metrics(self) -> dict[str, Any]:
        active = [row for row in self.objects.values() if row.get("state") != "inactive"]
        return {
            "objects_total": len(self.objects),
            "objects_active": len(active),
            "root_obligations": sum(row.get("role") == "root_obligation" for row in self.objects.values()),
            "relations_total": len(self.relations),
            "update_count": self.update_count,
            "rejected_root_mutations": self.rejected_root_mutations,
            **({"revision_count": len(self.revision_history)}
               if self.versioned_revision_enabled else {}),
            **({"invalidation_count": len(self.invalidation_history),
                "pending_invalidations": len(self.pending_invalidations)}
               if self.justification_invalidation_enabled else {}),
            **({"semantic_impact_count": len(self.semantic_impact_history),
                "pending_semantic_impacts": len(self.pending_semantic_impacts),
                "rejected_semantic_impacts": self.rejected_semantic_impacts}
               if self.semantic_impact_enabled else {}),
        }

    def view(self, *, include_inactive: bool = False) -> dict[str, Any]:
        objects = [row for row in self.objects.values()
                   if include_inactive or row.get("state") != "inactive"]
        objects.sort(key=lambda row: (str(row.get("role", "")), str(row.get("id", ""))))
        relations = sorted(self.relations.values(), key=self._relation_key)
        active_ids = {row["id"] for row in objects}
        if not include_inactive:
            relations = [row for row in relations
                         if row["source"] in active_ids and row["target"] in active_ids]
        result = {
            "schema_version": SCHEMA_VERSION,
            "public_task_sha256": self.public_task_sha256,
            "objects": objects,
            "relations": relations,
            "update_count": self.update_count,
            "last_internal_turn": self.last_internal_turn,
            "last_state_transaction_id": self.last_state_transaction_id,
            "root_ledger_frozen": self.root_ledger_frozen,
            "rejected_root_mutations": self.rejected_root_mutations,
        }
        if self.versioned_revision_enabled:
            result["versioned_revision_enabled"] = True
            result["revision_history"] = list(self.revision_history)
        if self.justification_invalidation_enabled:
            result["justification_invalidation_enabled"] = True
            result["invalidation_history"] = list(self.invalidation_history)
            result["pending_invalidations"] = list(self.pending_invalidations.values())
        if self.semantic_impact_enabled:
            result["semantic_impact_enabled"] = True
            result["semantic_impact_history"] = list(self.semantic_impact_history)
            result["pending_semantic_impacts"] = list(self.pending_semantic_impacts.values())
            result["rejected_semantic_impacts"] = self.rejected_semantic_impacts
        return result

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
