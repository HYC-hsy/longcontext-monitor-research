"""Model-owned semantic files for a persistent monitor.

The monitor may organize natural-language cognition freely inside this
workspace.  The runtime owns only filesystem safety, optimistic concurrency,
atomic replacement, and append-only versions; it never interprets semantics.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "monitor-semantic-files/1"
MAX_FILE_CHARACTERS = 1_000_000
MAX_EDIT_CHARACTERS = 250_000
DEFAULT_FILES = {
    "state/task_model.md": """# Task model

Use this file for your revisable understanding of the original task. Preserve
explicit requirements, distinguish observations from claims, and link useful
public evidence in ordinary language. Organize it to fit this task.
""",
    "state/working_state.md": """# Working state

Record the current task-level picture, what you have investigated, and what
still matters. This is your own durable cognition, not a required schema.
""",
    "state/current_repair.md": """# Current repair

No repair is currently open. When a correction needs follow-up, record what
was contested, what response you are watching, and what would release focus.
""",
    "evidence/index.md": """# Evidence index

Keep only useful navigation anchors to public trajectory, files, diffs, tests,
and tool results. Evidence remains authoritative at its source, not here.
""",
}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


class MonitorSemanticFiles:
    """A small generic filesystem owned by one persistent monitor."""

    def __init__(self, artifact_dir: str | os.PathLike[str] | None,
                 public_task: str):
        self.artifact_dir = Path(artifact_dir).resolve() if artifact_dir else None
        self.root = self.artifact_dir / "semantic_files" if self.artifact_dir else None
        self._lock = threading.RLock()
        if self.root is not None:
            self._initialize(public_task)

    @property
    def enabled(self) -> bool:
        return self.root is not None

    def _initialize(self, public_task: str) -> None:
        assert self.root is not None
        (self.root / "task").mkdir(parents=True, exist_ok=True)
        (self.root / "state").mkdir(parents=True, exist_ok=True)
        (self.root / "evidence").mkdir(parents=True, exist_ok=True)
        (self.root / ".versions").mkdir(parents=True, exist_ok=True)
        task_path = self.root / "task" / "original_task.md"
        if not task_path.exists():
            self._atomic_write(task_path, public_task)
        elif task_path.read_text(encoding="utf-8-sig") != public_task:
            raise ValueError("semantic workspace belongs to a different public task")
        for relative, content in DEFAULT_FILES.items():
            path = self.root / relative
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                self._atomic_write(path, content)
        metadata = self.root / ".workspace.json"
        if not metadata.exists():
            self._atomic_write(metadata, json.dumps({
                "schema_version": SCHEMA_VERSION,
                "public_task_sha256": _sha256(public_task),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }, ensure_ascii=False, indent=2))

    def _path(self, value: Any, *, writable: bool = False) -> Path:
        if self.root is None:
            raise ValueError("monitor semantic workspace is disabled")
        relative = str(value or ".").replace("\\", "/")
        path = (self.root / relative).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as error:
            raise ValueError("path escapes monitor semantic workspace") from error
        if writable:
            rel = path.relative_to(self.root).as_posix()
            if rel.startswith("task/") or rel.startswith(".versions/") or rel == ".workspace.json":
                raise ValueError("path is runtime-owned or read-only")
            if not (rel.startswith("state/") or rel.startswith("evidence/")):
                raise ValueError("monitor may edit only state/ and evidence/")
            if path.suffix.lower() not in {".md", ".txt", ".json"}:
                raise ValueError("unsupported semantic file type")
        return path

    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
        try:
            temporary.write_text(text, encoding="utf-8")
            os.replace(temporary, path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    @contextmanager
    def _process_edit_lock(self):
        """Serialize short edits across replaced or overlapping worker processes."""
        assert self.root is not None
        lock_path = self.root / ".edit.lock"
        deadline = time.monotonic() + 5.0
        descriptor = None
        while descriptor is None:
            try:
                descriptor = os.open(
                    lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY
                )
                os.write(descriptor, json.dumps({
                    "pid": os.getpid(), "created_at": time.time(),
                }).encode("utf-8"))
            except FileExistsError:
                try:
                    age = time.time() - lock_path.stat().st_mtime
                    if age > 30:
                        lock_path.unlink(missing_ok=True)
                        continue
                except OSError:
                    pass
                if time.monotonic() >= deadline:
                    raise ValueError("monitor semantic workspace is busy; read and retry")
                time.sleep(0.01)
        try:
            yield
        finally:
            try:
                if descriptor is not None:
                    os.close(descriptor)
            finally:
                lock_path.unlink(missing_ok=True)

    def execute(self, request: Mapping[str, Any]) -> dict[str, Any]:
        operation = str(request.get("operation", "")).strip()
        try:
            if operation == "list_files":
                return self._list_files(request)
            if operation == "read_file":
                return self._read_file(request)
            if operation == "search":
                return self._search(request)
            if operation == "edit_file":
                return self._edit_file(request)
            return {"ok": False, "error": f"unsupported semantic operation: {operation}"}
        except (OSError, UnicodeError, ValueError, re.error) as error:
            return {"ok": False, "error": str(error), "error_type": type(error).__name__}

    def initialize_task_model(self, task_model: str) -> dict[str, Any]:
        """Seed the monitor-authored natural task model once at turn zero."""
        path = self._path("state/task_model.md", writable=True)
        with self._lock, self._process_edit_lock():
            current = path.read_text(encoding="utf-8-sig")
            if current != DEFAULT_FILES["state/task_model.md"]:
                return {"ok": True, "changed": False, "reason": "already_initialized"}
            body = task_model.strip()
            if not body:
                raise ValueError("turn-zero task model is empty")
            text = "# Task model\n\n" + body + "\n"
            self._archive_version(path, current, _sha256(current))
            self._atomic_write(path, text)
            return {"ok": True, "changed": True, "sha256": _sha256(text)}

    def _list_files(self, request: Mapping[str, Any]) -> dict[str, Any]:
        base = self._path(request.get("path", "."))
        if not base.exists():
            return {"ok": False, "error": "path does not exist"}
        limit = min(500, max(1, int(request.get("limit", 200))))
        paths = [base] if base.is_file() else base.rglob("*")
        files: list[dict[str, Any]] = []
        for path in paths:
            if not path.is_file():
                continue
            relative = path.relative_to(self.root).as_posix()  # type: ignore[arg-type]
            if (relative.startswith(".versions/")
                    or relative in {".workspace.json", ".edit.lock"}):
                continue
            files.append({"path": relative, "characters": path.stat().st_size})
            if len(files) >= limit:
                break
        return {"ok": True, "files": files, "truncated": len(files) >= limit}

    def _read_file(self, request: Mapping[str, Any]) -> dict[str, Any]:
        path = self._path(request.get("path", ""))
        if not path.is_file():
            return {"ok": False, "error": "file does not exist"}
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        if len(text) > MAX_FILE_CHARACTERS:
            return {"ok": False, "error": "semantic file exceeds safe read limit"}
        start = max(1, int(request.get("start_line", 1)))
        count = min(4000, max(1, int(request.get("line_count", 800))))
        lines = text.splitlines()
        selected = "\n".join(
            f"{number}: {line}"
            for number, line in enumerate(lines[start - 1:start - 1 + count], start)
        )
        return {
            "ok": True,
            "path": path.relative_to(self.root).as_posix(),  # type: ignore[union-attr]
            "content": selected,
            "sha256": _sha256(text),
            "line_count": len(lines),
            "truncated": start - 1 + count < len(lines),
        }

    def _search(self, request: Mapping[str, Any]) -> dict[str, Any]:
        base = self._path(request.get("path", "."))
        pattern = re.compile(
            str(request.get("pattern", "")),
            re.IGNORECASE if request.get("ignore_case", True) else 0,
        )
        limit = min(500, max(1, int(request.get("limit", 100))))
        paths = [base] if base.is_file() else base.rglob("*")
        matches: list[dict[str, Any]] = []
        for path in paths:
            if not path.is_file() or ".versions" in path.parts:
                continue
            if path.stat().st_size > MAX_FILE_CHARACTERS:
                continue
            for line_number, line in enumerate(path.read_text(
                    encoding="utf-8-sig", errors="replace").splitlines(), 1):
                if pattern.search(line):
                    matches.append({
                        "path": path.relative_to(self.root).as_posix(),  # type: ignore[union-attr]
                        "line": line_number,
                        "text": line[:2000],
                    })
                    if len(matches) >= limit:
                        return {"ok": True, "matches": matches, "truncated": True}
        return {"ok": True, "matches": matches, "truncated": False}

    def _edit_file(self, request: Mapping[str, Any]) -> dict[str, Any]:
        path = self._path(request.get("path", ""), writable=True)
        expected = str(request.get("expected_sha256", "")).strip()
        edits = request.get("edits")
        if not isinstance(edits, list) or not edits:
            return {"ok": False, "error": "edits must be a non-empty list"}
        with self._lock, self._process_edit_lock():
            exists = path.exists()
            previous = path.read_text(encoding="utf-8-sig") if exists else ""
            previous_hash = _sha256(previous)
            if exists and not expected:
                return {
                    "ok": False,
                    "conflict": True,
                    "error": "expected_sha256 from read_file is required",
                    "current_sha256": previous_hash,
                }
            if expected and expected != previous_hash:
                return {
                    "ok": False,
                    "conflict": True,
                    "error": "file changed since it was read",
                    "expected_sha256": expected,
                    "current_sha256": previous_hash,
                }
            updated = previous
            receipts: list[dict[str, Any]] = []
            for index, edit in enumerate(edits):
                if not isinstance(edit, Mapping):
                    return {"ok": False, "error": f"edit {index} is not an object"}
                old = str(edit.get("old_text", ""))
                new = str(edit.get("new_text", ""))
                if not old:
                    if exists or len(edits) != 1 or index != 0:
                        return {
                            "ok": False,
                            "error": (
                                f"edit {index} has empty old_text; this is allowed only "
                                "for one-step creation of a new file"
                            ),
                        }
                    updated = new
                    receipts.append({
                        "edit": index, "created": True,
                        "removed_characters": 0, "added_characters": len(new),
                    })
                    continue
                occurrences = updated.count(old)
                if occurrences != 1:
                    return {
                        "ok": False,
                        "conflict": True,
                        "error": f"edit {index} expected one exact match, found {occurrences}",
                        "current_sha256": previous_hash,
                    }
                updated = updated.replace(old, new, 1)
                receipts.append({
                    "edit": index,
                    "removed_characters": len(old),
                    "added_characters": len(new),
                })
            if len(updated) > MAX_EDIT_CHARACTERS:
                return {"ok": False, "error": "edited file exceeds semantic state limit"}
            if updated == previous:
                return {"ok": True, "changed": False, "sha256": previous_hash}
            self._archive_version(path, previous, previous_hash)
            self._atomic_write(path, updated)
            current_hash = _sha256(updated)
            return {
                "ok": True,
                "changed": True,
                "path": path.relative_to(self.root).as_posix(),  # type: ignore[union-attr]
                "previous_sha256": previous_hash,
                "sha256": current_hash,
                "edits": receipts,
            }

    def _archive_version(self, path: Path, previous: str, digest: str) -> None:
        assert self.root is not None
        relative = path.relative_to(self.root).as_posix()
        sequence = len(list((self.root / ".versions").glob("*.json"))) + 1
        archive = self.root / ".versions" / f"{sequence:06d}.json"
        self._atomic_write(archive, json.dumps({
            "schema_version": SCHEMA_VERSION,
            "path": relative,
            "previous_sha256": digest,
            "previous_content": previous,
            "archived_at": datetime.now(timezone.utc).isoformat(),
        }, ensure_ascii=False, indent=2))
