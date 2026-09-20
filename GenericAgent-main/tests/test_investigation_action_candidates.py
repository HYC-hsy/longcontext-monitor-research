import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from monitor_agent_core.provider import ModelResponse, ToolCall
from monitor_agent_core.workspace import MonitorWorkspace


ROOT = Path(__file__).parents[2]


def load_module():
    path = ROOT / "method_discovery/investigation_action_candidates.py"
    spec = importlib.util.spec_from_file_location("investigation_action_candidates", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def call(name, arguments, cid):
    return ModelResponse("", [ToolCall(cid, name, json.dumps(arguments))], {})


class Client:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.history = []
        self.calls = []

    def restore_history(self, history):
        self.history = json.loads(json.dumps(history))

    def complete(self, messages, tools):
        self.calls.append({
            "history": json.loads(json.dumps(self.history)),
            "messages": json.loads(json.dumps(messages)),
            "tools": json.loads(json.dumps(tools)),
        })
        self.history.extend(messages)
        return next(self.responses)

    def record_tool_results(self, results):
        self.history.append({"role": "user", "content": results})

    def history_measure(self):
        return {"items": len(self.history), "characters": 0, "sha256": "fixture"}


def fixture(tmp_path):
    root = tmp_path / "checkpoint"
    (root / "task/workspace").mkdir(parents=True)
    (root / "task/original_task.txt").write_text(
        "The implementation must expose a stable API.\n", encoding="utf-8")
    (root / "task/workspace/api.go").write_text(
        "package sample\nfunc API() {}\n", encoding="utf-8")
    files = {}
    for path in root.rglob("*"):
        if path.is_file():
            files[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    checkpoint = {"root": root, "complete": {"manifest_sha256": "version"},
                  "manifest": {"files": files}}
    private = tmp_path / "private"
    private.mkdir()
    (private / "working.md").write_text("parent state", encoding="utf-8")
    return checkpoint, MonitorWorkspace(root / "task", private)


def finish():
    return call("finish_parent_decision", {
        "outcome": "supported_in_scope", "conclusion": "The inspected API matches the requirement."
    }, "finish")


def test_a_and_b_execute_one_existing_action_then_restore_same_parent_state(tmp_path):
    module = load_module()
    direct = sys.modules["direct_evidence_diagnostic"]
    checkpoint, workspace = fixture(tmp_path)
    index = direct.FrozenEvidenceIndex(checkpoint)
    history = [{"role": "user", "content": "historical task-agent completion claim"}]
    results = {}
    selectors = {}
    parents = {}
    for candidate in module.CANDIDATES:
        selectors[candidate] = Client([
            call("file_read", {"path": "task/workspace/api.go", "start": 1, "count": 20}, "s")
        ])
        parents[candidate] = Client([finish()])
        results[candidate] = module.run_investigation_candidate(
            candidate=candidate, selector_client=selectors[candidate],
            parent_client=parents[candidate], seed_workspace=workspace,
            run_key="same-r1",
            branch_private_root=tmp_path / "branches", index=index,
            initial_paths=("task/original_task.txt",), parent_history=history,
            parent_system="Original supervisor system",
            original_task="The implementation must expose a stable API.",
            decision_scope="root completion", acceptance_question="Can the task complete?",
        )
    assert results["full_parent_action"]["calls"] == 2
    assert results["requirement_side_action"]["calls"] == 2
    assert results["full_parent_action"]["selection_observation"]["model_visible"]["status"] == "executed"
    assert results["requirement_side_action"]["selection_observation"]["model_visible"]["status"] == "executed"
    assert selectors["full_parent_action"].calls[0]["history"] == history
    assert selectors["requirement_side_action"].calls[0]["history"] == []
    assert parents["full_parent_action"].calls[0]["history"] == history
    assert parents["requirement_side_action"].calls[0]["history"] == history
    parent_visible = json.dumps(
        parents["full_parent_action"].calls[0]["messages"], ensure_ascii=False)
    assert "current observation" in parent_visible
    assert "full_parent_action" not in parent_visible
    assert "caller" not in parent_visible


def test_selector_rejects_multiple_actions_without_free_retry_and_parent_continues(tmp_path):
    module = load_module()
    direct = sys.modules["direct_evidence_diagnostic"]
    checkpoint, workspace = fixture(tmp_path)
    index = direct.FrozenEvidenceIndex(checkpoint)
    selector = Client([ModelResponse("", [
        ToolCall("a", "file_list", json.dumps({"path": "task/workspace"})),
        ToolCall("b", "text_search", json.dumps({"query": "API"})),
    ], {})])
    parent = Client([finish()])
    result = module.run_investigation_candidate(
        candidate="full_parent_action", selector_client=selector, parent_client=parent,
        run_key="multiple-r1",
        seed_workspace=workspace, branch_private_root=tmp_path / "branches", index=index,
        initial_paths=("task/original_task.txt",), parent_history=[],
        parent_system="Original", original_task="Requirement", decision_scope="root completion",
        acceptance_question="Can the task complete?",
    )
    assert result["selection_observation"]["model_visible"]["status"] == "selection_error"
    assert result["calls"] == 2
    assert len(selector.calls) == 1
    assert len(parent.calls) == 1


def test_candidate_specs_contain_no_research_labels(tmp_path):
    module = load_module()
    direct = sys.modules["direct_evidence_diagnostic"]
    checkpoint, _ = fixture(tmp_path)
    index = direct.FrozenEvidenceIndex(checkpoint)
    for candidate in module.CANDIDATES:
        spec = module.selector_spec(
            candidate=candidate, parent_system="Original", original_task="Requirement",
            decision_scope="root completion", index=index, remaining_calls=6)
        visible = json.dumps(spec, ensure_ascii=False)
        assert "JSON" not in visible
        assert "Sprintf" not in visible
        assert "expected_label" not in visible
        assert "run_id" not in visible


def test_candidate_name_only_does_not_change_actual_parent_request(tmp_path):
    module = load_module()
    direct = sys.modules["direct_evidence_diagnostic"]
    checkpoint, workspace = fixture(tmp_path)
    index = direct.FrozenEvidenceIndex(checkpoint)
    history = [{"role": "user", "content": "same complete parent state"}]
    parent_requests = {}
    for candidate in module.CANDIDATES:
        selector = Client([
            call("file_read", {"path": "task/workspace/api.go", "start": 1, "count": 20}, "s")
        ])
        parent = Client([finish()])
        module.run_investigation_candidate(
            candidate=candidate, selector_client=selector, parent_client=parent,
            run_key="invariance-r1",
            seed_workspace=workspace, branch_private_root=tmp_path / "isolated", index=index,
            initial_paths=("task/original_task.txt",), parent_history=history,
            parent_system="Original supervisor system", original_task="Requirement",
            decision_scope="root completion", acceptance_question="Can the task complete?",
        )
        parent_requests[candidate] = parent.calls[0]
    assert parent_requests["full_parent_action"] == parent_requests["requirement_side_action"]


def test_screen_manifest_freezes_nine_records_and_six_call_budget():
    config = json.loads((ROOT / "method_discovery/runs/dual_opus_20260919/"
                         "r11_investigation_action_screen_config.json").read_text(
                             encoding="utf-8"))
    triples = [(item["case"], item["condition"], item["repeat"])
               for item in config["run_order"]]
    assert len(triples) == len(set(triples)) == 9
    assert config["conditions"] == [
        "ordinary", "full_parent_action", "requirement_side_action"]
    assert config["protocol"]["total_calls_per_record"] == 6
    assert config["protocol"]["ordinary_calls"] == 6
    assert config["protocol"]["selector_calls"] == 1
    assert config["protocol"]["selected_parent_calls"] == 5
    assert config["protocol"]["independent_c"] is False
