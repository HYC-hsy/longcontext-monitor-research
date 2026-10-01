"""Offline end-to-end research orchestration; no model or Task process."""

import base64
import hashlib
import json
from pathlib import Path

import pytest

from method_discovery.diagnostics.epistemic_checkpoint_v0 import capture_checkpoint, verify_checkpoint
from method_discovery.diagnostics.epistemic_checkpoint_v0.experiment_harness import run_offline_experiment
from method_discovery.diagnostics.epistemic_checkpoint_v0.transition_fixture import SOURCE_SCHEMA


DEFINITIONS = json.loads(Path(__file__).with_name("synthetic_experiments.json").read_text(encoding="utf-8"))


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _checkpoint(tmp_path, definition):
    workspace = tmp_path / "live-workspace"
    workspace.mkdir()
    for name, content in definition["initial_files"].items():
        target = workspace / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode())
    working = tmp_path / "private" / "working.md"
    working.parent.mkdir()
    working.write_bytes(b"Current focal understanding.\n")
    boundary = {"review_id": "review-1", "request_id": "request-1",
                "public_cursor": 9, "task_turn": 4,
                "completion_control_state": {"pending_completion": None}}
    identities = {"task_identity": "synthetic:task", "source_identity": "frozen-source",
                  "system_prompt_sha256": _sha(b"system"),
                  "continuation_prompt_sha256": _sha(b"continuation"),
                  "tool_schema_sha256": _sha(b"seven tools"),
                  "model_config_sha256": _sha(b"synthetic profile")}
    return capture_checkpoint(
        checkpoint_root=tmp_path / "checkpoints", checkpoint_id="checkpoint-1",
        workspace_root=workspace, working_path=working,
        history_prefix=[{"role": "assistant", "content": "synthetic ground"}],
        identities=identities, boundary=boundary,
        boundary_probe=lambda: {**boundary, "task_writes_paused": True,
                                "supervisor_idle": True, "inflight_requests": 0,
                                "inflight_tools": 0})


def _source(tmp_path, definition):
    operations = []
    for name, content in definition["writes"].items():
        before = definition["initial_files"].get(name)
        operations.append({"op": "write", "path": name,
                           "before_sha256": _sha(before.encode()) if before is not None else None,
                           "content_base64": base64.b64encode(content.encode()).decode()})
    path = tmp_path / "researcher-bundle.json"
    path.write_text(json.dumps({"schema": SOURCE_SCHEMA,
                                "checkpoint_id": "checkpoint-1",
                                "transition_id": "transition-1",
                                "operations": operations}, sort_keys=True), encoding="utf-8")
    return path, _sha(path.read_bytes())


def _run(tmp_path, checkpoint, source, digest, **overrides):
    arguments = {"checkpoint_dir": checkpoint, "transition_source": source,
                 "transition_id": "transition-1", "expected_source_sha256": digest,
                 "expected_checkpoint_id": "checkpoint-1",
                 "experiment_id": "experiment-1", "output_root": tmp_path / "experiments",
                 "supervisor_session_ref": {"status": "operator-supplied-reference-only",
                                            "reference": "synthetic-session"}}
    arguments.update(overrides)
    return run_offline_experiment(**arguments)


@pytest.mark.parametrize("definition", DEFINITIONS, ids=lambda row: row["id"])
def test_checkpoint_fixture_wtv_archive_chain(tmp_path, definition):
    checkpoint = _checkpoint(tmp_path, definition)
    source, digest = _source(tmp_path, definition)
    original_binding = (checkpoint / "binding.json").read_bytes()
    original_manifest = (checkpoint / "workspace_manifest.json").read_bytes()
    root = _run(tmp_path, checkpoint, source, digest)
    assert json.loads((root / "metadata.json").read_text())["status"] == "complete"
    checkpoint_ref = json.loads((root / "checkpoint_ref.json").read_text())
    transition_ref = json.loads((root / "transition_ref.json").read_text())
    transition_record = json.loads((root / "transitions/transition-1/transition.json").read_text())
    assert checkpoint_ref["checkpoint_id"] == transition_record["checkpoint_id"] == "checkpoint-1"
    assert checkpoint_ref["binding_sha256"] == _sha(original_binding)
    assert transition_ref["source_sha256"] == digest
    assert transition_ref["status"] == "complete"
    wtv = json.loads((root / "wtv_result.json").read_text())
    assert wtv["before"]["audit"]["initial_baseline"] is True
    assert wtv["before"]["audit"]["sample_complete"] is True
    assert wtv["after"]["audit"]["initial_baseline"] is False
    assert wtv["after"]["audit"]["sample_complete"] is True
    assert wtv["after"]["audit"]["from_cursor"] == 9
    assert wtv["after"]["audit"]["to_cursor"] == 9
    assert wtv["after"]["audit"]["modified"] == definition["expected_modified"]
    assert wtv["after"]["audit"]["total_changed"] == len(definition["expected_modified"])
    assert (checkpoint / "binding.json").read_bytes() == original_binding
    assert (checkpoint / "workspace_manifest.json").read_bytes() == original_manifest
    assert verify_checkpoint(checkpoint)["capture_status"] == "complete"
    session = json.loads((root / "supervisor_session_ref.json").read_text())
    assert session["reference"] == "synthetic-session"
    assert "not_run" == json.loads((root / "metadata.json").read_text())["supervisor_continuation"]


def test_fixture_failure_is_preserved_by_harness(tmp_path):
    definition = DEFINITIONS[0]
    checkpoint = _checkpoint(tmp_path, definition)
    source, _ = _source(tmp_path, definition)
    with pytest.raises(ValueError, match="source hash mismatch"):
        _run(tmp_path, checkpoint, source, "0" * 64)
    root = tmp_path / "experiments/experiment-1"
    assert json.loads((root / "metadata.json").read_text())["status"] == "failed"
    assert json.loads((root / "transition_ref.json").read_text())["status"] == "failed"
    assert json.loads((root / "transitions/transition-1/end.json").read_text())["status"] == "failed"


def test_identity_mismatch_is_recorded_without_transition(tmp_path):
    definition = DEFINITIONS[0]
    checkpoint = _checkpoint(tmp_path, definition)
    source, digest = _source(tmp_path, definition)
    with pytest.raises(ValueError, match="checkpoint identity mismatch"):
        _run(tmp_path, checkpoint, source, digest, expected_checkpoint_id="wrong-id")
    root = tmp_path / "experiments/experiment-1"
    assert json.loads((root / "metadata.json").read_text())["status"] == "failed"
    assert not (root / "transitions").exists()


def test_no_model_visible_or_semantic_output(tmp_path):
    checkpoint = _checkpoint(tmp_path, DEFINITIONS[0])
    source, digest = _source(tmp_path, DEFINITIONS[0])
    root = _run(tmp_path, checkpoint, source, digest, supervisor_session_ref=None)
    assert json.loads((root / "supervisor_session_ref.json").read_text())["status"] == "unavailable"
    all_metadata = "\n".join(p.read_text(encoding="utf-8") for p in root.glob("*.json"))
    for prohibited in ("ground_valid", "stale", "reopen", "carry", "relevant",
                       "semantic_impact", "requirement_status"):
        assert prohibited not in all_metadata
    assert not (root / "model_input.json").exists()
