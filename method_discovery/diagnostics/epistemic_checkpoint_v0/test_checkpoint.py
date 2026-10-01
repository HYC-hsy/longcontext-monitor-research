"""Synthetic filesystem-only checks; no Agent, provider, or verifier is run."""

import hashlib
import json
from pathlib import Path

import pytest

from method_discovery.diagnostics.epistemic_checkpoint_v0 import (
    capture_checkpoint, verify_checkpoint,
)
from method_discovery.diagnostics.epistemic_checkpoint_v0 import checkpoint as implementation


def _hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _case(tmp_path):
    workspace = tmp_path / "task-workspace"
    (workspace / "pkg").mkdir(parents=True)
    (workspace / "pkg" / "main.py").write_bytes(b"value = 1\n")
    (workspace / "empty").mkdir()
    working = tmp_path / "monitor-private" / "working.md"
    working.parent.mkdir()
    working.write_bytes(b"Current decision and scoped ground.\n")
    identities = {
        "task_identity": "synthetic:task-1", "source_identity": "frozen-source",
        "system_prompt_sha256": _hash("system"),
        "continuation_prompt_sha256": _hash("continuation"),
        "tool_schema_sha256": _hash("seven-tools"),
        "model_config_sha256": _hash("synthetic-config"),
    }
    boundary = {
        "review_id": "review-7", "request_id": "request-12",
        "public_cursor": 23, "task_turn": 11,
        "completion_control_state": {"pending_completion": None, "pending_delivery": None},
    }
    attestation = {**boundary, "task_writes_paused": True, "supervisor_idle": True,
                   "inflight_requests": 0, "inflight_tools": 0}
    arguments = {
        "checkpoint_root": tmp_path / "research-archive", "checkpoint_id": "checkpoint-1",
        "workspace_root": workspace, "working_path": working,
        "history_prefix": [{"role": "user", "content": "public task"},
                           {"role": "assistant", "content": "scoped observation"}],
        "identities": identities, "boundary": boundary,
        "boundary_probe": lambda: dict(attestation),
    }
    return arguments, workspace, working, attestation


def test_capture_and_verify_full_workspace_binding(tmp_path):
    arguments, workspace, working, _ = _case(tmp_path)
    root = capture_checkpoint(**arguments)
    result = verify_checkpoint(root, expected_identities=arguments["identities"])
    assert result == {"checkpoint_id": "checkpoint-1", "capture_status": "complete",
                      "task_identity": "synthetic:task-1", "source_identity": "frozen-source",
                      "public_cursor": 23, "task_turn": 11}
    assert (root / "workspace/pkg/main.py").read_bytes() == b"value = 1\n"
    assert (root / "workspace/empty").is_dir()
    assert (root / "epistemic/working.md").read_bytes() == working.read_bytes()
    assert json.loads((root / "epistemic/history.json").read_text())[1]["content"] == "scoped observation"
    binding = json.loads((root / "binding.json").read_text())
    assert binding["history_sha256"] == hashlib.sha256((root / "epistemic/history.json").read_bytes()).hexdigest()
    assert binding["workspace_manifest_sha256"] == hashlib.sha256((root / "workspace_manifest.json").read_bytes()).hexdigest()
    assert binding["barrier"]["task_writes_paused"] is True
    (workspace / "pkg/main.py").write_bytes(b"value = 2\n")
    assert (root / "workspace/pkg/main.py").read_bytes() == b"value = 1\n"
    with pytest.raises(FileExistsError):
        capture_checkpoint(**arguments)


@pytest.mark.parametrize("relative", ["workspace/pkg/main.py", "epistemic/working.md"])
def test_verify_rejects_content_mutation(tmp_path, relative):
    arguments, *_ = _case(tmp_path)
    root = capture_checkpoint(**arguments)
    (root / relative).write_bytes(b"tampered\n")
    with pytest.raises(ValueError, match="manifest mismatch"):
        verify_checkpoint(root)


