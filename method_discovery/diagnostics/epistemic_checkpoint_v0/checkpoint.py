"""One-shot, model-invisible research capture of (Supervisor state, workspace).

The caller owns the short-lived Task-write barrier and supplies a probe of the
quiescent control boundary. This module neither starts a barrier nor resumes a
process. A changing boundary or workspace leaves an explicitly incomplete
archive; no semantic ground judgment is made here.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
from pathlib import Path
from typing import Callable, Mapping


SCHEMA = "epistemic-research-checkpoint/0"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_IDENTITY_KEYS = (
    "task_identity", "source_identity", "system_prompt_sha256",
    "tool_schema_sha256", "model_config_sha256",
)
_BOUNDARY_KEYS = (
    "review_id", "request_id", "public_cursor", "task_turn",
    "completion_control_state",
)


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _read_json(path: Path):
    return json.loads(path.read_bytes())


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def _validate_inputs(checkpoint_id, identities, boundary, history_prefix):
    if not isinstance(checkpoint_id, str) or not _ID.fullmatch(checkpoint_id):
        raise ValueError("checkpoint_id must be one safe path component")
    if not isinstance(identities, Mapping) or any(not identities.get(k) for k in _IDENTITY_KEYS):
        raise ValueError("contract/task identities are incomplete")
    for key in ("system_prompt_sha256", "tool_schema_sha256", "model_config_sha256"):
        if not isinstance(identities[key], str) or not _HEX.fullmatch(identities[key]):
            raise ValueError(f"{key} must be a SHA-256 digest")
    continuation = identities.get("continuation_prompt_sha256")
    if continuation is not None and (not isinstance(continuation, str) or not _HEX.fullmatch(continuation)):
        raise ValueError("continuation_prompt_sha256 must be a SHA-256 digest or null")
    if not isinstance(boundary, Mapping) or any(k not in boundary for k in _BOUNDARY_KEYS):
        raise ValueError("control boundary is incomplete")
    if not isinstance(boundary["review_id"], str) or not boundary["review_id"]:
        raise ValueError("review_id is required")
    if not isinstance(boundary["request_id"], str) or not boundary["request_id"]:
        raise ValueError("request_id is required")
    for key in ("public_cursor", "task_turn"):
        if type(boundary[key]) is not int or boundary[key] < 0:
            raise ValueError(f"{key} must be a nonnegative integer")
    if (not isinstance(boundary["completion_control_state"], Mapping)
            or not boundary["completion_control_state"]):
        raise ValueError("completion_control_state must be a nonempty object")
    if not isinstance(history_prefix, list):
        raise ValueError("provider History prefix must be a list")
    # Fail before writing if the caller supplied non-serializable or lossy input.
    for value in (dict(identities), dict(boundary), history_prefix):
        _json_bytes(value)


def _stable_boundary(probe: Callable[[], Mapping], expected: dict) -> dict:
    observed = probe()
    if not isinstance(observed, Mapping):
        raise ValueError("boundary probe did not return an object")
    observed = json.loads(_json_bytes(dict(observed)))
    if any(observed.get(key) != expected[key] for key in _BOUNDARY_KEYS):
        raise ValueError("capture boundary changed")
    if (observed.get("task_writes_paused") is not True
            or observed.get("supervisor_idle") is not True
            or observed.get("inflight_requests") != 0
            or observed.get("inflight_tools") != 0):
        raise ValueError("capture barrier is not quiescent")
    return observed


def _tree_manifest(root: Path) -> dict:
    """List all in-tree content without following links; reject special files."""
    if not root.is_dir() or root.is_symlink():
        raise ValueError("workspace root is not a real directory")
    entries = {}

    def visit(directory: Path):
        for child in sorted(directory.iterdir(), key=lambda p: p.name):
            relative = child.relative_to(root).as_posix()
            mode = child.lstat().st_mode
            if stat.S_ISLNK(mode):
                target = os.readlink(child)
                # An external target is not part of the captured workspace.
                resolved = (child.parent / target).resolve(strict=False)
                if not resolved.is_relative_to(root):
                    raise ValueError(f"workspace symlink escapes capture root: {relative}")
                entries[relative] = {"kind": "symlink", "target": target}
            elif stat.S_ISDIR(mode):
                entries[relative] = {"kind": "directory", "mode": stat.S_IMODE(mode)}
                visit(child)
            elif stat.S_ISREG(mode):
                entries[relative] = {"kind": "file", "sha256": _sha_file(child),
                                     "size": child.stat().st_size, "mode": stat.S_IMODE(mode)}
            else:
                raise ValueError(f"workspace contains unsupported special file: {relative}")

    visit(root)
    return {"schema": SCHEMA, "entries": entries}


def _archive_files(root: Path) -> dict[str, str]:
    """Hash every archive file except the two sealing files."""
    excluded = {"manifest.json", "binding.json", "complete.json", "capture_status.json"}
    return {path.relative_to(root).as_posix(): _sha_file(path)
            for path in sorted(root.rglob("*"))
            if path.is_file() and not path.is_symlink()
            and path.relative_to(root).as_posix() not in excluded}


def capture_checkpoint(*, checkpoint_root, checkpoint_id, workspace_root,
                       working_path, history_prefix, identities, boundary,
                       boundary_probe: Callable[[], Mapping]) -> Path:
    """Capture one caller-selected, externally quiesced research boundary.

    ``boundary_probe`` must attest that Task writes are paused and the
    Supervisor is idle, and return the same control facts before/after copy.
    The archive is never a live Monitor input. Failed captures remain visibly
    incomplete at their reserved ID and cannot be silently retried over.
    """
    _validate_inputs(checkpoint_id, identities, boundary, history_prefix)
    source = Path(workspace_root).resolve(strict=True)
    working = Path(working_path).resolve(strict=True)
    parent = Path(checkpoint_root).resolve()
    if parent == source or parent.is_relative_to(source):
        raise ValueError("checkpoint archive must be outside the task workspace")
    if not working.is_file():
        raise ValueError("working state is not a regular file")
    parent.mkdir(parents=True, exist_ok=True)
    final = parent / checkpoint_id
    final.mkdir()  # exclusive: never overwrite a prior complete or failed capture
    try:
        expected = json.loads(_json_bytes(dict(boundary)))
        identity_snapshot = json.loads(_json_bytes(dict(identities)))
        before = _stable_boundary(boundary_probe, expected)
        source_before = _tree_manifest(source)
        working_before = working.read_bytes()
        history_bytes = _json_bytes(history_prefix)
        identities_bytes = _json_bytes(identity_snapshot)
        boundary_bytes = _json_bytes(expected)

        epistemic = final / "epistemic"
        epistemic.mkdir()
        (epistemic / "history.json").write_bytes(history_bytes)
        (epistemic / "working.md").write_bytes(working_before)
        (epistemic / "identities.json").write_bytes(identities_bytes)
        (epistemic / "boundary.json").write_bytes(boundary_bytes)
        shutil.copytree(source, final / "workspace", symlinks=True)
        copied = _tree_manifest(final / "workspace")
        source_after = _tree_manifest(source)
        working_after = working.read_bytes()
        after = _stable_boundary(boundary_probe, expected)
        if source_before != copied or copied != source_after:
            raise ValueError("workspace changed during capture")
        if working_before != working_after:
            raise ValueError("working state changed during capture")
        if history_bytes != _json_bytes(history_prefix):
            raise ValueError("provider History changed during capture")
        if identities_bytes != _json_bytes(dict(identities)) or boundary_bytes != _json_bytes(dict(boundary)):
            raise ValueError("identity or control state changed during capture")
        if before != after:
            raise ValueError("capture barrier attestation changed")

        _write_json(final / "workspace_manifest.json", copied)
        manifest = {"schema": SCHEMA, "files": _archive_files(final)}
        _write_json(final / "manifest.json", manifest)
        binding = {
            "schema": SCHEMA, "capture_status": "complete",
            "checkpoint_id": checkpoint_id,
            "task_identity": identity_snapshot["task_identity"],
            "source_identity": identity_snapshot["source_identity"],
            "review_id": expected["review_id"], "request_id": expected["request_id"],
            "public_cursor": expected["public_cursor"], "task_turn": expected["task_turn"],
            "history_sha256": _sha_bytes(history_bytes),
            "working_sha256": _sha_bytes(working_before),
            "identities_sha256": _sha_bytes(identities_bytes),
            "boundary_sha256": _sha_bytes(boundary_bytes),
            "workspace_manifest_sha256": _sha_file(final / "workspace_manifest.json"),
            "manifest_sha256": _sha_file(final / "manifest.json"),
            "barrier": {"task_writes_paused": True, "supervisor_idle": True,
                        "inflight_requests": 0, "inflight_tools": 0},
        }
        _write_json(final / "binding.json", binding)
        _write_json(final / "complete.json", {"schema": SCHEMA, "status": "complete",
                                              "binding_sha256": _sha_file(final / "binding.json")})
        verify_checkpoint(final)
        return final
    except Exception as exc:
        (final / "complete.json").unlink(missing_ok=True)
        _write_json(final / "capture_status.json", {"schema": SCHEMA, "status": "incomplete",
                                                    "error_type": type(exc).__name__,
                                                    "reason": str(exc)})
        raise


def verify_checkpoint(checkpoint_dir, *, expected_identities=None) -> dict:
    """Check archive bytes and identities only; never judge evidence semantics."""
    root = Path(checkpoint_dir).resolve(strict=True)
    if (root / "capture_status.json").exists() or not (root / "complete.json").is_file():
        raise ValueError("checkpoint is incomplete")
    complete = _read_json(root / "complete.json")
    binding = _read_json(root / "binding.json")
    manifest = _read_json(root / "manifest.json")
    identities = _read_json(root / "epistemic" / "identities.json")
    boundary = _read_json(root / "epistemic" / "boundary.json")
    history = _read_json(root / "epistemic" / "history.json")
    workspace_manifest = _read_json(root / "workspace_manifest.json")
    _validate_inputs(root.name, identities, boundary, history)
    if (complete != {"schema": SCHEMA, "status": "complete",
                     "binding_sha256": _sha_file(root / "binding.json")}
            or binding.get("schema") != SCHEMA or binding.get("capture_status") != "complete"
            or manifest.get("schema") != SCHEMA or workspace_manifest.get("schema") != SCHEMA):
        raise ValueError("checkpoint seal or schema mismatch")
    if manifest.get("files") != _archive_files(root):
        raise ValueError("archive manifest mismatch")
    if binding.get("manifest_sha256") != _sha_file(root / "manifest.json"):
        raise ValueError("binding manifest mismatch")
    file_bindings = {
        "history_sha256": root / "epistemic" / "history.json",
        "working_sha256": root / "epistemic" / "working.md",
        "identities_sha256": root / "epistemic" / "identities.json",
        "boundary_sha256": root / "epistemic" / "boundary.json",
        "workspace_manifest_sha256": root / "workspace_manifest.json",
    }
    if any(binding.get(key) != _sha_file(path) for key, path in file_bindings.items()):
        raise ValueError("binding content hash mismatch")
    if _tree_manifest(root / "workspace") != workspace_manifest:
        raise ValueError("workspace manifest mismatch")
    if (binding.get("checkpoint_id") != root.name
            or binding.get("task_identity") != identities.get("task_identity")
            or binding.get("source_identity") != identities.get("source_identity")
            or binding.get("barrier") != {"task_writes_paused": True,
                                          "supervisor_idle": True,
                                          "inflight_requests": 0, "inflight_tools": 0}
            or any(binding.get(key) != boundary.get(key)
                   for key in ("review_id", "request_id", "public_cursor", "task_turn"))):
        raise ValueError("checkpoint identity mismatch")
    if expected_identities is not None and dict(expected_identities) != identities:
        raise ValueError("expected identity mismatch")
    return {"checkpoint_id": root.name, "capture_status": "complete",
            "task_identity": binding["task_identity"],
            "source_identity": binding["source_identity"],
            "public_cursor": binding["public_cursor"], "task_turn": binding["task_turn"]}
