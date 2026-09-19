import importlib.util
import json
import sys
from pathlib import Path

import pytest

from monitor_agent_core.provider import ModelResponse, ToolCall
from monitor_agent_core.workspace import MonitorWorkspace


def _load():
    path = Path(__file__).parents[2] / "method_discovery" / "decision_question_diagnostic.py"
    spec = importlib.util.spec_from_file_location("decision_question_diagnostic", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _call(name, args, cid):
    return ModelResponse("", [ToolCall(cid, name, json.dumps(args))], {})


class Client:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.history = []
        self.calls = 0

    def complete(self, messages, tools):
        self.calls += 1
        response = next(self.responses)
        self.history.extend(messages)
        return response

    def record_tool_results(self, results):
        self.history.append({"role": "user", "content": results})

    def history_measure(self):
        return {"items": len(self.history), "characters": 0, "sha256": "fixture"}

    def restore_history(self, history):
        self.history = json.loads(json.dumps(history))

    def export_history(self):
        return json.loads(json.dumps(self.history))


class ErrorClient(Client):
    def complete(self, messages, tools):
        self.calls += 1
        raise RuntimeError("synthetic transport failure")


def test_three_way_uses_one_question_for_parent_and_c(tmp_path):
    module = _load()
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "original_task.txt").write_text("The result must be ordered.\n", encoding="utf-8")
    (evidence / "events.jsonl").write_text("ordering observed\n", encoding="utf-8")
    workspace = MonitorWorkspace(evidence, tmp_path / "private")
    base = [{"role": "user", "content": [{"type": "text", "text": "prior state"}]}]

    def parent(kind):
        if kind == "ordinary":
            return Client([
                _call("file_read", {"path": "task/events.jsonl"}, "a1"),
                _call("finish_parent_decision", {
                    "outcome": "unresolved", "conclusion": "not enough evidence"}, "a2"),
            ])
        if kind == "question":
            return Client([
                _call("file_read", {"path": "task/original_task.txt"}, "q1"),
                _call("file_read", {"path": "task/events.jsonl"}, "q2"),
                _call("select_decision_question", {
                    "question": "Does the observation establish ordering?",
                    "reason": "It could change acceptance.", "worthwhile": True}, "q3"),
            ])
        if kind == "parent_direct":
            return Client([
                _call("file_read", {"path": "task/events.jsonl"}, "b1"),
                _call("finish_parent_decision", {
                    "outcome": "supported_in_scope", "conclusion": "ordering observed"}, "b2"),
            ])
        return Client([_call("finish_parent_decision", {
            "outcome": "supported_in_scope", "conclusion": "C supports ordering"}, "f1")])

    def child(kind):
        return Client([
            _call("file_read", {"path": "task/events.jsonl"}, "c1"),
            _call("finish_probe", {
                "outcome": "supported_in_scope", "conclusion": "ordering observed"}, "c2"),
        ])

    result = module.run_three_way_case(
        parent, child, workspace, "Should this implementation be accepted?",
        ("task/original_task.txt",), ("task/events.jsonl",), base,
    )
    assert result["status"] == "completed"
    assert result["selected_question"]["question"] == "Does the observation establish ordering?"
    assert result["parent_direct"]["outcome"] == "supported_in_scope"
    assert result["isolated_c"]["child_outcome"] == "supported_in_scope"
    # Both branches receive the same six-call ceiling and both charge the
    # shared question prefix; actual use may differ if one reaches a verdict
    # earlier.
    assert result["parent_direct"]["calls"] <= 6
    assert result["isolated_c"]["calls"] <= 6


