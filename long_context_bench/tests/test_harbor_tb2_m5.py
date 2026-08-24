from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_harbor_tb2_m5", ROOT / "scripts" / "run_harbor_tb2_m5.py"
)
assert SPEC and SPEC.loader
m5 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m5)


def test_development_pool_is_exactly_twenty_unique_tasks():
    assert len(m5.TOP_20) == 20
    assert len(set(m5.TOP_20)) == 20
    assert m5.TOP_20[:3] == (
        "schemelike-metacircular-eval",
        "sam-cell-seg",
        "feal-differential-cryptanalysis",
    )


def test_direct_script_bootstrap_precedes_scripts_import():
    source = (ROOT / "scripts" / "run_harbor_tb2_m5.py").read_text(encoding="utf-8")
    bootstrap = source.index("sys.path.insert")
    adapter_import = source.index("from scripts import run_harbor_tb2_m4")
    assert bootstrap < adapter_import
    assert m5.TOP_20[-5:] == (
        "mcmc-sampling-stan",
        "git-multibranch",
        "portfolio-optimization",
        "modernize-scientific-stack",
        "distribution-search",
    )


def test_every_development_task_has_two_concrete_obligations():
    obligations = json.loads(m5.OBLIGATIONS_PATH.read_text(encoding="utf-8"))
    assert set(obligations) == set(m5.TOP_20)
    for task_id, audit in obligations.items():
        assert audit["task_form"]
        assert len(audit["obligations"]) == 2, task_id
        assert len({item["id"] for item in audit["obligations"]}) == 2
        assert all(item["description"] for item in audit["obligations"])
        assert audit["stability_risks"]


def test_parse_tasks_rejects_outside_registry():
    assert m5.parse_tasks("all") == list(m5.TOP_20)
    assert m5.parse_tasks("fix-code-vulnerability,git-multibranch") == [
        "fix-code-vulnerability", "git-multibranch"
    ]
    with pytest.raises(ValueError, match="outside M5 registry"):
        m5.parse_tasks("not-a-task")


def test_image_identity_does_not_pull_when_audit_only(monkeypatch):
    seen = []

    class Result:
        returncode = 1
        stdout = ""
        stderr = "missing"

    monkeypatch.setattr(
        m5, "task_config",
        lambda _: {"environment": {"docker_image": "repo/task:tag"}},
    )
    monkeypatch.setattr(
        m5, "docker",
        lambda args, timeout=600: seen.append(args) or Result(),
    )

    identity = m5.image_identity("task", pull=False)

    assert identity["available"] is False
    assert seen == [["image", "inspect", "repo/task:tag"]]


def test_pull_budget_is_bounded():
    assert m5.PULL_ATTEMPTS == 2
    assert m5.PULL_TIMEOUT_SEC == 300


def test_run_one_resumes_from_immutable_per_task_result(tmp_path, monkeypatch):
    destination = tmp_path / "ga" / "task--r1.json"
    destination.parent.mkdir(parents=True)
    expected = {"status": "completed", "reward": 0.0}
    destination.write_text(json.dumps(expected), encoding="utf-8")
    monkeypatch.setattr(m5, "result_path", lambda *_: destination)
    monkeypatch.setattr(
        m5, "task_preflight",
        lambda *_args, **_kwargs: pytest.fail("resume must not rerun preflight"),
    )

    assert m5.run_one("task", "ga", 1, 0, 900) == expected


def test_run_one_records_preflight_environment_failure(tmp_path, monkeypatch):
    destination = tmp_path / "oracle" / "task--r1.json"
    monkeypatch.setattr(m5, "result_path", lambda *_: destination)
    monkeypatch.setattr(
        m5, "task_preflight",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("failed to pull image: TLS timeout")
        ),
    )

    result = m5.run_one("task", "oracle", 1, 0, 900)

    assert result["status"] == "failed"
    assert result["failure_class"] == "environment_failure"
    assert result["source_identity"] is None
    assert json.loads(destination.read_text(encoding="utf-8"))["status"] == "failed"


