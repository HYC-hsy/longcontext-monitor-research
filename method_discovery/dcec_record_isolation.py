"""Host-side OS isolation for one generic Supervisor record."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
IMAGE_LABEL = "debian:bookworm-slim"
IMAGE = "sha256:88200866dfff7ea7f5cbcb6ec7c8a701889efe6fe859fe64d6990e4b07ea4171"
RUNTIME = ROOT / "bench_runtime/m2/linux"
PYTHON_HOME = "cpython-3.12.12-linux-x86_64-gnu"
PYTHON = f"/opt/m4-runtime/python/{PYTHON_HOME}/bin/python3.12"
SITE = "/opt/m4-runtime/ga-env/lib/python3.12/site-packages"
TRANSPORT = ROOT / "long_context_bench/adapters/isolated_transport.py"
WORKER = ROOT / "method_discovery/dcec_isolated_record_worker.py"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_manifest(root: Path) -> list[dict]:
    return [{
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    } for path in sorted(root.rglob("*")) if path.is_file()]


def tree_sha256(root: Path) -> str:
    payload = json.dumps(tree_manifest(root), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def docker(*args, check=True, timeout=60):
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, check=check, timeout=timeout)


def image_identity() -> str:
    result = docker("image", "inspect", "--format", "{{.Id}}", IMAGE)
    value = result.stdout.strip()
    if not value:
        raise RuntimeError("isolated execution image identity is empty")
    return value


def prepare_runtime(destination: Path, supervisor: dict, disabled_keys: list[str]) -> dict:
    if destination.exists():
        raise FileExistsError(f"isolated runtime already exists: {destination}")
    destination.mkdir(parents=True)
    core = ROOT / "GenericAgent-main/monitor_agent_core"
    shutil.copytree(core, destination / "monitor_agent_core", ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", "*.local.json", "tests"))
    shutil.copy2(WORKER, destination / "dcec_isolated_record_worker.py")
    shutil.copy2(TRANSPORT, destination / "isolated_transport.py")
    safe = {key: supervisor.get(key) for key in (
        "provider", "api_mode", "model", "thinking_type", "reasoning_effort", "temperature",
        "context_win", "timeout", "read_timeout", "max_retries", "transport_route")}
    safe["max_tokens"] = supervisor.get("max_tokens") or 8192
    (destination / "supervisor_config.json").write_text(
        json.dumps(safe, ensure_ascii=False), encoding="utf-8")
    (destination / "disabled_candidate_keys.json").write_text(
        json.dumps(disabled_keys), encoding="utf-8")
    forbidden = ("fixture_spec.json", "discriminating_manifest.json")
    for path in destination.rglob("*"):
        if path.is_file() and path.name in forbidden:
            raise ValueError(f"research file entered isolated runtime: {path.name}")
    return {
        "image": IMAGE_LABEL, "image_id": image_identity(),
        "runtime_root": str(RUNTIME.resolve()),
        "source_tree_sha256": tree_sha256(destination),
        "source_files": tree_manifest(destination),
        "worker_sha256": sha256_file(destination / WORKER.name),
        "transport_sha256": sha256_file(destination / TRANSPORT.name),
    }


def _mounts(source: Path, record: Path) -> list[str]:
    values = [
        (RUNTIME, "/opt/m4-runtime", "ro"),
        (source, "/source", "ro"),
        (record / "task", "/record/task", "ro"),
        (record / "monitor", "/record/monitor", "rw"),
    ]
    result = []
    for host, target, mode in values:
        option = f"type=bind,src={host.resolve()},dst={target}"
        if mode == "ro":
            option += ",readonly"
        result.extend(["--mount", option])
    return result


def _run_prefix(source: Path, record: Path) -> list[str]:
    return [
        "docker", "run", "--rm", "-i", "--network", "none", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true", "--read-only", "--pids-limit", "128",
        "--tmpfs", "/tmp:rw,nosuid,nodev", "--workdir", "/record/monitor",
        "-e", f"PYTHONPATH=/source:{SITE}", "-e", "PYTHONDONTWRITEBYTECODE=1",
        *_mounts(source, record),
    ]


def _base(source: Path, record: Path) -> list[str]:
    return [*_run_prefix(source, record), IMAGE, PYTHON,
            "/source/dcec_isolated_record_worker.py"]


def _worker_event(stdout: str, expected: str) -> dict:
    events = []
    for line in stdout.splitlines():
        if line.startswith("DCEC_WORKER "):
            events.append(json.loads(line[len("DCEC_WORKER "):]))
    matches = [item for item in events if item.get("event") == expected]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {expected} event, got {len(matches)}; output={stdout[-4000:]}")
    return matches[0]


def request_probe(source: Path, record: Path, dcec: bool) -> dict:
    result = subprocess.run(
        [*_base(source, record), "request", "--dcec", "1" if dcec else "0"],
        capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise RuntimeError("isolated request probe failed: " + result.stderr[-4000:])
    return _worker_event(result.stdout, "request_snapshot")["request"]


def filesystem_probe(source: Path, record: Path) -> dict:
    probe = json.dumps({
        "names": ["fixture_spec.json", "discriminating_manifest.json"],
        "terms": ["research_only", "latent_defect", "correct_control"],
        "host_paths": ["/workspace", "/repo", "/method_discovery",
                       "/run/desktop/mnt/host/e/LongContext"],
    }) + "\n"
    result = subprocess.run(
        [*_base(source, record), "filesystem"], input=probe,
        capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise RuntimeError("isolated filesystem probe failed: " + result.stderr[-4000:])
    return _worker_event(result.stdout, "filesystem_probe")


def _gateway_config(profile: dict) -> dict:
    endpoint = urlsplit(str(profile["apibase"]))
    if endpoint.scheme != "https" or not endpoint.hostname:
        raise ValueError("isolated gateway requires a fixed HTTPS provider")
    key = profile["apikey"]
    headers = {"x-api-key": key} if key.startswith("sk-ant-") else {
        "Authorization": "Bearer " + key}
    return {"models": {"monitor": {
        "base": profile["apibase"], "headers": headers,
        "paths": ["/v1/messages"], "model": profile["model"],
    }}, "telemetry": "http://127.0.0.1:9/v1/traces"}


def run_record(source: Path, record: Path, profile: dict, dcec: bool, max_turns: int,
               on_intervention, on_root_ready) -> dict:
    token = uuid.uuid4().hex[:12]
    volume, gateway, main = f"dcec-channel-{token}", f"dcec-gateway-{token}", f"dcec-main-{token}"
    docker("volume", "create", volume)
    with tempfile.TemporaryDirectory(prefix="dcec-gateway-") as temporary:
        gateway_root = Path(temporary)
        (gateway_root / "config.json").write_text(
            json.dumps(_gateway_config(profile)), encoding="utf-8")
        shutil.copy2(TRANSPORT, gateway_root / "transport.py")
        try:
            docker("run", "-d", "--rm", "--name", gateway, "--network", "bridge",
                   "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
                   "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev",
                   "--mount", f"type=bind,src={RUNTIME.resolve()},dst=/opt/m4-runtime,readonly",
                   "--mount", f"type=bind,src={gateway_root.resolve()},dst=/gateway,readonly",
                   "--mount", f"type=volume,src={volume},dst=/run/model-channel",
                   IMAGE, PYTHON, "/gateway/transport.py", "gateway", "--config", "/gateway/config.json")
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                check = docker("exec", gateway, PYTHON, "-c",
                    "import socket;s=socket.socket(socket.AF_UNIX);s.connect('/run/model-channel/gateway.sock')",
                    check=False, timeout=5)
                if check.returncode == 0:
                    break
                time.sleep(0.5)
            else:
                raise RuntimeError("isolated inference gateway did not become ready")
            command = [*_run_prefix(source, record), "--name", main,
                       "--mount", f"type=volume,src={volume},dst=/run/model-channel,readonly",
                       IMAGE, PYTHON, "/source/dcec_isolated_record_worker.py",
                       "execute", "--dcec", "1" if dcec else "0", "--max-turns", str(max_turns)]
            process = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1)
            result = None
            output = []
            for line in process.stdout:
                output.append(line)
                if not line.startswith("DCEC_WORKER "):
                    continue
                event = json.loads(line[len("DCEC_WORKER "):])
                if event["event"] == "intervention":
                    on_intervention(event["message"])
                    process.stdin.write(json.dumps({"ack": "intervention"}) + "\n")
                    process.stdin.flush()
                elif event["event"] == "root_ready":
                    on_root_ready()
                    process.stdin.write(json.dumps({"ack": "root_ready"}) + "\n")
                    process.stdin.flush()
                elif event["event"] == "result":
                    result = event["result"]
            code = process.wait(timeout=30)
            if code or result is None:
                raise RuntimeError("isolated record worker failed: " + "".join(output)[-8000:])
            return result
        finally:
            docker("rm", "-f", main, check=False, timeout=30)
            docker("rm", "-f", gateway, check=False, timeout=30)
            docker("volume", "rm", "-f", volume, check=False, timeout=30)
