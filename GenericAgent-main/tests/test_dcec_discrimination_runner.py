import importlib.util
import json
import subprocess
import sys
from types import SimpleNamespace
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


def prepare_isolated_source(runner, tmp_path, manifest):
    profiles = runner.load_json(CONFIG_PATH)
    return runner.prepare_isolated_runtime(
        tmp_path / "isolated-runtime",
        profiles[manifest["shared_contract"]["supervisor_profile"]],
        manifest["historical_candidate_config_keys"],
    )


def isolation_module(runner):
    return runner.sys.modules[runner.run_isolated_record.__module__]


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
    paths = [item["path"] for item in materialized["visible_files"]]
    assert len(paths) == len(set(paths))
    assert paths.count("workspace/neutral_ops.py") == 1
    assert not (tmp_path / "case/task").joinpath("fixture_spec.json").exists()


def test_frozen_transition_uses_real_intervention_and_claim_not_research_conclusion(tmp_path):
    runner = load_runner()
    spec = runner.load_json(ROOT / runner.load_json(MANIFEST_PATH)["fixture_spec"])
    projection = runner.model_visible_projection(spec, "latent_defect")
    root = tmp_path / "case"
    runner.materialize_visible(root, projection)
    before = (root / "task/workspace/neutral_ops.py").read_text(encoding="utf-8")
    assert "strip" not in before
    repair = runner.apply_repair(root, projection, "Please repair normalize_key using the requirement.")
    after = (root / "task/workspace/neutral_ops.py").read_text(encoding="utf-8")
    events = (root / "task/public_events.jsonl").read_text(encoding="utf-8")
    assert 'strip(" ")' in after
    assert repair["semantic_validity"] == "not_judged_online"
    assert projection["repair_task_agent_message"] in events
    assert spec["model_visible"]["repair_event"]["public_post_repair_observation"] not in events


def test_production_request_metadata_invariance_hidden_object_and_treatment_delta(tmp_path):
    runner = load_runner()
    manifest = runner.load_json(MANIFEST_PATH)
    spec = runner.load_json(ROOT / manifest["fixture_spec"])
    prepare_isolated_source(runner, tmp_path, manifest)
    audit = runner.anti_leakage_audit(
        manifest, spec, tmp_path / "scratch", tmp_path / "isolated-runtime")
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


def test_archived_r1b_preflight_remains_zero_api_and_materialized():
    result = json.loads((ROOT / "method_discovery/runs/dcec_v0_r1b_tls_preflight_20260921"
                         / "preflight.json").read_text(encoding="utf-8"))
    assert result["status"] == "passed_not_executed"
    assert result["execution_authorized"] is False
    assert result["provider_http_requests"] == 0
    assert result["api_requests_sent"] == 0
    assert len(result["records"]) == 4
    assert all(item["private_initial_files"] == [] for item in result["records"])
    assert all(item["initial_visible_tree_equal"] for item in result["same_variant_parity"].values())
    assert result["code_run_filesystem_isolation"]["forbidden_name_hits"] == []
    assert result["code_run_filesystem_isolation"]["forbidden_content_hits"] == []
    assert result["code_run_filesystem_isolation"]["task_workspace_write_blocked"] is True
    deadline = result["record_wall_deadline_enforcement"]
    assert deadline["manifest_budget_seconds"] == 900
    assert deadline["provider"]["budget_seconds"] == 900
    assert deadline["provider"]["recovery_deadline_configured"] is True
    assert deadline["provider"]["recovery_stop_configured"] is True
    assert deadline["host_watchdog"]["deadline_exceeded"] is True
    assert deadline["same_budget_for_all_records"] is True
    assert result["formal_execution_output"]["exists"] is False
    assert result["production_tls_semantics"]["verification_enabled"] is True
    assert result["production_tls_semantics"]["proxy_present"] is False
    assert result["upstream_tls_handshake"]["tls_handshake_success"] is True
    assert result["scientific_request_invariance"]["unchanged"] is True


def test_production_tls_semantics_use_requests_ca_and_reject_proxy():
    runner = load_runner()
    isolation = isolation_module(runner)
    profiles = runner.load_json(CONFIG_PATH)
    profile = profiles[runner.load_json(MANIFEST_PATH)["shared_contract"]["supervisor_profile"]]
    tls, ca_path = isolation.production_tls_semantics(profile)
    assert profile.get("verify", True) is True
    assert tls["verification_enabled"] is True
    assert tls["verify_value_class"] == "bool"
    assert tls["ca_source_kind"] == "production_requests_certifi"
    assert tls["production_proxy_present"] is False
    assert ca_path.is_file()
    assert tls["ca_bundle_sha256"] == isolation.sha256_file(ca_path)
    gateway = isolation._gateway_config(profile)
    assert gateway["models"]["monitor"]["tls"] == tls
    with pytest.raises(ValueError, match="proxy equivalence"):
        isolation.production_tls_semantics({**profile, "proxy": "http://127.0.0.1:8080"})


