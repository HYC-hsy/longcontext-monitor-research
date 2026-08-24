"""R1 checkpoints for deterministic, file-only GenericAgent experiments."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Mapping, Optional

from research_runtime import emit


SCHEMA_VERSION = "checkpoint-packet/1"
DEFAULT_EXCLUSIONS = (".git", "__pycache__", ".pytest_cache", ".mypy_cache")
MODEL_FIELDS = (
    "model", "temperature", "max_tokens", "context_win", "reasoning_effort",
    "service_tier", "thinking_type", "thinking_budget_tokens", "stream", "api_mode",
)


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _write_json(path: Path, value: Any) -> str:
    raw = _json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return _sha256_bytes(raw)


def tree_hash(root: Path, exclusions: tuple[str, ...] = DEFAULT_EXCLUSIONS) -> str:
    digest = hashlib.sha256()
    excluded = set(exclusions)
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        rel = path.relative_to(root)
        if any(part in excluded for part in rel.parts):
            continue
        marker = rel.as_posix().encode("utf-8")
        if path.is_symlink():
            raise ValueError(f"R1 workspace cannot contain symlinks: {rel}")
        if path.is_dir():
            digest.update(b"D\0" + marker + b"\0")
        elif path.is_file():
            digest.update(b"F\0" + marker + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    return "sha256:" + digest.hexdigest()


def _ignore(_directory: str, names: list[str]) -> set[str]:
    return set(names).intersection(DEFAULT_EXCLUSIONS)


def _model_config(backend: Any) -> dict[str, Any]:
    return {field: getattr(backend, field) for field in MODEL_FIELDS if hasattr(backend, field)}


def _session_state(client: Any) -> dict[str, Any]:
    backend = client.backend
    return {
        "history": backend.history,
        "system": getattr(backend, "system", ""),
        "client_type": type(client).__name__,
        "backend_type": type(backend).__name__,
        "model_config": _model_config(backend),
        "last_tools": getattr(client, "last_tools", ""),
    }


def _packet_hash(packet: Mapping[str, Any]) -> str:
    unsigned = {key: value for key, value in packet.items() if key != "packet_hash"}
    return _sha256_bytes(_json_bytes(unsigned))


def create_r1_checkpoint(
    *, checkpoint_root: os.PathLike[str] | str, workspace: os.PathLike[str] | str,
    client: Any, identity: Mapping[str, Any], boundary: str,
    continuation: Optional[Mapping[str, Any]] = None, method_state: Any = None,
    verifier: Optional[Mapping[str, Any]] = None, budget: Optional[Mapping[str, Any]] = None,
) -> Path:
    """Atomically create an R1 packet without mutating the live workspace."""
    if boundary not in {"post_tool_pre_next_llm", "pre_completion_decision", "pre_checker"}:
        raise ValueError(f"Unsupported checkpoint boundary: {boundary}")
    source = Path(workspace).resolve(strict=True)
    if not source.is_dir():
        raise ValueError("R1 workspace must be a directory")
    root = Path(checkpoint_root).resolve()
    if root == source or source in root.parents:
        raise ValueError("Checkpoint root must be outside the workspace")
    root.mkdir(parents=True, exist_ok=True)
    checkpoint_id = f"cp_{uuid.uuid4().hex}"
    temp = Path(tempfile.mkdtemp(prefix=f".{checkpoint_id}.", dir=root))
    final = root / checkpoint_id
    try:
        snapshot = temp / "workspace"
        shutil.copytree(source, snapshot, ignore=_ignore)
        source_hash = tree_hash(source)
        snapshot_hash = tree_hash(snapshot)
        if source_hash != snapshot_hash:
            raise RuntimeError("Workspace changed or copied inconsistently during checkpoint")
        session = _session_state(client)
        session_hash = _write_json(temp / "state" / "session.json", session)
        method_ref = None
        if method_state is not None:
            _write_json(temp / "state" / "method_state.json", method_state)
            method_ref = "state/method_state.json"
        cont = dict(continuation or {})
        refs = {}
        for key in ("next_prompt", "tool_results", "completion_proposal"):
            value = cont.get(key)
            if value is None:
                refs[f"{key}_ref"] = None
            else:
                ref = f"state/{key}.json"
                _write_json(temp / ref, value)
                refs[f"{key}_ref"] = ref
        backend = client.backend
        packet = {
            "schema_version": SCHEMA_VERSION,
            "checkpoint_id": checkpoint_id,
            "boundary": boundary,
            "identity": {
                "experiment_id": str(identity["experiment_id"]), "task_id": str(identity["task_id"]),
                "run_id": str(identity["run_id"]), "parent_branch_id": str(identity.get("branch_id", "original")),
                "user_turn": int(identity.get("user_turn", 0)), "internal_turn": int(identity.get("internal_turn", 0)),
                "llm_call_id": identity.get("llm_call_id"),
            },
            "agent_state": {"session_ref": "state/session.json", "session_hash": session_hash,
                            "client_type": type(client).__name__, "model_config": _model_config(backend)},
            "tool_protocol_state": {
                "pending_tool_ids": list(cont.get("pending_tool_ids", [])),
                "last_tools_hash": _sha256_bytes(str(getattr(client, "last_tools", "")).encode()) if getattr(client, "last_tools", "") else None,
                "total_cd_tokens": int(getattr(client, "total_cd_tokens", 0)),
            },
            "method_state_ref": method_ref,
            "workspace": {"snapshot_ref": "workspace", "content_hash": snapshot_hash,
                          "exclusions": list(DEFAULT_EXCLUSIONS)},
            "environment": {"recoverability": "R1", "image_or_revision": None,
                            "time_source": "host_utc", "external_state_refs": []},
            "continuation": refs,
            "verifier": dict(verifier or {"level": "V0", "kind": "file", "entrypoint": None, "deterministic": True}),
            "budget": dict(budget or {"calls_used": 0, "input_tokens_used": 0, "output_tokens_used": 0,
                                    "wall_seconds_used": 0, "remaining_policy": {}}),
        }
        packet["packet_hash"] = _packet_hash(packet)
        _write_json(temp / "packet.json", packet)
        temp.replace(final)
        emit("checkpoint_created", {"checkpoint_id": checkpoint_id, "packet_ref": str(final / "packet.json"),
                                    "workspace_hash": snapshot_hash, "recoverability": "R1"})
        return final
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def restore_r1_checkpoint(checkpoint_dir: os.PathLike[str] | str, target_workspace: os.PathLike[str] | str,
                          client: Any) -> dict[str, Any]:
    """Restore into a new empty workspace and verify all declared hashes."""
    source = Path(checkpoint_dir).resolve(strict=True)
    packet = json.loads((source / "packet.json").read_text(encoding="utf-8"))
    if packet.get("packet_hash") != _packet_hash(packet):
        raise ValueError("Checkpoint packet hash mismatch")
    session_path = source / packet["agent_state"]["session_ref"]
    if _sha256_bytes(session_path.read_bytes()) != packet["agent_state"]["session_hash"]:
        raise ValueError("Checkpoint session hash mismatch")
    snapshot = source / packet["workspace"]["snapshot_ref"]
    if tree_hash(snapshot) != packet["workspace"]["content_hash"]:
        raise ValueError("Checkpoint workspace hash mismatch")
    session = json.loads(session_path.read_text(encoding="utf-8"))
    if type(client).__name__ != packet["agent_state"]["client_type"]:
        raise ValueError("Client type mismatch")
    actual_model = _model_config(client.backend)
    if actual_model != packet["agent_state"]["model_config"]:
        raise ValueError("Model configuration mismatch")
    restored_tools = session.get("last_tools", "")
    expected_tools_hash = packet["tool_protocol_state"].get("last_tools_hash")
    actual_tools_hash = _sha256_bytes(str(restored_tools).encode()) if restored_tools else None
    if actual_tools_hash != expected_tools_hash:
        raise ValueError("Checkpoint tool protocol state mismatch")

    target = Path(target_workspace).resolve()
    if target == source or source in target.parents or target in source.parents:
        raise ValueError("Restore target must not overlap the checkpoint")
    if target.exists() and any(target.iterdir()):
        raise ValueError("Restore target must be absent or empty")
    target.parent.mkdir(parents=True, exist_ok=True)
    target_was_empty = target.exists()
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.restore.", dir=target.parent))
    try:
        staging.rmdir()
        shutil.copytree(snapshot, staging)
        if tree_hash(staging) != packet["workspace"]["content_hash"]:
            raise RuntimeError("Restored workspace hash mismatch")
        if target_was_empty:
            target.rmdir()
        staging.replace(target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        if target_was_empty and not target.exists():
            target.mkdir()
        raise

    client.backend.history = session["history"]
    client.backend.system = session["system"]
    client.total_cd_tokens = packet["tool_protocol_state"]["total_cd_tokens"]
    client.last_tools = restored_tools
    return packet
