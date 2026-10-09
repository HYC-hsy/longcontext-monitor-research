"""Create a non-secret local run identity after the research-only implementation is committed."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from . import adapter
from .docker_tool import IMAGE
from .protocol import RUN_BUDGET
from method_discovery.curator_supervisor_convergence_v0.diagnostic_flex_preflight_v0_20261009 import freeze_inputs

HOST_PROFILE = Path(r"E:\LongContext\monitor_config\models.local.json")
V1_COMMIT = "d6a7cc56cc6006e9f44d6b324ba6c55b1881fa6f"


def code_hashes() -> dict[str, str]:
    research = adapter.HERE
    production = freeze_inputs.REPO / "GenericAgent-main/monitor_agent_core"
    sources = {"research/adapter.py": research / "adapter.py",
               "research/docker_tool.py": research / "docker_tool.py",
               "research/protocol.py": research / "protocol.py",
               "research/live_batch.py": research / "live_batch.py",
               "research/freeze_run.py": research / "freeze_run.py",
               "research/certify_v2.py": research / "certify_v2.py",
               "research/archive_static_batch.py": research / "archive_static_batch.py",
               "production/provider.py": production / "provider.py",
               "production/loop.py": production / "loop.py",
               "production/workspace.py": production / "workspace.py",
               "production/actions.py": production / "actions.py"}
    return {name: adapter.sha(path.read_bytes()) for name, path in sources.items()}


def v1_request_hashes() -> dict[str, str]:
    result = {}
    for scene in adapter.SCENES:
        for arm in ("B", "F"):
            name = f"{scene}_{arm}_STATIC_REQUEST.json"
            relative = (adapter.HERE / name).relative_to(freeze_inputs.REPO).as_posix()
            raw = subprocess.run(["git", "show", f"{V1_COMMIT}:{relative}"],
                                 cwd=freeze_inputs.REPO, capture_output=True, check=True).stdout
            old = json.loads(raw)
            current = adapter.request(scene, arm)
            if old != current:
                raise RuntimeError("First request changed since batch v1: " + name)
            result[f"{scene}_{arm}"] = adapter.sha(adapter.canonical(old))
    return result


def build() -> dict:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=freeze_inputs.REPO,
                          text=True, capture_output=True, check=True).stdout.strip()
    cert = adapter.HERE / "ISOLATION_CERTIFICATION_V3.json"
    if not cert.exists():
        raise RuntimeError("Amended Docker isolation has not been certified")
    identity = json.loads(cert.read_text(encoding="utf-8"))
    if identity["tool_port_source_sha256"] != adapter.sha((adapter.HERE / "docker_tool.py").read_bytes()):
        raise RuntimeError("Tool port changed since certification")
    historical_requests = v1_request_hashes()
    archived = json.loads(freeze_inputs.PROFILE.read_text(encoding="utf-8"))["claude_monitor_opus48"]
    profile = json.loads(HOST_PROFILE.read_text(encoding="utf-8"))["claude_monitor_opus48"]
    model_fields = ("model", "provider", "max_tokens", "thinking_type", "reasoning_effort",
                    "temperature", "transport_route", "timeout", "read_timeout")
    if any(profile.get(key) != archived.get(key) for key in model_fields):
        raise RuntimeError("Host transport profile differs from archived model configuration")
    return {"source_commit": head, "batch_revision": "v2_execution_fidelity_repair",
            "v1_archive_commit": V1_COMMIT,
            "stage1_commit": "d76d8a178e4268582f3d5b5a2c052c6cd85a18bf",
            "historical_stage1_limits_superseded": True,
            "code_hashes": code_hashes(),
            "profile_sha256": adapter.sha(HOST_PROFILE.read_bytes()),
            "archived_profile_sha256": adapter.sha(freeze_inputs.PROFILE.read_bytes()),
            "image": IMAGE,
            "docker_tool_sha256": adapter.sha((adapter.HERE / "docker_tool.py").read_bytes()),
            "probe_sha256": adapter.sha((adapter.HERE / "probe_isolation.py").read_bytes()),
            "requests": historical_requests,
            "order": [list(item) for item in adapter.ORDER], "limits": RUN_BUDGET,
            "provider_policy": {"model": "claude-opus-4-8", "provider": "anthropic",
                                "max_tokens": 8192, "thinking_type": "adaptive",
                                "reasoning_effort": "high", "stream": True,
                                "temperature_sent": False,
                                "connect_timeout_seconds": max(1, int(profile.get("timeout", 10))),
                                "read_timeout_seconds": max(10, int(profile.get("read_timeout", 300))),
                                "automatic_retry_on_ambiguous_failure": False},
            "tool_policy": {"image": IMAGE, "network": "none", "app": "read_only",
                            "evidence": "read_only", "private": "per_attempt_writable",
                            "scratch": "per_attempt_persistent_home_tmp_build_cache_output",
                            "new_command_timeout_max_seconds": 300,
                            "poll_wait_max_seconds": 5,
                            "total_tool_calls_ceiling": None,
                            "cumulative_tool_wait_ceiling": None,
                            "certification_sha256": adapter.sha(cert.read_bytes())},
            "visibility_manifests": {scene: adapter.sha((adapter.HERE / f"{scene}_VISIBILITY_MANIFEST.json").read_bytes())
                                     for scene in adapter.SCENES}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("Run freeze path already exists")
    adapter.save_json(args.output, build())


if __name__ == "__main__":
    main()
