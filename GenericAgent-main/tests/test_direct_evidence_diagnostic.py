import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from monitor_agent_core.provider import ModelResponse, ToolCall
from monitor_agent_core.workspace import MonitorWorkspace


def _load():
    path = Path(__file__).parents[2] / "method_discovery" / "direct_evidence_diagnostic.py"
    spec = importlib.util.spec_from_file_location("direct_evidence_diagnostic", path)
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
    (workspace / "pkg").mkdir(parents=True)
    (workspace / "evaluation").mkdir()
    (workspace / "pkg" / "found.go").write_text(
        "package pkg\nfunc ExistingSymbol() {}\n", encoding="utf-8")
    (workspace / "pkg" / "other.go").write_text("package pkg\n", encoding="utf-8")
    (workspace / "evaluation" / "answer.txt").write_text("hidden", encoding="utf-8")
    files = {}
    for path in (workspace / "pkg" / "found.go", workspace / "pkg" / "other.go",
                 workspace / "evaluation" / "answer.txt"):
        files[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "root": root,
        "complete": {"manifest_sha256": "checkpoint-version"},
        "manifest": {"files": files},
    }


def test_frozen_index_lists_searches_reads_and_preserves_scope(tmp_path):
    module = _load()
    checkpoint = _checkpoint(tmp_path)
    index = module.FrozenEvidenceIndex(checkpoint)
    private = tmp_path / "private"
    workspace = MonitorWorkspace(checkpoint["root"] / "task", private)

    listed = index.dispatch(workspace, "file_list", {
        "path": "task/workspace/pkg", "recursive": True}).data
    assert listed["status"] == "success"
    assert {item["path"] for item in listed["entries"]} == {
        "task/workspace/pkg/found.go", "task/workspace/pkg/other.go"}

    found = index.dispatch(workspace, "text_search", {
        "query": "ExistingSymbol", "path": "task/workspace", "file_pattern": "*.go"}).data
    assert found["status"] == "success"
    assert found["matches"][0]["path"] == "task/workspace/pkg/found.go"
    assert found["matches"][0]["file_version"]

    missing = index.dispatch(workspace, "text_search", {
        "query": "AbsentSymbol", "path": "task/workspace/pkg", "file_pattern": "*.go"}).data
    assert missing["status"] == "success"
    assert missing["matches"] == []
    assert missing["scope"] == "task/workspace/pkg/**"
    assert "outside" in missing["absence_boundary"]

    exact_missing = index.dispatch(workspace, "file_read", {
        "path": "task/workspace/pkg/missing.go"}).data
    assert exact_missing["status"] == "not_found"
    denied = index.dispatch(workspace, "file_read", {
        "path": "task/workspace/evaluation/answer.txt"}).data
    assert denied["status"] == "denied"
    assert "hidden" not in json.dumps(denied)
    denied_list = index.dispatch(workspace, "file_list", {
        "path": "task/workspace/evaluation"}).data
    denied_search = index.dispatch(workspace, "text_search", {
        "query": "hidden", "path": "task/workspace/evaluation"}).data
    assert denied_list["status"] == denied_search["status"] == "denied"

    live = tmp_path / "live" / "pkg"
    live.mkdir(parents=True)
    (live / "found.go").write_text("changed live file", encoding="utf-8")
    reread = index.dispatch(workspace, "file_read", {
        "path": "task/workspace/pkg/found.go"}).data
    assert "ExistingSymbol" in reread["content"]
    assert "changed live file" not in reread["content"]


def test_frozen_index_distinguishes_integrity_failure_from_no_match(tmp_path):
    module = _load()
    checkpoint = _checkpoint(tmp_path)
    index = module.FrozenEvidenceIndex(checkpoint)
    workspace = MonitorWorkspace(checkpoint["root"] / "task", tmp_path / "private")
    (checkpoint["root"] / "task" / "workspace" / "pkg" / "found.go").write_text(
        "mutated", encoding="utf-8")
    result = index.dispatch(workspace, "text_search", {
        "query": "ExistingSymbol", "path": "task/workspace/pkg"}).data
    assert result["status"] == "error"
    assert "changed" in result["error"]


def test_direct_conditions_clone_state_and_charge_query_and_notes(tmp_path):
    module = _load()
    checkpoint = _checkpoint(tmp_path)
    index = module.FrozenEvidenceIndex(checkpoint)
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "working.md").write_text("S0", encoding="utf-8")
    workspace = MonitorWorkspace(checkpoint["root"] / "task", seed)
    branches = tmp_path / "branches"
    branches.mkdir()

    specified = Client([
        _call("file_write", {"path": "monitor/working.md", "content": "A",
                             "mode": "replace"}, "a1"),
        _call("finish_parent_decision", {"outcome": "unresolved",
              "conclusion": "specified done"}, "a2"),
    ])
    a = module.run_direct_condition(
        condition="specified_files", parent_client=specified,
        seed_workspace=workspace, branch_private_root=branches, index=index,
        acceptance_question="Decide.",
        initial_paths=("task/workspace/pkg/found.go",), parent_history=[],
        parent_system="Supervisor", total_calls=6,
    )
    assert a["calls"] == 2

    query = Client([
        _call("file_list", {"path": "task/workspace/pkg"}, "q1"),
        _call("text_search", {"query": "ExistingSymbol", "path": "task/workspace/pkg"}, "q2"),
        _call("file_write", {"path": "monitor/query.md", "content": "observed"}, "q3"),
        _call("finish_parent_decision", {"outcome": "supported_in_scope",
              "conclusion": "query done"}, "q4"),
    ])
    b = module.run_direct_condition(
        condition="frozen_query", parent_client=query,
        seed_workspace=workspace, branch_private_root=branches, index=index,
        acceptance_question="Decide.",
        initial_paths=("task/workspace/pkg/found.go",), parent_history=[],
        parent_system="Supervisor", total_calls=6,
    )
    assert b["calls"] == 4
    assert query.calls == 4
    assert (branches / "specified_files" / "working.md").read_text() == "A"
    assert (branches / "frozen_query" / "working.md").read_text() == "S0"
    assert (branches / "frozen_query" / "query.md").read_text() == "observed"
    assert (seed / "working.md").read_text() == "S0"
    assert any("direct-frozen-evidence-query-v1" in json.dumps(message)
               for message in query.history)
