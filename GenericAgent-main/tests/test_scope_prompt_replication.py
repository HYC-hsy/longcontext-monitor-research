import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from monitor_agent_core.provider import ModelResponse, ToolCall
from monitor_agent_core.workspace import MonitorWorkspace


ROOT = Path(__file__).parents[2]


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
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


def _finish(conclusion="done"):
    return _call("finish_parent_decision", {
        "outcome": "supported_in_scope", "conclusion": conclusion}, "finish")


def test_candidate_is_exact_r8_prompt_condition(tmp_path):
    scoped = _load("scoped_decision_diagnostic", "method_discovery/scoped_decision_diagnostic.py")
    module = _load("scope_prompt_replication", "method_discovery/scope_prompt_replication.py")
    direct = sys.modules["direct_evidence_diagnostic"]
    checkpoint = _checkpoint(tmp_path)
    index = direct.FrozenEvidenceIndex(checkpoint)
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "working.md").write_text("S0", encoding="utf-8")
    common = dict(
        case="r7_local_recovery", seed_workspace=MonitorWorkspace(checkpoint["root"] / "task", seed),
        index=index, initial_paths=("task/original_task.txt",), parent_history=[],
        parent_system="Original supervisor system", total_calls=6,
    )
    r8_client = Client([_finish("r8")])
    new_client = Client([_finish("new")])
    scoped.run_scoped_decision_condition(
        condition="scope_prompt_control", parent_client=r8_client,
        branch_private_root=tmp_path / "r8", **common)
    module.run_scope_prompt_condition(
        condition="scope_prompt_candidate", run_key="r1", parent_client=new_client,
        branch_private_root=tmp_path / "new", **common)
    assert r8_client.calls[0]["messages"] == new_client.calls[0]["messages"]
    assert r8_client.calls[0]["tools"] == new_client.calls[0]["tools"]


def test_only_guidance_differs_and_tools_are_identical():
    module = _load("scope_prompt_replication_specs", "method_discovery/scope_prompt_replication.py")
    common = dict(case="r7_root_completion", parent_system="Original",
                  initial_paths=("task/original_task.txt",),
                  descriptor={"scope": "task/workspace/", "indexed_files": 3}, total_calls=6)
    ordinary = module.condition_spec(condition="ordinary_investigation", **common)
    candidate = module.condition_spec(condition="scope_prompt_candidate", **common)
    assert ordinary["tools"] == candidate["tools"]
    assert module.R8_SCOPE_GUIDANCE not in ordinary["system"]
    assert module.R8_SCOPE_GUIDANCE not in ordinary["prompt"]
    assert candidate["system"] == ordinary["system"] + " " + module.R8_SCOPE_GUIDANCE
    assert module.R8_SCOPE_GUIDANCE in candidate["prompt"]
    assert module.R8_NATURAL_ORGANIZATION in candidate["prompt"]


def test_repeats_start_from_isolated_private_state(tmp_path):
    module = _load("scope_prompt_replication_isolation", "method_discovery/scope_prompt_replication.py")
    direct = sys.modules["direct_evidence_diagnostic"]
    checkpoint = _checkpoint(tmp_path)
    index = direct.FrozenEvidenceIndex(checkpoint)
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "working.md").write_text("S0", encoding="utf-8")
    workspace = MonitorWorkspace(checkpoint["root"] / "task", seed)
    first = Client([
        _call("file_write", {"path": "monitor/working.md", "content": "R1", "mode": "replace"}, "w"),
        _finish(),
    ])
    second = Client([_finish()])
    common = dict(case="r7_local_recovery", condition="ordinary_investigation",
                  seed_workspace=workspace, branch_private_root=tmp_path / "branches",
                  index=index, initial_paths=("task/original_task.txt",), parent_history=[],
                  parent_system="Original", total_calls=6)
    module.run_scope_prompt_condition(run_key="repeat-1", parent_client=first, **common)
    module.run_scope_prompt_condition(run_key="repeat-2", parent_client=second, **common)
    assert (tmp_path / "branches" / "repeat-1" / "ordinary_investigation" / "working.md").read_text() == "R1"
    assert (tmp_path / "branches" / "repeat-2" / "ordinary_investigation" / "working.md").read_text() == "S0"
    assert (seed / "working.md").read_text() == "S0"


def test_frozen_order_contains_twelve_unique_records():
    config = json.loads((ROOT / "method_discovery/runs/dual_opus_20260919/"
                         "r9_scope_prompt_replication_config.json").read_text(encoding="utf-8"))
    triples = [(item["case"], item["condition"], item["repeat"])
               for item in config["run_order"]]
    assert len(triples) == len(set(triples)) == 12
    assert {item[2] for item in triples} == {1, 2}
