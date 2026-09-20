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


def test_supplement_is_current_neutral_input_not_r8_guidance():
    module = _load("scope_prompt_replication_supplement", "method_discovery/scope_prompt_replication.py")
    spec = module.condition_spec(
        case="r7_root_completion", condition="ordinary_investigation",
        parent_system="Original", initial_paths=("task/original_task.txt",),
        descriptor={"scope": "task/workspace/", "indexed_files": 3}, total_calls=6,
        supplemental_observation={"observations": [{
            "path": "task/original_task.txt", "file_sha256": "abc", "start": 1,
            "lines": 1, "total_lines": 1, "content": "1: raw",
        }]})
    assert module.SUPPLEMENTAL_NEUTRAL_INSTRUCTION in spec["prompt"]
    assert '"content": "1: raw"' in spec["prompt"]
    assert module.R8_SCOPE_GUIDANCE not in spec["prompt"]
    assert module.R8_SCOPE_GUIDANCE not in spec["system"]
    assert all(tool["function"]["name"] != "finish_scoped_decision" for tool in spec["tools"])


def test_visible_counterexample_config_has_six_fixed_runs():
    config = json.loads((ROOT / "method_discovery/runs/dual_opus_20260919/"
                         "r10_neutral_calibration_config.json").read_text(encoding="utf-8"))
    pairs = [(item["material"], item["repeat"]) for item in config["run_order"]]
    assert len(pairs) == len(set(pairs)) == 6
    assert config["protocol"]["scope_prompt"] is False
    assert config["protocol"]["scoped_interface"] is False
    assert config["protocol"]["independent_c"] is False


def _visibility_checkpoint(tmp_path):
    root = tmp_path / "visibility-checkpoint"
    (root / "task/workspace/theme").mkdir(parents=True)
    task_lines = [f"requirement line {index}" for index in range(1, 90)]
    task_lines[51:60] = [
        "JSON theme requirement", "FromJSON(data string)", "FromJSONReader(io.Reader)",
        "required schema", "required variants", "required colors", "required fonts",
        "required icons", "required errors",
    ]
    (root / "task/original_task.txt").write_text("\n".join(task_lines) + "\n", encoding="utf-8")
    code_lines = [f"// code line {index}" for index in range(1, 100)]
    code_lines[68:82] = [
        "func FromJSON(data []byte, base Theme) (Theme, error) {",
        "  return nil, nil", "}", "func FromJSONReader(r io.Reader, base Theme) (Theme, error) {",
        "  return nil, nil", "}", "// context", "// context", "// context", "// context",
        "// context", "// context", "// context", "// context",
    ]
    (root / "task/workspace/theme/json.go").write_text(
        "\n".join(code_lines) + "\n", encoding="utf-8")
    files = {}
    for path in root.rglob("*"):
        if path.is_file():
            files[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"root": root, "manifest": {"files": files}}


def test_production_supplement_projection_hides_research_metadata_in_actual_request(tmp_path):
    runner = _load("scope_prompt_replication_runner_projection",
                   "method_discovery/run_scope_prompt_replication.py")
    module = sys.modules["scope_prompt_replication"]
    direct = sys.modules["direct_evidence_diagnostic"]
    checkpoint = _visibility_checkpoint(tmp_path)
    supplement = runner._supplement(checkpoint, "r7_json_counterexample_visible")
    assert "material_condition" in supplement["research_record"]
    assert "material_condition" not in supplement["model_visible"]

    evidence = tmp_path / "evidence"
    (evidence / "workspace/theme").mkdir(parents=True)
    (evidence / "original_task.txt").write_text("requirements", encoding="utf-8")
    (evidence / "workspace/theme/json.go").write_text("implementation", encoding="utf-8")
    index_checkpoint = _checkpoint(tmp_path / "index")
    index = direct.FrozenEvidenceIndex(index_checkpoint)
    seed = tmp_path / "seed-projection"
    seed.mkdir()
    (seed / "working.md").write_text("S0", encoding="utf-8")
    client = Client([_finish()])
    module.run_scope_prompt_condition(
        case="r7_root_completion", condition="ordinary_investigation", run_key="projection",
        parent_client=client,
        seed_workspace=MonitorWorkspace(index_checkpoint["root"] / "task", seed),
        branch_private_root=tmp_path / "branches-projection", index=index,
        initial_paths=("task/original_task.txt",), parent_history=[],
        parent_system="Original supervisor system", total_calls=6,
        supplemental_observation=supplement["model_visible"])
    sent = json.dumps(client.calls[0], ensure_ascii=False, sort_keys=True)
    assert "FromJSON(data string)" in sent
    assert "r7_json_counterexample_visible" not in sent
    assert "material_condition" not in sent
    assert "expected_label" not in sent
    assert "run_id" not in sent


def test_research_labels_do_not_change_model_visible_request(tmp_path):
    runner = _load("scope_prompt_replication_runner_label_invariance",
                   "method_discovery/run_scope_prompt_replication.py")
    module = sys.modules["scope_prompt_replication"]
    checkpoint = _visibility_checkpoint(tmp_path)
    supplement = runner._supplement(checkpoint, "r7_json_counterexample_visible")
    common = dict(
        case="r7_root_completion", condition="ordinary_investigation",
        parent_system="Original", initial_paths=("task/original_task.txt",),
        descriptor={"scope": "task/workspace/", "indexed_files": 3}, total_calls=6,
        supplemental_observation=supplement["model_visible"])
    first = module.condition_spec(**common)
    supplement["research_record"].update({
        "material_condition": "renamed", "expected_label": "different", "run_id": "other"})
    second = module.condition_spec(**common)
    assert first == second


def test_changing_raw_observation_changes_visible_request_and_keeps_provenance():
    module = _load("scope_prompt_replication_observation_change",
                   "method_discovery/scope_prompt_replication.py")
    base = {
        "path": "task/workspace/theme/json.go", "file_sha256": "sha-v1",
        "start": 70, "lines": 2, "total_lines": 100,
        "content": "70: first\n71: observation",
    }
    common = dict(
        case="r7_root_completion", condition="ordinary_investigation",
        parent_system="Original", initial_paths=("task/original_task.txt",),
        descriptor={"scope": "task/workspace/", "indexed_files": 3}, total_calls=6)
    first = module.condition_spec(
        **common, supplemental_observation={"observations": [base]})
    changed = dict(base, file_sha256="sha-v2", content="70: changed\n71: observation")
    second = module.condition_spec(
        **common, supplemental_observation={"observations": [changed]})
    assert first["system"] == second["system"]
    assert first["tools"] == second["tools"]
    assert first["prompt"] != second["prompt"]
    assert "sha-v1" in first["prompt"] and "sha-v2" in second["prompt"]
