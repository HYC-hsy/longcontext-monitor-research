"""Research-only micro-run orchestration with an externally supplied continuation.

This module never creates a Supervisor context or restores a session. The
operator supplies both the context artifact and an explicit continuation
callback. No model call occurs when either is missing. The callback's raw
artifacts are archived; semantic ground handling is left to human audit.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Callable, Mapping

from .checkpoint import _json_bytes, _sha_file, verify_checkpoint
from .experiment_harness import run_offline_experiment


SCHEMA = "controlled-transition-micro-run/0"
_ID = re.compile(r"micro-[0-9]{2}\Z")
_ARTIFACT_KEYS = ("input_artifact", "output_artifact", "tool_calls_artifact",
                  "working_mutations_artifact", "provider_attempts_artifact")


def _write_json(path: Path, value) -> None:
    path.write_bytes(_json_bytes(value))


def _archive_continuation(root: Path, receipt: Mapping) -> dict:
    """Copy caller-produced raw files and record mechanical cost facts only."""
    if not isinstance(receipt, Mapping):
        raise ValueError("continuation callback must return an object")
    for key in ("model_identity", "model_calls", "usage", "duration_seconds"):
        if key not in receipt:
            raise ValueError(f"continuation receipt lacks {key}")
    if type(receipt["model_calls"]) is not int or receipt["model_calls"] < 0:
        raise ValueError("model_calls must be a nonnegative integer")
    if not isinstance(receipt["usage"], Mapping):
        raise ValueError("usage must be an object; unknown values may be null")
    if not isinstance(receipt["duration_seconds"], (int, float)) or receipt["duration_seconds"] < 0:
        raise ValueError("duration_seconds must be nonnegative")
    archived = {}
    for key in _ARTIFACT_KEYS:
        value = receipt.get(key)
        if value is None:
            archived[key] = {"status": "missing"}
            continue
        source = Path(value).resolve(strict=True)
        if not source.is_file():
            raise ValueError(f"{key} is not a file")
        destination = root / "supervisor" / f"{key}{source.suffix}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source != destination.resolve():
            shutil.copy2(source, destination)
        archived[key] = {"status": "available", "path": str(destination),
                         "sha256": _sha_file(destination), "bytes": destination.stat().st_size}
    summary = {"model_identity": receipt["model_identity"],
               "model_calls": receipt["model_calls"],
               "usage": dict(receipt["usage"]),
               "duration_seconds": receipt["duration_seconds"],
               "artifacts": archived}
    _write_json(root / "supervisor_continuation.json", summary)
    return summary


def _contains_text(value, needle: str) -> bool:
    if isinstance(value, str):
        return needle in value
    if isinstance(value, list):
        return any(_contains_text(item, needle) for item in value)
    if isinstance(value, dict):
        return any(_contains_text(item, needle) for item in value.values())
    return False


def _mechanical_facts(root: Path, experiment: Path, checkpoint: Path, summary: Mapping) -> dict:
    wtv = json.loads((experiment / "wtv_result.json").read_bytes())
    delta = wtv["after"]["audit"]
    facts = {"wtv_supplied_to_driver": True,
             "wtv_present_in_archived_input": None,
             "wtv_sample_complete": delta["sample_complete"],
             "added": delta["added"], "modified": delta["modified"],
             "deleted": delta["deleted"],
             "working_mutation_count": None, "working_max_chars": None,
             "field_like_headings": None, "tool_call_count": None,
             "tool_call_events": None,
             "semantic_ground_handling": "not_classified"}
    submitted = summary["artifacts"]["input_artifact"]
    if submitted["status"] == "available":
        raw = Path(submitted["path"]).read_text(encoding="utf-8")
        try:
            facts["wtv_present_in_archived_input"] = _contains_text(json.loads(raw), wtv["after"]["view"])
        except json.JSONDecodeError:
            facts["wtv_present_in_archived_input"] = wtv["after"]["view"] in raw
    baseline = (checkpoint / "epistemic" / "working.md").read_text(encoding="utf-8")
    facts["working_max_chars"] = len(baseline)
    working = summary["artifacts"]["working_mutations_artifact"]
    if working["status"] == "available":
        rows = [json.loads(line) for line in Path(working["path"]).read_text(encoding="utf-8").splitlines()
                if line.strip()]
        facts["working_mutation_count"] = len(rows)
        if all(isinstance(row, dict) and isinstance(row.get("content"), str) for row in rows):
            facts["working_max_chars"] = max([len(baseline)] + [len(row["content"]) for row in rows])
            headings = ("Contrast:", "Measurement:", "Basis:", "Transport:")
            facts["field_like_headings"] = {
                heading: sum(any(line.strip().startswith(heading) for line in text.splitlines())
                             for text in [baseline] + [row["content"] for row in rows])
                for heading in headings}
    tools = summary["artifacts"]["tool_calls_artifact"]
    if tools["status"] == "available":
        rows = [json.loads(line) for line in Path(tools["path"]).read_text(encoding="utf-8").splitlines()
                if line.strip()]
        facts["tool_call_count"] = len(rows)
        facts["tool_call_events"] = rows
    _write_json(root / "mechanism_facts.json", facts)
    return facts


def run_micro_case(*, case_id, checkpoint_dir, expected_checkpoint_id,
                   transition_source, transition_id, expected_source_sha256,
                   continuation_context, expected_context_sha256,
                   continuation_source, operator_claims_complete_recovery,
                   output_root, continuation_driver: Callable | None = None) -> Path:
    """Run one explicitly sourced micro case, or record why it cannot start.

    The callback receives only the operator's context path, the changed task
    workspace, the mechanical WTV text and an output directory. Research case
    labels, expected outcomes, checkpoint analysis and fixture source are not
    passed to it. This is *not* automatic same-Supervisor restoration.
    """
    if not isinstance(case_id, str) or not _ID.fullmatch(case_id):
        raise ValueError("case_id must use a neutral micro-00 identity")
    parent = Path(output_root).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    root = parent / case_id
    root.mkdir()  # no rerun over an existing attempt
    record = {"schema": SCHEMA, "case_id": case_id, "status": "preflight",
              "checkpoint_id": expected_checkpoint_id, "transition_id": transition_id,
              "model_calls_recorded": 0, "started_at_epoch": time.time()}
    _write_json(root / "micro_run.json", record)
    try:
        checkpoint_path = Path(checkpoint_dir).resolve(strict=True)
        verified = verify_checkpoint(checkpoint_path)
        if verified["checkpoint_id"] != expected_checkpoint_id:
            raise ValueError("checkpoint identity mismatch")
        binding = json.loads((checkpoint_path / "binding.json").read_bytes())
        _write_json(root / "checkpoint_identity.json", {
            "checkpoint_id": expected_checkpoint_id,
            "task_identity": binding["task_identity"],
            "source_identity": binding["source_identity"],
            "public_cursor": binding["public_cursor"],
            "task_turn": binding["task_turn"],
            "history_sha256": binding["history_sha256"],
            "working_sha256": binding["working_sha256"],
            "workspace_manifest_sha256": binding["workspace_manifest_sha256"],
            "binding_sha256": _sha_file(checkpoint_path / "binding.json"),
        })
        if not continuation_source or not isinstance(continuation_source, str):
            raise ValueError("continuation source is required")
        if continuation_context is None or continuation_driver is None:
            raise ValueError("continuation context and explicit driver are required")
        context_path = Path(continuation_context).resolve(strict=True)
        if not context_path.is_file():
            raise ValueError("continuation context is not a file")
        context_hash = _sha_file(context_path)
        if context_hash != expected_context_sha256:
            raise ValueError("continuation context hash mismatch")
        _write_json(root / "continuation_source.json", {
            "source": continuation_source, "context_path": str(context_path),
            "context_sha256": context_hash,
            "operator_claims_complete_recovery": operator_claims_complete_recovery is True,
            "runner_verified_complete_recovery": False,
            "limitation": "This runner cannot prove or perform same-Supervisor resume.",
        })
        experiment = run_offline_experiment(
            checkpoint_dir=checkpoint_path, transition_source=transition_source,
            transition_id=transition_id, expected_source_sha256=expected_source_sha256,
            expected_checkpoint_id=expected_checkpoint_id,
            experiment_id="mechanical-prefix", output_root=root / "experiments",
            supervisor_session_ref={"status": "operator_context_reference_only",
                                    "context_sha256": context_hash})
        _write_json(root / "mechanical_ref.json", {
            "experiment_path": str(experiment),
            "checkpoint_ref_sha256": _sha_file(experiment / "checkpoint_ref.json"),
            "transition_ref_sha256": _sha_file(experiment / "transition_ref.json"),
            "wtv_result_sha256": _sha_file(experiment / "wtv_result.json"),
        })
        wtv = json.loads((experiment / "wtv_result.json").read_bytes())
        view = wtv["after"]["view"]
        record["status"] = "awaiting_explicit_continuation"
        record["model_calls_recorded"] = None
        _write_json(root / "micro_run.json", record)
        output = root / "supervisor"
        output.mkdir()
        receipt = continuation_driver(context_path=context_path,
                                      workspace_path=experiment / "transitions" / transition_id / "workspace",
                                      wtv_view=view, output_dir=output)
        summary = _archive_continuation(root, receipt)
        _mechanical_facts(root, experiment, checkpoint_path, summary)
        record["model_calls_recorded"] = summary["model_calls"]
        record["status"] = "completed_with_operator_continuation"
        record["ended_at_epoch"] = time.time()
        _write_json(root / "micro_run.json", record)
        return root
    except Exception as exc:
        record["status"] = ("incomplete" if (root / "experiments" / "mechanical-prefix").exists()
                            else "not_started")
        record["error_type"] = type(exc).__name__
        record["reason"] = str(exc)
        record["ended_at_epoch"] = time.time()
        _write_json(root / "micro_run.json", record)
        raise
