import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "method_discovery/run_dcec_v0_discrimination.py"
MANIFEST_PATH = ROOT / "method_discovery/artifacts/dcec_v0_20260921/discriminating_manifest.json"
CONFIG_PATH = ROOT / "monitor_config/models.local.json"


def load_runner():
    spec = importlib.util.spec_from_file_location("dcec_v0_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_visible_projection_and_materialization_do_not_expose_research_metadata(tmp_path):
    runner = load_runner()
    spec = runner.load_json(ROOT / runner.load_json(MANIFEST_PATH)["fixture_spec"])
    latent = runner.model_visible_projection(spec, "latent_defect")
    control = runner.model_visible_projection(spec, "correct_control")
    assert "research_only" not in latent
    assert "sequence_variants" not in latent
    assert latent["initial_files"] != control["initial_files"]
    materialized = runner.materialize_visible(tmp_path / "case", latent)
    text = json.dumps(runner.readable_snapshot(tmp_path / "case"), ensure_ascii=False)
    assert "latent_defect" not in text
    assert "research_only" not in text
    assert materialized["private_initial_files"] == []
    assert not (tmp_path / "case/task").joinpath("fixture_spec.json").exists()


def test_frozen_transition_uses_real_intervention_and_claim_not_research_conclusion(tmp_path):
    runner = load_runner()
    spec = runner.load_json(ROOT / runner.load_json(MANIFEST_PATH)["fixture_spec"])
    projection = runner.model_visible_projection(spec, "latent_defect")
    root = tmp_path / "case"
    runner.materialize_visible(root, projection)
    before = (root / "workspace/neutral_ops.py").read_text(encoding="utf-8")
    assert "strip" not in before
    repair = runner.apply_repair(root, projection, "Please repair normalize_key using the requirement.")
    after = (root / "workspace/neutral_ops.py").read_text(encoding="utf-8")
    events = (root / "task/public_events.jsonl").read_text(encoding="utf-8")
    assert 'strip(" ")' in after
    assert repair["semantic_validity"] == "not_judged_online"
    assert projection["repair_task_agent_message"] in events
    assert spec["model_visible"]["repair_event"]["public_post_repair_observation"] not in events


def test_production_request_metadata_invariance_hidden_object_and_treatment_delta(tmp_path):
    runner = load_runner()
    manifest = runner.load_json(MANIFEST_PATH)
    spec = runner.load_json(ROOT / manifest["fixture_spec"])
    audit = runner.anti_leakage_audit(manifest, spec, tmp_path)
    assert audit["metadata_rename_model_request_deep_equal"] is True
    assert audit["hidden_research_terms_absent"] is True
    assert audit["ordinary_vs_dcec_only_registered_mechanism_difference"] is True
    assert audit["api_requests_sent"] == 0


def test_state_audit_accepts_production_write_receipt_and_flags_unexplained_change(tmp_path):
    runner = load_runner()
    private = tmp_path / "monitor"
    audit = private / "audit"
    audit.mkdir(parents=True)
    hashes = [runner.sha256_bytes(value.encode()) for value in ("", "one", "two")]
    timeline = [
        {"sha256": hashes[0]}, {"sha256": hashes[1]}, {"sha256": hashes[2]},
    ]
    dialogue = [
        {"event": "tool_call", "tool_id": "w1", "name": "file_write",
         "arguments": json.dumps({"path": "monitor/working.md"})},
        {"event": "tool_result", "tool_id": "w1",
         "data": {"path": "monitor/working.md", "sha256": hashes[1]}},
    ]
    for name, rows in (("runner_state_timeline.jsonl", timeline), ("dialogue.jsonl", dialogue)):
        (audit / name).write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    result = runner.state_audit(private)
    assert result["out_of_band_state_changes"] == [{
        "before": hashes[1], "after": hashes[2], "classification": "out_of_band_state_change"}]


def test_archived_usage_and_transport_attempts_remain_readable_after_provider_drain(tmp_path):
    runner = load_runner()
    audit = tmp_path / "monitor/audit"
    audit.mkdir(parents=True)
    runner.append_jsonl(audit / "provider_usage.jsonl", {"input_tokens": 10, "output_tokens": 2})
    runner.append_jsonl(audit / "request_attempts.jsonl", {"attempt": 1, "status": "response"})
    assert runner.jsonl_rows(audit / "provider_usage.jsonl") == [
        {"input_tokens": 10, "output_tokens": 2}]
    assert runner.jsonl_rows(audit / "request_attempts.jsonl") == [
        {"attempt": 1, "status": "response"}]


def test_preflight_materializes_four_isolated_records_without_api(tmp_path, monkeypatch):
    runner = load_runner()
    provider_module = runner.sys.modules[runner.MonitorProviderClient.__module__]
    monkeypatch.setattr(provider_module.requests, "post", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("network request path must not run during preflight")))
    output = tmp_path / "preflight"
    result = runner.preflight(MANIFEST_PATH, output, CONFIG_PATH)
    assert result["status"] == "passed_not_executed"
    assert result["execution_authorized"] is False
    assert result["api_requests_sent"] == 0
    assert len(result["records"]) == 4
    assert all(item["private_initial_files"] == [] for item in result["records"])
    assert all(item["initial_visible_tree_equal"] for item in result["same_variant_parity"].values())


def test_execution_lock_rejects_before_provider_creation(tmp_path, monkeypatch):
    runner = load_runner()
    monkeypatch.setattr(runner, "MonitorProviderClient", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("provider must not be created while execution is unauthorized")))
    with pytest.raises(PermissionError, match="execution_authorized=false"):
        runner.execute(MANIFEST_PATH, tmp_path / "run", CONFIG_PATH)


def test_manifest_freezes_order_and_disables_historical_candidates():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["implementation_commit"] == "1cd7048c5742ca7415937ec5142cc28fd2bcaf22"
    assert manifest["execution_authorized"] is False
    assert [(item["sequence"], item["condition"]) for item in manifest["runs"]] == [
        ("latent_defect", "ordinary"),
        ("latent_defect", "dcec_v0"),
        ("correct_control", "dcec_v0"),
        ("correct_control", "ordinary"),
    ]
    assert set(manifest["historical_candidate_switches"].values()) == {"0"}
