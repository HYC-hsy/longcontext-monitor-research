import importlib.util
import json
import sys
from pathlib import Path

from monitor_agent_core.provider import ModelResponse, ToolCall
from monitor_agent_core.workspace import MonitorWorkspace


def call(name, arguments, cid):
    return ModelResponse("", [ToolCall(cid, name, json.dumps(arguments))], {})


def load_module():
    path = Path(__file__).parents[2] / "method_discovery" / "autonomous_selection_probe.py"
    spec = importlib.util.spec_from_file_location("autonomous_selection_probe", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def test_parent_selection_child_c_and_final_share_budget(tmp_path):
    module = load_module()
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "original_task.txt").write_text("The result must be ordered.\n", encoding="utf-8")
    (evidence / "events.jsonl").write_text("ordering observed\n", encoding="utf-8")
    workspace = MonitorWorkspace(evidence, tmp_path / "private")
    parent = Client([
        call("file_read", {"path": "task/original_task.txt"}, "p1"),
        call("select_local_question", {
            "question": "Does the observed result establish the required ordering?",
            "reason": "This could change the acceptance decision.",
        }, "p2"),
        call("finalize_parent_decision", {
            "outcome": "supported_in_scope",
            "conclusion": "The selected question was supported by the scoped evidence.",
        }, "p3"),
    ])
    child = Client([
        call("file_read", {"path": "task/events.jsonl"}, "c1"),
        call("finish_probe", {
            "outcome": "supported_in_scope", "conclusion": "ordering observed",
        }, "c2"),
    ])
    result = module.run_autonomous_selection_case(
        parent, child, workspace, "Should this implementation be accepted?",
        ("task/original_task.txt",), ("task/events.jsonl",),
        module.SelectionConfig(total_calls=6, selection_turns=2, child_turns=3, final_turns=2),
    )
    assert result["status"] == "completed"
    assert result["selection"]["question"].startswith("Does the observed")
    assert result["child"].outcome == "supported_in_scope"
    assert result["final"]["outcome"] == "supported_in_scope"
    assert result["budget_used"] == 5
    assert parent.calls == 3
    assert child.calls == 2
