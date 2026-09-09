"""Run representative Natural GA proofs for the two M12 ultralong sources."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import prepare_harbor_lhtb_m12 as continuation_patch  # noqa: E402
from scripts import prepare_harbor_lhtb_structured_pass_m12 as pass_patch  # noqa: E402
from scripts import prepare_harbor_windows_sidecar_m12 as sidecar_patch  # noqa: E402
from scripts import run_harbor_tb2_m4 as m4  # noqa: E402
from scripts.m11_trajectory_validation import (  # noqa: E402
    fatal_agent_output,
    terminal_agent_error,
)


WORK_ROOT = Path(os.environ.get(
    "BENCHMARK_CAMPAIGN_ROOT",
    ROOT / "output" / "m12_proofs" / "natural_ga",
))
JOBS_ROOT = WORK_ROOT / "jobs"
RUNS_ROOT = WORK_ROOT / "runs"
OTEL_ROOT = WORK_ROOT / "otel"
COLLECTOR_NAME = "m12-natural-ga-otel"
COLLECTOR_PORT = 15340

MANIFEST_ENV_KEYS = {"BENCHMARK_CAMPAIGN_ROOT"}
MANIFEST_CONTROLLED_ENV_KEYS = {
    "GA_MONITOR_GROUNDED_CONTEXT",
    "BENCHMARK_CAMPAIGN_ROOT",
    "GA_BASELINE_CONDITION", "GA_EXPERIMENT_ID", "GA_CONDITION_ID",
    "GA_LLM_CONFIG_NAME", "GA_MAX_TURNS", "GA_PROVIDER_MAX_RETRIES",
    "GA_METHOD_EXPECTED_SOURCE_SHA256", "GA_EXPERIMENT_HARNESS_SHA256",
    "GA_MONITOR_ENABLED", "GA_MONITOR_CONFIG", "GA_MONITOR_EXPECTED_MODEL",
    "GA_M0_MONITOR_ENABLED", "GA_M0_MONITOR_CONFIG",
    "GA_M0_MONITOR_EXPECTED_MODEL", "GA_M0_MAX_INSPECTIONS",
    "GA_M0_RECENT_TRAJECTORY_TURNS", "GA_MONITOR_REQUEST_TIMEOUT_SECONDS",
    "GA_M3_HUMAN_LOOP_ENABLED",
    "GA_M3_DECISION_VALUE_ENABLED", "GA_M3_DISCRIMINATIVE_CONTROL_ENABLED",
    "GA_M3_COMBINED_CONTROL_ENABLED",
    "GA_MONITOR_HISTORY_SOFT_CHAR_LIMIT", "GA_MONITOR_HISTORY_TARGET_CHARACTERS",
    "GA_MANUAL_COMPLETION_ENABLED", "GA_MANUAL_COMPLETION_TIMEOUT_SECONDS",
    "GA_TASK_CARD_PATH", "GA_OBLIGATION_LEDGER_CARD_PATH",
    "GA_STAGE6D_BUNDLE_DIR", "GA_EVIDENCE_STATE_PATH",
    "GA_COMPLETION_CONTRACT_PATH", "GA_PUBLIC_TASK_PATH",
    "GA_EVIDENCE_FRONTEND_CONFIG", "GA_EVIDENCE_GATE_MODE",
    "GA_REPRESENTATION_AUDIT_CARD_PATH", "GA_REPRESENTATION_AUDIT_CONFIG",
    "GA_COMPLETION_BRANCH_CHECKPOINT",
    "GA_COMPLETION_BRANCH_BUNDLE", "GA_COMPLETION_BRANCH_POLICY",
    "GA_COMPLETION_CHECKPOINT_ROOT", "GA_KEEP_HARBOR_ENV",
}
EXECUTION_HARNESS_FILES = (
    "scripts/run_ultralong_m12_proofs.py",
    "scripts/run_harbor_tb2_m4.py",
    "scripts/prepare_harbor_lhtb_m12.py",
    "scripts/prepare_harbor_lhtb_structured_pass_m12.py",
    "scripts/prepare_harbor_windows_sidecar_m12.py",
    "scripts/m11_trajectory_validation.py",
    "adapters/harbor_ga_agent.py",
    "adapters/harbor_ga_lhtb.py",
)

SOURCES = {
    "lhtb": {
        "representative_task_id": "grammar-fuzz-coverage-hunt",
        "task_root": ROOT / ".cache" / "m12_lhtb_repo" / "tasks",
        "proposal": ROOT / "tasks" / "ultralong_m12_lhtb_proposal.jsonl",
        "adapter": "adapters.harbor_ga_lhtb:HarborLHTBGenericAgent",
        "persistent_session": True,
    },
    "roadmapbench": {
        "representative_task_id": "tpl-4.0.0-roadmap",
        "task_root": ROOT / ".cache" / "m12_roadmap_tasks",
        "proposal": ROOT
        / "tasks"
        / "ultralong_m12_roadmapbench_proposal.jsonl",
        "adapter": "adapters.harbor_ga_agent:HarborGenericAgent",
        "persistent_session": False,
    },
}


def execution_harness_hash() -> str:
    digest = hashlib.sha256()
    for relative in EXECUTION_HARNESS_FILES:
        data = (ROOT / relative).read_bytes()
        encoded = relative.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def apply_experiment_manifest(path: str | os.PathLike[str], run_id: str) -> dict[str, Any]:
    """Load one frozen, secret-free run environment without a shell wrapper."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("secrets_included") is not False:
        raise ValueError("experiment manifest must explicitly exclude secrets")
    runs = payload.get("runs")
    if not isinstance(runs, list):
        raise ValueError("experiment manifest runs must be a list")
    matches = [row for row in runs
               if isinstance(row, Mapping) and row.get("run_id") == run_id]
    if len(matches) != 1:
        raise ValueError(f"experiment manifest must contain exactly one run {run_id!r}")
    selected = dict(matches[0])
    environment = selected.get("environment")
    if not isinstance(environment, Mapping):
        raise ValueError("selected manifest run has no environment mapping")
    normalized_environment: dict[str, str] = {}
    for key, value in environment.items():
        name = str(key)
        if not (name.startswith("GA_") or name in MANIFEST_ENV_KEYS):
            raise ValueError(f"manifest environment key is not allowlisted: {name}")
        upper = name.upper()
        if any(marker in upper for marker in ("KEY", "TOKEN", "SECRET", "AUTH")):
            raise ValueError(f"secret-like manifest environment key is forbidden: {name}")
        normalized_environment[name] = str(value)
    expected_harness = str(
        normalized_environment.get("GA_EXPERIMENT_HARNESS_SHA256", "")
    ).strip().lower()
    if expected_harness:
        actual_harness = execution_harness_hash()
        if expected_harness != actual_harness:
            raise RuntimeError(
                "experiment execution harness mismatch: "
                f"expected {expected_harness}, got {actual_harness}"
            )
    # A manifest condition is a complete experimental assignment, not a patch
    # over whichever candidate happened to run previously in this process.
    # Validate first, then remove only experiment-owned keys and apply once.
    for name in MANIFEST_CONTROLLED_ENV_KEYS:
        os.environ.pop(name, None)
    os.environ.update(normalized_environment)

    # These roots were initialized at import time. Rebind them after applying
    # the manifest and before preflight configures the shared Harbor runner.
    global WORK_ROOT, JOBS_ROOT, RUNS_ROOT, OTEL_ROOT
    WORK_ROOT = Path(os.environ.get(
        "BENCHMARK_CAMPAIGN_ROOT", ROOT / "output" / "m12_proofs" / "natural_ga"
    ))
    JOBS_ROOT = WORK_ROOT / "jobs"
    RUNS_ROOT = WORK_ROOT / "runs"
    OTEL_ROOT = WORK_ROOT / "otel"
    return selected