def test_checkpoint_validation_does_not_require_prior_approval(tmp_path):
    module = _load()
    fixture = tmp_path / "fixture"
    (fixture / "task_evidence").mkdir(parents=True)
    (fixture / "parent_context").mkdir()
    (fixture / "task_evidence" / "visible.jsonl").write_text(
        json.dumps({"cursor": 3, "task_turn": 2}) + "\n", encoding="utf-8")
    (fixture / "task_evidence" / "full.jsonl").write_text(
        json.dumps({"cursor": 3, "task_turn": 2}) + "\n" + json.dumps({"cursor": 4}) + "\n",
        encoding="utf-8")
    (fixture / "parent_context" / "history.json").write_text("[]", encoding="utf-8")
    config = {
        "checkpoint": {
            "id": "before-diagnosis",
            "model_visible": {
                "events": "task_evidence/visible.jsonl",
                "parent_history": "parent_context/history.json",
                "history_source_kind": "provider_snapshot",
                "through_cursor": 3,
            },
            "research_archive": {"events": "task_evidence/full.jsonl"},
            "forbid_control_actions": ["allow_complete"],
        },
        "cases": [{"evidence_paths": ["task/original_task.txt"]}],
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    import hashlib
    def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = {
        "checkpoint": "before-diagnosis",
        "model_visible_cursor": 3,
        "config_sha256": sha(config_path),
        "artifact_sha256": {
            "task_evidence/visible.jsonl": sha(fixture / "task_evidence/visible.jsonl"),
            "task_evidence/full.jsonl": sha(fixture / "task_evidence/full.jsonl"),
            "parent_context/history.json": sha(fixture / "parent_context/history.json"),
        },
    }
    (fixture / "materialization.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert module.validate_checkpoint_fixture(config, fixture, config_path) == []


def test_checkpoint_validation_rejects_missing_cursor(tmp_path):
    module = _load()
    fixture = tmp_path / "fixture"
    (fixture / "task_evidence").mkdir(parents=True)
    (fixture / "parent_context").mkdir()
    (fixture / "task_evidence" / "visible.jsonl").write_text(
        json.dumps({"task_turn": 2}) + "\n", encoding="utf-8")
    (fixture / "task_evidence" / "full.jsonl").write_text(
        json.dumps({"task_turn": 2}) + "\n", encoding="utf-8")
    (fixture / "parent_context" / "history.json").write_text("[]", encoding="utf-8")
    config = {"checkpoint": {"id": "missing-cursor", "model_visible": {
        "events": "task_evidence/visible.jsonl", "parent_history": "parent_context/history.json",
        "history_source_kind": "provider_snapshot", "through_cursor": 0},
        "research_archive": {"events": "task_evidence/full.jsonl"}}, "cases": []}
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    import hashlib
    def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
    files = ["task_evidence/visible.jsonl", "task_evidence/full.jsonl",
             "parent_context/history.json"]
    (fixture / "materialization.json").write_text(json.dumps({
        "checkpoint": "missing-cursor", "model_visible_cursor": 0,
        "config_sha256": sha(config_path),
        "artifact_sha256": {name: sha(fixture / name) for name in files},
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="cursor"):
        module.validate_checkpoint_fixture(config, fixture, config_path)


def test_history_extraction_uses_complete_model_input_not_posthoc_output(tmp_path):
    module = _load()
    dialogue = tmp_path / "dialogue.jsonl"
    rows = [
        {"event": "model_input", "review_id": "r1", "wake_context": "Public task cursor advanced through 3.",
         "messages": [{"role": "user", "content": "old"}]},
        {"event": "model_output", "tool_calls": [{"name": "intervene"}]},
        {"event": "model_input", "review_id": "r1", "wake_context": "Public task cursor advanced through 8.",
         "messages": [{"role": "user", "content": "new"}]},
        {"event": "model_output", "tool_calls": [{"name": "allow_complete"}]},
    ]
    dialogue.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    increment = module.select_review_model_input(dialogue, "r1", 0)
    assert increment["line"] == 1
    snapshot = tmp_path / "history.json"
    snapshot.write_text(json.dumps([{"role": "user", "content": "old"}]), encoding="utf-8")
    history = module.extract_model_history_at_checkpoint(snapshot)
    assert history == [{"role": "user", "content": "old"}]


def test_no_worthwhile_question_does_not_force_isolated_probe(tmp_path):
    module = _load()
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "original_task.txt").write_text("No change is needed.\n", encoding="utf-8")
    workspace = MonitorWorkspace(evidence, tmp_path / "private")

    def parent(kind):
        if kind == "ordinary":
            return Client([_call("finish_parent_decision", {
                "outcome": "supported_in_scope", "conclusion": "already supported"}, "a1")])
        if kind == "question":
            return Client([_call("select_decision_question", {
                "question": "", "reason": "No unresolved premise can change this decision.",
                "worthwhile": False}, "q1")])
        return Client([_call("finish_parent_decision", {
            "outcome": "supported_in_scope", "conclusion": "no extra question needed"}, "f1")])

    def child(kind):
        raise AssertionError("isolated C must not run")

    result = module.run_three_way_case(
        parent, child, workspace, "Should this implementation be accepted?",
        ("task/original_task.txt",), (), [],
    )
    assert result["status"] == "completed"
    assert result["isolated_c"]["child_status"] == "not_called"


def test_question_budget_exit_preserves_completed_ordinary_branch(tmp_path):
    module = _load()
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "original_task.txt").write_text("Requirement.\n", encoding="utf-8")
    workspace = MonitorWorkspace(evidence, tmp_path / "private")

    def parent(kind):
        if kind == "ordinary":
            return Client([_call("finish_parent_decision", {
                "outcome": "unresolved", "conclusion": "ordinary completed"}, "a1")])
        if kind == "question":
            return Client([
                _call("file_read", {"path": "task/original_task.txt"}, "q1"),
                _call("file_read", {"path": "task/original_task.txt"}, "q2"),
                _call("file_read", {"path": "task/original_task.txt"}, "q3"),
            ])
        raise AssertionError(kind)

    result = module.run_three_way_case(
        parent, lambda kind: None, workspace, "Decide.",
        ("task/original_task.txt",), (), [],
    )
    assert result["status"] == "incomplete"
    assert result["ordinary"]["status"] == "completed"
    assert result["ordinary"]["outcome"] == "unresolved"
    assert result["question"]["status"] == "budget_or_protocol_incomplete"
    assert result["parent_direct"]["status"] == "not_run"


def test_one_branch_exception_does_not_erase_other_branch_results(tmp_path):
    module = _load()
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "original_task.txt").write_text("Requirement.\n", encoding="utf-8")
    workspace = MonitorWorkspace(evidence, tmp_path / "private")

    def parent(kind):
        if kind == "ordinary":
            return ErrorClient([])
        if kind == "question":
            return Client([_call("select_decision_question", {
                "question": "", "reason": "No useful question.",
                "worthwhile": False}, "q1")])
        return Client([_call("finish_parent_decision", {
            "outcome": "unresolved", "conclusion": "saved sibling result"}, "f1")])

    result = module.run_three_way_case(
        parent, lambda kind: None, workspace, "Decide.",
        ("task/original_task.txt",), (), [],
    )
    assert result["ordinary"]["status"] == "error"
    assert result["parent_direct"]["status"] == "completed"
    assert result["parent_direct"]["conclusion"] == "saved sibling result"


def test_model_view_contains_only_declared_case_material(tmp_path):
    module = _load()
    fixture = tmp_path / "fixture"
    (fixture / "task_evidence").mkdir(parents=True)
    (fixture / "workspace").mkdir()
    (fixture / "task_evidence" / "events.jsonl").write_text(
        json.dumps({"cursor": 2}) + "\n", encoding="utf-8")
    (fixture / "task_evidence" / "original_task.txt").write_text("task", encoding="utf-8")
    (fixture / "task_evidence" / "full_archive.jsonl").write_text(
        json.dumps({"cursor": 2}) + "\n" + json.dumps({"cursor": 3}) + "\n",
        encoding="utf-8")
    (fixture / "workspace" / "impl.go").write_text("impl", encoding="utf-8")
    config = {"checkpoint": {"id": "cp", "model_visible": {
        "events": "task_evidence/events.jsonl", "parent_history": "parent.json",
        "through_cursor": 2}, "research_archive": {"events": "task_evidence/full_archive.jsonl"}},
        "cases": [{"id": "x", "source_paths": ["task/original_task.txt"],
                   "evidence_paths": ["task/workspace/impl.go"]}]}
    (fixture / "parent.json").write_text("[]", encoding="utf-8")
    import hashlib
    def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
    files = ["task_evidence/events.jsonl", "task_evidence/full_archive.jsonl",
             "task_evidence/original_task.txt", "workspace/impl.go", "parent.json"]
    (fixture / "materialization.json").write_text(json.dumps({
        "checkpoint": "cp", "model_visible_cursor": 2,
        "artifact_sha256": {name: sha(fixture / name) for name in files},
    }), encoding="utf-8")
    destination = tmp_path / "view"
    module.materialize_model_view(config, fixture, config["cases"][0], destination)
    assert (destination / "original_task.txt").is_file()
    assert (destination / "workspace" / "impl.go").is_file()
    assert not (destination / "task_evidence" / "full_archive.jsonl").exists()