def test_verify_rejects_manifest_and_identity_mismatch(tmp_path):
    arguments, *_ = _case(tmp_path)
    root = capture_checkpoint(**arguments)
    wrong = dict(arguments["identities"], source_identity="other-source")
    with pytest.raises(ValueError, match="expected identity mismatch"):
        verify_checkpoint(root, expected_identities=wrong)
    manifest = root / "workspace_manifest.json"
    manifest.write_bytes(manifest.read_bytes() + b" ")
    with pytest.raises(ValueError, match="manifest mismatch"):
        verify_checkpoint(root)


def test_verify_rejects_missing_file(tmp_path):
    arguments, *_ = _case(tmp_path)
    root = capture_checkpoint(**arguments)
    (root / "workspace/pkg/main.py").unlink()
    with pytest.raises(ValueError, match="manifest mismatch"):
        verify_checkpoint(root)


def test_incomplete_capture_is_never_sealed(tmp_path):
    arguments, *_ = _case(tmp_path)
    arguments["boundary_probe"] = lambda: {**arguments["boundary"],
                                             "task_writes_paused": False,
                                             "supervisor_idle": True,
                                             "inflight_requests": 0, "inflight_tools": 0}
    with pytest.raises(ValueError, match="not quiescent"):
        capture_checkpoint(**arguments)
    root = arguments["checkpoint_root"] / arguments["checkpoint_id"]
    assert not (root / "complete.json").exists()
    assert json.loads((root / "capture_status.json").read_text())["status"] == "incomplete"
    with pytest.raises(ValueError, match="incomplete"):
        verify_checkpoint(root)


def test_boundary_change_during_capture_is_incomplete(tmp_path):
    arguments, _, _, attestation = _case(tmp_path)
    calls = 0

    def probe():
        nonlocal calls
        calls += 1
        return {**attestation, "public_cursor": 23 if calls == 1 else 24}

    arguments["boundary_probe"] = probe
    with pytest.raises(ValueError, match="boundary changed"):
        capture_checkpoint(**arguments)
    assert not (arguments["checkpoint_root"] / "checkpoint-1" / "complete.json").exists()


def test_concurrent_workspace_change_is_incomplete(tmp_path, monkeypatch):
    arguments, workspace, *_ = _case(tmp_path)
    original = implementation._tree_manifest
    calls = 0

    def changing_scan(root):
        nonlocal calls
        result = original(root)
        calls += 1
        if calls == 1:
            (workspace / "pkg/main.py").write_bytes(b"value = 2\n")
        return result

    monkeypatch.setattr(implementation, "_tree_manifest", changing_scan)
    with pytest.raises(ValueError, match="workspace changed"):
        capture_checkpoint(**arguments)
    root = arguments["checkpoint_root"] / "checkpoint-1"
    assert not (root / "complete.json").exists()
    assert json.loads((root / "capture_status.json").read_text())["status"] == "incomplete"


def test_history_change_during_capture_is_incomplete(tmp_path, monkeypatch):
    arguments, *_ = _case(tmp_path)
    original = implementation._tree_manifest
    calls = 0

    def changing_scan(root):
        nonlocal calls
        result = original(root)
        calls += 1
        if calls == 2:
            arguments["history_prefix"].append({"role": "assistant", "content": "late"})
        return result

    monkeypatch.setattr(implementation, "_tree_manifest", changing_scan)
    with pytest.raises(ValueError, match="History changed"):
        capture_checkpoint(**arguments)


def test_reject_archive_inside_workspace_and_unsafe_id(tmp_path):
    arguments, workspace, *_ = _case(tmp_path)
    arguments["checkpoint_root"] = workspace / "archive"
    with pytest.raises(ValueError, match="outside"):
        capture_checkpoint(**arguments)
    arguments["checkpoint_id"] = "../escape"
    with pytest.raises(ValueError, match="safe path"):
        capture_checkpoint(**arguments)


def test_no_semantic_verdict_or_live_agent_dependency():
    source = Path(__file__).with_name("checkpoint.py").read_text(encoding="utf-8")
    for prohibited in ("ground_valid", "ground_invalid", "stale_flag", "reopen_flag",
                       "requirement_status", "confidence_score", "def resume", "def replay"):
        assert prohibited not in source
    assert "monitor_agent_core" not in source
