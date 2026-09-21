"""Versioned one-request isolated transport smoke runner."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METHOD = ROOT / "method_discovery"
GA_ROOT = ROOT / "GenericAgent-main"
sys.path.insert(0, str(GA_ROOT))
sys.path.insert(0, str(METHOD))

from dcec_record_isolation import (  # noqa: E402
    IMAGE, PYTHON, RUNTIME, SITE, TRANSPORT, _collect_gateway_diagnostics,
    _gateway_config, docker, production_tls_semantics,
)


DEFAULT_MANIFEST = METHOD / "artifacts/dcec_v0_20260921/infra_smoke_manifest.json"
FROZEN_OUTPUT = METHOD / "runs/dcec_v0_infra_smoke_r1"
WORKER = METHOD / "dcec_transport_smoke_worker.py"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_manifest(manifest: dict, manifest_path: Path) -> None:
    if manifest.get("execution_authorized") is not True:
        raise PermissionError("smoke execution_authorized=false; zero provider requests permitted")
    expected = {
        "dcec_enabled": False,
        "scientific_fixture_used": False,
        "scientific_result": False,
        "max_logical_calls": 1,
        "max_provider_requests": 1,
        "transport_retries": 0,
        "execution_output": "method_discovery/runs/dcec_v0_infra_smoke_r1",
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(f"invalid frozen smoke field {key}: {manifest.get(key)!r}")
    identities = manifest.get("runner_identity") or {}
    checks = {
        Path(__file__).resolve(): identities.get("runner_sha256"),
        WORKER.resolve(): identities.get("worker_sha256"),
        TRANSPORT.resolve(): manifest.get("transport_source_sha256"),
        (METHOD / "dcec_record_isolation.py").resolve(): manifest.get("isolation_source_sha256"),
    }
    for path, expected_hash in checks.items():
        actual = sha256_file(path)
        if not expected_hash or actual != expected_hash:
            raise ValueError(f"frozen source identity mismatch: {path.name}")
    if (ROOT / manifest["execution_output"]).resolve() != FROZEN_OUTPUT.resolve():
        raise ValueError("smoke output is not the frozen output path")


def validate_output(output: Path, frozen: Path) -> None:
    if output.resolve() != frozen.resolve():
        raise ValueError(f"smoke output must equal frozen path: {frozen}")
    if output.exists():
        raise FileExistsError(f"smoke output already exists: {output}")


def _prepare_source(destination: Path, profile: dict, manifest: dict) -> None:
    destination.mkdir(parents=True)
    shutil.copytree(GA_ROOT / "monitor_agent_core", destination / "monitor_agent_core",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.local.json", "tests"))
    shutil.copy2(TRANSPORT, destination / "isolated_transport.py")
    shutil.copy2(WORKER, destination / WORKER.name)
    safe = {key: profile.get(key) for key in (
        "provider", "api_mode", "model", "thinking_type", "reasoning_effort", "temperature",
        "context_win", "timeout", "read_timeout", "transport_route")}
    safe.update({
        "apikey": "isolated-local-channel",
        "apibase": "http://127.0.0.1:18765",
        "max_tokens": profile.get("max_tokens") or 256,
        "max_retries": 0,
    })
    smoke = {
        "dcec_enabled": False,
        "scientific_fixture_used": False,
        "prompt": manifest["prompt"],
        "expected_short_response": manifest["expected_short_response"],
        "provider_config": safe,
    }
    write_json(destination / "smoke_config.json", smoke)
    forbidden = {"fixture_spec.json", "discriminating_manifest.json"}
    if any(path.name in forbidden for path in destination.rglob("*")):
        raise RuntimeError("scientific fixture entered smoke runtime")


def _extract_worker_result(stdout: str) -> dict:
    rows = [json.loads(line[len("DCEC_SMOKE "):]) for line in stdout.splitlines()
            if line.startswith("DCEC_SMOKE ")]
    if len(rows) != 1:
        raise RuntimeError(f"expected one smoke result, got {len(rows)}")
    return rows[0]


def _run_isolated(source: Path, output: Path, profile: dict) -> dict:
    token = uuid.uuid4().hex[:12]
    volume, gateway, main = f"dcec-smoke-channel-{token}", f"dcec-smoke-gateway-{token}", f"dcec-smoke-main-{token}"
    docker("volume", "create", volume)
    diagnostics = []
    with tempfile.TemporaryDirectory(prefix="dcec-smoke-gateway-") as temporary:
        gateway_root = Path(temporary)
        _, ca_path = production_tls_semantics(profile)
        write_json(gateway_root / "config.json", _gateway_config(profile))
        shutil.copy2(TRANSPORT, gateway_root / "transport.py")
        if ca_path is not None:
            shutil.copy2(ca_path, gateway_root / "ca-bundle.pem")
        gateway_started = False
        try:
            docker("run", "-d", "--rm", "--name", gateway, "--network", "bridge",
                   "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--read-only",
                   "--tmpfs", "/tmp:rw,nosuid,nodev",
                   "--mount", f"type=bind,src={RUNTIME.resolve()},dst=/opt/m4-runtime,readonly",
                   "--mount", f"type=bind,src={gateway_root.resolve()},dst=/gateway,readonly",
                   "--mount", f"type=volume,src={volume},dst=/run/model-channel",
                   IMAGE, PYTHON, "/gateway/transport.py", "gateway", "--config", "/gateway/config.json")
            gateway_started = True
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                ready = docker("exec", gateway, PYTHON, "-c",
                    "import socket;s=socket.socket(socket.AF_UNIX);s.connect('/run/model-channel/gateway.sock')",
                    check=False, timeout=5)
                if ready.returncode == 0:
                    break
                time.sleep(0.5)
            else:
                raise RuntimeError("smoke gateway did not become ready")
            command = [
                "docker", "run", "--rm", "--name", main, "--network", "none", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges:true", "--read-only", "--pids-limit", "128",
                "--tmpfs", "/tmp:rw,nosuid,nodev", "--workdir", "/record/monitor",
                "-e", f"PYTHONPATH=/source:{SITE}", "-e", "PYTHONDONTWRITEBYTECODE=1",
                "--mount", f"type=bind,src={RUNTIME.resolve()},dst=/opt/m4-runtime,readonly",
                "--mount", f"type=bind,src={source.resolve()},dst=/source,readonly",
                "--mount", f"type=bind,src={(output / 'monitor').resolve()},dst=/record/monitor",
                "--mount", f"type=volume,src={volume},dst=/run/model-channel,readonly",
                IMAGE, PYTHON, "/source/dcec_transport_smoke_worker.py",
                "--config", "/source/smoke_config.json", "--output", "/record/monitor",
            ]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=300)
            result = _extract_worker_result(completed.stdout)
            result["worker_exit_code"] = completed.returncode
        finally:
            if gateway_started:
                diagnostics = _collect_gateway_diagnostics(
                    gateway, output / "gateway_transport.jsonl")
            docker("rm", "-f", main, check=False, timeout=30)
            docker("rm", "-f", gateway, check=False, timeout=30)
            docker("volume", "rm", "-f", volume, check=False, timeout=30)
    result["gateway_safe_stages"] = diagnostics
    result["gateway_provider_http_requests"] = sum(
        1 for item in diagnostics if item.get("stage") == "request_sent")
    if result["logical_calls"] != 1 or result["provider_attempts"] > 1:
        raise RuntimeError("smoke exceeded frozen call/request limit")
    return result


def execute(manifest_path: Path, output: Path, monitor_config: Path) -> dict:
    manifest = load_json(manifest_path)
    # This authorization check intentionally precedes profile loading, output
    # creation, Docker startup, or any provider construction.
    validate_manifest(manifest, manifest_path)
    frozen = (ROOT / manifest["execution_output"]).resolve()
    validate_output(output, frozen)
    profiles = load_json(monitor_config)
    profile = profiles[manifest["provider_profile"]]
    if profile.get("model") != manifest["model"] or profile.get("transport_route") != manifest["transport_route"]:
        raise ValueError("resolved smoke provider identity differs from manifest")
    output.mkdir(parents=True)
    (output / "monitor").mkdir()
    source = output / "isolated_runtime"
    _prepare_source(source, profile, manifest)
    result = _run_isolated(source, output, profile)
    write_json(output / "result.json", result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--monitor-config", type=Path, default=ROOT / "monitor_config/models.local.json")
    parser.add_argument("--execute", action="store_true", required=True)
    args = parser.parse_args(argv)
    manifest = load_json(args.manifest.resolve())
    output = args.output.resolve() if args.output else (ROOT / manifest["execution_output"]).resolve()
    execute(args.manifest.resolve(), output, args.monitor_config.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
