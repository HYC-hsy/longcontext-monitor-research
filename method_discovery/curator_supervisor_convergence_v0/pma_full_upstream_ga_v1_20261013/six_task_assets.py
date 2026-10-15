"""Host-only fixed-source descriptors for the PMA/GA discovery draft.

The public role gets instruction.md, task.toml and environment; evaluator
blobs are exported separately after the Task has stopped. No solution or
research selection metadata is copied into either role.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import tomllib

from .export_official_evaluator import COMMIT, SIX_TASKS, git, official_members


def _members(source: Path, task: str, prefix: str, *, registered: bool = False) -> list[dict]:
    if task not in SIX_TASKS and not registered:
        raise ValueError("task outside registered official panel")
    if git(source, "cat-file", "-t", COMMIT).strip() != b"commit":
        raise RuntimeError("fixed official source commit unavailable")
    result = []
    for row in git(source, "ls-tree", "-r", "-z", COMMIT, prefix).split(b"\0"):
        if not row:
            continue
        identity, filename = row.split(b"\t", 1)
        mode, kind, blob = identity.decode("ascii").split()
        name = filename.decode("utf-8")
        if (not name.startswith(task + "/") or kind != "blob" or
                mode not in {"100644", "100755"}):
            raise RuntimeError("unsupported official task member")
        relative = Path(name).relative_to(task)
        if not relative.parts or ".." in relative.parts:
            raise RuntimeError("unsafe official task member path")
        raw = git(source, "cat-file", "blob", blob)
        result.append({"path": name, "mode": mode, "git_blob": blob,
                       "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                       "raw": raw})
    return result


def public_members(source: Path, task: str, *, registered: bool = False) -> list[dict]:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", task):
        raise ValueError("invalid official task identity")
    members = _members(source, task, task + "/", registered=registered)
    chosen = [m for m in members if Path(m["path"]).relative_to(task).parts[0]
              in {"instruction.md", "task.toml", "environment"}]
    if {task + "/instruction.md", task + "/task.toml"} - {
            m["path"] for m in chosen}:
        raise RuntimeError("official public task files missing")
    if not any(m["path"].startswith(task + "/environment/") for m in chosen):
        raise RuntimeError("official environment missing")
    return chosen


def descriptor(source: Path, task: str, *, registered: bool = False) -> dict:
    public = public_members(source, task, registered=registered)
    toml = next(m["raw"] for m in public if m["path"] == task + "/task.toml")
    cfg = tomllib.loads(toml.decode("utf-8"))
    env = cfg["environment"]
    test_script = next(m["raw"] for m in official_members(source, task, registered=registered)
                       if m["path"] == task + "/tests/test.sh")
    report_paths = list(dict.fromkeys(re.findall(
        r"--ctrf\s+(/logs/verifier/[^\s]+)", test_script.decode("utf-8"))))
    return {
        "official_commit": COMMIT, "task": task,
        "public_members": [{k: v for k, v in m.items() if k != "raw"} for m in public],
        "evaluator_members": [{k: v for k, v in m.items() if k != "raw"}
                              for m in official_members(source, task, registered=registered)],
        "image_tag": env["docker_image"],
        "resources": {k: env[k] for k in ("cpus", "memory_mb", "storage_mb",
                                             "gpus", "allow_internet")},
        "native_agent_seconds": cfg["agent"]["timeout_sec"],
        "native_verifier_seconds": cfg["verifier"]["timeout_sec"],
        "verifier_environment_mode": cfg["verifier"].get("environment_mode", "shared_default"),
        "expected_native_reports": report_paths,
        "report_contract": "source_declared_report_presence_only_native_reward_authoritative",
    }


def materialize_public(source: Path, task: str, target: Path,
                       expected: list[dict], *, registered: bool = False) -> None:
    """Copy only fixed public Git blobs to a fresh host-side Harbor task root."""
    if target.exists():
        raise FileExistsError(target)
    members = public_members(source, task, registered=registered)
    identities = [{k: v for k, v in m.items() if k != "raw"} for m in members]
    if identities != expected:
        raise RuntimeError("official public files differ from frozen descriptor")
    target.mkdir(parents=True)
    for item in members:
        relative = Path(item["path"]).relative_to(task)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(item["raw"])
        if hashlib.sha256(destination.read_bytes()).hexdigest() != item["sha256"]:
            raise RuntimeError("official public file readback mismatch")
        if item["mode"] == "100755":
            destination.chmod(destination.stat().st_mode | 0o111)
