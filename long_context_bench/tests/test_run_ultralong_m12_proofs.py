from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_ultralong_m12_proofs.py"
SPEC = importlib.util.spec_from_file_location(
    "run_ultralong_m12_proofs", SCRIPT
)
m12 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m12)


def test_representatives_are_in_approved_proposals():
    for source in m12.SOURCES:
        row = m12.proposal_row(source)
        assert row["proposal"]["status"] == "approved_pending_execution_proof"
        assert row["selection_uses_ga_result"] is False


def test_lhtb_and_roadmap_use_distinct_session_contracts():
    assert m12.SOURCES["lhtb"]["persistent_session"] is True
    assert "harbor_ga_lhtb" in m12.SOURCES["lhtb"]["adapter"]
    assert m12.SOURCES["roadmapbench"]["persistent_session"] is False
    assert m12.SOURCES["roadmapbench"]["adapter"].endswith(
        ":HarborGenericAgent"
    )


def test_proof_source_rejects_reward_as_selection_gate():
    source = SCRIPT.read_text(encoding="utf-8")
    assert '"selection_uses_this_run": False' in source
    assert '"reward_not_a_proof_gate": True' in source
    assert '"--allow-agent-host"' in source


def test_stage4_kwargs_are_allowlisted_and_card_is_encoded(tmp_path, monkeypatch):
    card = tmp_path / "card.json"
    card.write_text(json.dumps({
        "schema_version": "obligation-state/1", "obligations": [{"description": "x"}],
    }), encoding="utf-8")
    monkeypatch.setenv("GA_BASELINE_CONDITION", "static_checklist")
    monkeypatch.setenv("GA_TASK_CARD_PATH", str(card))
    monkeypatch.setenv("GA_EXPERIMENT_ID", "exp")
    monkeypatch.setenv("GA_LLM_CONFIG_NAME", "named")
    values = m12.stage4_agent_kwargs()
    assert values["baseline_condition"] == "static_checklist"
    assert values["experiment_id"] == "exp"
    assert values["llm_config_name"] == "named"
    assert "task_card_b64" in values
    assert "API" not in json.dumps(values)


def test_manual_completion_boundary_is_explicitly_opt_in(monkeypatch):
    monkeypatch.setenv("GA_BASELINE_CONDITION", "original")
    monkeypatch.setenv("GA_MANUAL_COMPLETION_ENABLED", "1")
    monkeypatch.setenv("GA_MANUAL_COMPLETION_TIMEOUT_SECONDS", "420")
    values = m12.stage4_agent_kwargs()
    assert values["manual_completion_dir"] == "/logs/agent/manual_completion"
    assert values["manual_completion_timeout_seconds"] == 420.0


def test_m0_monitor_is_explicitly_opt_in(monkeypatch):
    monkeypatch.setenv("GA_BASELINE_CONDITION", "original")
    monkeypatch.setenv("GA_M0_MONITOR_ENABLED", "1")
    monkeypatch.setenv("GA_M0_MONITOR_CONFIG", "native_openai_cc_vibe")
    monkeypatch.setenv("GA_M0_MAX_INSPECTIONS", "12")
    monkeypatch.setenv("GA_M1_WORKSPACE_ENABLED", "1")
    monkeypatch.setenv("GA_M1_ACTIVE_RECONSTRUCTION_ENABLED", "1")
    monkeypatch.setenv("GA_M2_VERSIONED_REVISION_ENABLED", "1")
    values = m12.stage4_agent_kwargs()
    assert values["m0_monitor_enabled"] is True
    assert values["m0_monitor_config"] == "native_openai_cc_vibe"
    assert values["m0_max_inspections"] == 12
    assert values["m1_workspace_enabled"] is True
    assert values["m1_active_reconstruction_enabled"] is True
    assert values["m2_versioned_revision_enabled"] is True


def test_m2_justification_invalidation_is_explicitly_forwarded(monkeypatch):
    monkeypatch.setenv("GA_BASELINE_CONDITION", "original")
    monkeypatch.setenv("GA_M0_MONITOR_ENABLED", "1")
    monkeypatch.setenv("GA_M0_MONITOR_CONFIG", "native_openai_cc_vibe")
    monkeypatch.setenv("GA_M1_WORKSPACE_ENABLED", "1")
    monkeypatch.setenv("GA_M2_JUSTIFICATION_INVALIDATION_ENABLED", "1")
    values = m12.stage4_agent_kwargs()
    assert values["m2_justification_invalidation_enabled"] is True


def test_m2_semantic_impact_is_explicitly_forwarded(monkeypatch):
    monkeypatch.setenv("GA_BASELINE_CONDITION", "original")
    monkeypatch.setenv("GA_M0_MONITOR_ENABLED", "1")
    monkeypatch.setenv("GA_M0_MONITOR_CONFIG", "native_openai_cc_vibe")
    monkeypatch.setenv("GA_M1_WORKSPACE_ENABLED", "1")
    monkeypatch.setenv("GA_M2_SEMANTIC_IMPACT_ENABLED", "1")
    values = m12.stage4_agent_kwargs()
    assert values["m2_semantic_impact_enabled"] is True


