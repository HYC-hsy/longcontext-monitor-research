import json
import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[2]
CONFIG = ROOT / "method_discovery" / "artifacts" / "independent_verification_20260918" / "checkpoint_config.json"


def test_checkpoint_panel_is_frozen_and_balanced():
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert data["status"] == "pilot-calibration-hold"
    cases = data["cases"]
    assert len(cases) == 11
    assert {c["scoring"]["expected_label"] for c in cases} == {"correct", "incorrect", "insufficient"}
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids))
    assert {c["event_prefix"]["through_task_turn"] for c in cases} == {60}


def test_probe_groups_have_equal_bounded_budgets_and_hidden_scoring():
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    groups = data["groups"]
    assert groups["B_same_context"]["max_requests"] == groups["C_isolated_direct"]["max_requests"] == groups["D_expectation_first_isolated"]["max_requests"] == 6
    assert groups["C_isolated_direct"]["max_turns"] == groups["D_expectation_first_isolated"]["max_turns"] == 8
    assert "scoring" in data["model_input_rule"].lower()
    for case in data["cases"]:
        assert case["event_prefix"]["inclusive"] is True
        assert case["source_paths"]
        assert case["evidence_paths"]
        assert not any(path.startswith(("verifier/", "solution/")) for path in case["evidence_paths"])


def test_public_only_materialization(tmp_path):
    script = ROOT / "method_discovery" / "materialize_independent_probe.py"
    spec = importlib.util.spec_from_file_location("materialize_probe_fixture", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "fixture"
    manifest = module.build(CONFIG, output)
    assert manifest["public_event_lines"] == 117
    assert len(manifest["replayed_operations"]) == 19
    assert len(manifest["files"]) == 10
    assert (output / "task_evidence" / "original_task.txt").is_file()
    assert (output / "task_evidence" / "build_observation.json").is_file()
    assert (output / "workspace" / "data" / "binding" / "sprintf.go").is_file()
    assert (output / "parent_context" / "provider_history.json").is_file()
    assert not (output / "task_evidence" / "provider_history.json").exists()
    assert not list(output.rglob("*test-stdout*"))
    assert not list(output.rglob("*changes.patch"))


def test_materializer_rejects_hidden_answer_path(tmp_path):
    script = ROOT / "method_discovery" / "materialize_independent_probe.py"
    spec = importlib.util.spec_from_file_location("materialize_probe_fixture", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    data["cases"][0]["evidence_paths"].append("verifier/test-stdout.txt")
    unsafe = tmp_path / "unsafe.json"
    unsafe.write_text(json.dumps(data), encoding="utf-8")
    try:
        module.build(unsafe, tmp_path / "fixture")
    except ValueError as exc:
        assert "posthoc/hidden evidence" in str(exc)
    else:
        assert False, "hidden verifier evidence must be rejected"
