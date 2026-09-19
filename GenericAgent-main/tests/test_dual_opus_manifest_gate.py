import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]


def load_module():
    path = ROOT / "method_discovery" / "validate_dual_opus_manifest.py"
    spec = importlib.util.spec_from_file_location("validate_dual_opus_manifest", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_manifest(tmp_path, contract, *, task="native_claude_cc_vibe_opus48",
                   supervisor="claude_monitor_opus48", child_override=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    environment = {
        "GA_LLM_CONFIG_NAME": task,
        "GA_MONITOR_CONFIG": supervisor,
        "GA_MODEL_CONTRACT_FILE": str(contract),
        "GA_PROVIDER_MAX_RETRIES": "8",
    }
    if child_override:
        environment["GA_MONITOR_INDEPENDENT_C_PROFILE"] = child_override
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({
        "model_contract": json.loads(contract.read_text(encoding="utf-8")),
        "runs": [{"run_id": "test", "environment": environment}],
    }), encoding="utf-8")
    return path


def test_production_manifest_gate_rejects_old_task_before_model_request(tmp_path):
    module = load_module()
    contract = ROOT / "GenericAgent-main" / "monitor_agent_core" / "dual_opus_contract.json"
    manifest = write_manifest(tmp_path, contract, task="native_claude_cc_vibe")
    with pytest.raises(ValueError, match="role=task_agent field=profile"):
        module.validate_manifest_models(
            manifest, ROOT / "monitor_config" / "models.local.json")


def test_production_manifest_gate_rejects_old_supervisor_and_child_default(tmp_path):
    module = load_module()
    contract = ROOT / "GenericAgent-main" / "monitor_agent_core" / "dual_opus_contract.json"
    profile_path = tmp_path / "profiles.json"
    good = json.loads((ROOT / "monitor_config" / "models.local.json").read_text(encoding="utf-8"))
    good["old-supervisor"] = dict(good["claude_monitor_opus48"], model="gpt-5.6-sol")
    profile_path.write_text(json.dumps(good), encoding="utf-8")
    manifest = write_manifest(tmp_path, contract, supervisor="old-supervisor")
    with pytest.raises(ValueError, match="role=supervisor field=profile"):
        module.validate_manifest_models(manifest, profile_path)
    manifest = write_manifest(tmp_path / "child", contract, child_override="old-default")
    with pytest.raises(ValueError, match="must inherit supervisor"):
        module.validate_manifest_models(
            manifest, ROOT / "monitor_config" / "models.local.json")


def test_production_manifest_gate_rejects_bundle_rewritten_source_profile(tmp_path):
    module = load_module()
    contract = ROOT / "GenericAgent-main" / "monitor_agent_core" / "dual_opus_contract.json"
    profile_path = tmp_path / "profiles.json"
    profiles = json.loads(
        (ROOT / "monitor_config" / "models.local.json").read_text(encoding="utf-8"))
    profiles["claude_monitor_opus48"]["apibase"] = "http://127.0.0.1:18765"
    profile_path.write_text(json.dumps(profiles), encoding="utf-8")
    manifest = write_manifest(tmp_path, contract)
    with pytest.raises(ValueError, match="model source mismatch: role=supervisor"):
        module.validate_manifest_models(manifest, profile_path)
