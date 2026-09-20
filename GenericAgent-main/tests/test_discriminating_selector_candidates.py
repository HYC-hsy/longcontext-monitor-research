import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from monitor_agent_core.provider import ModelResponse, MonitorProviderClient, ToolCall
from monitor_agent_core.workspace import MonitorWorkspace


ROOT = Path(__file__).parents[2]


def load_module():
    path = ROOT / "method_discovery/discriminating_selector_candidates.py"
    spec = importlib.util.spec_from_file_location("discriminating_selector_candidates", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_runner():
    path = ROOT / "method_discovery/run_discriminating_selector_screen.py"
    spec = importlib.util.spec_from_file_location("run_discriminating_selector_screen", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def tool_call(name, arguments, cid="call"):
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


class ProductionCapture(MonitorProviderClient):
    """Use production complete()/request assembly while replacing network transport."""

    def __init__(self, responses):
        super().__init__("capture", {
            "apikey": "not-used", "apibase": "https://invalid.example",
            "model": "claude-opus-4-8", "provider": "anthropic",
            "api_mode": "messages", "max_tokens": 1024, "context_win": 200000,
        })
        self.responses = iter(responses)
        self.snapshots = []

    def _request(self, tools):
        self.snapshots.append(self.assembled_request_snapshot(tools))
        return next(self.responses), {"input_tokens": 1, "output_tokens": 1}


def fixture(tmp_path):
    root = tmp_path / "checkpoint"
    (root / "task/workspace").mkdir(parents=True)
    (root / "task/original_task.txt").write_text("Expose API.\n", encoding="utf-8")
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


def selection_payload(*, premise=None, tool="file_read", arguments=None):
    value = {
        "requirement_or_claim_being_tested": "The API has the required signature.",
        "outcome_if_supported": "The declaration exactly matches the required signature.",
        "outcome_if_violated": "The declaration is absent or has a different signature.",
        "action": {"tool": tool, "arguments": arguments or {
            "path": "task/workspace/api.go", "start": 1, "count": 20}},
    }
    if premise is not None:
        value["premise"] = premise
    return value


def finish():
    return tool_call("finish_parent_decision", {
        "outcome": "supported_in_scope", "conclusion": "The API matches."
    }, "finish")


def run(module, tmp_path, *, mode, condition, payload, identity):
    direct = sys.modules["direct_evidence_diagnostic"]
    checkpoint, workspace = fixture(tmp_path)
    index = direct.FrozenEvidenceIndex(checkpoint)
    selector = Client([tool_call(module.SELECT_ACTION_TOOL, payload, "selector")])
    parent = Client([finish()])
    result = module.run_candidate(
        mode=mode, research_condition=condition,
        selector_client=selector, parent_client=parent, branch_identity=identity,
        seed_workspace=workspace, branch_private_root=tmp_path / "branches", index=index,
        initial_paths=("task/original_task.txt",),
        parent_history=[{"role": "user", "content": "same parent History"}],
        parent_system="Original supervisor system", original_task="Expose API.",
        decision_scope="root_completion", acceptance_question="Can the task complete?",
    )
    return result, selector, parent


def test_g_and_e_execute_one_structured_action_with_identical_tools(tmp_path):
    module = load_module()
    direct = sys.modules["direct_evidence_diagnostic"]
    checkpoint, _ = fixture(tmp_path / "spec")
    index = direct.FrozenEvidenceIndex(checkpoint)
    specs = {mode: module.selector_spec(
        mode=mode, parent_system="Original", original_task="Expose API.",
        decision_scope="root_completion", index=index, remaining_calls=6)
        for mode in module.MODES}
    assert specs[module.MODES[0]]["tools"] == specs[module.MODES[1]]["tools"]
    assert specs[module.MODES[0]]["prompt"] == specs[module.MODES[1]]["prompt"]

    g, g_selector, _ = run(
        module, tmp_path / "g", mode="counterfactual_observation", condition="G",
        payload=selection_payload(), identity="case-r1-G")
    e, e_selector, _ = run(
        module, tmp_path / "e", mode="decision_frontier", condition="E",
        payload=selection_payload(premise="This exact API determines root completion."),
        identity="case-r1-E")
    assert g["selection_observation"]["model_visible"]["status"] == "executed"
    assert e["selection_observation"]["model_visible"]["status"] == "executed"
    assert "premise" not in g["selection_observation"]["model_visible"]["selection_semantics"]
    assert e["selection_observation"]["model_visible"]["selection_semantics"]["premise"]
    assert g_selector.calls[0]["history"] == e_selector.calls[0]["history"]
    assert g["calls"] == e["calls"] == 2


def test_missing_field_and_multiple_calls_consume_selector_once_without_retry(tmp_path):
    module = load_module()
    direct = sys.modules["direct_evidence_diagnostic"]
    checkpoint, workspace = fixture(tmp_path)
    index = direct.FrozenEvidenceIndex(checkpoint)
    cases = [
        [tool_call(module.SELECT_ACTION_TOOL, {
            "requirement_or_claim_being_tested": "API", "outcome_if_supported": "yes",
            "action": {"tool": "file_read", "arguments": {"path": "task/workspace/api.go"}},
        }, "missing")],
        [ModelResponse("", [
            ToolCall("one", module.SELECT_ACTION_TOOL, json.dumps(selection_payload())),
            ToolCall("two", module.SELECT_ACTION_TOOL, json.dumps(selection_payload())),
        ], {})],
    ]
    for number, responses in enumerate(cases):
        selector = Client(responses)
        parent = Client([finish()])
        result = module.run_candidate(
            mode="counterfactual_observation", research_condition=f"condition-{number}",
            selector_client=selector, parent_client=parent,
            branch_identity=f"case-r{number}-condition", seed_workspace=workspace,
            branch_private_root=tmp_path / "branches", index=index,
            initial_paths=("task/original_task.txt",), parent_history=[],
            parent_system="Original", original_task="Expose API.",
            decision_scope="root_completion", acceptance_question="Complete?",
        )
        assert result["selection_observation"]["model_visible"]["status"] == "selector_protocol_failure"
        assert result["calls"] == 2
        assert len(selector.calls) == len(parent.calls) == 1


def test_illegal_nested_tool_or_arguments_are_not_executed(tmp_path):
    module = load_module()
    direct = sys.modules["direct_evidence_diagnostic"]
    checkpoint, workspace = fixture(tmp_path)
    real = direct.FrozenEvidenceIndex(checkpoint)

    class SpyIndex:
        def __init__(self):
            self.dispatch_calls = 0

        def descriptor(self):
            return real.descriptor()

        def dispatch(self, workspace, name, arguments):
            self.dispatch_calls += 1
            return real.dispatch(workspace, name, arguments)

    for number, payload in enumerate((
            selection_payload(tool="code_run", arguments={"code": "exit 0"}),
            selection_payload(tool="file_read", arguments={
                "path": "task/workspace/api.go", "count": 0}),
    )):
        index = SpyIndex()
        observation = module.execute_selection(
            response=tool_call(module.SELECT_ACTION_TOOL, payload),
            mode="counterfactual_observation", research_condition=f"condition-{number}",
            workspace=workspace, public_allowed={"task/original_task.txt"}, index=index)
        assert observation["model_visible"]["status"] == "selector_protocol_failure"
        assert index.dispatch_calls == 0


def test_premise_contract_is_the_only_mode_specific_payload_rule(tmp_path):
    module = load_module()
    direct = sys.modules["direct_evidence_diagnostic"]
    checkpoint, workspace = fixture(tmp_path)
    index = direct.FrozenEvidenceIndex(checkpoint)
    missing = module.execute_selection(
        response=tool_call(module.SELECT_ACTION_TOOL, selection_payload()),
        mode="decision_frontier", research_condition="E", workspace=workspace,
        public_allowed={"task/original_task.txt"}, index=index)
    extra = module.execute_selection(
        response=tool_call(module.SELECT_ACTION_TOOL,
                           selection_payload(premise="Unexpected premise")),
        mode="counterfactual_observation", research_condition="G", workspace=workspace,
        public_allowed={"task/original_task.txt"}, index=index)
    assert missing["model_visible"]["status"] == "selector_protocol_failure"
    assert extra["model_visible"]["status"] == "selector_protocol_failure"


def test_full_branch_identity_prevents_repeat_and_condition_collisions(tmp_path):
    module = load_module()
    runner = load_runner()
    assert runner.branch_identity("r7-root", 2, "decision_frontier") == (
        "r7-root-r2-decision_frontier")
    assert len({runner.branch_identity("r7-root", repeat, mode)
                for repeat in (1, 2) for mode in module.MODES}) == 4
    identities = ("r7-root-r1-G", "r7-root-r2-G", "r7-root-r1-E")
    for number, identity in enumerate(identities):
        mode = "decision_frontier" if identity.endswith("E") else "counterfactual_observation"
        payload = selection_payload(
            premise="Root-relevant premise" if mode == "decision_frontier" else None)
        run(module, tmp_path / f"run-{number}", mode=mode, condition=identity[-1],
            payload=payload, identity=identity)
    # The production clone also rejects accidental reuse rather than contaminating a sibling.
    direct = sys.modules["direct_evidence_diagnostic"]
    checkpoint, workspace = fixture(tmp_path / "collision")
    index = direct.FrozenEvidenceIndex(checkpoint)
    kwargs = dict(
        mode="counterfactual_observation", research_condition="G",
        branch_identity="same-case-r1-G", seed_workspace=workspace,
        branch_private_root=tmp_path / "collision-branches", index=index,
        initial_paths=("task/original_task.txt",), parent_history=[],
        parent_system="Original", original_task="Expose API.",
        decision_scope="root_completion", acceptance_question="Complete?",
    )
    module.run_candidate(selector_client=Client([
        tool_call(module.SELECT_ACTION_TOOL, selection_payload())]),
        parent_client=Client([finish()]), **kwargs)
    try:
        module.run_candidate(selector_client=Client([
            tool_call(module.SELECT_ACTION_TOOL, selection_payload())]),
            parent_client=Client([finish()]), **kwargs)
    except FileExistsError:
        pass
    else:
        raise AssertionError("reusing a full branch identity must fail")


def test_research_condition_name_does_not_change_parent_request(tmp_path):
    module = load_module()
    requests = []
    for number, condition in enumerate(("opaque-one", "opaque-two")):
        result, _, parent = run(
            module, tmp_path / str(number), mode="counterfactual_observation",
            condition=condition, payload=selection_payload(), identity=f"case-r1-{number}")
        assert result["selection_observation"]["research_record"]["condition"] == condition
        requests.append(parent.calls[0])
    assert requests[0] == requests[1]
    visible = json.dumps(requests[0], ensure_ascii=False)
    assert "opaque-one" not in visible and "opaque-two" not in visible


def test_condition_name_only_keeps_production_parent_send_request_identical(tmp_path):
    module = load_module()
    snapshots = []
    selector_block = [{
        "type": "tool_use", "id": "selector", "name": module.SELECT_ACTION_TOOL,
        "input": selection_payload(),
    }]
    finish_block = [{
        "type": "tool_use", "id": "finish", "name": "finish_parent_decision",
        "input": {"outcome": "supported_in_scope", "conclusion": "The API matches."},
    }]
    for number, condition in enumerate(("research-name-one", "research-name-two")):
        direct = sys.modules["direct_evidence_diagnostic"]
        checkpoint, workspace = fixture(tmp_path / str(number))
        index = direct.FrozenEvidenceIndex(checkpoint)
        selector = ProductionCapture([selector_block])
        parent = ProductionCapture([finish_block])
        module.run_candidate(
            mode="counterfactual_observation", research_condition=condition,
            selector_client=selector, parent_client=parent,
            branch_identity=f"same-case-r1-{number}", seed_workspace=workspace,
            branch_private_root=tmp_path / f"branches-{number}", index=index,
            initial_paths=("task/original_task.txt",),
            parent_history=[{"role": "user", "content": "same parent History"}],
            parent_system="Original supervisor system", original_task="Expose API.",
            decision_scope="root_completion", acceptance_question="Can the task complete?",
        )
        snapshots.append(parent.snapshots[0])
    assert snapshots[0] == snapshots[1]
    visible = json.dumps(snapshots[0], ensure_ascii=False)
    assert "research-name-one" not in visible and "research-name-two" not in visible
