"""Small single-run file transport; host bank and raw logs are never in spool.

The caller supplies pre-created mount roots.  This module does not create a
Docker container, select a host path for one, or retry an accepted event.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time
import uuid

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from episode import PMAEpisode


class SpoolError(RuntimeError):
    pass


def _atomic_json(path: Path, value: dict) -> None:
    descriptor, pending = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, path)
    finally:
        if os.path.exists(pending):
            os.unlink(pending)


class EventClient:
    """GA-side request/receipt client; timeout means delivery is unknown."""

    def __init__(self, request_dir: Path, response_dir: Path, run_id: str,
                 task_id: str, *, deadline_monotonic: float):
        self.requests = Path(request_dir).resolve(strict=True)
        self.responses = Path(response_dir).resolve(strict=True)
        self.run_id = run_id
        self.task_id = task_id
        self.deadline = deadline_monotonic
        self.sequence = 0
        if not self.requests.is_dir() or not self.responses.is_dir():
            raise SpoolError("PMA event spool unavailable")

    def exchange(self, kind: str, **fields):
        if time.monotonic() >= self.deadline:
            raise SpoolError("PMA event deadline expired before send")
        self.sequence += 1
        event_id = uuid.uuid4().hex
        request = {"schema": "pma-ga-events-v1", "kind": kind,
                   "run_id": self.run_id, "task_id": self.task_id,
                   "sequence": self.sequence, "event_id": event_id, **fields}
        target = self.requests / (event_id + ".json")
        _atomic_json(target, request)
        receipt = self.responses / target.name
        while True:
            if receipt.is_file():
                try:
                    value = json.loads(receipt.read_text(encoding="utf-8"))
                except (OSError, ValueError) as exc:
                    raise SpoolError("PMA receipt unreadable") from exc
                if (value.get("run_id"), value.get("task_id"), value.get("event_id")) != (
                        self.run_id, self.task_id, event_id):
                    raise SpoolError("PMA receipt identity mismatch")
                if value.get("status") != "ok":
                    raise SpoolError("PMA host event failed; see host-private event log")
                result = value.get("result")
                if not isinstance(result, dict):
                    raise SpoolError("PMA result is not an object")
                return result
            if time.monotonic() >= self.deadline:
                raise SpoolError("PMA receipt unknown; accepted event will not be replayed")
            time.sleep(0.02)


class EventDispatcher:
    """Trusted-host single-worker dispatcher with private PMA episode state."""

    def __init__(self, episode: PMAEpisode, request_dir: Path, response_dir: Path,
                 *, deadline_epoch: float | None = None):
        self.episode = episode
        self.requests = Path(request_dir).resolve(strict=True)
        self.responses = Path(response_dir).resolve(strict=True)
        self._processed = set()
        self.deadline_epoch = deadline_epoch
        if self.requests == self.responses or not self.requests.is_dir() or not self.responses.is_dir():
            raise SpoolError("invalid host event spool")
        shared_parent = self.requests.parent if self.requests.parent == self.responses.parent else None
        if (self.episode.archive.is_relative_to(self.requests)
                or self.episode.archive.is_relative_to(self.responses)
                or (shared_parent is not None
                    and self.episode.archive.is_relative_to(shared_parent))):
            raise SpoolError("private PMA archive must not be inside shared spool")

    async def serve_once(self) -> int:
        count = 0
        for path in sorted(self.requests.glob("*.json")):
            if self.deadline_epoch is not None and time.time() >= self.deadline_epoch:
                break
            if path.name in self._processed:
                continue
            if path.is_symlink() or not path.is_file():
                raise SpoolError("event request path is not a regular file")
            try:
                request = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise SpoolError("event request unreadable") from exc
            if (not isinstance(request, dict) or request.get("schema") != "pma-ga-events-v1"
                    or path.stem != request.get("event_id")
                    or (request.get("run_id"), request.get("task_id")) != (
                        self.episode.run_id, self.episode.task_id)):
                raise SpoolError("event identity mismatch")
            try:
                result = await self.episode.handle(request)
                response = {"status": "ok", "result": result}
            except Exception as exc:
                # Do not expose the bank, prompts, raw errors or credentials to GA.
                response = {"status": "error", "error_type": type(exc).__name__}
            if self.deadline_epoch is not None and time.time() >= self.deadline_epoch:
                with (self.episode.archive / "late_results.jsonl").open(
                        "a", encoding="utf-8") as stream:
                    stream.write(json.dumps({"event_id": request["event_id"],
                                             "status": "discarded_after_deadline",
                                             "remote_execution": "unknown"}) + "\n")
                self._processed.add(path.name)
                break
            response.update(run_id=self.episode.run_id, task_id=self.episode.task_id,
                            event_id=request["event_id"])
            _atomic_json(self.responses / path.name, response)
            self._processed.add(path.name)
            count += 1
        return count
