"""Offline checkpoint -> content fixture -> WTV research orchestration.

The archived WTV text is never sent to a model. No Supervisor/Task resume or
semantic transport is attempted here.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Mapping

from .checkpoint import _json_bytes, _sha_file, verify_checkpoint
from .transition_fixture import apply_transition_fixture


SCHEMA = "controlled-transition-experiment/0"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_RUNTIME = Path(__file__).resolve().parents[3] / "GenericAgent-main" / "monitor_agent_core" / "runtime.py"


def _write_json(path: Path, value) -> None:
    path.write_bytes(_json_bytes(value))


def _sampler_class():
    """Load the frozen WTV implementation without starting MonitorRuntime."""
    name = "_offline_research_wtv_runtime"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, _RUNTIME)
        if spec is None or spec.loader is None:
            raise RuntimeError("WTV runtime source cannot be loaded")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            del sys.modules[name]
            raise
    return sys.modules[name].WorkspaceTransitionSampler


def run_offline_experiment(*, checkpoint_dir, transition_source, transition_id,
                           expected_source_sha256, expected_checkpoint_id,
                           experiment_id, output_root, supervisor_session_ref=None) -> Path:
    """Archive one deterministic experiment prefix, without continuation.

    The before sample is taken on the *independent copied workspace*, after
    checkpoint verification and before the fixture's first write. Sampling
    only after the transition would establish a new baseline and lose the
    intended delta. A supplied Supervisor reference is archived, not used.
    """
    if not isinstance(experiment_id, str) or not _ID.fullmatch(experiment_id):
        raise ValueError("experiment_id must be one safe path component")
    if supervisor_session_ref is not None and not isinstance(supervisor_session_ref, Mapping):
        raise ValueError("supervisor_session_ref must be an object or null")
    checkpoint = Path(checkpoint_dir).resolve(strict=True)
    parent = Path(output_root).resolve()
    if parent == checkpoint or parent.is_relative_to(checkpoint):
        raise ValueError("experiment output must be outside the checkpoint")
    parent.mkdir(parents=True, exist_ok=True)
    root = parent / experiment_id
    root.mkdir()  # unique attempt; do not overwrite success or failure
    record = {"schema": SCHEMA, "experiment_id": experiment_id, "status": "initializing",
              "checkpoint_id": expected_checkpoint_id, "transition_id": transition_id,
              "supervisor_continuation": "not_run",
              "limitation": "No Supervisor restore or resume is implemented."}
    _write_json(root / "metadata.json", record)
    sampler = None
    baseline = None
    transition_path = root / "transitions" / transition_id
    try:
        checkpoint_info = verify_checkpoint(checkpoint)
        if checkpoint_info["checkpoint_id"] != expected_checkpoint_id:
            raise ValueError("checkpoint identity mismatch")
        binding = json.loads((checkpoint / "binding.json").read_bytes())
        cursor, turn = binding["public_cursor"], binding["task_turn"]
        _write_json(root / "checkpoint_ref.json", {
            "checkpoint_id": expected_checkpoint_id, "checkpoint_path": str(checkpoint),
            "binding_sha256": _sha_file(checkpoint / "binding.json"),
            "workspace_manifest_sha256": binding["workspace_manifest_sha256"],
            "task_identity": binding["task_identity"],
            "source_identity": binding["source_identity"],
            "public_cursor": cursor, "task_turn": turn,
        })
        session = (dict(supervisor_session_ref) if supervisor_session_ref is not None
                   else {"status": "unavailable", "limitation": "Operator supplied no continuation environment."})
        _write_json(root / "supervisor_session_ref.json", session)
        sampler = _sampler_class()()

        def before_apply(workspace, before_manifest):
            nonlocal baseline
            view, audit = sampler.sample(workspace, cursor=cursor, task_turn=turn)
            baseline = {"view": view, "audit": audit,
                        "workspace_manifest_sha256": binding["workspace_manifest_sha256"]}
            _write_json(root / "wtv_before.json", baseline)
            if not audit["initial_baseline"] or not audit["sample_complete"]:
                raise ValueError("WTV before sample is incomplete")

        transition = apply_transition_fixture(
            checkpoint_dir=checkpoint, transition_source=transition_source,
            transition_id=transition_id, expected_source_sha256=expected_source_sha256,
            expected_checkpoint_id=expected_checkpoint_id,
            output_root=root / "transitions", before_apply=before_apply)
        _write_json(root / "transition_ref.json", {
            "transition_id": transition_id, "transition_path": str(transition),
            "transition_record_sha256": _sha_file(transition / "transition.json"),
            "before_workspace_manifest_sha256": _sha_file(transition / "before_manifest.json"),
            "after_workspace_manifest_sha256": _sha_file(transition / "after_manifest.json"),
            "source_sha256": expected_source_sha256, "status": "complete",
        })
        view, audit = sampler.sample(transition / "workspace", cursor=cursor, task_turn=turn)
        _write_json(root / "wtv_result.json", {
            "schema": SCHEMA, "before": baseline, "after": {"view": view, "audit": audit},
            "cursor_did_not_advance": True,
            "note": "This controlled file transition created no Task public event.",
            "wtv_runtime_sha256": _sha_file(_RUNTIME),
        })
        if not audit["sample_complete"]:
            raise ValueError("WTV after sample is incomplete")
        record["status"] = "complete"
        _write_json(root / "metadata.json", record)
        return root
    except Exception as exc:
        if transition_path.is_dir():
            try:
                transition_record = json.loads((transition_path / "transition.json").read_bytes())
                _write_json(root / "transition_ref.json", {
                    "transition_id": transition_id, "transition_path": str(transition_path),
                    "status": transition_record.get("status", "unknown"),
                    "transition_record_sha256": _sha_file(transition_path / "transition.json"),
                })
                if baseline is not None and (transition_path / "workspace").is_dir() and sampler is not None:
                    view, audit = sampler.sample(transition_path / "workspace", cursor=cursor, task_turn=turn)
                    _write_json(root / "wtv_result.json", {
                        "schema": SCHEMA, "before": baseline,
                        "after_failure": {"view": view, "audit": audit},
                        "note": "Transition did not complete; this delta is partial evidence only.",
                        "wtv_runtime_sha256": _sha_file(_RUNTIME),
                    })
            except Exception:
                pass  # Preserve the primary failure and any raw fixture artifact.
        record["status"] = "failed"
        record["error_type"] = type(exc).__name__
        record["reason"] = str(exc)
        _write_json(root / "metadata.json", record)
        raise
