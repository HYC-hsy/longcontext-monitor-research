import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from monitor_agent_core.actions import ToolOutcome
from monitor_agent_core.provider import ModelResponse, ToolCall
from monitor_agent_core.workspace import MonitorWorkspace


def _load():
    path = Path(__file__).parents[2] / "method_discovery" / "scoped_decision_diagnostic.py"
    spec = importlib.util.spec_from_file_location("scoped_decision_diagnostic", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _call(name, args, call_id):
    return ModelResponse("", [ToolCall(call_id, name, json.dumps(args))], {})


class Client:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.history = []
        self.calls = []

    def complete(self, messages, tools):
        self.calls.append({"messages": json.loads(json.dumps(messages)),
                           "tools": json.loads(json.dumps(tools))})
        self.history.extend(messages)
        return next(self.responses)

    def record_tool_results(self, results):
        self.history.append({"role": "user", "content": results})

    def restore_history(self, history):
        self.history = json.loads(json.dumps(history))

    def history_measure(self):
        return {"items": len(self.history), "characters": 0, "sha256": "fixture"}


def _checkpoint(tmp_path):
    root = tmp_path / "checkpoint"
    workspace = root / "task" / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "ok.go").write_text("package sample\n", encoding="utf-8")
    (root / "task" / "research_derived_local_repair.json").write_text(
        '{"scope":"NewAllStrings only"}', encoding="utf-8")
    (root / "task" / "original_task.txt").write_text("requirements", encoding="utf-8")
    files = {}
    for path in root.rglob("*"):
        if path.is_file():
            files[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"root": root, "complete": {"manifest_sha256": "version"},
            "manifest": {"files": files}}


def _history():
    return [{
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "good", "content": json.dumps({
                "path": "task/original_task.txt", "sha256": "abc", "start": 1, "lines": 3,
            })},
            {"type": "tool_result", "tool_use_id": "bad", "content": json.dumps({
                "status": "error", "error": "failed",
            })},
        ],
    }]


def test_registry_accepts_real_history_and_current_success_only(tmp_path):
    module = _load()
    registry = module.EvidenceRegistry(_history())
    assert registry.validate_refs(["history:good"]) == (True, None)
    assert registry.validate_refs(["history:bad"])[0] is False

    success = registry.decorate("file_read", {
        "path": "task/research_derived_local_repair.json"}, ToolOutcome({
            "path": "task/research_derived_local_repair.json", "sha256": "repair",
            "start": 1, "lines": 5,
        }))
    reference = success.data["evidence_ref"]
    assert success.data["declared_support_scope"] == "local:validation.NewAllStrings"
    failed = registry.decorate("text_search", {}, ToolOutcome({
        "status": "denied", "error": "no access"}))
    assert "evidence_ref" not in failed.data
    assert registry.validate_refs([reference]) == (True, None)


def test_scoped_action_checks_scope_provenance_and_local_repair_boundary(tmp_path):
    module = _load()
    registry = module.EvidenceRegistry(_history())
    decorated = registry.decorate("file_read", {
        "path": "task/research_derived_local_repair.json"}, ToolOutcome({
            "path": "task/research_derived_local_repair.json", "sha256": "repair",
            "start": 1, "lines": 5,
        }))
    reference = decorated.data["evidence_ref"]
    base = {
        "decision_scope": "local_recovery",
        "local_update": {"summary": "repair added", "update_scope": "NewAllStrings",
                         "evidence_refs": [reference]},
        "decision_basis": [{"evidence_ref": reference, "supports": "whole task",
                            "support_scope": "root_completion"}],
        "remaining_limits": "Other requirements were not assessed.",
        "outcome": "supported_in_scope", "conclusion": "done",
    }
    rejected = registry.scoped_action("local_recovery", base)
    assert rejected.action is None
    assert rejected.data["status"] == "error"

    base["decision_basis"][0]["support_scope"] = "local:validation.NewAllStrings"
    accepted = registry.scoped_action("local_recovery", base)
    assert accepted.action.kind == "finish_scoped_decision"
    wrong_scope = registry.scoped_action("root_completion", base)
    assert wrong_scope.action is None


