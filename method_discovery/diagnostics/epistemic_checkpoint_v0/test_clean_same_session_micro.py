import json
import shutil
import sys
from pathlib import Path

import pytest

from .checkpoint import _tree_manifest, capture_checkpoint, verify_checkpoint
from .clean_same_session_micro import (
    HOST_EVENT, SECOND_WAKE_CONTEXT, apply_live_bundle, bundle,
    canonical_bytes, input_boundary_audit, manifest_hash, neutral_path,
    prepare, public_inputs, same_session_proof, sha256_bytes,
    validate_prereg,
)


def _profile(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"claude_monitor_opus48": {
        "apikey": "offline-only", "apibase": "http://127.0.0.1:1",
        "model": "claude-opus-4-8", "provider": "anthropic"}}))
    return path


def _prepare(tmp_path):
    root = tmp_path / "archive"
    prepare(archive_root=root, live_parent=Path("E:/runs"),
            profile_file=_profile(tmp_path), source_sha="impl-sha")
    prereg = json.loads((root / "PREREGISTRATION.json").read_text())
    return root, prereg


def test_preregistration_freezes_exact_tasks_workspaces_and_bundles(tmp_path):
    root, prereg = _prepare(tmp_path)
    assert prereg["run_order"] == [1, 2, 3]
    assert prereg["max_supervisor_reviews_per_record"] == 2
    assert prereg["second_wake_context"] == SECOND_WAKE_CONTEXT
    assert prereg["python_dont_write_bytecode"] is True
    assert [record["task_sha256"] for record in prereg["records"]] == [
        "f9d0387c655ae7f0037464fa336deed9bcc50b6ed15c8fb2cfcc338a9713bb2f",
        "f9d0387c655ae7f0037464fa336deed9bcc50b6ed15c8fb2cfcc338a9713bb2f",
        "e1faace08e0523d16128fac910a2aa50a948f4391b82652e1bbcbc3bb02bc774",
    ]
    assert all(len(record["initial_workspace_manifest_sha256"]) == 64
               for record in prereg["records"])
    validate_prereg(root, prereg, "impl-sha")
    for record in prereg["records"]:
        assert neutral_path(Path(record["live_root"]))
        assert not Path(record["live_root"]).exists()
        assert len(record["transition_bundle_sha256"]) == 64
    assert not neutral_path(Path("E:/runs/seed_run"))
    assert not neutral_path(Path("E:/runs/case-a"))


def test_exact_bundle_paths_and_no_change(tmp_path):
    root, prereg = _prepare(tmp_path)
    assert [[item["path"] for item in bundle(i)["changes"]] for i in (1, 2, 3)] == [
        ["wiring.py"], ["validation.py"], []]
    for record in prereg["records"]:
        base = root / record["input_path"]
        spec = json.loads((base / "transition_bundle.json").read_text())
        assert spec == bundle(record["index"])
        _, expected_files = public_inputs(record["index"])
        assert {p.name: p.read_text() for p in (base / "workspace").iterdir()} == expected_files


def _checkpoint(tmp_path, workspace):
    working = tmp_path / "working.md"
    working.write_text("The current route response is observed.\n")
    identities = {"task_identity": "task", "source_identity": "impl-sha",
                  "system_prompt_sha256": "a" * 64, "tool_schema_sha256": "b" * 64,
                  "model_config_sha256": "c" * 64}
    boundary = {"review_id": "r1", "request_id": "init-r1", "public_cursor": 0,
                "task_turn": 0, "completion_control_state": {"pending": False}}
    probe = lambda: dict(boundary, task_writes_paused=True, supervisor_idle=True,
                         inflight_requests=0, inflight_tools=0)
    return capture_checkpoint(checkpoint_root=tmp_path / "cp", checkpoint_id="micro-01",
                              workspace_root=workspace, working_path=working,
                              history_prefix=[{"role": "user", "content": "ordinary task"}],
                              identities=identities, boundary=boundary, boundary_probe=probe)


@pytest.mark.parametrize("index,expected", [(1, ["task/workspace/wiring.py"]),
                                            (2, ["task/workspace/validation.py"]),
                                            (3, [])])
