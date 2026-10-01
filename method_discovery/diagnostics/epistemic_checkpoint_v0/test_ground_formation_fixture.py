import hashlib
import json
from pathlib import Path

import pytest

from .checkpoint import _tree_manifest, verify_checkpoint
from .ground_formation_fixture import (
    RESEARCH_MARKERS, archive_input, audit_model_input, capture_seed,
    create_workspace, eligible_boundary,
)


def _sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


@pytest.mark.parametrize("kind,count", [("a", 3), ("b", 4), ("c", 2)])
def test_workspace_and_public_task_are_neutral(tmp_path, kind, count):
    work = tmp_path / "work"
    task = create_workspace(kind, work)
    assert len(list(work.iterdir())) == count
    visible = task + "\n" + "\n".join(p.read_text() for p in work.iterdir())
    assert not any(marker in visible.lower() for marker in RESEARCH_MARKERS)
    assert ("validation.py" in [p.name for p in work.iterdir()]) == (kind == "b")


def test_checkpoint_requires_idle_and_preserves_workspace(tmp_path):
    work = tmp_path / "work"
    task = create_workspace("a", work)
    before = _tree_manifest(work)
    working = tmp_path / "working.md"
    working.write_text("The observed route currently returns the home response.\n")
    identities = dict(task_identity=_sha(task), source_identity="source-commit",
                      system_prompt_sha256=_sha("system"),
                      continuation_prompt_sha256=_sha("continuation"),
                      tool_schema_sha256=_sha("tools"), model_config_sha256=_sha("model"))
    boundary = dict(review_id="review-one", request_id="init-one", public_cursor=0,
                    task_turn=0, completion_control_state={"pending": False})
    state = dict(boundary, task_writes_paused=True, supervisor_idle=True,
                 inflight_requests=0, inflight_tools=0)
    probe = lambda: dict(state)
    with pytest.raises(ValueError, match="idle"):
        capture_seed(checkpoint_root=tmp_path / "checkpoints", checkpoint_id="seed-01",
                     workspace_root=work, working_path=working, history_prefix=[],
                     identities=identities, boundary=boundary, boundary_probe=probe,
                     review_finished=False, observed_task_tool=True)
    assert not (tmp_path / "checkpoints" / "seed-01").exists()
    final = capture_seed(checkpoint_root=tmp_path / "checkpoints", checkpoint_id="seed-01",
                         workspace_root=work, working_path=working,
                         history_prefix=[{"role": "user", "content": "task"}],
                         identities=identities, boundary=boundary, boundary_probe=probe,
                         review_finished=True, observed_task_tool=True)
    assert verify_checkpoint(final)["capture_status"] == "complete"
    assert _tree_manifest(work) == before
    with pytest.raises(FileExistsError):
        capture_seed(checkpoint_root=tmp_path / "checkpoints", checkpoint_id="seed-01",
                     workspace_root=work, working_path=working, history_prefix=[],
                     identities=identities, boundary=boundary, boundary_probe=probe,
                     review_finished=True, observed_task_tool=True)


def test_no_checkpoint_after_review_if_observation_or_note_missing(tmp_path):
    assert not eligible_boundary(review_finished=True, provider_idle=True, tools_idle=True,
                                 workspace_idle=True, observed_task_tool=False,
                                 working_bytes=b"note")
    assert not eligible_boundary(review_finished=True, provider_idle=True, tools_idle=True,
                                 workspace_idle=True, observed_task_tool=True,
                                 working_bytes=b"  ")


def test_model_input_metadata_audit(tmp_path):
    dialogue = tmp_path / "dialogue.jsonl"
    rows = [dict(event="review_context", system_prompt="ordinary contract", wake_context="read task"),
            dict(event="model_input", messages=[{"role": "user", "content": "read dispatcher.py"}]),
            dict(event="model_output", content="case-a-control")]
    dialogue.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    assert audit_model_input(dialogue, ("case-a-control",))["contaminated"] is False
    rows[1]["messages"][0]["content"] = "case-a-control"
    dialogue.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    assert audit_model_input(dialogue, ("case-a-control",))["contaminated"] is True


def test_archive_input_does_not_modify_workspace(tmp_path):
    work = tmp_path / "work"
    task = create_workspace("c", work)
    before = _tree_manifest(work)
    receipt = archive_input(tmp_path / "archive", task, work, {"model": "test"})
    assert receipt["task_sha256"] == _sha(task)
    assert _tree_manifest(work) == before