def test_matched_conditions_share_system_evidence_budget_and_isolate_state(tmp_path):
    module = _load()
    direct = sys.modules["direct_evidence_diagnostic"]
    checkpoint = _checkpoint(tmp_path)
    index = direct.FrozenEvidenceIndex(checkpoint)
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "working.md").write_text("S0", encoding="utf-8")
    workspace = MonitorWorkspace(checkpoint["root"] / "task", seed)
    branches = tmp_path / "branches"
    branches.mkdir()
    history = _history()
    prompt_client = Client([
        _call("file_write", {"path": "monitor/working.md", "content": "prompt",
                             "mode": "replace"}, "p1"),
        _call("finish_parent_decision", {"outcome": "supported_in_scope",
              "conclusion": "scope=local; update=repair; basis=history:good; limits=others"}, "p2"),
    ])
    mechanism_client = Client([
        _call("finish_scoped_decision", {
            "decision_scope": "local_recovery",
            "local_update": {"summary": "repair", "update_scope": "local",
                             "evidence_refs": ["history:good"]},
            "decision_basis": [{"evidence_ref": "history:good", "supports": "requirement",
                                "support_scope": "file:task/original_task.txt"}],
            "remaining_limits": "other requirements not assessed",
            "outcome": "supported_in_scope", "conclusion": "local repaired",
        }, "m1"),
    ])
    common = dict(
        case="r7_local_recovery", seed_workspace=workspace,
        branch_private_root=branches, index=index,
        initial_paths=("task/original_task.txt", "task/research_derived_local_repair.json"),
        parent_history=history, parent_system="Supervisor", total_calls=6,
    )
    prompt_result = module.run_scoped_decision_condition(
        condition="scope_prompt_control", parent_client=prompt_client, **common)
    mechanism_result = module.run_scoped_decision_condition(
        condition="scope_decision_interface", parent_client=mechanism_client, **common)

    assert prompt_result["status"] == mechanism_result["status"] == "completed"
    assert prompt_client.calls[0]["messages"][0] == mechanism_client.calls[0]["messages"][0]
    prompt_tools = [item["function"]["name"] for item in prompt_client.calls[0]["tools"]]
    mechanism_tools = [item["function"]["name"] for item in mechanism_client.calls[0]["tools"]]
    assert prompt_tools[:-1] == mechanism_tools[:-1]
    assert prompt_tools[-1] == "finish_parent_decision"
    assert mechanism_tools[-1] == "finish_scoped_decision"
    assert (branches / "r7_local_recovery" / "scope_prompt_control" / "working.md").read_text() == "prompt"
    assert (branches / "r7_local_recovery" / "scope_decision_interface" / "working.md").read_text() == "S0"
    assert (seed / "working.md").read_text() == "S0"


def test_prompt_control_is_not_subject_to_structured_reference_validation(tmp_path):
    module = _load()
    direct = sys.modules["direct_evidence_diagnostic"]
    checkpoint = _checkpoint(tmp_path)
    index = direct.FrozenEvidenceIndex(checkpoint)
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "working.md").write_text("S0", encoding="utf-8")
    client = Client([_call("finish_parent_decision", {
        "outcome": "supported_in_scope", "conclusion": "natural unvalidated explanation"}, "p1")])
    result = module.run_scoped_decision_condition(
        case="r7_local_recovery", condition="scope_prompt_control", parent_client=client,
        seed_workspace=MonitorWorkspace(checkpoint["root"] / "task", seed),
        branch_private_root=tmp_path / "branches", index=index,
        initial_paths=("task/original_task.txt",), parent_history=_history(),
        parent_system="Supervisor", total_calls=6,
    )
    assert result["status"] == "completed"
    assert result["calls"] == 1
