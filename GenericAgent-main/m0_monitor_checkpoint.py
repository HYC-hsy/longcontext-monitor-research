"""Durable, auditable checkpoint storage for the M0 monitor.

The checkpoint is a task-memory index, not a replacement for raw trajectories.
It contains only state needed to resume supervision after context trimming or a
process restart.  Detailed observations remain in the JSONL/decision archive.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "m0-monitor-checkpoint/2"
READABLE_SCHEMA_VERSIONS = {"m0-monitor-checkpoint/1", SCHEMA_VERSION}


class MonitorCheckpointStore:
    """Atomically persist and restore one monitor's durable task state."""

    def __init__(self, artifact_dir: str | os.PathLike[str] | None,
                 public_task: str):
        self.artifact_dir = Path(artifact_dir).resolve() if artifact_dir else None
        self.public_task_sha256 = hashlib.sha256(
            public_task.encode("utf-8", errors="replace")
        ).hexdigest()
        self.path = self.artifact_dir / "monitor_checkpoint.json" if self.artifact_dir else None

    def load(self) -> dict[str, Any] | None:
        if self.path is None or not self.path.exists():
            return None
        try:
            value = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(value, Mapping):
            return None
        if value.get("schema_version") not in READABLE_SCHEMA_VERSIONS:
            return None
        if value.get("public_task_sha256") != self.public_task_sha256:
            return None
        return dict(value)

    def save(self, state: Mapping[str, Any]) -> None:
        if self.path is None:
            return
        payload = {
            "schema_version": SCHEMA_VERSION,
            "public_task_sha256": self.public_task_sha256,
            **dict(state),
        }
        self.write_json(self.path, payload)

    @staticmethod
    def write_json(path: Path, payload: Mapping[str, Any]) -> None:
        """Write one UTF-8 JSON object atomically without changing its semantics."""
        serialized = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        # Validate the exact serialized text before it can replace an archive.
        json.loads(serialized)
        temporary = path.with_name(path.name + ".tmp")
        try:
            temporary.write_text(serialized, encoding="utf-8")
            os.replace(temporary, path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    def load_archives(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Recover raw public trajectory and decisions without trusting them as authority."""
        if self.artifact_dir is None:
            return [], []
        trajectory: list[dict[str, Any]] = []
        trajectory_path = self.artifact_dir / "public_trajectory.jsonl"
        if trajectory_path.exists():
            for line in trajectory_path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    trajectory.append(value)
        decisions: list[dict[str, Any]] = []
        for path in sorted(self.artifact_dir.glob("decision_*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(value, dict):
                decisions.append(value)
        return trajectory, decisions
