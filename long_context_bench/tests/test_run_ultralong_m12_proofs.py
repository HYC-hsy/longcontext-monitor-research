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


def test_clean_launch_refuses_legacy_public_network(monkeypatch):
    monkeypatch.setenv('GA_MONITOR_ENABLED', '1')
    monkeypatch.delenv('GA_RUN_ISOLATION', raising=False)
    monkeypatch.setattr(m12, 'preflight', lambda *args: pytest.fail('must fail before preflight'))
    with pytest.raises(RuntimeError, match='isolated inference profile'):
        m12.run_proof('roadmapbench', 'not-launched', 0, 10000)


@pytest.mark.parametrize('flag', ['GA_MONITOR_ACTIVE_WORKING_CONTEXT', 'GA_MONITOR_LIVE_AWARENESS',
                                 'GA_MONITOR_DECISION_CONTEXT', 'GA_MONITOR_HYBRID_CONTROL',
                                 'GA_MONITOR_PMA_MEMORY', 'GA_MONITOR_TASK_MODEL',
                                 'GA_MONITOR_INDEPENDENT_C',
                                 'GA_MONITOR_INDEPENDENT_C_TOTAL_REQUESTS',
                                 'GA_MONITOR_INDEPENDENT_C_MAX_REQUESTS'])
def test_active_working_context_reaches_container_and_is_reset_between_conditions(flag):
    import ast
    tree = ast.parse((ROOT / 'adapters/harbor_ga_agent.py').read_text(encoding='utf-8'))
    forwarded = next(ast.literal_eval(node.value) for node in tree.body
                     if isinstance(node, ast.Assign)
                     and any(isinstance(target, ast.Name) and target.id == 'FORWARDED_ENV_VARS'
                             for target in node.targets))
    assert flag in forwarded
    assert flag in m12.MANIFEST_CONTROLLED_ENV_KEYS


def test_isolation_refuses_old_branch_mounts(monkeypatch):
    monkeypatch.setenv('GA_RUN_ISOLATION', m12.ISOLATION_PROFILE)
    monkeypatch.setenv('GA_COMPLETION_BRANCH_CHECKPOINT', 'old-run')
    monkeypatch.setattr(m12, 'preflight', lambda *args: pytest.fail('must fail before preflight'))
    with pytest.raises(RuntimeError, match='Historical branch mounts'):
        m12.run_proof('roadmapbench', 'not-launched', 0, 10000)


def test_host_preflight_forwards_named_config(monkeypatch):
    monkeypatch.setenv('GA_LLM_CONFIG_NAME', 'native_claude_cc_vibe_opus48')
    monkeypatch.setattr(m12.m4, 'python_home', lambda: Path('python-test'))
    commands = []

    def checked(argv, timeout):
        commands.append(argv)
        return 'M12_HOSTS=["cc-vibe.com"]'

    monkeypatch.setattr(m12.m4, 'checked', checked)
    assert m12.resolve_agent_hosts(0) == ['cc-vibe.com']
    assert 'GA_LLM_CONFIG_NAME=native_claude_cc_vibe_opus48' in commands[0]


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
    values = m12.stage4_agent_kwargs()
    assert values["m0_monitor_enabled"] is True
    assert values["m0_monitor_config"] == "native_openai_cc_vibe"
    assert values["m0_max_inspections"] == 12
    assert values["m0_recent_trajectory_turns"] == 0


def test_clean_monitor_is_explicitly_opt_in(monkeypatch):
    monkeypatch.setenv("GA_BASELINE_CONDITION", "original")
    monkeypatch.setenv("GA_MONITOR_ENABLED", "1")
    monkeypatch.setenv("GA_MONITOR_CONFIG", "native_oai_cc_vibe_gpt56_sol_high")

    values = m12.stage4_agent_kwargs()

    assert values["monitor_enabled"] is True
    assert values["monitor_config"] == "native_oai_cc_vibe_gpt56_sol_high"






