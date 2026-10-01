"""Offline, researcher-specified workspace transition on a verified checkpoint.

This research fixture copies X_t and applies explicit file-content operations.
It does not restore E_t, run either Agent, call a model, or classify the change.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
import shutil
import stat
import time
from pathlib import Path

from .checkpoint import _json_bytes, _sha_bytes, _sha_file, _tree_manifest, verify_checkpoint


SCHEMA = "controlled-workspace-transition/0"
SOURCE_SCHEMA = "research-content-patch/1"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")


def _write_json(path: Path, value) -> None:
    path.write_bytes(_json_bytes(value))


def _copy_workspace(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination, symlinks=True)


def _relative_path(raw) -> Path:
    if (not isinstance(raw, str) or not raw or "\\" in raw
            or raw.startswith("/") or ":" in raw
            or any(part in ("", ".", "..") for part in raw.split("/"))):
        raise ValueError("patch path must be a normalized relative POSIX path")
    if raw.split("/")[0] == ".git":
        raise ValueError("patch may not modify .git metadata")
    return Path(*raw.split("/"))


def _parse_source(raw: bytes, *, transition_id: str, checkpoint_id: str) -> list[dict]:
    source = json.loads(raw)
    if (not isinstance(source, dict) or source.get("schema") != SOURCE_SCHEMA
            or source.get("transition_id") != transition_id
            or source.get("checkpoint_id") != checkpoint_id
            or not isinstance(source.get("operations"), list)
            or set(source) != {"schema", "checkpoint_id", "transition_id", "operations"}):
        raise ValueError("transition source identity or schema mismatch")
    operations = []
    seen = set()
    for index, item in enumerate(source["operations"]):
        if not isinstance(item, dict) or item.get("op") not in ("write", "delete"):
            raise ValueError(f"operation {index} is not a supported content patch")
        relative = _relative_path(item.get("path"))
        folded = relative.as_posix().casefold()
        if any(folded == old or folded.startswith(old + "/") or old.startswith(folded + "/")
               for old in seen):
            raise ValueError("duplicate or overlapping patch path")
        seen.add(folded)
        prior = item.get("before_sha256")
        if prior is not None and (not isinstance(prior, str) or not _HEX.fullmatch(prior)):
            raise ValueError(f"operation {index} has an invalid before hash")
        if item["op"] == "delete":
            if prior is None or set(item) != {"op", "path", "before_sha256"}:
                raise ValueError("delete requires an exact existing-file precondition")
            content = None
        else:
            if set(item) != {"op", "path", "before_sha256", "content_base64"}:
                raise ValueError("write requires exact content and a before precondition")
            try:
                content = base64.b64decode(item["content_base64"], validate=True)
            except (binascii.Error, TypeError, ValueError) as exc:
                raise ValueError("write has invalid base64 content") from exc
        operations.append({"op": item["op"], "path": relative,
                           "before_sha256": prior, "content": content})
    return operations


def _target(root: Path, relative: Path) -> Path:
    current = root
    for part in relative.parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise ValueError("patch path traverses a symlink")
        if current.exists() and not current.is_dir():
            raise ValueError("patch parent is not a directory")
    path = root / relative
    if path.is_symlink():
        raise ValueError("patch target is a symlink")
    return path


def _check_preconditions(root: Path, operations: list[dict]) -> None:
    for item in operations:
        target = _target(root, item["path"])
        prior = item["before_sha256"]
        if prior is None:
            if target.exists():
                raise ValueError(f"added path already exists: {item['path'].as_posix()}")
        elif not target.is_file() or _sha_file(target) != prior:
            raise ValueError(f"before-file identity mismatch: {item['path'].as_posix()}")


def _apply(root: Path, operations: list[dict], log: Path) -> None:
    with log.open("wb") as stream:
        for index, item in enumerate(operations):
            target = _target(root, item["path"])
            if item["op"] == "delete":
                target.unlink()
                after = None
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(target.name + ".fixture-partial")
                if temporary.exists() or temporary.is_symlink():
                    raise ValueError("patch temporary path already exists")
                try:
                    temporary.write_bytes(item["content"])
                    if target.exists():
                        os.chmod(temporary, stat.S_IMODE(target.stat().st_mode))
                    os.replace(temporary, target)
                finally:
                    temporary.unlink(missing_ok=True)
                after = _sha_file(target)
            stream.write(_json_bytes({"operation_index": index, "op": item["op"],
                                      "path": item["path"].as_posix(),
                                      "before_sha256": item["before_sha256"],
                                      "after_sha256": after, "status": "applied"}))
            stream.flush()


def apply_transition_fixture(*, checkpoint_dir, transition_source, transition_id,
                             expected_source_sha256, expected_checkpoint_id,
                             output_root) -> Path:
    """Apply one preregistered content bundle to an independent X_t copy.

    The source file is frozen by its caller-supplied SHA-256. Every attempt gets
    a unique output directory; errors retain the partial copy and a failure
    marker. No retry, repair or rollback is performed.
    """
    if not isinstance(transition_id, str) or not _ID.fullmatch(transition_id):
        raise ValueError("transition_id must be one safe path component")
    if not isinstance(expected_checkpoint_id, str) or not _ID.fullmatch(expected_checkpoint_id):
        raise ValueError("expected_checkpoint_id must be one safe path component")
    if not isinstance(expected_source_sha256, str) or not _HEX.fullmatch(expected_source_sha256):
        raise ValueError("expected_source_sha256 must be a SHA-256 digest")
    checkpoint = Path(checkpoint_dir).resolve(strict=True)
    output_parent = Path(output_root).resolve()
    if output_parent == checkpoint or output_parent.is_relative_to(checkpoint):
        raise ValueError("transition output must be outside the checkpoint")
    output_parent.mkdir(parents=True, exist_ok=True)
    root = output_parent / transition_id
    root.mkdir()  # exclusive; never overwrite a prior attempt or failure
    record = {"schema": SCHEMA, "transition_id": transition_id,
              "checkpoint_id": expected_checkpoint_id,
              "status": "initializing", "source_sha256_expected": expected_source_sha256,
              "source_sha256_actual": None, "before_workspace_manifest_sha256": None,
              "after_workspace_manifest_sha256": None}
    _write_json(root / "transition.json", record)
    try:
        verified = verify_checkpoint(checkpoint)
        if verified["checkpoint_id"] != expected_checkpoint_id:
            raise ValueError("checkpoint identity mismatch")
        source_bytes = Path(transition_source).read_bytes()
        source_hash = _sha_bytes(source_bytes)
        record["source_sha256_actual"] = source_hash
        (root / "transition_source.json").write_bytes(source_bytes)
        _write_json(root / "source_hash.json", {"expected_sha256": expected_source_sha256,
                                                "actual_sha256": source_hash,
                                                "matches": source_hash == expected_source_sha256})
        if source_hash != expected_source_sha256:
            raise ValueError("transition source hash mismatch")
        operations = _parse_source(source_bytes, transition_id=transition_id,
                                   checkpoint_id=expected_checkpoint_id)

        workspace = root / "workspace"
        _copy_workspace(checkpoint / "workspace", workspace)
        before = _tree_manifest(workspace)
        frozen_before = json.loads((checkpoint / "workspace_manifest.json").read_bytes())
        if before != frozen_before:
            raise ValueError("before workspace identity mismatch")
        _write_json(root / "before_manifest.json", before)
        record["before_workspace_manifest_sha256"] = _sha_file(root / "before_manifest.json")
        _check_preconditions(workspace, operations)
        _write_json(root / "start.json", {"schema": SCHEMA, "transition_id": transition_id,
                                          "checkpoint_id": expected_checkpoint_id,
                                          "source_sha256": source_hash,
                                          "before_workspace_manifest_sha256": record["before_workspace_manifest_sha256"],
                                          "started_at_epoch": time.time()})
        record["status"] = "applying"
        _write_json(root / "transition.json", record)
        _apply(workspace, operations, root / "execution_log.jsonl")
        after = _tree_manifest(workspace)
        _write_json(root / "after_manifest.json", after)
        record["after_workspace_manifest_sha256"] = _sha_file(root / "after_manifest.json")
        # The supposedly immutable research starting point must still verify.
        verify_checkpoint(checkpoint)
        record["status"] = "complete"
        _write_json(root / "transition.json", record)
        _write_json(root / "end.json", {"schema": SCHEMA, "status": "complete",
                                        "transition_id": transition_id,
                                        "after_workspace_manifest_sha256": record["after_workspace_manifest_sha256"],
                                        "ended_at_epoch": time.time()})
        return root
    except Exception as exc:
        if (root / "workspace").is_dir() and not (root / "after_manifest.json").exists():
            try:
                _write_json(root / "after_manifest.json", _tree_manifest(root / "workspace"))
                record["after_workspace_manifest_sha256"] = _sha_file(root / "after_manifest.json")
            except Exception:
                pass  # The failure marker remains authoritative when the copy cannot be scanned.
        record["status"] = "failed"
        record["error_type"] = type(exc).__name__
        record["reason"] = str(exc)
        _write_json(root / "transition.json", record)
        _write_json(root / "end.json", {"schema": SCHEMA, "status": "failed",
                                        "transition_id": transition_id,
                                        "error_type": type(exc).__name__,
                                        "reason": str(exc),
                                        "ended_at_epoch": time.time()})
        raise
