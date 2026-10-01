"""Three synthetic micro cases with a fake continuation callback (zero models)."""

import hashlib
import json
from pathlib import Path

import pytest

from method_discovery.diagnostics.epistemic_checkpoint_v0.micro_runner import run_micro_case
from method_discovery.diagnostics.epistemic_checkpoint_v0.test_experiment_harness import (
    DEFINITIONS, _checkpoint, _source,
)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _fake_driver(observed):
    def invoke(*, context_path, workspace_path, wtv_view, output_dir):
        observed.append({"context": Path(context_path), "workspace": Path(workspace_path),
                         "view": wtv_view, "output": Path(output_dir)})
        assert "micro-" not in wtv_view
        assert "related" not in wtv_view
        artifacts = {}
        for key, content in {
            "input_artifact": json.dumps({"context": Path(context_path).read_text(), "wtv": wtv_view}),
            "output_artifact": "synthetic response; no model was called\n",
            "tool_calls_artifact": json.dumps({"tool": "file_read", "path": "task/workspace/source.go"}) + "\n",
            "working_mutations_artifact": json.dumps({"content": "Scoped current ground.\n"}) + "\n",
            "provider_attempts_artifact": "",
        }.items():
            path = Path(output_dir) / (key + ".jsonl")
            path.write_text(content, encoding="utf-8")
            artifacts[key] = path
        return {"model_identity": "fake-transport-no-model", "model_calls": 0,
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "duration_seconds": 0.01, **artifacts}
    return invoke


def _run(tmp_path, definition, driver, **overrides):
    checkpoint = _checkpoint(tmp_path, definition)
    source, source_hash = _source(tmp_path, definition)
    context = tmp_path / "operator-context.json"
    context.write_text('{"normal_context":"synthetic"}\n', encoding="utf-8")
    arguments = {
        "case_id": "micro-01", "checkpoint_dir": checkpoint,
        "expected_checkpoint_id": "checkpoint-1",
        "transition_source": source, "transition_id": "transition-1",
        "expected_source_sha256": source_hash,
        "continuation_context": context, "expected_context_sha256": _sha(context),
        "continuation_source": "operator-supplied synthetic context",
        "operator_claims_complete_recovery": False,
        "output_root": tmp_path / "micro-runs", "continuation_driver": driver,
    }
    arguments.update(overrides)
    return arguments, checkpoint


@pytest.mark.parametrize("definition", DEFINITIONS, ids=lambda row: row["id"])
def test_three_synthetic_micro_cases(tmp_path, definition):
    observed = []
    arguments, checkpoint = _run(tmp_path, definition, _fake_driver(observed))
    original_binding = (checkpoint / "binding.json").read_bytes()
    root = run_micro_case(**arguments)
    run = json.loads((root / "micro_run.json").read_text())
    assert run["status"] == "completed_with_operator_continuation"
    assert run["model_calls_recorded"] == 0
    assert len(observed) == 1
    assert (checkpoint / "binding.json").read_bytes() == original_binding
    identity = json.loads((root / "checkpoint_identity.json").read_text())
    assert identity["checkpoint_id"] == "checkpoint-1"
    assert identity["history_sha256"] and identity["workspace_manifest_sha256"]
    mechanical = root / "experiments/mechanical-prefix"
    wtv = json.loads((mechanical / "wtv_result.json").read_text())
    assert wtv["after"]["audit"]["modified"] == definition["expected_modified"]
    assert observed[0]["view"] == wtv["after"]["view"]
    continuation = json.loads((root / "continuation_source.json").read_text())
    assert continuation["runner_verified_complete_recovery"] is False
    facts = json.loads((root / "mechanism_facts.json").read_text())
    assert facts["modified"] == definition["expected_modified"]
    assert facts["working_mutation_count"] == 1
    assert facts["working_max_chars"] == max(len("Current focal understanding.\n"),
                                             len("Scoped current ground.\n"))
    assert facts["field_like_headings"]["Contrast:"] == 0
    assert facts["wtv_present_in_archived_input"] is True
    assert facts["tool_call_events"][0]["tool"] == "file_read"
    assert facts["semantic_ground_handling"] == "not_classified"
    assert json.loads((root / "supervisor_continuation.json").read_text())["model_calls"] == 0


def test_missing_context_does_not_invoke_driver_or_patch(tmp_path):
    observed = []
    arguments, _ = _run(tmp_path, DEFINITIONS[0], _fake_driver(observed), continuation_context=None)
    with pytest.raises(ValueError, match="context and explicit driver"):
        run_micro_case(**arguments)
    root = tmp_path / "micro-runs/micro-01"
    assert json.loads((root / "micro_run.json").read_text())["status"] == "not_started"
    assert not (root / "experiments").exists()
    assert observed == []


def test_missing_checkpoint_does_not_invoke_driver(tmp_path):
    observed = []
    arguments, _ = _run(tmp_path, DEFINITIONS[0], _fake_driver(observed),
                        checkpoint_dir=tmp_path / "missing-checkpoint")
    with pytest.raises(FileNotFoundError):
        run_micro_case(**arguments)
    assert json.loads((tmp_path / "micro-runs/micro-01/micro_run.json").read_text(encoding="utf-8"))["status"] == "not_started"
    assert observed == []


def test_fixture_source_mismatch_preserves_failure_without_driver(tmp_path):
    observed = []
    arguments, _ = _run(tmp_path, DEFINITIONS[0], _fake_driver(observed),
                        expected_source_sha256="0" * 64)
    with pytest.raises(ValueError, match="source hash mismatch"):
        run_micro_case(**arguments)
    root = tmp_path / "micro-runs/micro-01"
    assert json.loads((root / "micro_run.json").read_text(encoding="utf-8"))["status"] == "incomplete"
    assert json.loads((root / "experiments/mechanical-prefix/transitions/transition-1/end.json")
                      .read_text(encoding="utf-8"))["status"] == "failed"
    assert observed == []


def test_continuation_failure_preserves_mechanical_prefix_and_unknown_usage(tmp_path):
    def failing_driver(**_kwargs):
        raise RuntimeError("synthetic continuation failure after possible request")

    arguments, _ = _run(tmp_path, DEFINITIONS[0], failing_driver)
    with pytest.raises(RuntimeError, match="synthetic continuation failure"):
        run_micro_case(**arguments)
    root = tmp_path / "micro-runs/micro-01"
    record = json.loads((root / "micro_run.json").read_text())
    assert record["status"] == "incomplete"
    assert record["model_calls_recorded"] is None
    assert (root / "mechanical_ref.json").is_file()
    assert (root / "experiments/mechanical-prefix/wtv_result.json").is_file()


def test_neutral_id_and_no_case_label_in_callback(tmp_path):
    with pytest.raises(ValueError, match="neutral"):
        run_micro_case(case_id="related-change", checkpoint_dir="unused",
                       expected_checkpoint_id="unused", transition_source="unused",
                       transition_id="unused", expected_source_sha256="unused",
                       continuation_context="unused", expected_context_sha256="unused",
                       continuation_source="unused", operator_claims_complete_recovery=False,
                       output_root=tmp_path, continuation_driver=lambda **_: None)
