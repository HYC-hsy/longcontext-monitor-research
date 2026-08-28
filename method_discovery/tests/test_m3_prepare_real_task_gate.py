import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "m3_prepare_real_task_gate.py"
SPEC = importlib.util.spec_from_file_location("m3_prepare_real_task_gate", SCRIPT)
gate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(gate)


def test_manifest_is_paired_real_task_and_never_executes_on_prepare():
    manifest = gate.build_manifest("roadmapbench:fbr-2.27.0-roadmap")

    assert manifest["status"] == "prepared_not_executed"
    assert manifest["run_count"] == 2
    assert manifest["online_native_checker"] is False
    assert manifest["native_evaluation"] == "post_termination_only"
    control, treatment = manifest["runs"]
    assert control["task_id"] == treatment["task_id"]
    control_argv = ["<run-id>" if item == control["run_id"] else item
                    for item in control["argv"]]
    treatment_argv = ["<run-id>" if item == treatment["run_id"] else item
                      for item in treatment["argv"]]
    assert control_argv == treatment_argv
    assert control["executes_on_prepare"] is False
    assert treatment["executes_on_prepare"] is False


def test_m3a_differs_from_m2c_only_by_candidate_switch_and_run_identity():
    control, treatment = gate.build_manifest(
        "roadmapbench:fbr-2.27.0-roadmap"
    )["runs"]
    control_env = dict(control["environment"])
    treatment_env = dict(treatment["environment"])
    assert "GA_M3_HUMAN_LOOP_ENABLED" not in control_env
    assert treatment_env.pop("GA_M3_HUMAN_LOOP_ENABLED") == "1"
    control_env.pop("GA_CONDITION_ID")
    treatment_env.pop("GA_CONDITION_ID")
    control_env.pop("BENCHMARK_CAMPAIGN_ROOT")
    treatment_env.pop("BENCHMARK_CAMPAIGN_ROOT")
    assert control_env == treatment_env


def test_gate_rejects_non_method_dev_and_unknown_condition():
    with pytest.raises(ValueError, match="method_dev"):
        gate.build_manifest("roadmapbench:does-not-exist")
    with pytest.raises(ValueError, match="unsupported M3 condition"):
        gate.environment("sha", "m3b")
    with pytest.raises(ValueError, match="non-empty subset"):
        gate.build_manifest("roadmapbench:fbr-2.27.0-roadmap", conditions=("m3b",))


def test_treatment_only_manifest_does_not_schedule_control():
    manifest = gate.build_manifest(
        "roadmapbench:fyn-2.2.0-roadmap",
        conditions=("m3a_human_loop",),
    )

    assert manifest["run_count"] == 1
    assert manifest["candidate"] == "m3a_human_loop"
    assert manifest["runs"][0]["condition"] == "m3a_human_loop"
    assert manifest["runs"][0]["environment"]["GA_M3_HUMAN_LOOP_ENABLED"] == "1"