def test_m3_human_loop_is_explicitly_forwarded(monkeypatch):
    monkeypatch.setenv("GA_BASELINE_CONDITION", "original")
    monkeypatch.setenv("GA_M0_MONITOR_ENABLED", "1")
    monkeypatch.setenv("GA_M0_MONITOR_CONFIG", "native_openai_cc_vibe")
    monkeypatch.setenv("GA_M3_HUMAN_LOOP_ENABLED", "1")
    values = m12.stage4_agent_kwargs()
    assert values["m3_human_loop_enabled"] is True


def test_m3_decision_value_is_explicitly_forwarded(monkeypatch):
    monkeypatch.setenv("GA_BASELINE_CONDITION", "original")
    monkeypatch.setenv("GA_M0_MONITOR_ENABLED", "1")
    monkeypatch.setenv("GA_M0_MONITOR_CONFIG", "native_openai_cc_vibe")
    monkeypatch.setenv("GA_M3_HUMAN_LOOP_ENABLED", "1")
    monkeypatch.setenv("GA_M3_DECISION_VALUE_ENABLED", "1")
    values = m12.stage4_agent_kwargs()
    assert values["m3_human_loop_enabled"] is True
    assert values["m3_decision_value_enabled"] is True


def test_m3_discriminative_control_is_explicitly_forwarded(monkeypatch):
    monkeypatch.setenv("GA_BASELINE_CONDITION", "original")
    monkeypatch.setenv("GA_M0_MONITOR_ENABLED", "1")
    monkeypatch.setenv("GA_M0_MONITOR_CONFIG", "native_openai_cc_vibe")
    monkeypatch.setenv("GA_M3_HUMAN_LOOP_ENABLED", "1")
    monkeypatch.setenv("GA_M3_DISCRIMINATIVE_CONTROL_ENABLED", "1")
    values = m12.stage4_agent_kwargs()
    assert values["m3_discriminative_control_enabled"] is True


def test_m3_combined_control_is_explicitly_forwarded(monkeypatch):
    monkeypatch.setenv("GA_BASELINE_CONDITION", "original")
    monkeypatch.setenv("GA_M0_MONITOR_ENABLED", "1")
    monkeypatch.setenv("GA_M0_MONITOR_CONFIG", "native_openai_cc_vibe")
    monkeypatch.setenv("GA_M3_HUMAN_LOOP_ENABLED", "1")
    monkeypatch.setenv("GA_M3_DISCRIMINATIVE_CONTROL_ENABLED", "1")
    monkeypatch.setenv("GA_M3_COMBINED_CONTROL_ENABLED", "1")

    values = m12.stage4_agent_kwargs()

    assert values["m3_discriminative_control_enabled"] is True
    assert values["m3_combined_control_enabled"] is True






def test_experiment_manifest_applies_allowlisted_secret_free_environment(
        tmp_path, monkeypatch):
    campaign = tmp_path / "campaign"
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "secrets_included": False,
        "runs": [{
            "run_id": "run-1",
            "environment": {
                "GA_M3_HUMAN_LOOP_ENABLED": "1",
                "GA_MONITOR_HANDOFF_VALIDATION": "1",
                "GA_MONITOR_ADVICE_REVISION": "1",
                "GA_EXPERIMENT_HARNESS_SHA256": m12.execution_harness_hash(),
                "BENCHMARK_CAMPAIGN_ROOT": str(campaign),
            },
        }],
    }), encoding="utf-8")
    monkeypatch.delenv("GA_M3_HUMAN_LOOP_ENABLED", raising=False)

    selected = m12.apply_experiment_manifest(manifest, "run-1")

    assert selected["run_id"] == "run-1"
    assert m12.os.environ["GA_M3_HUMAN_LOOP_ENABLED"] == "1"
    assert m12.os.environ["GA_MONITOR_HANDOFF_VALIDATION"] == "1"
    assert m12.os.environ["GA_MONITOR_ADVICE_REVISION"] == "1"
    assert m12.WORK_ROOT == campaign
    assert m12.JOBS_ROOT == campaign / "jobs"