def test_run_record_host_watchdog_terminates_once_and_cleans_all_resources(tmp_path, monkeypatch):
    runner = load_runner()
    isolation = isolation_module(runner)
    source, record = tmp_path / "source", tmp_path / "record"
    source.mkdir()
    (record / "task").mkdir(parents=True)
    (record / "monitor").mkdir(parents=True)
    docker_calls = []

    def fake_docker(*args, **kwargs):
        docker_calls.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    real_popen = subprocess.Popen
    worker_starts = []

    def hanging_popen(command, **kwargs):
        worker_starts.append(command)
        return real_popen(
            [sys.executable, "-u", "-c", "import time; time.sleep(60)"], **kwargs)

    monkeypatch.setattr(isolation, "docker", fake_docker)
    monkeypatch.setattr(isolation.subprocess, "Popen", hanging_popen)
    result = isolation.run_record(
        source, record,
        {"apibase": "https://example.invalid", "apikey": "offline", "model": "test"},
        False, 20, 0.1, lambda _: None, lambda: None)
    assert result["status"] == "timeout"
    assert result["deadline_exceeded"] is True
    assert result["budget_seconds"] == 0.1
    assert result["elapsed_seconds"] < 3
    assert len(worker_starts) == 1
    assert sum(call[:2] == ("rm", "-f") for call in docker_calls) == 2
    assert sum(call[:3] == ("volume", "rm", "-f") for call in docker_calls) == 1


def test_run_record_fast_worker_finishes_without_false_watchdog_timeout(tmp_path, monkeypatch):
    runner = load_runner()
    isolation = isolation_module(runner)
    source, record = tmp_path / "source", tmp_path / "record"
    source.mkdir()
    (record / "task").mkdir(parents=True)
    (record / "monitor").mkdir(parents=True)
    monkeypatch.setattr(isolation, "docker", lambda *args, **kwargs: SimpleNamespace(
        returncode=0, stdout="", stderr=""))
    real_popen = subprocess.Popen

    def fast_popen(command, **kwargs):
        script = (
            "import json; print('DCEC_WORKER '+json.dumps("
            "{'event':'result','result':{'status':'completed'}}), flush=True)"
        )
        return real_popen([sys.executable, "-u", "-c", script], **kwargs)

    monkeypatch.setattr(isolation.subprocess, "Popen", fast_popen)
    result = isolation.run_record(
        source, record,
        {"apibase": "https://example.invalid", "apikey": "offline", "model": "test"},
        True, 20, 2.0, lambda _: None, lambda: None)
    assert result["status"] == "completed"
    assert result["deadline_exceeded"] is False
    assert result["budget_seconds"] == 2.0


def test_ordinary_and_dcec_receive_identical_manifest_wall_budget(tmp_path, monkeypatch):
    runner = load_runner()
    manifest = runner.load_json(MANIFEST_PATH)
    spec = runner.load_json(ROOT / manifest["fixture_spec"])
    observed = []

    def fake_run(source, slot, profile, dcec, max_turns, wall_seconds, deliver, root_ready):
        observed.append((dcec, wall_seconds))
        return {"status": "completed", "budget_seconds": wall_seconds,
                "elapsed_seconds": 0.01, "deadline_exceeded": False}

    monkeypatch.setattr(runner, "run_isolated_record", fake_run)
    ordinary = next(run for run in manifest["runs"] if run["condition"] == "ordinary")
    dcec = next(run for run in manifest["runs"] if run["condition"] == "dcec_v0")
    runner.execute_record(tmp_path / "ordinary", tmp_path / "source", manifest, spec, ordinary, {})
    runner.execute_record(tmp_path / "dcec", tmp_path / "source", manifest, spec, dcec, {})
    assert observed == [(False, 900), (True, 900)]


def test_execution_lock_rejects_before_provider_creation(tmp_path, monkeypatch):
    runner = load_runner()
    manifest = runner.load_json(MANIFEST_PATH)
    manifest["execution_authorized"] = False
    locked = tmp_path / "locked-manifest.json"
    locked.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(runner, "run_isolated_record", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("isolated worker must not start while execution is unauthorized")))
    with pytest.raises(PermissionError, match="execution_authorized=false"):
        runner.execute(locked, tmp_path / "run", CONFIG_PATH)


def test_manifest_freezes_order_and_disables_historical_candidates():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["implementation_commit"] == "1cd7048c5742ca7415937ec5142cc28fd2bcaf22"
    assert manifest["execution_authorized"] is True
    assert manifest["execution_output"] == (
        "method_discovery/runs/dcec_v0_discrimination_r1b_tls_recovery")
    assert (ROOT / manifest["execution_output"] / "results.json").is_file()
    assert [(item["sequence"], item["condition"]) for item in manifest["runs"]] == [
        ("latent_defect", "ordinary"),
        ("latent_defect", "dcec_v0"),
        ("correct_control", "dcec_v0"),
        ("correct_control", "ordinary"),
    ]
    assert set(manifest["historical_candidate_switches"].values()) == {"0"}