def stage4_agent_kwargs() -> dict[str, object]:
    """Forward only frozen, non-secret experiment inputs."""
    condition = os.environ.get("GA_BASELINE_CONDITION")
    if not condition:
        return {}
    if condition not in {"original", "always_visible_task", "static_checklist", "oracle_evidence_gate"}:
        raise ValueError(f"unsupported GA_BASELINE_CONDITION: {condition}")
    values: dict[str, object] = {
        "baseline_condition": condition,
        "experiment_id": os.environ.get("GA_EXPERIMENT_ID", ""),
        "condition_id": os.environ.get("GA_CONDITION_ID", condition),
        "llm_config_name": os.environ.get("GA_LLM_CONFIG_NAME", ""),
        "max_turns": int(os.environ.get("GA_MAX_TURNS", "180")),
    }
    if os.environ.get("GA_MANUAL_COMPLETION_ENABLED") == "1":
        values["manual_completion_dir"] = "/logs/agent/manual_completion"
        values["manual_completion_timeout_seconds"] = float(
            os.environ.get("GA_MANUAL_COMPLETION_TIMEOUT_SECONDS", "300")
        )
    if os.environ.get("GA_MONITOR_ENABLED") == "1":
        monitor_config = os.environ.get("GA_MONITOR_CONFIG", "")
        if not monitor_config:
            raise ValueError("GA_MONITOR_CONFIG is required when the clean Monitor is enabled")
        values["monitor_enabled"] = True
        values["monitor_config"] = monitor_config
    if os.environ.get("GA_M0_MONITOR_ENABLED") == "1":
        monitor_config = os.environ.get("GA_M0_MONITOR_CONFIG", "")
        if not monitor_config:
            raise ValueError("GA_M0_MONITOR_CONFIG is required when M0 is enabled")
        values["m0_monitor_enabled"] = True
        values["m0_monitor_config"] = monitor_config
        values["m0_max_inspections"] = int(os.environ.get("GA_M0_MAX_INSPECTIONS", "8"))
        values["m0_recent_trajectory_turns"] = int(
            os.environ.get("GA_M0_RECENT_TRAJECTORY_TURNS", "0")
        )
        if os.environ.get("GA_M3_HUMAN_LOOP_ENABLED") == "1":
            values["m3_human_loop_enabled"] = True
        if os.environ.get("GA_M3_DECISION_VALUE_ENABLED") == "1":
            values["m3_decision_value_enabled"] = True
        if os.environ.get("GA_M3_DISCRIMINATIVE_CONTROL_ENABLED") == "1":
            values["m3_discriminative_control_enabled"] = True
        if os.environ.get("GA_M3_COMBINED_CONTROL_ENABLED") == "1":
            values["m3_combined_control_enabled"] = True
    card_path = os.environ.get("GA_TASK_CARD_PATH")
    if condition == "static_checklist":
        if not card_path:
            raise ValueError("static_checklist requires GA_TASK_CARD_PATH")
        card = Path(card_path).read_bytes()
        values["task_card_b64"] = base64.b64encode(card).decode("ascii")
    ledger_path = os.environ.get("GA_OBLIGATION_LEDGER_CARD_PATH")
    if condition == "oracle_evidence_gate":
        if not ledger_path:
            raise ValueError("evidence_gate requires GA_OBLIGATION_LEDGER_CARD_PATH")
        ledger_card = Path(ledger_path).read_bytes()
        values["obligation_ledger_card_b64"] = base64.b64encode(ledger_card).decode("ascii")
    bundle_dir = os.environ.get("GA_STAGE6D_BUNDLE_DIR")
    evidence_paths = {
        "evidence_state_b64": os.environ.get("GA_EVIDENCE_STATE_PATH"),
        "completion_contract_b64": os.environ.get("GA_COMPLETION_CONTRACT_PATH"),
        "public_task_b64": os.environ.get("GA_PUBLIC_TASK_PATH"),
    }
    if bundle_dir:
        bundle = Path(bundle_dir)
        required = [
            bundle / "evidence_state.json", bundle / "completion_contract.json",
            bundle / "public_task.txt",
        ]
        if not all(path.is_file() for path in required):
            raise ValueError("Stage 6D bundle is incomplete")
        values["evidence_bundle_dir"] = "/opt/stage6d-bundle"
        values["evidence_frontend_config"] = os.environ.get(
            "GA_EVIDENCE_FRONTEND_CONFIG", ""
        )
        values["evidence_gate_mode"] = os.environ.get("GA_EVIDENCE_GATE_MODE", "")
    elif any(evidence_paths.values()):
        if not all(evidence_paths.values()):
            raise ValueError("Stage 6D requires state, contract, and public task together")
        for key, path in evidence_paths.items():
            values[key] = base64.b64encode(Path(path).read_bytes()).decode("ascii")
        values["evidence_frontend_config"] = os.environ.get(
            "GA_EVIDENCE_FRONTEND_CONFIG", ""
        )
        values["evidence_gate_mode"] = os.environ.get("GA_EVIDENCE_GATE_MODE", "")
    checkpoint_dir = os.environ.get("GA_COMPLETION_BRANCH_CHECKPOINT")
    branch_bundle = os.environ.get("GA_COMPLETION_BRANCH_BUNDLE")
    branch_policy = os.environ.get("GA_COMPLETION_BRANCH_POLICY")
    if checkpoint_dir or branch_policy or branch_bundle:
        supported_branch_policies = {
            "K4", "K5", "K5M2", "I0", "I1", "I2",
            "A0_ATOMIC", "A1_PRIORITY", "A2_RESIDUAL",
            "A3_PRIORITY_RESIDUAL",
        }
        if (not checkpoint_dir or not branch_bundle
                or branch_policy not in supported_branch_policies):
            raise ValueError("Completion branch requires checkpoint, bundle, and a supported policy")
        values["completion_branch_checkpoint"] = "/opt/completion-checkpoint"
        values["completion_branch_bundle"] = "/opt/completion-branch"
        values["completion_branch_policy"] = branch_policy
    return values


