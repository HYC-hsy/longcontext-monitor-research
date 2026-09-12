"""Hard filesystem boundary for Monitor Agent evidence and private cognition."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from collections import deque
from pathlib import Path


class MonitorPathError(ValueError):
    pass


class MonitorWorkspace:
    def __init__(self, evidence_root, private_root, task_mounts=None):
        self.evidence_root = Path(evidence_root).resolve(strict=True)
        self.private_root = Path(private_root).resolve()
        if not self.evidence_root.is_dir():
            raise MonitorPathError(f"Evidence root is not a directory: {self.evidence_root}")
        self.private_root.mkdir(parents=True, exist_ok=True)
        self.snapshot_root = self.private_root / ".task_view"
        self.task_mounts = {}
        for name, value in (task_mounts or {}).items():
            if not name or any(token in name for token in ("/", "\\")) or name in {".", ".."}:
                raise MonitorPathError(f"Invalid task mount name: {name!r}")
            root = Path(value).resolve(strict=True)
            if not root.is_dir():
                raise MonitorPathError(f"Task mount is not a directory: {root}")
            self.task_mounts[name] = root

    @staticmethod
    def _parts(virtual_path: str):
        normalized = str(virtual_path or "").replace("\\", "/").strip("/")
        parts = tuple(part for part in normalized.split("/") if part)
        if not parts or parts[0] not in {"task", "monitor"}:
            raise MonitorPathError("Path must start with task/ or monitor/")
        if any(part in {".", ".."} for part in parts[1:]):
            raise MonitorPathError("Path traversal is not allowed")
        return parts[0], parts[1:]

    @staticmethod
    def _within(root: Path, candidate: Path) -> Path:
        resolved = candidate.resolve(strict=False)
        try: resolved.relative_to(root)
        except ValueError as exc: raise MonitorPathError("Path escapes its workspace root") from exc
        return resolved

    def resolve_read(self, virtual_path: str) -> Path:
        namespace, parts = self._parts(virtual_path)
        root = self.evidence_root if namespace == "task" else self.private_root
        if namespace == "task" and parts and parts[0] in self.task_mounts:
            root, parts = self.task_mounts[parts[0]], parts[1:]
        path = self._within(root, root.joinpath(*parts))
        if not path.is_file():
            raise FileNotFoundError(virtual_path)
        return path

    def resolve_private(self, virtual_path: str) -> Path:
        namespace, parts = self._parts(virtual_path)
        if namespace != "monitor" or not parts:
            raise MonitorPathError("Writes require a file under monitor/")
        path = self._within(self.private_root, self.private_root.joinpath(*parts))
        if path == self.snapshot_root or self.snapshot_root in path.parents:
            raise MonitorPathError("The analysis snapshot is runtime-owned")
        return path

    def read_text(self, virtual_path: str, start=1, count=200, tail=False) -> dict:
        start, count = int(start), int(count)
        if start < 1 or not 1 <= count <= 1000:
            raise ValueError("start >= 1 and 1 <= count <= 1000 are required")
        if type(tail) is not bool or (tail and start != 1):
            raise ValueError("tail must be boolean; with tail=true omit start")
        path = self.resolve_read(virtual_path)
        selected, total = deque(maxlen=count) if tail else [], 0
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for raw in stream:
                total += 1
                digest.update(raw)
                if tail or start <= total < start + count:
                    selected.append(raw.decode("utf-8", errors="replace").replace("\r\n", "\n"))
        if tail:
            start = max(1, total - len(selected) + 1)
        return {
            "path": virtual_path, "start": start, "lines": len(selected),
            "total_lines": total, "content": "".join(selected), "sha256": digest.hexdigest(),
        }

    def write_text(self, virtual_path: str, content: str, mode="replace") -> dict:
        if mode not in {"replace", "append", "prepend"}:
            raise ValueError("mode must be replace, append, or prepend")
        path = self.resolve_private(virtual_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        old = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        updated = content if mode == "replace" else old + content if mode == "append" else content + old
        path.write_text(updated, encoding="utf-8")
        return self._receipt(virtual_path, path, len(updated))

    def patch_text(self, virtual_path: str, old_text: str, new_text: str) -> dict:
        if not old_text:
            raise ValueError("old_text must not be empty")
        path = self.resolve_private(virtual_path)
        content = path.read_text(encoding="utf-8", errors="replace")
        matches = content.count(old_text)
        if matches != 1:
            raise ValueError(f"old_text must match exactly once; found {matches}")
        updated = content.replace(old_text, new_text, 1)
        path.write_text(updated, encoding="utf-8")
        return self._receipt(virtual_path, path, len(updated))

    @staticmethod
    def _receipt(virtual_path, path, characters):
        return {
            "path": virtual_path, "characters": characters,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    @staticmethod
    def _copy_tree(source_root: Path, target_root: Path):
        for source_dir, dirs, files in os.walk(source_root, followlinks=False):
            source_dir = Path(source_dir)
            target_dir = target_root / source_dir.relative_to(source_root)
            target_dir.mkdir(parents=True, exist_ok=True)
            dirs[:] = [name for name in dirs if not (source_dir / name).is_symlink()]
            for name in files:
                source = source_dir / name
                if not source.is_symlink(): shutil.copy2(source, target_dir / name)

    def refresh_snapshot(self) -> Path:
        temporary = Path(tempfile.mkdtemp(prefix="task-view-", dir=self.private_root))
        try:
            self._copy_tree(self.evidence_root, temporary)
            for name, root in self.task_mounts.items(): self._copy_tree(root, temporary / name)
            if self.snapshot_root.exists(): shutil.rmtree(self.snapshot_root)
            temporary.replace(self.snapshot_root)
            return self.snapshot_root
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