def test_extended_ga_timeout_reaches_adapter_and_harbor_outer_phase(tmp_path, monkeypatch):
    destination = tmp_path / "ga" / "task--r1.json"
    captured = {}
    identity = {
        "m5": {
            "native_agent_timeout_sec": 3600,
            "native_verifier_timeout_sec": 120,
        }
    }

    monkeypatch.setattr(m5, "result_path", lambda *_: destination)
    monkeypatch.setattr(m5, "JOBS_ROOT", tmp_path / "jobs")
    monkeypatch.setattr(m5, "task_preflight", lambda *_args, **_kwargs: identity)
    monkeypatch.setenv("TB2_M5_ALLOW_EXTENDED_AGENT_TIMEOUT", "1")

    def fake_harbor_job(*args, **kwargs):
        captured.update(kwargs)
        return tmp_path / "jobs" / "run"

    monkeypatch.setattr(m5.m4, "harbor_job", fake_harbor_job)
    monkeypatch.setattr(m5.m4, "finalize_ga", lambda *_: {
        "reward": 1.0,
        "trace": {"span_count": 1},
        "trial_result": str(tmp_path / "result.json"),
    })
    (tmp_path / "result.json").write_text(
        json.dumps({"agent_result": {"metadata": {}}}), encoding="utf-8"
    )

    result = m5.run_one("task", "ga", 1, 0, 7200)

    assert captured["agent_timeout_sec"] == 7200
    assert captured["agent_timeout_multiplier"] == 2.0
    assert captured["launcher_timeout_sec"] == 8220
    assert result["status"] == "completed"


@pytest.mark.parametrize(("message", "expected"), [
    ("failed to pull image", "environment_failure"),
    ("agent timeout expired", "timeout"),
    ("custom import failed", "launcher_failure"),
])
def test_failure_classification_without_trial(message, expected):
    assert m5.classify_failure(RuntimeError(message), None) == expected


def test_failure_classification_reads_harbor_agent_timeout(tmp_path):
    trial = tmp_path / "task__trial"
    trial.mkdir()
    (trial / "exception.txt").write_text(
        "harbor.trial.errors.AgentTimeoutError: "
        "Agent execution timed out after 900.0 seconds",
        encoding="utf-8",
    )
    assert (
        m5.classify_failure(RuntimeError("M4 GA validation failed"), tmp_path)
        == "agent_timeout"
    )


def test_failure_classification_reads_harbor_verifier_timeout(tmp_path):
    trial = tmp_path / "task__trial"
    trial.mkdir()
    (trial / "exception.txt").write_text(
        "harbor.trial.errors.VerifierTimeoutError: "
        "Verifier execution timed out after 900.0 seconds",
        encoding="utf-8",
    )
    assert (
        m5.classify_failure(RuntimeError("M4 GA validation failed"), tmp_path)
        == "verifier_timeout"
    )


def test_refresh_results_is_deterministic(tmp_path, monkeypatch):
    smokes = tmp_path / "smokes"
    output = tmp_path / "results.jsonl"
    (smokes / "ga").mkdir(parents=True)
    (smokes / "oracle").mkdir()
    (smokes / "ga" / "b.json").write_text(
        json.dumps({"run_id": "b"}), encoding="utf-8"
    )
    (smokes / "oracle" / "a.json").write_text(
        json.dumps({"run_id": "a"}), encoding="utf-8"
    )
    monkeypatch.setattr(m5, "SMOKES_ROOT", smokes)
    monkeypatch.setattr(m5, "RESULTS_PATH", output)

    rows = m5.refresh_results()

    assert [row["run_id"] for row in rows] == ["b", "a"]
    assert len(m5.read_jsonl(output)) == 2


def test_selection_requires_and_records_runtime_evidence(tmp_path, monkeypatch):
    registry_path = tmp_path / "registry.jsonl"
    results_path = tmp_path / "results.jsonl"
    selected_path = tmp_path / "selected.jsonl"
    core_path = tmp_path / "core.jsonl"
    registry = []
    results = []
    for task_id in m5.FORMAL_12:
        registry.append({
            "source": {"task_id": task_id},
            "obligation_design": {"obligations": [{}, {}]},
            "horizon_evidence": {"qualification": "pending_smoke"},
        })
        results.extend([
            {
                "task_id": task_id, "mode": "oracle", "status": "completed",
                "reward": 1.0, "run_id": f"oracle-{task_id}",
            },
            {
                "task_id": task_id, "mode": "ga", "status": "completed",
                "reward": 0.0, "run_id": f"ga-{task_id}",
                "trace": {"span_count": 10, "sha256": task_id},
            },
        ])
    m5.write_jsonl(registry_path, registry)
    m5.write_jsonl(results_path, results)
    monkeypatch.setattr(m5, "REGISTRY_PATH", registry_path)
    monkeypatch.setattr(m5, "RESULTS_PATH", results_path)
    monkeypatch.setattr(m5, "SELECTED_PATH", selected_path)
    monkeypatch.setattr(m5, "CORE_PATH", core_path)

    selected, core = m5.select_candidates()

    assert len(selected) == 12
    assert len(core) == 6
    assert all(row["status"] == "accepted_source_candidate" for row in selected)
    assert all(row["m5_selection"]["grandfathered"] for row in selected)
    assert all(row["horizon_evidence"]["qualification"] == "pilot_observed"
               for row in selected)