def expected_otel_models(primary_model: str) -> list[str]:
    """Return the pre-registered allowed model set for this proof condition."""
    models = {primary_model.lower()}
    if os.environ.get("GA_MONITOR_ENABLED") == "1":
        monitor_model = os.environ.get("GA_MONITOR_EXPECTED_MODEL", "").strip().lower()
        if not monitor_model:
            raise ValueError(
                "GA_MONITOR_EXPECTED_MODEL is required for Monitor OTel identity validation"
            )
        models.add(monitor_model)
    return sorted(models)


def otel_models_match(observed: list[str], primary_model: str) -> bool:
    """Require the task model and reject models outside the registered set.

    The monitor may use a provider path that is not OTel-instrumented, so its
    registered model is allowed but is not required to appear in the archive.
    """
    primary = primary_model.lower()
    observed_set = {item.lower() for item in observed}
    allowed = set(expected_otel_models(primary))
    return primary in observed_set and observed_set <= allowed


def no_checker_leakage_errors(
    metadata: dict[str, Any], outputs: list[str]
) -> list[str]:
    """Reject Monitor evidence containing native-verifier information online."""
    if not online_checker_forbidden():
        return []
    errors = []
    forbidden_metadata = {
        "interim_verifier_rewards", "interim_verifier_result",
        "verifier_feedback", "native_verifier_feedback",
    }
    leaked_keys = sorted(forbidden_metadata & set(metadata))
    if leaked_keys:
        errors.append(
            "online checker metadata leaked into Monitor: " + ", ".join(leaked_keys)
        )
    forbidden_text = (
        "INTERIM VERIFICATION DID NOT PASS",
        "Interim verifier result:",
        "until the verifier passes",
    )
    if any(marker in output for marker in forbidden_text for output in outputs):
        errors.append("online checker feedback leaked into the public Agent trajectory")
    return errors


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def proposal_rows(source: str) -> list[dict[str, Any]]:
    config = SOURCES[source]
    return [
        json.loads(line)
        for line in config["proposal"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def proposal_row(source: str, task_id: str | None = None) -> dict[str, Any]:
    selected = task_id or SOURCES[source]["representative_task_id"]
    for row in proposal_rows(source):
        if row["source_task_id"] == selected:
            return row
    raise RuntimeError(f"task is not in the frozen {source} proposal: {selected}")


def task_path(source: str, task_id: str) -> Path:
    return SOURCES[source]["task_root"] / task_id


def online_checker_forbidden() -> bool:
    """Return whether this run must keep native verification strictly post-run."""
    return os.environ.get("GA_MONITOR_ENABLED") == "1"


def validate_expected_ga_source(actual_hash: str) -> None:
    """Fail before launch when the manifest no longer names this GA tree."""
    expected = os.environ.get("GA_METHOD_EXPECTED_SOURCE_SHA256", "").strip().lower()
    if expected and actual_hash.lower() != expected:
        raise RuntimeError(
            f"GA source mismatch: expected {expected}, got {actual_hash.lower()}"
        )


def materialize_execution_task(
    source: str, task_id: str, run_id: str
) -> Path:
    """Create the Monitor execution copy that disables LHTB verifier-feedback loops.

    Harbor still runs the task's native verifier once after the agent phase.  The
    copied task prevents ``continue_until_timeout`` from running that verifier
    online and feeding its reward back to the task Agent and Monitor.
    """
    original = task_path(source, task_id)
    if source != "lhtb" or not online_checker_forbidden():
        return original

    execution = WORK_ROOT / "execution_tasks" / run_id / task_id
    if execution.exists():
        raise RuntimeError(f"immutable execution task already exists: {execution}")
    shutil.copytree(original, execution)
    config_path = execution / "task.toml"
    source_text = config_path.read_text(encoding="utf-8")
    enabled = "continue_until_timeout = true"
    if source_text.count(enabled) != 1:
        raise RuntimeError(
            "Monitor no-checker isolation requires exactly one enabled "
            "continue_until_timeout setting"
        )
    config_path.write_text(
        source_text.replace(enabled, "continue_until_timeout = false"),
        encoding="utf-8",
    )
    return execution


def configure_m4() -> None:
    m4.WORK_ROOT = WORK_ROOT
    m4.JOBS_ROOT = JOBS_ROOT
    m4.RUNS_ROOT = RUNS_ROOT
    m4.OTEL_ROOT = OTEL_ROOT
    m4.COLLECTOR_NAME = COLLECTOR_NAME
    m4.COLLECTOR_PORT = COLLECTOR_PORT


def image_identity(row: dict[str, Any]) -> dict[str, Any]:
    expected = row["proposal"]["image"]
    tag = row["docker_image"]
    raw = m4.checked(["docker", "image", "inspect", tag], 60)
    image = json.loads(raw)[0]
    if image["Id"] != expected["digest"]:
        raise RuntimeError(
            f"image mismatch for {tag}: {image['Id']} != {expected['digest']}"
        )
    return {
        "tag": tag,
        "image_id": image["Id"],
        "expected_digest": expected["digest"],
        "architecture": image["Architecture"],
        "os": image["Os"],
    }


def resolve_agent_hosts(llm_no: int) -> list[str]:
    py_home = m4.python_home()
    python_bin = f"/opt/m4-runtime/python/{py_home.name}/bin/python3.12"
    site = "/opt/m4-runtime/ga-env/lib/python3.12/site-packages"
    resolver = (
        "import json,os;from urllib.parse import urlparse;"
        "from agentmain import GenericAgent;"
        "a=GenericAgent();a.next_llm(int(os.environ['M12_LLM_NO']));"
        "b=a.llmclient.backend;"
        "vals=[getattr(b,'api_base',''),getattr(b,'proxy','')];"
        "hosts=sorted({urlparse(str(v)).hostname for v in vals "
        "if v and urlparse(str(v)).hostname});"
        "print('M12_HOSTS='+json.dumps(hosts))"
    )
    output = m4.checked(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{m4.GA_RUNTIME.resolve()}:/opt/m4-runtime:ro",
            "-v",
            f"{m4.GA_ROOT.resolve()}:/opt/genericagent:ro",
            "-e",
            f"M12_LLM_NO={llm_no}",
            "-e",
            f"GA_LLM_CONFIG_NAME={os.environ.get('GA_LLM_CONFIG_NAME', '')}",
            "-e",
            f"PYTHONPATH={site}:/opt/genericagent",
            "debian:bookworm-slim",
            python_bin,
            "-c",
            resolver,
        ],
        180,
    )
    marker = next(
        (line for line in output.splitlines() if line.startswith("M12_HOSTS=")),
        None,
    )
    if marker is None:
        raise RuntimeError("GA backend emitted no API host identity")
    hosts = json.loads(marker.split("=", 1)[1])
    if not hosts or any(
        not isinstance(host, str)
        or urllib.parse.urlparse(f"//{host}").hostname != host
        for host in hosts
    ):
        raise RuntimeError(f"invalid GA API host identity: {hosts}")
    return hosts


def harbor_patch_identity() -> dict[str, Any]:
    root = continuation_patch.DEFAULT_HARBOR_ROOT
    states = {
        "continuation": continuation_patch.patch_state(root),
        "windows_sidecar_crlf": sidecar_patch.state(root),
        "structured_pass": pass_patch.state(root),
    }
    if set(states.values()) != {"applied"}:
        raise RuntimeError(f"required Harbor patches are not applied: {states}")
    return {
        "base_commit": continuation_patch.EXPECTED_HARBOR_COMMIT,
        "states": states,
        "patch_sha256": {
            "continuation": continuation_patch.EXPECTED_PATCH_SHA256,
            "windows_sidecar_crlf": sidecar_patch.EXPECTED_PATCH_SHA256,
            "structured_pass": pass_patch.EXPECTED_PATCH_SHA256,
        },
    }


def preflight(
    source: str,
    llm_no: int,
    task_id: str | None = None,
) -> dict[str, Any]:
    configure_m4()
    config = SOURCES[source]
    selected = task_id or config["representative_task_id"]
    row = proposal_row(source, selected)
    selected_task_path = task_path(source, selected)
    if not selected_task_path.is_dir():
        raise RuntimeError(f"task assets are missing: {selected_task_path}")
    ga_hash = m4.tree_hash(m4.GA_ROOT, ga_mode=True)
    validate_expected_ga_source(ga_hash)
    identity = {
        "schema_version": "ultralong-m12-natural-ga-preflight/1",
        "created_at": now(),
        "source": source,
        "task_id": selected,
        "task_path": str(selected_task_path.resolve()),
        "task_tree_sha256": m4.tree_hash(selected_task_path),
        "source_revision": row["source_revision"],
        "selection_uses_ga_result": False,
        "adapter": config["adapter"],
        "persistent_session": config["persistent_session"],
        "image": image_identity(row),
        "harbor": harbor_patch_identity(),
        "generic_agent": {
            "path": str(m4.GA_ROOT.resolve()),
            "source_sha256": ga_hash,
            "hash_scope": "all runtime files excluding transient temp/cache paths",
        },
        "runtime": {
            "root": str(m4.GA_RUNTIME.resolve()),
            "python_home": m4.python_home().name,
        },
        "model": m4.resolve_model(llm_no),
        "agent_phase_allowed_hosts": [
            *resolve_agent_hosts(llm_no),
            "host.docker.internal",
        ],
    }
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    path = WORK_ROOT / f"preflight_{source}_{selected}.json"
    path.write_text(
        json.dumps(identity, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return identity


def _finalize_proof(
    source: str,
    selected: str,
    run_id: str,
    max_agent_seconds: int,
    identity: dict[str, Any],
    launcher_returncode: int | None,
) -> dict[str, Any]:
    config = SOURCES[source]
    job_dir = JOBS_ROOT / run_id
    row = proposal_row(source, selected)
    task_timeout = float(
        row.get("agent_timeout_sec")
        or float(row["agent_timeout_min"]) * 60
    )
    model = identity["model"]
    result_path, result = m4.trial_result(job_dir)
    run_dir = RUNS_ROOT / run_id
    if run_dir.exists():
        raise RuntimeError(f"immutable proof run already exists: {run_id}")
    run_dir.mkdir(parents=True, exist_ok=False)
    trace = m4.archive_trace(run_id, run_dir)
    metadata = (result.get("agent_result") or {}).get("metadata") or {}
    expected_model = model["model"].lower()
    errors = []
    exception = result.get("exception_info")
    expected_budget_exhaustion = bool(
        source == "lhtb"
        and exception
        and exception.get("exception_type") == "AgentTimeoutError"
        and int(metadata.get("continue_until_timeout_phases", 0)) >= 1
    )
    if launcher_returncode and not expected_budget_exhaustion:
        errors.append(f"Harbor launcher returned {launcher_returncode}")
    if exception is not None and not expected_budget_exhaustion:
        errors.append("Harbor trial has an unexpected exception")
    if metadata.get("run_id") != run_id:
        errors.append("agent metadata is not linked to the run")
    if metadata.get("round_end_seen") is not True:
        errors.append("GA did not finish a protocol round")
    if metadata.get("wrapper_return_code") != 0:
        errors.append("GA wrapper did not complete successfully")
    if config["persistent_session"]:
        if metadata.get("persistent_session") is not True:
            errors.append("LHTB proof did not use a persistent GA session")
    elif not isinstance(metadata.get("ga_process_return_code"), int):
        errors.append("GA subprocess return code is missing")
    if not otel_models_match(trace["observed_models"], expected_model):
        errors.append("OTel model identity mismatch")

    agent_dir = result_path.parent / "agent"
    output_paths = sorted(agent_dir.glob("output*.txt"))
    outputs = [
        path.read_text(encoding="utf-8", errors="replace")
        for path in output_paths
    ]
    if not outputs:
        errors.append("no GA protocol output was archived")
    elif all(fatal_agent_output(output) for output in outputs):
        errors.append("every GA phase contains only an API/infrastructure error")
    elif any(terminal_agent_error(output) for output in outputs):
        errors.append("GA terminated on a provider/API error")
    errors.extend(no_checker_leakage_errors(metadata, outputs))

    reward = (result.get("verifier_result") or {}).get("rewards")
    manifest = {
        "schema_version": "ultralong-m12-natural-ga-proof/1",
        "created_at": now(),
        "run_id": run_id,
        "source": source,
        "task_id": selected,
        "integration_budget_sec": max_agent_seconds,
        "formal_task_budget_sec": task_timeout,
        "selection_uses_this_run": False,
        "completion_evaluation": "native_deterministic_verifier",
        "online_checker_feedback": False if online_checker_forbidden() else None,
        "reward_not_a_proof_gate": True,
        "rewards": reward,
        "trial_outcome": (
            "short_integration_budget_exhausted"
            if expected_budget_exhaustion
            else "agent_phase_completed"
        ),
        "agent_outputs": {
            "count": len(output_paths),
            "all_fatal_infrastructure_error_only": bool(outputs)
            and all(fatal_agent_output(output) for output in outputs),
            "paths": [str(path.resolve()) for path in output_paths],
        },
        "trial_result": str(result_path.resolve()),
        "agent_protocol": metadata,
        "trace": trace,
        "source_identity": identity,
        "validation_errors": errors,
        "valid": not errors,
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if errors:
        raise RuntimeError("M12 Natural GA proof invalid: " + "; ".join(errors))
    return manifest


def finalize_existing_proof(
    source: str,
    run_id: str,
    llm_no: int,
    max_agent_seconds: int,
    task_id: str | None = None,
) -> dict[str, Any]:
    config = SOURCES[source]
    selected = task_id or config["representative_task_id"]
    identity = preflight(source, llm_no, selected)
    if not (JOBS_ROOT / run_id).exists():
        raise RuntimeError(f"Harbor job does not exist: {run_id}")
    return _finalize_proof(
        source, selected, run_id, max_agent_seconds, identity, None
    )


def run_proof(
    source: str,
    run_id: str,
    llm_no: int,
    max_agent_seconds: int,
    task_id: str | None = None,
) -> dict[str, Any]:
    config = SOURCES[source]
    selected = task_id or config["representative_task_id"]
    identity = preflight(source, llm_no, selected)
    job_dir = JOBS_ROOT / run_id
    if job_dir.exists() or (RUNS_ROOT / run_id).exists():
        raise RuntimeError(f"immutable proof run already exists: {run_id}")
    execution_task = materialize_execution_task(source, selected, run_id)

    row = proposal_row(source, selected)
    task_timeout = float(
        row.get("agent_timeout_sec")
        or float(row["agent_timeout_min"]) * 60
    )
    timeout_multiplier = max_agent_seconds / task_timeout
    model = identity["model"]
    mounts = [
        {
            "type": "bind",
            "source": str(m4.GA_RUNTIME.resolve()),
            "target": "/opt/m4-runtime",
            "read_only": True,
        },
        {
            "type": "bind",
            "source": str(m4.GA_ROOT.resolve()),
            "target": "/opt/genericagent-source",
            "read_only": True,
        },
    ]
    stage6d_bundle = os.environ.get("GA_STAGE6D_BUNDLE_DIR")
    if stage6d_bundle:
        mounts.append({
            "type": "bind", "source": str(Path(stage6d_bundle).resolve()),
            "target": "/opt/stage6d-bundle", "read_only": True,
        })
    completion_checkpoint = os.environ.get("GA_COMPLETION_BRANCH_CHECKPOINT")
    if completion_checkpoint:
        mounts.append({
            "type": "bind", "source": str(Path(completion_checkpoint).resolve()),
            "target": "/opt/completion-checkpoint", "read_only": True,
        })
        mounts.append({
            "type": "bind", "source": str(Path(os.environ["GA_COMPLETION_BRANCH_BUNDLE"]).resolve()),
            "target": "/opt/completion-branch", "read_only": True,
        })
    command = [
        str(m4.HARBOR_EXE),
        "jobs",
        "start",
        "--job-name",
        run_id,
        "--jobs-dir",
        str(JOBS_ROOT.resolve()),
        "--path",
        str(execution_task.resolve()),
        "--agent",
        config["adapter"],
        "--model",
        model["model"],
        "--mounts",
        json.dumps(mounts),
        "--agent-timeout-multiplier",
        str(timeout_multiplier),
        "--n-concurrent",
        "1",
        "--max-retries",
        "0",
        "--yes",
    ]
    if os.environ.get("GA_KEEP_HARBOR_ENV") != "1":
        command.append("--delete")
    for host in identity["agent_phase_allowed_hosts"]:
        command += ["--allow-agent-host", host]
    kwargs = {
        "llm_no": model["effective_llm_no"],
        "run_id": run_id,
        "expected_model": model["model"],
        "python_home": identity["runtime"]["python_home"],
        "ga_source_sha256": identity["generic_agent"]["source_sha256"],
        "task_id": f"{source}:{selected}",
        "collector_endpoint": (
            f"http://host.docker.internal:{COLLECTOR_PORT}/v1/traces"
        ),
        "timeout_sec": max_agent_seconds,
    }
    kwargs.update(stage4_agent_kwargs())
    for key, value in kwargs.items():
        command += ["--ak", f"{key}={value}"]

    m4.start_collector()
    try:
        launched = m4.run(
            command,
            timeout=max_agent_seconds + 900,
        )
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "launcher_stdout.log").write_text(
            launched.stdout, encoding="utf-8"
        )
        (job_dir / "launcher_stderr.log").write_text(
            launched.stderr, encoding="utf-8"
        )
        time.sleep(5)
    finally:
        m4.stop_collector()

    return _finalize_proof(
        source,
        selected,
        run_id,
        max_agent_seconds,
        identity,
        launched.returncode,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=sorted(SOURCES), required=True)
    parser.add_argument("--task-id")
    parser.add_argument("--run-id")
    parser.add_argument("--llm-no", type=int, default=0)
    parser.add_argument("--max-agent-seconds", type=int, default=300)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--finalize-existing", action="store_true")
    parser.add_argument("--experiment-manifest")
    args = parser.parse_args()
    if args.experiment_manifest:
        if not args.run_id:
            parser.error("--experiment-manifest requires --run-id")
        apply_experiment_manifest(args.experiment_manifest, args.run_id)
    if args.preflight_only and args.finalize_existing:
        parser.error("--preflight-only and --finalize-existing are mutually exclusive")
    if args.preflight_only:
        result = preflight(args.source, args.llm_no, args.task_id)
    elif args.finalize_existing:
        if not args.run_id:
            parser.error("--finalize-existing requires --run-id")
        result = finalize_existing_proof(
            args.source,
            args.run_id,
            args.llm_no,
            args.max_agent_seconds,
            args.task_id,
        )
    else:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        run_id = args.run_id or f"m12-{args.source}-ga-proof-{stamp}"
        result = run_proof(
            args.source,
            run_id,
            args.llm_no,
            args.max_agent_seconds,
            args.task_id,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
