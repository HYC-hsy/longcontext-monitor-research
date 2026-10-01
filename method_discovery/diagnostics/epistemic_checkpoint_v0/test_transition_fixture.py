"""Synthetic content transitions only; case names never enter run artifacts."""

import base64
import hashlib
import json

import pytest

from method_discovery.diagnostics.epistemic_checkpoint_v0 import capture_checkpoint, verify_checkpoint
from method_discovery.diagnostics.epistemic_checkpoint_v0 import transition_fixture as fixture


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _starting_point(tmp_path, files=None):
    workspace = tmp_path / "live-task"
    workspace.mkdir()
    for name, data in (files or {"source.go": b"old\n"}).items():
        path = workspace / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    working = tmp_path / "private" / "working.md"
    working.parent.mkdir()
    working.write_bytes(b"Current scoped understanding.\n")
    identities = {
        "task_identity": "synthetic:task", "source_identity": "frozen-source",
        "system_prompt_sha256": _sha(b"system"),
        "continuation_prompt_sha256": _sha(b"continuation"),
        "tool_schema_sha256": _sha(b"seven tools"),
        "model_config_sha256": _sha(b"model profile"),
    }
    boundary = {"review_id": "review-1", "request_id": "request-1",
                "public_cursor": 5, "task_turn": 3,
                "completion_control_state": {"pending_completion": None}}
    attested = {**boundary, "task_writes_paused": True, "supervisor_idle": True,
                "inflight_requests": 0, "inflight_tools": 0}
    checkpoint = capture_checkpoint(
        checkpoint_root=tmp_path / "checkpoints", checkpoint_id="checkpoint-1",
        workspace_root=workspace, working_path=working,
        history_prefix=[{"role": "assistant", "content": "synthetic ground"}],
        identities=identities, boundary=boundary, boundary_probe=lambda: dict(attested))
    return checkpoint


def _bundle(tmp_path, *, operations, checkpoint_id="checkpoint-1", transition_id="transition-1"):
    source = tmp_path / "researcher-source.json"
    source.write_text(json.dumps({"schema": fixture.SOURCE_SCHEMA,
                                  "checkpoint_id": checkpoint_id,
                                  "transition_id": transition_id,
                                  "operations": operations}, sort_keys=True), encoding="utf-8")
    return source, _sha(source.read_bytes())


def _write(path, before, after):
    return {"op": "write", "path": path,
            "before_sha256": _sha(before) if before is not None else None,
            "content_base64": base64.b64encode(after).decode("ascii")}


def _apply(tmp_path, checkpoint, source, digest, **overrides):
    arguments = {"checkpoint_dir": checkpoint, "transition_source": source,
                 "transition_id": "transition-1", "expected_source_sha256": digest,
                 "expected_checkpoint_id": "checkpoint-1",
                 "output_root": tmp_path / "transitions"}
    arguments.update(overrides)
    return fixture.apply_transition_fixture(**arguments)


def test_successful_patch_and_after_manifest(tmp_path):
    checkpoint = _starting_point(tmp_path)
    source, digest = _bundle(tmp_path, operations=[
        _write("source.go", b"old\n", b"new\n"),
        _write("added.go", None, b"added\n"),
    ])
    original_manifest = (checkpoint / "workspace_manifest.json").read_bytes()
    root = _apply(tmp_path, checkpoint, source, digest)
    assert (root / "workspace/source.go").read_bytes() == b"new\n"
    assert (root / "workspace/added.go").read_bytes() == b"added\n"
    assert (checkpoint / "workspace/source.go").read_bytes() == b"old\n"
    assert (checkpoint / "workspace_manifest.json").read_bytes() == original_manifest
    assert verify_checkpoint(checkpoint)["capture_status"] == "complete"
    before = json.loads((root / "before_manifest.json").read_text())
    after = json.loads((root / "after_manifest.json").read_text())
    assert before["entries"]["source.go"]["sha256"] == _sha(b"old\n")
    assert after["entries"]["source.go"]["sha256"] == _sha(b"new\n")
    assert after["entries"]["added.go"]["sha256"] == _sha(b"added\n")
    assert json.loads((root / "transition.json").read_text())["status"] == "complete"
    assert json.loads((root / "end.json").read_text())["status"] == "complete"
    assert len((root / "execution_log.jsonl").read_text().splitlines()) == 2
    with pytest.raises(FileExistsError):
        _apply(tmp_path, checkpoint, source, digest)


def test_checkpoint_identity_mismatch_is_recorded(tmp_path):
    checkpoint = _starting_point(tmp_path)
    source, digest = _bundle(tmp_path, operations=[])
    with pytest.raises(ValueError, match="checkpoint identity mismatch"):
        _apply(tmp_path, checkpoint, source, digest, expected_checkpoint_id="wrong-id")
    root = tmp_path / "transitions/transition-1"
    assert json.loads((root / "end.json").read_text())["status"] == "failed"
    assert not (root / "start.json").exists()


def test_before_workspace_mismatch_is_recorded(tmp_path, monkeypatch):
    checkpoint = _starting_point(tmp_path)
    source, digest = _bundle(tmp_path, operations=[])
    original = fixture._copy_workspace

    def changed_copy(src, dst):
        original(src, dst)
        (dst / "source.go").write_bytes(b"unexpected\n")

    monkeypatch.setattr(fixture, "_copy_workspace", changed_copy)
    with pytest.raises(ValueError, match="before workspace identity mismatch"):
        _apply(tmp_path, checkpoint, source, digest)
    root = tmp_path / "transitions/transition-1"
    assert not (root / "start.json").exists()
    assert json.loads((root / "transition.json").read_text())["status"] == "failed"


