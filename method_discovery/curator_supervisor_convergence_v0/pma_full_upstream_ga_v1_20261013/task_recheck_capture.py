"""Default-off host-side Docker checkpoint capture for Task recheck research.

This module never changes the manager decision or Task request. A failed
capture is recorded locally and returned to the caller as unavailable.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def _atomic_json(path: Path, value: dict) -> None:
    pending = path.with_suffix(path.suffix + ".pending")
    with pending.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    pending.replace(path)


def _docker(*args: str, timeout: int = 300) -> str:
    result = subprocess.run(["docker", *args], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"docker {args[0]} failed with exit {result.returncode}: "
                           f"{result.stderr[:500]}")
    return result.stdout.strip()


def _image_identity(container_id: str) -> tuple[str, dict]:
    identity = json.loads(_docker("inspect", container_id, timeout=30))[0]
    if identity.get("Id") != container_id or not identity.get("State", {}).get("Running"):
        raise RuntimeError("original Task container identity or running state changed")
    mounts = identity.get("Mounts", [])
    if any(mount.get("Destination") == "/app" or
           str(mount.get("Destination", "")).startswith("/app/") for mount in mounts):
        raise RuntimeError("Task workspace is mounted; Docker commit cannot capture it")
    return identity["Image"], identity


def capture_wake_boundary(*, run_root: Path, run_id: str, actor_attempt: int,
                          pending_reminder: str | None, bank_file: Path,
                          batch_rounds: int,
                          capture_root: Path | None = None) -> dict:
    """Capture after a manager wake and before the Task's next model call."""
    configured = capture_root or (Path(os.environ["PMA_TASK_RECHECK_CAPTURE_ROOT"])
                                  if os.environ.get("PMA_TASK_RECHECK_CAPTURE_ROOT") else None)
    if configured is None or actor_attempt <= 1:
        return {"status": "disabled_or_initial"}
    root = Path(configured).resolve()
    run_root = Path(run_root).resolve(strict=True)
    if not root.is_absolute() or root == run_root or root in run_root.parents or run_root in root.parents:
        raise ValueError("capture root must be absolute and outside the run directory")
    item = root / run_id / f"after-step-{actor_attempt - 1:04d}"
    item.mkdir(parents=True, exist_ok=False)
    record = {"schema": "task-recheck-capture-v1", "run_id": run_id,
              "actor_attempt": actor_attempt, "after_task_step": actor_attempt - 1,
              "captured_at_epoch": time.time(), "status": "capture_failed"}
    try:
        original = json.loads((run_root / "archive/agent_start_identity.json").read_text(encoding="utf-8"))
        if original.get("run_id") != run_id:
            raise RuntimeError("agent_start_identity run mismatch")
        container_id = original["container_id"]
        original_image, container = _image_identity(container_id)
        bank = Path(bank_file).read_bytes()
        (item / "knowledge.json").write_bytes(bank)
        tag = f"lc-task-recheck:{run_id.lower()}-step-{actor_attempt - 1}"
        snapshot_image = _docker("commit", container_id, tag)
        if not snapshot_image.startswith("sha256:"):
            raise RuntimeError("Docker commit did not return an image ID")
        actual_image = json.loads(_docker("image", "inspect", tag, timeout=30))[0]["Id"]
        if actual_image != snapshot_image:
            raise RuntimeError("snapshot image ID changed after commit")
        network_mode = container.get('HostConfig', {}).get('NetworkMode')
        network_policy = None
        if network_mode and network_mode not in ('none', 'host', 'bridge'):
            network = json.loads(_docker('network', 'inspect', network_mode,
                                         timeout=30))[0]
            network_policy = {key: network.get(key) for key in
                              ('Driver', 'Internal', 'Attachable', 'EnableIPv6')}
        record.update(status="captured", original_container_id=container_id,
                      original_image_id=original_image, snapshot_image_id=snapshot_image,
                      snapshot_image_tag=tag,
                      original_network_mode=network_mode,
                      original_network_policy=network_policy,
                      original_mounts=[{key: mount.get(key) for key in
                                        ("Destination", "Type", "RW", "Name", "Source")}
                                       for mount in container.get("Mounts", [])],
                      knowledge_sha256=hashlib.sha256(bank).hexdigest(),
                      knowledge_bytes=len(bank),
                      pending_reminder=pending_reminder,
                      pending_reminder_sha256=(hashlib.sha256(pending_reminder.encode()).hexdigest()
                                               if pending_reminder else None))
    except Exception as exc:
        record.update(error_type=type(exc).__name__, error=str(exc))
    _atomic_json(item / "capture.json", record)
    return record
