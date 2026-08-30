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
    assert manifest["execution_harness_sha256"] == gate.execution_harness_hash()
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


def test_written_run_command_loads_its_own_frozen_manifest(tmp_path):
    path = tmp_path / "m3.json"
    run = gate.build_manifest(
        "roadmapbench:fyn-2.2.0-roadmap",
        conditions=("m3c_discriminative_control",),
        manifest_path=path,
    )["runs"][0]

    index = run["argv"].index("--experiment-manifest")
    assert run["argv"][index + 1] == str(path.resolve())
    assert run["argv"][run["argv"].index("--run-id") + 1] == run["run_id"]


def test_m3b_treatment_adds_only_decision_value_over_m3a():
    m3a = gate.build_manifest(
        "roadmapbench:fyn-2.2.0-roadmap",
        conditions=("m3a_human_loop",),
    )["runs"][0]
    m3b = gate.build_manifest(
        "roadmapbench:fyn-2.2.0-roadmap",
        conditions=("m3b_decision_value",),
    )["runs"][0]
    a_env = dict(m3a["environment"])
    b_env = dict(m3b["environment"])
    assert b_env.pop("GA_M3_DECISION_VALUE_ENABLED") == "1"
    for key in ("GA_CONDITION_ID", "BENCHMARK_CAMPAIGN_ROOT"):
        a_env.pop(key)
        b_env.pop(key)
    assert a_env == b_env


def test_m3c_uses_c_not_b_with_the_same_concurrent_continuity_stack():
    env = gate.environment("same-source", "m3c_discriminative_control")

    assert env["GA_M3_HUMAN_LOOP_ENABLED"] == "1"
    assert env["GA_M3_DISCRIMINATIVE_CONTROL_ENABLED"] == "1"
    assert "GA_M3_DECISION_VALUE_ENABLED" not in env
    assert env["GA_M32_ADAPTIVE_OBSERVATION_ENABLED"] == "1"
    assert env["GA_M35_CONTINUITY_ENABLED"] == "1"
    assert env["GA_M35_HISTORY_COMPACTION_ENABLED"] == "1"
    assert env["GA_M35_MINIMAL_FRONTSTAGE_ENABLED"] == "1"

    run = gate.build_manifest(
        "roadmapbench:fyn-2.2.0-roadmap",
        conditions=("m3c_discriminative_control",),
    )["runs"][0]
    assert run["executes_on_prepare"] is False
    assert "human_gap_increments" in run["environment"]["BENCHMARK_CAMPAIGN_ROOT"]


def test_m3d_adds_only_decision_sufficient_lifecycle_to_m3c():
    c_env = gate.environment("same-source", "m3c_discriminative_control")
    d_env = gate.environment("same-source", "m3d_decision_sufficient_control")

    assert d_env.pop("GA_M3_COMBINED_CONTROL_ENABLED") == "1"
    assert "GA_M3_DECISION_VALUE_ENABLED" not in d_env
    for key in ("GA_CONDITION_ID",):
        c_env.pop(key)
        d_env.pop(key)
    assert d_env == c_env

    run = gate.build_manifest(
        "roadmapbench:fyn-2.2.0-roadmap",
        conditions=("m3d_decision_sufficient_control",),
    )["runs"][0]
    assert run["executes_on_prepare"] is False
    assert "human_gap_increments" in run["environment"]["BENCHMARK_CAMPAIGN_ROOT"]


def test_m31_is_registered_as_the_full_m3b_parent_plus_new_source_version():
    m3b = gate.environment("same-source", "m3b_decision_value")
    m31 = gate.environment("same-source", "m31_baseline_perception")

    assert m31["GA_M3_HUMAN_LOOP_ENABLED"] == "1"
    assert m31["GA_M3_DECISION_VALUE_ENABLED"] == "1"
    assert m31["GA_EXPERIMENT_ID"] == "m3-human-gap-v1"
    assert m31["GA_CONDITION_ID"] == "m31-baseline-perception"
    for key in ("GA_EXPERIMENT_ID", "GA_CONDITION_ID"):
        m3b.pop(key)
        m31.pop(key)
    assert m31 == m3b

    run = gate.build_manifest(
        "roadmapbench:fyn-2.2.0-roadmap",
        conditions=("m31_baseline_perception",),
    )["runs"][0]
    assert "human_gap_increments" in run["environment"]["BENCHMARK_CAMPAIGN_ROOT"]

def test_m32_adds_only_adaptive_observation_to_the_m31_parent():
    m31 = gate.environment("same-source", "m31_baseline_perception")
    m32 = gate.environment("same-source", "m32_adaptive_observation")

    assert m32.pop("GA_M32_ADAPTIVE_OBSERVATION_ENABLED") == "1"
    assert m32["GA_EXPERIMENT_ID"] == "m3-human-gap-v1"
    assert m32["GA_CONDITION_ID"] == "m32-adaptive-observation"
    for key in ("GA_EXPERIMENT_ID", "GA_CONDITION_ID"):
        m31.pop(key)
        m32.pop(key)
    assert m32 == m31

    run = gate.build_manifest(
        "roadmapbench:fyn-2.2.0-roadmap",
        conditions=("m32_adaptive_observation",),
    )["runs"][0]
    assert "human_gap_increments" in run["environment"]["BENCHMARK_CAMPAIGN_ROOT"]


def test_m35_adds_only_continuity_to_the_m32_parent():
    m32 = gate.environment("same-source", "m32_adaptive_observation")
    m35 = gate.environment("same-source", "m35_continuity")

    assert m35.pop("GA_M35_CONTINUITY_ENABLED") == "1"
    assert m35["GA_CONDITION_ID"] == "m35-continuity"
    for key in ("GA_CONDITION_ID",):
        m32.pop(key)
        m35.pop(key)
    assert m35 == m32


def test_m35_h4_adds_compaction_and_minimal_frontstage_to_continuity():
    continuity = gate.environment("same-source", "m35_continuity")
    h4 = gate.environment("same-source", "m35_h4_minimal_frontstage")

    assert h4.pop("GA_M35_HISTORY_COMPACTION_ENABLED") == "1"
    assert h4.pop("GA_M35_MINIMAL_FRONTSTAGE_ENABLED") == "1"
    assert h4["GA_CONDITION_ID"] == "m35-h4-minimal-frontstage"
    continuity.pop("GA_CONDITION_ID")
    h4.pop("GA_CONDITION_ID")
    assert h4 == continuity