def test_patch_hash_mismatch_is_recorded(tmp_path):
    checkpoint = _starting_point(tmp_path)
    source, digest = _bundle(tmp_path, operations=[])
    with pytest.raises(ValueError, match="source hash mismatch"):
        _apply(tmp_path, checkpoint, source, "0" * 64)
    marker = json.loads((tmp_path / "transitions/transition-1/source_hash.json").read_text())
    assert marker == {"expected_sha256": "0" * 64, "actual_sha256": digest, "matches": False}


def test_patch_failure_preserves_partial_result(tmp_path, monkeypatch):
    checkpoint = _starting_point(tmp_path)
    source, digest = _bundle(tmp_path, operations=[_write("source.go", b"old\n", b"new\n")])
    original = fixture._apply

    def fail_after_application(root, operations, log):
        original(root, operations, log)
        raise OSError("synthetic write failure after application")

    monkeypatch.setattr(fixture, "_apply", fail_after_application)
    with pytest.raises(OSError, match="synthetic write failure"):
        _apply(tmp_path, checkpoint, source, digest)
    root = tmp_path / "transitions/transition-1"
    assert (root / "start.json").exists()
    assert (root / "workspace/source.go").read_bytes() == b"new\n"
    assert json.loads((root / "end.json").read_text())["status"] == "failed"
    assert json.loads((root / "after_manifest.json").read_text())["entries"]["source.go"]["sha256"] == _sha(b"new\n")
    assert (checkpoint / "workspace/source.go").read_bytes() == b"old\n"


def test_delete_exact_file_and_reject_bad_paths(tmp_path):
    checkpoint = _starting_point(tmp_path, {"obsolete.go": b"obsolete\n"})
    source, digest = _bundle(tmp_path, operations=[
        {"op": "delete", "path": "obsolete.go", "before_sha256": _sha(b"obsolete\n")},
    ])
    root = _apply(tmp_path, checkpoint, source, digest)
    assert not (root / "workspace/obsolete.go").exists()
    assert (checkpoint / "workspace/obsolete.go").read_bytes() == b"obsolete\n"
    assert "obsolete.go" not in json.loads((root / "after_manifest.json").read_text())["entries"]


@pytest.mark.parametrize("bad_path", ["../escape", "/absolute", "src/../escape", ".git/config"])
def test_reject_unsafe_patch_paths(tmp_path, bad_path):
    checkpoint = _starting_point(tmp_path)
    source, digest = _bundle(tmp_path, operations=[_write(bad_path, None, b"data")])
    with pytest.raises(ValueError, match="patch path|git metadata"):
        _apply(tmp_path, checkpoint, source, digest)
    assert json.loads((tmp_path / "transitions/transition-1/end.json").read_text())["status"] == "failed"


@pytest.mark.parametrize("case_name,files,operations,changed", [
    ("endpoint-like", {"pkg/endpoint/endpoint.go": b"before\n"},
     [_write("pkg/endpoint/endpoint.go", b"before\n", b"after\n")],
     {"pkg/endpoint/endpoint.go"}),
    ("option-wiring-like", {"client/option.go": b"a\n", "internal/client/option.go": b"b\n",
                            "pkg/endpoint/endpoint.go": b"c\n"},
     [_write("client/option.go", b"a\n", b"a2\n"),
      _write("internal/client/option.go", b"b\n", b"b2\n"),
      _write("pkg/endpoint/endpoint.go", b"c\n", b"c2\n")],
     {"client/option.go", "internal/client/option.go", "pkg/endpoint/endpoint.go"}),
    ("validation-only-like", {"widget/hyperlink.go": b"link\n",
                              "data/validation/all.go": b"before\n"},
     [_write("data/validation/all.go", b"before\n", b"after\n")],
     {"data/validation/all.go"}),
    ("no-transition", {"widget/menu.go": b"unchanged\n"}, [], set()),
])
def test_offline_transition_examples(tmp_path, case_name, files, operations, changed):
    checkpoint = _starting_point(tmp_path, files)
    source, digest = _bundle(tmp_path, operations=operations)
    root = _apply(tmp_path, checkpoint, source, digest)
    before = json.loads((root / "before_manifest.json").read_text())["entries"]
    after = json.loads((root / "after_manifest.json").read_text())["entries"]
    actual = {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}
    assert actual == changed
    assert case_name not in (root / "transition.json").read_text()


def test_no_semantic_verdict_in_output(tmp_path):
    checkpoint = _starting_point(tmp_path)
    source, digest = _bundle(tmp_path, operations=[])
    root = _apply(tmp_path, checkpoint, source, digest)
    metadata = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.json"))
    for prohibited in ("ground_valid", "stale", "reopen", "carry", "relevant",
                       "semantic_impact", "requirement_status"):
        assert prohibited not in metadata


def test_before_apply_observer_cannot_modify_baseline(tmp_path):
    checkpoint = _starting_point(tmp_path)
    source, digest = _bundle(tmp_path, operations=[_write("source.go", b"old\n", b"new\n")])

    def bad_observer(workspace, _manifest):
        (workspace / "source.go").write_bytes(b"observer mutation\n")

    with pytest.raises(ValueError, match="observer changed"):
        _apply(tmp_path, checkpoint, source, digest, before_apply=bad_observer)
    root = tmp_path / "transitions/transition-1"
    assert not (root / "start.json").exists()
    assert json.loads((root / "end.json").read_text())["status"] == "failed"
