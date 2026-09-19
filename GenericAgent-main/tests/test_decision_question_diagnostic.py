import importlib.util
import json
import sys
from pathlib import Path

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
                _call("select_decision_question", {
                    "question": "Does the observation establish ordering?",
                    "reason": "It could change acceptance.", "worthwhile": True}, "q2"),
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
    assert result["parent_direct"]["payload"]["outcome"] == "supported_in_scope"
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
    (fixture / "task_evidence" / "visible.jsonl").write_text("prefix\n", encoding="utf-8")
    (fixture / "task_evidence" / "full.jsonl").write_text("prefix\nfuture\n", encoding="utf-8")
    (fixture / "parent_context" / "history.json").write_text("[]", encoding="utf-8")
    config = {
        "checkpoint": {
            "id": "before-diagnosis",
            "model_visible": {
                "events": "task_evidence/visible.jsonl",
                "parent_history": "parent_context/history.json",
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


def test_history_extraction_uses_complete_model_input_not_posthoc_output(tmp_path):
    module = _load()
    dialogue = tmp_path / "dialogue.jsonl"
    rows = [
        {"event": "model_input", "wake_context": "Public task cursor advanced through 3.",
         "messages": [{"role": "user", "content": "old"}]},
        {"event": "model_output", "tool_calls": [{"name": "intervene"}]},
        {"event": "model_input", "wake_context": "Public task cursor advanced through 8.",
         "messages": [{"role": "user", "content": "new"}]},
        {"event": "model_output", "tool_calls": [{"name": "allow_complete"}]},
    ]
    dialogue.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    history, cursor = module.extract_model_history_at_cursor(dialogue, 3)
    assert cursor == 3
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
        raise AssertionError("no branch should be created when no question is worthwhile")

    def child(kind):
        raise AssertionError("isolated C must not run")

    result = module.run_three_way_case(
        parent, child, workspace, "Should this implementation be accepted?",
        ("task/original_task.txt",), (), [],
    )
    assert result["status"] == "no_question"
