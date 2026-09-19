"""Atomic, self-validating snapshots of a Monitor root-handoff request."""

from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
import tempfile
import time
from pathlib import Path


SCHEMA = "monitor-root-checkpoint/1"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _copy_tree(source: Path, target: Path) -> None:
    if not source.exists():
        target.mkdir(parents=True, exist_ok=True)
        return
    shutil.copytree(source, target)


def _file_manifest(root: Path) -> dict[str, str]:
    excluded = {"manifest.json", "complete.json"}
    return {
        path.relative_to(root).as_posix(): _sha(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name not in excluded
    }


def write_root_checkpoint(*, checkpoint_root, checkpoint_id, request, identity,
                          event_source, synopsis_source, task_snapshot, private_root) -> Path:
    """Write a complete checkpoint atomically; ``complete.json`` is always last."""
    root = Path(checkpoint_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    final = root / checkpoint_id
    if final.exists():
        loaded = load_root_checkpoint(final)
        if loaded["identity"].get("handoff") != identity.get("handoff"):
            raise ValueError("checkpoint id already belongs to another handoff")
        return final
    temporary = Path(tempfile.mkdtemp(prefix=".capture-", dir=root))
    try:
        event_source = Path(event_source)
        task_snapshot = Path(task_snapshot)
        private_root = Path(private_root)
        _write_json(temporary / "request.json", request)
        _write_json(temporary / "identity.json", {"schema_version": SCHEMA, **identity})
        _copy_tree(task_snapshot, temporary / "task")
        events_dir = temporary / "task"
        shutil.copy2(event_source, events_dir / "public_events.jsonl")
        if synopsis_source and Path(synopsis_source).is_file():
            shutil.copy2(synopsis_source, events_dir / "synopsis.jsonl")
        state_dir = temporary / "monitor" / "state"
        state_dir.mkdir(parents=True)
        for child in private_root.iterdir():
            if child.name in {"audit", ".task_view"}:
                continue
            destination = state_dir / child.name
            _copy_tree(child, destination) if child.is_dir() else shutil.copy2(child, destination)
        manifest = {
            "schema_version": SCHEMA,
            "path_map": {
                "task/": "task/",
                "task/workspace/": "task/workspace/",
                "monitor/": "monitor/state/",
            },
            "files": _file_manifest(temporary),
        }
        _write_json(temporary / "manifest.json", manifest)
        _write_json(temporary / "complete.json", {
            "schema_version": SCHEMA,
            "status": "complete",
            "manifest_sha256": _sha(temporary / "manifest.json"),
            "completed_at": time.time(),
        })
        temporary.replace(final)
        return final
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def load_root_checkpoint(checkpoint_dir) -> dict:
    """Validate every declared file and reject additions, omissions, or mutations."""
    root = Path(checkpoint_dir).resolve(strict=True)
    complete_path, manifest_path = root / "complete.json", root / "manifest.json"
    if not complete_path.is_file() or not manifest_path.is_file():
        raise ValueError("checkpoint is incomplete")
    complete = json.loads(complete_path.read_text(encoding="utf-8"))
    if complete.get("status") != "complete" or complete.get("manifest_sha256") != _sha(manifest_path):
        raise ValueError("checkpoint completion marker is invalid")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = manifest.get("files")
    if not isinstance(expected, dict):
        raise ValueError("checkpoint manifest has no file map")
    actual = _file_manifest(root)
    if actual != expected:
        raise ValueError("checkpoint file set or content hash changed")
    request = json.loads((root / "request.json").read_text(encoding="utf-8"))
    identity = json.loads((root / "identity.json").read_text(encoding="utf-8"))
    return {"root": root, "complete": complete, "manifest": manifest,
            "request": request, "identity": identity}


def restored_request(checkpoint_dir) -> dict:
    """Return the exact pre-transport request without re-appending its dynamic input."""
    loaded = load_root_checkpoint(checkpoint_dir)
    request = loaded["request"]
    required = {"system", "messages", "tools", "model_parameters", "root_handoff"}
    if not required <= set(request):
        raise ValueError("checkpoint request is missing model input fields")
    return json.loads(json.dumps(request, ensure_ascii=False))


def package_root_checkpoint(checkpoint_dir) -> Path:
    """Create one atomic transport artifact for a validated checkpoint tree."""
    root = Path(checkpoint_dir).resolve(strict=True)
    load_root_checkpoint(root)
    archive = root.with_suffix(".tar")
    if archive.exists():
        return archive
    partial = archive.with_suffix(".tar.partial")
    try:
        with tarfile.open(partial, "w", dereference=False) as stream:
            stream.add(root, arcname=root.name, recursive=True)
        partial.replace(archive)
        return archive
    finally:
        partial.unlink(missing_ok=True)


def extract_root_checkpoint_archive(archive_path, destination) -> Path:
    """Safely extract one transport artifact, then enforce the normal manifest."""
    archive_path = Path(archive_path).resolve(strict=True)
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError(f"checkpoint extraction destination exists: {destination}")
    destination.mkdir(parents=True)
    try:
        with tarfile.open(archive_path, "r") as stream:
            members = stream.getmembers()
            if not members:
                raise ValueError("checkpoint archive is empty")
            roots = {Path(member.name).parts[0] for member in members if Path(member.name).parts}
            if len(roots) != 1:
                raise ValueError("checkpoint archive must contain exactly one root")
            for member in members:
                parts = Path(member.name).parts
                if (not parts or Path(member.name).is_absolute() or ".." in parts
                        or not (member.isdir() or member.isfile())):
                    raise ValueError("checkpoint archive contains an unsafe member")
                target = (destination / member.name).resolve()
                try:
                    target.relative_to(destination)
                except ValueError as exc:
                    raise ValueError("checkpoint archive member escapes destination") from exc
            stream.extractall(destination, members=members, filter="data")
        root = destination / next(iter(roots))
        load_root_checkpoint(root)
        return root
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def capture_live_root_checkpoint(*, workspace, checkpoint_root, snapshot, identity,
                                 current_handoff) -> Path:
    """Capture the exact observed root request and its stable public evidence.

    ``current_handoff`` is checked on both sides of the workspace snapshot.  The
    public archive uses the Monitor runtime's one-based ``archive_sequence``;
    this is deliberately distinct from research telemetry event counts.
    """
    handoff = snapshot.get("root_handoff")
    if not isinstance(handoff, dict) or current_handoff() != handoff:
        raise ValueError("root handoff changed before checkpoint capture")
    cutoff = handoff.get("cursor")
    if type(cutoff) is not int or cutoff < 1:
        raise ValueError("root handoff has no valid archive cursor")
    event_source = workspace.evidence_root / "public_events.jsonl"
    rows = []
    for index, line in enumerate(event_source.read_text(encoding="utf-8").splitlines(), 1):
        row = json.loads(line)
        if not isinstance(row, dict) or type(row.get("archive_sequence")) is not int:
            raise ValueError(f"public event {index} has no valid archive_sequence")
        if row["archive_sequence"] != index:
            raise ValueError(f"public event {index} breaks the one-based archive sequence")
        if index > cutoff:
            raise ValueError("public events advanced beyond the observed root boundary")
        rows.append(row)
    if len(rows) != cutoff:
        raise ValueError("public event prefix does not end at the root boundary")

    checkpoint_root = Path(checkpoint_root)
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    frozen_events = checkpoint_root / f".events-{handoff['generation']}-{handoff['request_id']}.jsonl"
    try:
        frozen_events.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8")
        task_snapshot = workspace.refresh_snapshot()
        if current_handoff() != handoff:
            raise ValueError("root handoff changed during checkpoint capture")
        full_identity = {
            **identity,
            "cursor": cutoff,
            "cursor_field": "archive_sequence",
            "captured_at": time.time(),
            "source": "live_request_before_transport",
            "history_source_kind": "provider_snapshot",
            "handoff": handoff,
        }
        final = write_root_checkpoint(
            checkpoint_root=checkpoint_root,
            checkpoint_id=f"checkpoint-{int(handoff['generation']):04d}",
            request=snapshot,
            identity=full_identity,
            event_source=frozen_events,
            synopsis_source=workspace.evidence_root / "synopsis.jsonl",
            task_snapshot=task_snapshot,
            private_root=workspace.private_root,
        )
        package_root_checkpoint(final)
        return final
    finally:
        frozen_events.unlink(missing_ok=True)