def test_experiment_manifest_rejects_execution_harness_drift(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "secrets_included": False,
        "runs": [{
            "run_id": "run-1",
            "environment": {"GA_EXPERIMENT_HARNESS_SHA256": "0" * 64},
        }],
    }), encoding="utf-8")

    with pytest.raises(RuntimeError, match="execution harness mismatch"):
        m12.apply_experiment_manifest(manifest, "run-1")


def test_preflight_rejects_generic_agent_source_drift(monkeypatch):
    monkeypatch.setenv("GA_METHOD_EXPECTED_SOURCE_SHA256", "a" * 64)

    with pytest.raises(RuntimeError, match="GA source mismatch"):
        m12.validate_expected_ga_source("b" * 64)

    m12.validate_expected_ga_source("a" * 64)


def test_experiment_manifest_clears_stale_candidate_switches(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "secrets_included": False,
        "runs": [{
            "run_id": "run-c",
            "environment": {
                "GA_M3_DISCRIMINATIVE_CONTROL_ENABLED": "1",
                "GA_EXPERIMENT_HARNESS_SHA256": m12.execution_harness_hash(),
            },
        }],
    }), encoding="utf-8")
    monkeypatch.setenv("GA_M3_DECISION_VALUE_ENABLED", "1")
    monkeypatch.setenv("GA_M3_COMBINED_CONTROL_ENABLED", "1")
    monkeypatch.setenv("GA_MONITOR_HANDOFF_VALIDATION", "1")
    monkeypatch.setenv("GA_MONITOR_ADVICE_REVISION", "1")
    monkeypatch.setenv("GA_MANUAL_COMPLETION_ENABLED", "1")
    monkeypatch.setenv("GA_STAGE6D_BUNDLE_DIR", str(tmp_path / "stale-oracle-bundle"))
    monkeypatch.setenv("GA_EVIDENCE_FRONTEND_CONFIG", "stale-frontend")
    monkeypatch.setenv("GA_REPRESENTATION_AUDIT_CONFIG", "stale-auditor")

    m12.apply_experiment_manifest(manifest, "run-c")

    assert "GA_M3_DECISION_VALUE_ENABLED" not in m12.os.environ
    assert "GA_M3_COMBINED_CONTROL_ENABLED" not in m12.os.environ
    assert "GA_MONITOR_HANDOFF_VALIDATION" not in m12.os.environ
    assert "GA_MONITOR_ADVICE_REVISION" not in m12.os.environ
    assert "GA_MANUAL_COMPLETION_ENABLED" not in m12.os.environ
    assert "GA_STAGE6D_BUNDLE_DIR" not in m12.os.environ
    assert "GA_EVIDENCE_FRONTEND_CONFIG" not in m12.os.environ
    assert "GA_REPRESENTATION_AUDIT_CONFIG" not in m12.os.environ
    assert m12.os.environ["GA_M3_DISCRIMINATIVE_CONTROL_ENABLED"] == "1"


def test_invalid_manifest_does_not_partially_mutate_environment(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "secrets_included": False,
        "runs": [{
            "run_id": "bad",
            "environment": {
                "GA_CONDITION_ID": "should-not-leak",
                "NOT_ALLOWED": "invalid",
            },
        }],
    }), encoding="utf-8")
    monkeypatch.setenv("GA_CONDITION_ID", "original-value")

    with pytest.raises(ValueError, match="not allowlisted"):
        m12.apply_experiment_manifest(manifest, "bad")

    assert m12.os.environ["GA_CONDITION_ID"] == "original-value"


@pytest.mark.parametrize("payload,match", [
    ({"secrets_included": True, "runs": []}, "exclude secrets"),
    ({"secrets_included": False, "runs": [{
        "run_id": "run-1", "environment": {"ANTHROPIC_AUTH_TOKEN": "x"},
    }]}, "not allowlisted"),
    ({"secrets_included": False, "runs": [{
        "run_id": "run-1", "environment": {"GA_API_KEY": "x"},
    }]}, "secret-like"),
])
def test_experiment_manifest_rejects_secrets_and_unapproved_environment(
        tmp_path, payload, match):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        m12.apply_experiment_manifest(manifest, "run-1")