def test_live_application_checkpoint_immutable_and_real_wtv(tmp_path, index, expected):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "GenericAgent-main"))
    from monitor_agent_core.runtime import WorkspaceTransitionSampler
    root, prereg = _prepare(tmp_path)
    record = prereg["records"][index - 1]
    workspace = tmp_path / "live"
    shutil.copytree(root / record["input_path"] / "workspace", workspace)
    sampler = WorkspaceTransitionSampler()
    first_view, first = sampler.sample(workspace, cursor=0, task_turn=0)
    assert first["initial_baseline"] and first["total_changed"] == 0
    assert "baseline" in first_view
    checkpoint = _checkpoint(tmp_path, workspace)
    original_binding = (checkpoint / "binding.json").read_bytes()
    result = apply_live_bundle(
        workspace=workspace, checkpoint=checkpoint,
        bundle_path=root / record["input_path"] / "transition_bundle.json",
        expected_bundle_sha256=record["transition_bundle_sha256"],
        output=tmp_path / "transition_application.json")
    assert result["checkpoint_binding_unchanged"]
    assert (checkpoint / "binding.json").read_bytes() == original_binding
    assert verify_checkpoint(checkpoint)["capture_status"] == "complete"
    second_view, second = sampler.sample(workspace, cursor=1, task_turn=1)
    assert second["modified"] == expected
    assert second["added"] == second["deleted"] == []
    assert ("no path-level changes detected" in second_view) == (index == 3)
    assert result["before_manifest"] == _tree_manifest(checkpoint / "workspace")


def test_same_session_identity_and_fixed_second_wake():
    h1 = [{"role": "user", "content": "first"}]
    h2 = h1 + [{"role": "assistant", "content": "second"}]
    assert same_session_proof(pid_before=5, pid_after=5, history_before=h1,
                              history_after=h2, review_ids=["r1", "r2"])["passed"]
    assert not same_session_proof(pid_before=5, pid_after=6, history_before=h1,
                                  history_after=h2, review_ids=["r1", "r2"])["passed"]
    assert "changed" not in SECOND_WAKE_CONTEXT.lower()
    assert "transition" not in SECOND_WAKE_CONTEXT.lower()
    assert HOST_EVENT["text"] == HOST_EVENT["synopsis"]


def test_input_audit_rejects_research_paths_and_accepts_production_wtv(tmp_path):
    dialogue = tmp_path / "dialogue.jsonl"
    good = [
        {"event": "review_context", "wake_context": "Ordinary start at E:\\runs\\a0\\workspace"},
        {"event": "model_input", "messages": [{"role": "user", "content": "ordinary start"}]},
        {"event": "review_context", "wake_context": SECOND_WAKE_CONTEXT + "\n"
         + "Workspace transition since the previous Supervisor sample: modified task/workspace/wiring.py"},
        {"event": "model_input", "messages": [{"role": "user", "content": SECOND_WAKE_CONTEXT}]},
    ]
    dialogue.write_text("\n".join(json.dumps(row) for row in good) + "\n")
    kwargs = dict(live_root=Path("E:/runs/a0"), archive_root=Path("E:/research/archive"),
                  checkpoint_id="micro-cp", bundle_sha256="f" * 64)
    assert input_boundary_audit(dialogue, **kwargs)["passed"]
    good[0]["wake_context"] += " E:\\runs\\seed_sessions\\workspace"
    dialogue.write_text("\n".join(json.dumps(row) for row in good) + "\n")
    assert not input_boundary_audit(dialogue, **kwargs)["passed"]


def test_runner_has_two_review_cap_and_no_task_agent_or_verifier_calls():
    import inspect
    from . import clean_same_session_micro as module
    source = inspect.getsource(module.run_record)
    assert "_wait_for_reviews(runtime, monitor_root, 1" in source
    assert "_wait_for_reviews(runtime, monitor_root, 2" in source
    assert "runtime.close()" in source
    assert "TaskAgent(" not in source and "verifier.run(" not in source
