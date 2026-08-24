import importlib.util
import json
import re
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "m1_prepare_real_task_batch.py"


def load_module():
    spec = importlib.util.spec_from_file_location("m1_prepare_real_task_batch", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_prepares_eight_nonexecuting_runs_without_secrets():
    module = load_module()
    manifest = module.build_manifest()

    assert manifest["status"] == "prepared_not_executed"
    assert manifest["run_count"] == 8
    assert manifest["secrets_included"] is False
    assert len({row["task_id"] for row in manifest["runs"]}) == 4
    assert {row["condition"] for row in manifest["runs"]} == {"control", "treatment"}
    assert all(row["executes_on_prepare"] is False for row in manifest["runs"])
    serialized = json.dumps(manifest).lower()
    assert "auth_token" not in serialized
    assert "api_key" not in serialized
    assert re.search(r"sk-[a-z0-9]{20,}", serialized) is None


def test_treatment_diff_is_only_workspace_switch_before_runner_paths():
    module = load_module()
    source_hash = "a" * 64
    control = module.common_environment(source_hash, "control")
    treatment = module.common_environment(source_hash, "treatment")

    assert treatment.pop("GA_M1_WORKSPACE_ENABLED") == "1"
    control["GA_CONDITION_ID"] = treatment["GA_CONDITION_ID"]
    assert treatment == control


def test_all_commands_keep_frozen_budget_and_no_online_checker():
    module = load_module()
    manifest = module.build_manifest()

    assert manifest["online_native_checker"] is False
    for row in manifest["runs"]:
        command = " ".join(row["argv"])
        assert "7200" in command
        assert row["environment"]["GA_MAX_TURNS"] == "500"
        assert row["environment"]["GA_M0_MONITOR_CONFIG"] == (
            "native_oai_cc_vibe_gpt56_sol_high"
        )
