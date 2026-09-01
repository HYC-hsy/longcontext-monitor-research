"""Filesystem boundary for the clean Monitor Agent foundation.

The monitor may inspect authoritative task evidence, but it may only mutate its
own private workspace.  Analysis programs receive a disposable copy of task
evidence so their writes can never change the supervised task.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path


class MonitorPathError(ValueError):
    """Raised when a virtual monitor path violates the workspace boundary."""


class MonitorWorkspace:
    """Expose ``task/...`` as read-only and ``monitor/...`` as writable."""

    TASK_PREFIX = "task"
    PRIVATE_PREFIX = "monitor"
    SNAPSHOT_NAME = ".task_view"

    def __init__(self, task_root: str | os.PathLike, private_root: str | os.PathLike,
                 task_mounts: dict[str, str | os.PathLike] | None = None):
        self.task_root = Path(task_root).resolve(strict=True)
        self.private_root = Path(private_root).resolve()
        if not self.task_root.is_dir():
            raise MonitorPathError(f"Task evidence root is not a directory: {self.task_root}")
        self.private_root.mkdir(parents=True, exist_ok=True)
        self.snapshot_root = self.private_root / self.SNAPSHOT_NAME
        self.task_mounts = {}
        for name, value in (task_mounts or {}).items():
            if not name or "/" in name or "\\" in name or name in {".", ".."}:
                raise MonitorPathError(f"Invalid task mount name: {name!r}")
            root = Path(value).resolve(strict=True)
            if not root.is_dir():
                raise MonitorPathError(f"Task mount is not a directory: {root}")
            self.task_mounts[name] = root

    @staticmethod
    def _relative_parts(path: str) -> tuple[str, tuple[str, ...]]:
        normalized = str(path or "").replace("\\", "/").strip("/")
        parts = tuple(part for part in normalized.split("/") if part)
        if not parts or parts[0] not in {MonitorWorkspace.TASK_PREFIX, MonitorWorkspace.PRIVATE_PREFIX}:
            raise MonitorPathError("Path must start with task/ or monitor/")
        if any(part in {".", ".."} for part in parts[1:]):
            raise MonitorPathError("Relative path traversal is not allowed")
        return parts[0], parts[1:]

    @staticmethod
    def _contained(root: Path, candidate: Path) -> Path:
        resolved = candidate.resolve(strict=False)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise MonitorPathError(f"Path escapes workspace root: {candidate}") from exc
        return resolved

    def resolve_read(self, virtual_path: str) -> Path:
        namespace, parts = self._relative_parts(virtual_path)
        root = self.task_root if namespace == self.TASK_PREFIX else self.private_root
        if namespace == self.TASK_PREFIX and parts and parts[0] in self.task_mounts:
            root = self.task_mounts[parts[0]]
            parts = parts[1:]
        path = self._contained(root, root.joinpath(*parts))
        if not path.is_file():
            raise FileNotFoundError(virtual_path)
        return path

    def resolve_private_write(self, virtual_path: str) -> Path:
        namespace, parts = self._relative_parts(virtual_path)
        if namespace != self.PRIVATE_PREFIX:
            raise MonitorPathError("Monitor writes are restricted to monitor/")
        if not parts:
            raise MonitorPathError("A file path under monitor/ is required")
        path = self._contained(self.private_root, self.private_root.joinpath(*parts))
        if path == self.snapshot_root or self.snapshot_root in path.parents:
            raise MonitorPathError("The disposable task view is runtime-owned")
        return path

    def read_text(self, virtual_path: str, start: int = 1, count: int = 200) -> dict:
        if start < 1 or count < 1 or count > 1000:
            raise ValueError("start must be >= 1 and count must be between 1 and 1000")
        path = self.resolve_read(virtual_path)
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            lines = stream.readlines()
        selected = lines[start - 1:start - 1 + count]
        content = "".join(selected)
        return {
            "path": virtual_path,
            "start": start,
            "lines": len(selected),
            "total_lines": len(lines),
            "content": content,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    def write_text(self, virtual_path: str, content: str, mode: str = "replace") -> dict:
        if mode not in {"replace", "append", "prepend"}:
            raise ValueError("mode must be replace, append, or prepend")
        path = self.resolve_private_write(virtual_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        old = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        updated = content if mode == "replace" else old + content if mode == "append" else content + old
        path.write_text(updated, encoding="utf-8")
        return self._write_receipt(virtual_path, path, len(updated))

    def patch_text(self, virtual_path: str, old_text: str, new_text: str) -> dict:
        if not old_text:
            raise ValueError("old_text must not be empty")
        path = self.resolve_private_write(virtual_path)
        if not path.is_file():
            raise FileNotFoundError(virtual_path)
        content = path.read_text(encoding="utf-8", errors="replace")
        matches = content.count(old_text)
        if matches != 1:
            raise ValueError(f"old_text must match exactly once; found {matches}")
        updated = content.replace(old_text, new_text, 1)
        path.write_text(updated, encoding="utf-8")
        return self._write_receipt(virtual_path, path, len(updated))

    @staticmethod
    def _write_receipt(virtual_path: str, path: Path, characters: int) -> dict:
        return {
            "path": virtual_path,
            "characters": characters,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    def refresh_analysis_snapshot(self) -> Path:
        """Build a disposable copy for analysis code without following links."""
        temp_root = Path(tempfile.mkdtemp(prefix="task-view-", dir=self.private_root))
        try:
            for source_dir, dir_names, file_names in os.walk(self.task_root, followlinks=False):
                source_dir = Path(source_dir)
                relative = source_dir.relative_to(self.task_root)
                target_dir = temp_root / relative
                target_dir.mkdir(parents=True, exist_ok=True)
                dir_names[:] = [name for name in dir_names if not (source_dir / name).is_symlink()]
                for name in file_names:
                    source = source_dir / name
                    if source.is_symlink():
                        continue
                    shutil.copy2(source, target_dir / name)
            for name, mount_root in self.task_mounts.items():
                self._copy_tree_without_links(mount_root, temp_root / name)
            if self.snapshot_root.exists():
                shutil.rmtree(self.snapshot_root)
            temp_root.replace(self.snapshot_root)
            return self.snapshot_root
        except Exception:
            shutil.rmtree(temp_root, ignore_errors=True)
            raise

    @staticmethod
    def _copy_tree_without_links(source_root: Path, target_root: Path) -> None:
        for source_dir, dir_names, file_names in os.walk(source_root, followlinks=False):
            source_dir = Path(source_dir)
            relative = source_dir.relative_to(source_root)
            target_dir = target_root / relative
            target_dir.mkdir(parents=True, exist_ok=True)
            dir_names[:] = [name for name in dir_names if not (source_dir / name).is_symlink()]
            for name in file_names:
                source = source_dir / name
                if not source.is_symlink():
                    shutil.copy2(source, target_dir / name)
