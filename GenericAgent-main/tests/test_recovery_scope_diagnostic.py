import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from monitor_agent_core.provider import ModelResponse, ToolCall
from monitor_agent_core.workspace import MonitorWorkspace


def _load(name, relative):
    path = Path(__file__).parents[2] / "method_discovery" / relative
    spec = importlib.util.spec_from_file_location(name, path)
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
    (workspace / "data" / "validation").mkdir(parents=True)
    (workspace / "evaluation").mkdir()
    (root / "task" / "original_task.txt").write_text("require NewAllStrings", encoding="utf-8")
    (root / "task" / "research_derived_local_repair.json").write_text(
        '{"scope":"NewAllStrings only"}', encoding="utf-8")
    (workspace / "data" / "validation" / "all.go").write_text(
        "package validation\nfunc NewAllStrings() {}\n", encoding="utf-8")
    (workspace / "evaluation" / "answer.txt").write_text("hidden", encoding="utf-8")
    files = {}
    for path in root.rglob("*"):
        if path.is_file():
            files[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"root": root, "complete": {"manifest_sha256": "derived-version"},
            "manifest": {"files": files}}


def test_scope_conditions_share_state_tools_evidence_and_budget(tmp_path):
    recovery = _load("recovery_scope_diagnostic", "recovery_scope_diagnostic.py")
    direct = sys.modules["direct_evidence_diagnostic"]
    checkpoint = _checkpoint(tmp_path)
    index = direct.FrozenEvidenceIndex(checkpoint)
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "working.md").write_text("S0", encoding="utf-8")
    workspace = MonitorWorkspace(checkpoint["root"] / "task", seed)
    branches = tmp_path / "branches"
    branches.mkdir()
    initial = ("task/original_task.txt", "task/research_derived_local_repair.json",
               "task/workspace/data/validation/all.go")

    local = Client([
        _call("file_write", {"path": "monitor/working.md", "content": "local",
                             "mode": "replace"}, "l1"),
        _call("finish_parent_decision", {"outcome": "supported_in_scope",
              "conclusion": "local repaired"}, "l2"),
    ])
    root = Client([
        _call("text_search", {"query": "NewAllStrings", "path": "task/workspace"}, "r1"),
        _call("finish_parent_decision", {"outcome": "unresolved",
              "conclusion": "root unknown"}, "r2"),
    ])
    common = dict(
        seed_workspace=workspace, branch_private_root=branches, index=index,
        initial_paths=initial, parent_history=[{"role": "user", "content": "history"}],
        parent_system="Supervisor", total_calls=6,
    )
    local_result = recovery.run_recovery_condition(
        condition="local_recovery", parent_client=local, **common)
    root_result = recovery.run_recovery_condition(
        condition="root_completion", parent_client=root, **common)

    assert local_result["calls"] == root_result["calls"] == 2
    assert local.calls[0]["tools"] == root.calls[0]["tools"]
    local_messages, root_messages = local.calls[0]["messages"], root.calls[0]["messages"]
    assert local_messages[0] == root_messages[0]
    assert local_messages[-1] != root_messages[-1]
    assert "NewAllStrings omission been resolved" in local_messages[-1]["content"]
    assert "whole original task" in root_messages[-1]["content"]
    assert (branches / "local_recovery" / "working.md").read_text() == "local"
    assert (branches / "root_completion" / "working.md").read_text() == "S0"
    assert (seed / "working.md").read_text() == "S0"


def test_both_conditions_expose_frozen_query_but_not_evaluation(tmp_path):
    recovery = _load("recovery_scope_diagnostic_access", "recovery_scope_diagnostic.py")
    direct = sys.modules["direct_evidence_diagnostic"]
    checkpoint = _checkpoint(tmp_path)
    index = direct.FrozenEvidenceIndex(checkpoint)
    workspace = MonitorWorkspace(checkpoint["root"] / "task", tmp_path / "private")

    found = index.dispatch(workspace, "text_search", {
        "query": "NewAllStrings", "path": "task/workspace"}).data
    denied = index.dispatch(workspace, "file_read", {
        "path": "task/workspace/evaluation/answer.txt"}).data
    assert found["status"] == "success" and len(found["matches"]) == 1
    assert denied["status"] == "denied"
    assert recovery.CONDITIONS == ("local_recovery", "root_completion")