def test_m3_human_loop_is_explicitly_forwarded(monkeypatch):
    monkeypatch.setenv("GA_BASELINE_CONDITION", "original")
    monkeypatch.setenv("GA_M0_MONITOR_ENABLED", "1")
    monkeypatch.setenv("GA_M0_MONITOR_CONFIG", "native_openai_cc_vibe")
    monkeypatch.setenv("GA_M1_WORKSPACE_ENABLED", "1")
    monkeypatch.setenv("GA_M2_SEMANTIC_IMPACT_ENABLED", "1")
    monkeypatch.setenv("GA_M3_HUMAN_LOOP_ENABLED", "1")
    values = m12.stage4_agent_kwargs()
    assert values["m2_semantic_impact_enabled"] is True
    assert values["m3_human_loop_enabled"] is True


def test_m1_workspace_cannot_run_without_m0(monkeypatch):
    monkeypatch.setenv("GA_BASELINE_CONDITION", "original")
    monkeypatch.setenv("GA_M1_WORKSPACE_ENABLED", "1")
    monkeypatch.delenv("GA_M0_MONITOR_ENABLED", raising=False)
    with pytest.raises(ValueError, match="requires GA_M0_MONITOR_ENABLED"):
        m12.stage4_agent_kwargs()


def test_m0_monitor_requires_named_model(monkeypatch):
    monkeypatch.setenv("GA_BASELINE_CONDITION", "original")
    monkeypatch.setenv("GA_M0_MONITOR_ENABLED", "1")
    monkeypatch.delenv("GA_M0_MONITOR_CONFIG", raising=False)
    with pytest.raises(ValueError, match="M0_MONITOR_CONFIG"):
        m12.stage4_agent_kwargs()


def test_m0_lhtb_execution_copy_disables_online_verifier_feedback(
    tmp_path, monkeypatch
):
    task = tmp_path / "source" / "task-a"
    task.mkdir(parents=True)
    (task / "task.toml").write_text(
        "[agent]\ncontinue_until_timeout = true\n[verifier]\ntimeout_sec = 30\n",
        encoding="utf-8",
    )
    (task / "instruction.md").write_text("public task", encoding="utf-8")
    monkeypatch.setitem(m12.SOURCES["lhtb"], "task_root", task.parent)
    monkeypatch.setattr(m12, "WORK_ROOT", tmp_path / "runs")
    monkeypatch.setenv("GA_M0_MONITOR_ENABLED", "1")

    execution = m12.materialize_execution_task("lhtb", "task-a", "run-1")

    assert execution != task
    assert "continue_until_timeout = false" in (
        execution / "task.toml"
    ).read_text(encoding="utf-8")
    assert (execution / "instruction.md").read_text(encoding="utf-8") == "public task"
    assert "continue_until_timeout = true" in (
        task / "task.toml"
    ).read_text(encoding="utf-8")


def test_non_m0_or_non_lhtb_uses_frozen_task_without_copy(tmp_path, monkeypatch):
    source = tmp_path / "task-b"
    source.mkdir()
    monkeypatch.setitem(m12.SOURCES["lhtb"], "task_root", tmp_path)
    monkeypatch.delenv("GA_M0_MONITOR_ENABLED", raising=False)
    assert m12.materialize_execution_task("lhtb", "task-b", "run-2") == source


def test_m0_finalizer_rejects_online_verifier_metadata(monkeypatch):
    monkeypatch.setenv("GA_M0_MONITOR_ENABLED", "1")
    errors = m12.no_checker_leakage_errors(
        {"interim_verifier_rewards": [{"reward": 0.25}]}, []
    )
    assert errors == [
        "online checker metadata leaked into M0: interim_verifier_rewards"
    ]


def test_m0_finalizer_rejects_public_verifier_feedback(monkeypatch):
    monkeypatch.setenv("GA_M0_MONITOR_ENABLED", "1")
    errors = m12.no_checker_leakage_errors(
        {}, ["Continue working. Interim verifier result: reward=0.25"]
    )
    assert errors == [
        "online checker feedback leaked into the public Agent trajectory"
    ]


def test_non_m0_finalizer_does_not_reinterpret_historical_continuation(monkeypatch):
    monkeypatch.delenv("GA_M0_MONITOR_ENABLED", raising=False)
    assert m12.no_checker_leakage_errors(
        {"interim_verifier_rewards": [{"reward": 0.25}]},
        ["Interim verifier result: reward=0.25"],
    ) == []