def test_m0_monitor_requires_named_model(monkeypatch):
    monkeypatch.setenv("GA_BASELINE_CONDITION", "original")
    monkeypatch.setenv("GA_M0_MONITOR_ENABLED", "1")
    monkeypatch.delenv("GA_M0_MONITOR_CONFIG", raising=False)
    with pytest.raises(ValueError, match="M0_MONITOR_CONFIG"):
        m12.stage4_agent_kwargs()


def test_monitor_lhtb_execution_copy_disables_online_verifier_feedback(
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
    monkeypatch.setenv("GA_MONITOR_ENABLED", "1")

    execution = m12.materialize_execution_task("lhtb", "task-a", "run-1")

    assert execution != task
    assert "continue_until_timeout = false" in (
        execution / "task.toml"
    ).read_text(encoding="utf-8")
    assert (execution / "instruction.md").read_text(encoding="utf-8") == "public task"
    assert "continue_until_timeout = true" in (
        task / "task.toml"
    ).read_text(encoding="utf-8")


def test_non_monitor_or_non_lhtb_uses_frozen_task_without_copy(tmp_path, monkeypatch):
    source = tmp_path / "task-b"
    source.mkdir()
    monkeypatch.setitem(m12.SOURCES["lhtb"], "task_root", tmp_path)
    monkeypatch.delenv("GA_MONITOR_ENABLED", raising=False)
    assert m12.materialize_execution_task("lhtb", "task-b", "run-2") == source


def test_monitor_finalizer_rejects_online_verifier_metadata(monkeypatch):
    monkeypatch.setenv("GA_MONITOR_ENABLED", "1")
    errors = m12.no_checker_leakage_errors(
        {"interim_verifier_rewards": [{"reward": 0.25}]}, []
    )
    assert errors == [
        "online checker metadata leaked into Monitor: interim_verifier_rewards"
    ]


def test_monitor_finalizer_rejects_public_verifier_feedback(monkeypatch):
    monkeypatch.setenv("GA_MONITOR_ENABLED", "1")
    errors = m12.no_checker_leakage_errors(
        {}, ["Continue working. Interim verifier result: reward=0.25"]
    )
    assert errors == [
        "online checker feedback leaked into the public Agent trajectory"
    ]


def test_non_monitor_finalizer_does_not_reinterpret_historical_continuation(monkeypatch):
    monkeypatch.delenv("GA_MONITOR_ENABLED", raising=False)
    assert m12.no_checker_leakage_errors(
        {"interim_verifier_rewards": [{"reward": 0.25}]},
        ["Interim verifier result: reward=0.25"],
    ) == []


def test_expected_otel_models_include_preregistered_monitor(monkeypatch):
    monkeypatch.setenv("GA_MONITOR_ENABLED", "1")
    monkeypatch.setenv("GA_MONITOR_EXPECTED_MODEL", "GPT-5.6-SOL")

    assert m12.expected_otel_models("Claude-Opus-4-6") == [
        "claude-opus-4-6", "gpt-5.6-sol"
    ]


def test_expected_otel_models_require_monitor_identity(monkeypatch):
    monkeypatch.setenv("GA_MONITOR_ENABLED", "1")
    monkeypatch.delenv("GA_MONITOR_EXPECTED_MODEL", raising=False)

    with pytest.raises(ValueError, match="MONITOR_EXPECTED_MODEL"):
        m12.expected_otel_models("claude-opus-4-6")


def test_expected_otel_models_remain_single_without_monitor(monkeypatch):
    monkeypatch.delenv("GA_MONITOR_ENABLED", raising=False)
    monkeypatch.setenv("GA_MONITOR_EXPECTED_MODEL", "ignored")

    assert m12.expected_otel_models("Claude-Opus-4-6") == ["claude-opus-4-6"]


def test_otel_model_match_allows_uninstrumented_registered_monitor(monkeypatch):
    monkeypatch.setenv("GA_MONITOR_ENABLED", "1")
    monkeypatch.setenv("GA_MONITOR_EXPECTED_MODEL", "gpt-5.6-sol")

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
