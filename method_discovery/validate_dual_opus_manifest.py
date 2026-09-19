"""Resolve and fail-close a dual-Opus run manifest without making model requests."""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GA_ROOT = ROOT / "GenericAgent-main"
sys.path.insert(0, str(GA_ROOT))

from llmcore import resolve_client  # noqa: E402
from monitor_agent_core.configuration import load_profile  # noqa: E402
from monitor_agent_core.experiment_contract import (  # noqa: E402
    load_contract, resolved_monitor_config, resolved_task_client, validate_live_roles,
    validate_source_upstream,
)


@contextmanager
def _manifest_environment(environment: dict):
    """Resolve clients under the exact manifest environment, then restore the caller."""
    previous = {key: os.environ.get(key) for key in environment}
    try:
        for key, value in environment.items():
            os.environ[str(key)] = str(value)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def validate_manifest_models(manifest_path, monitor_profile_path) -> dict:
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if len(manifest.get("runs") or []) != 1:
        raise ValueError("exactly one frozen run is required")
    environment = manifest["runs"][0].get("environment") or {}
    contract_reference = environment.get("GA_MODEL_CONTRACT_FILE")
    if not contract_reference:
        raise ValueError("GA_MODEL_CONTRACT_FILE is required")
    contract_path = Path(contract_reference)
    if not contract_path.is_absolute():
        contract_path = GA_ROOT / contract_path
    contract = load_contract(contract_path)
    embedded = manifest.get("model_contract")
    if embedded != contract:
        raise ValueError("embedded model contract differs from the runtime contract")
    task_profile = environment.get("GA_LLM_CONFIG_NAME") or ""
    monitor_profile = environment.get("GA_MONITOR_CONFIG") or ""
    with _manifest_environment(environment):
        task_client = resolve_client(task_profile)
        if task_client is None:
            raise ValueError(f"task profile cannot be resolved: {task_profile}")
        monitor_config = load_profile(monitor_profile, monitor_profile_path)
        source_task = resolved_task_client(task_profile, task_client)
        source_supervisor = resolved_monitor_config(monitor_profile, monitor_config)
    validate_source_upstream(contract, "task_agent", source_task)
    validate_source_upstream(contract, "supervisor", source_supervisor)
    task = dict(source_task, endpoint_host="127.0.0.1")
    supervisor = dict(source_supervisor, endpoint_host="127.0.0.1")
    child_override = (environment.get("GA_MONITOR_INDEPENDENT_C_PROFILE")
                      or environment.get("GA_MONITOR_INDEPENDENT_C_CONFIG"))
    resolved = validate_live_roles(
        contract, task, supervisor, child_override=child_override)
    resolved.update({
        "schema_version": "resolved-monitor-experiment-config/1",
        "run_id": manifest["runs"][0].get("run_id"),
        "network_requests": 0,
        "source_upstreams": {
            "task_agent": {"endpoint_host": source_task.get("endpoint_host")},
            "supervisor": {"endpoint_host": source_supervisor.get("endpoint_host")},
        },
    })
    return resolved


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--monitor-profile-file", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_manifest_models(args.manifest, args.monitor_profile_file)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        if args.output.exists():
            raise FileExistsError(args.output)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