def test_expected_otel_models_include_preregistered_monitor(monkeypatch):
    monkeypatch.setenv("GA_M0_MONITOR_ENABLED", "1")
    monkeypatch.setenv("GA_M0_MONITOR_EXPECTED_MODEL", "GPT-5.6-SOL")

    assert m12.expected_otel_models("Claude-Opus-4-6") == [
        "claude-opus-4-6", "gpt-5.6-sol"
    ]


def test_expected_otel_models_require_monitor_identity(monkeypatch):
    monkeypatch.setenv("GA_M0_MONITOR_ENABLED", "1")
    monkeypatch.delenv("GA_M0_MONITOR_EXPECTED_MODEL", raising=False)

    with pytest.raises(ValueError, match="M0_MONITOR_EXPECTED_MODEL"):
        m12.expected_otel_models("claude-opus-4-6")


def test_expected_otel_models_remain_single_for_non_m0(monkeypatch):
    monkeypatch.delenv("GA_M0_MONITOR_ENABLED", raising=False)
    monkeypatch.setenv("GA_M0_MONITOR_EXPECTED_MODEL", "ignored")

    assert m12.expected_otel_models("Claude-Opus-4-6") == ["claude-opus-4-6"]


def test_otel_model_match_allows_uninstrumented_registered_monitor(monkeypatch):
    monkeypatch.setenv("GA_M0_MONITOR_ENABLED", "1")
    monkeypatch.setenv("GA_M0_MONITOR_EXPECTED_MODEL", "gpt-5.6-sol")

    assert m12.otel_models_match(["claude-opus-4-6"], "claude-opus-4-6")
    assert m12.otel_models_match(
        ["claude-opus-4-6", "gpt-5.6-sol"], "claude-opus-4-6"
    )
    assert not m12.otel_models_match(["gpt-5.6-sol"], "claude-opus-4-6")
    assert not m12.otel_models_match(
        ["claude-opus-4-6", "unknown-model"], "claude-opus-4-6"
    )


def test_stage6d_bundle_is_encoded_and_requires_all_inputs(tmp_path, monkeypatch):
    paths = []
    for name, content in (("state.json", "{}"), ("contract.json", "{}"),
                          ("task.txt", "public task")):
        path = tmp_path / name
        path.write_text(content, encoding="utf-8")
        paths.append(path)
    monkeypatch.setenv("GA_BASELINE_CONDITION", "original")
    monkeypatch.setenv("GA_EVIDENCE_STATE_PATH", str(paths[0]))
    monkeypatch.setenv("GA_COMPLETION_CONTRACT_PATH", str(paths[1]))
    monkeypatch.setenv("GA_PUBLIC_TASK_PATH", str(paths[2]))
    monkeypatch.setenv("GA_EVIDENCE_FRONTEND_CONFIG", "named")
    monkeypatch.setenv("GA_EVIDENCE_GATE_MODE", "lineage_shadow")
    values = m12.stage4_agent_kwargs()
    assert values["evidence_frontend_config"] == "named"
    assert values["evidence_gate_mode"] == "lineage_shadow"
    assert all(values[key] for key in (
        "evidence_state_b64", "completion_contract_b64", "public_task_b64"
    ))

    monkeypatch.delenv("GA_PUBLIC_TASK_PATH")
    with pytest.raises(ValueError, match="state, contract, and public task"):
        m12.stage4_agent_kwargs()


def test_stage6d_directory_bundle_uses_short_container_path(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    for name in ("evidence_state.json", "completion_contract.json", "public_task.txt"):
        (bundle / name).write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GA_BASELINE_CONDITION", "original")
    monkeypatch.setenv("GA_STAGE6D_BUNDLE_DIR", str(bundle))
    values = m12.stage4_agent_kwargs()
    assert values["evidence_bundle_dir"] == "/opt/stage6d-bundle"
    assert not any(key.endswith("_b64") for key in values)


@pytest.mark.parametrize("policy", [
    "K5M2", "I0", "I1", "I2",
    "A0_ATOMIC", "A1_PRIORITY", "A2_RESIDUAL", "A3_PRIORITY_RESIDUAL",
])
def test_stage6d_checkpoint_branch_accepts_supported_policies(monkeypatch, policy):
    monkeypatch.setenv("GA_BASELINE_CONDITION", "original")
    monkeypatch.setenv("GA_COMPLETION_BRANCH_CHECKPOINT", "checkpoint")
    monkeypatch.setenv("GA_COMPLETION_BRANCH_BUNDLE", "bundle")
    monkeypatch.setenv("GA_COMPLETION_BRANCH_POLICY", policy)
    values = m12.stage4_agent_kwargs()
    assert values["completion_branch_checkpoint"] == "/opt/completion-checkpoint"
    assert values["completion_branch_bundle"] == "/opt/completion-branch"
    assert values["completion_branch_policy"] == policy
