"""Host-side OS isolation for one generic Supervisor record."""
from __future__ import annotations

import hashlib
import json
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from requests.certs import where as requests_ca_where


ROOT = Path(__file__).resolve().parents[1]
IMAGE_LABEL = "debian:bookworm-slim"
IMAGE = "sha256:88200866dfff7ea7f5cbcb6ec7c8a701889efe6fe859fe64d6990e4b07ea4171"
RUNTIME = ROOT / "bench_runtime/m2/linux"
PYTHON_HOME = "cpython-3.12.12-linux-x86_64-gnu"
PYTHON = f"/opt/m4-runtime/python/{PYTHON_HOME}/bin/python3.12"
SITE = "/opt/m4-runtime/ga-env/lib/python3.12/site-packages"
CONTAINER_CA_BUNDLE = "/gateway/ca-bundle.pem"
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


def production_tls_semantics(profile: dict) -> tuple[dict, Path | None]:
    proxy = profile.get("proxy")
    if proxy:
        raise ValueError("production proxy is configured; isolated gateway proxy equivalence is not implemented")
    verify = profile.get("verify", True)
    if verify is True:
        ca_path = Path(requests_ca_where()).resolve()
        source_kind = "production_requests_certifi"
    elif verify is False:
        ca_path = None
        source_kind = "production_profile_verify_false"
    elif isinstance(verify, str) and verify:
        ca_path = Path(verify).expanduser().resolve()
        source_kind = "production_profile_ca_path"
    else:
        raise ValueError(f"unsupported production verify setting: {type(verify).__name__}")
    if ca_path is not None and not ca_path.is_file():
        raise FileNotFoundError(f"production CA bundle is missing: {ca_path}")
    return ({
        "verification_enabled": verify is not False,
        "verify_value_class": "bool" if isinstance(verify, bool) else "path",
        "ca_source_kind": source_kind,
        "ca_file": CONTAINER_CA_BUNDLE if ca_path is not None else None,
        "ca_bundle_sha256": sha256_file(ca_path) if ca_path is not None else None,
        "production_proxy_present": False,
    }, ca_path)


def tls_handshake_probe(profile: dict) -> dict:
    endpoint = urlsplit(str(profile["apibase"]))
    if endpoint.scheme != "https" or not endpoint.hostname:
        raise ValueError("TLS probe requires the fixed HTTPS provider endpoint")
    tls, ca_path = production_tls_semantics(profile)
    script = (
        "import importlib.util,json,socket,sys;"
        "spec=importlib.util.spec_from_file_location('transport','/gateway/transport.py');"
        "transport=importlib.util.module_from_spec(spec);spec.loader.exec_module(transport);"
        "route=json.load(open('/gateway/config.json'))['models']['monitor'];"
        "host=sys.argv[1];port=int(sys.argv[2]);"
        "ctx=transport.create_tls_context(route);"
        "raw=socket.create_connection((host,port),10);"
        "conn=ctx.wrap_socket(raw,server_hostname=host);"
        "print(json.dumps({'tls_version':conn.version(),"
        "'peer_common_name':dict(x[0] for x in conn.getpeercert()['subject']).get('commonName')}));"
        "conn.close()")
    with tempfile.TemporaryDirectory(prefix="dcec-tls-probe-") as temporary:
        root = Path(temporary)
        config = _gateway_config(profile)
        (root / "config.json").write_text(json.dumps(config), encoding="utf-8")
        shutil.copy2(TRANSPORT, root / "transport.py")
        if ca_path is not None:
            shutil.copy2(ca_path, root / "ca-bundle.pem")
        result = docker(
            "run", "--rm", "--network", "bridge", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true", "--read-only",
            "--tmpfs", "/tmp:rw,nosuid,nodev",
            "--mount", f"type=bind,src={RUNTIME.resolve()},dst=/opt/m4-runtime,readonly",
            "--mount", f"type=bind,src={root.resolve()},dst=/gateway,readonly",
            IMAGE, PYTHON, "-c", script, endpoint.hostname, str(endpoint.port or 443),
            timeout=30)
    observed = json.loads(result.stdout)
    return {
        "tls_handshake_attempts": 1,
        "tls_handshake_success": True,
        "endpoint_host": endpoint.hostname,
        "endpoint_port": endpoint.port or 443,
        "peer_hostname": observed.pop("peer_common_name", None),
        "verification_enabled": tls["verification_enabled"],
        "ca_source_kind": tls["ca_source_kind"],
        "ca_bundle_sha256_if_applicable": tls["ca_bundle_sha256"],
        "provider_http_requests": 0,
        "model_api_calls": 0,
        **observed,
    }


def prepare_runtime(destination: Path, supervisor: dict, disabled_keys: list[str]) -> dict:
    tls, _ = production_tls_semantics(supervisor)
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
        "production_tls": tls,
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


def provider_deadline_probe(source: Path, record: Path, wall_seconds: float) -> dict:
    result = subprocess.run(
        [*_base(source, record), "deadline", "--wall-seconds", str(wall_seconds)],
        capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise RuntimeError("isolated provider deadline probe failed: " + result.stderr[-4000:])
    return _worker_event(result.stdout, "deadline_probe")


def _stop_process(process, grace_seconds: float = 2.0) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=grace_seconds)


def _drive_worker(process, wall_seconds: float, on_intervention, on_root_ready) -> tuple[dict, list[str]]:
    if wall_seconds <= 0:
        raise ValueError("wall_seconds must be positive")
    lines: queue.Queue = queue.Queue()

    def read_stdout() -> None:
        try:
            for line in process.stdout:
                lines.put(line)
        finally:
            lines.put(None)

    threading.Thread(target=read_stdout, daemon=True).start()
    started = time.monotonic()
    deadline = started + wall_seconds
    output, result = [], None
    stream_finished = False
    while not stream_finished:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _stop_process(process)
            return ({
                "status": "timeout",
                "stop_reason": "record_wall_deadline_exceeded",
                "budget_seconds": wall_seconds,
                "elapsed_seconds": time.monotonic() - started,
                "deadline_exceeded": True,
                "partial_artifacts_preserved": True,
            }, output)
        try:
            line = lines.get(timeout=min(0.1, remaining))
        except queue.Empty:
            if process.poll() is not None:
                continue
            continue
        if line is None:
            stream_finished = True
            continue
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
    remaining = max(0.001, deadline - time.monotonic())
    try:
        code = process.wait(timeout=remaining)
    except subprocess.TimeoutExpired:
        _stop_process(process)
        return ({
            "status": "timeout",
            "stop_reason": "record_wall_deadline_exceeded",
            "budget_seconds": wall_seconds,
            "elapsed_seconds": time.monotonic() - started,
            "deadline_exceeded": True,
            "partial_artifacts_preserved": True,
        }, output)
    if code or result is None:
        raise RuntimeError("isolated record worker failed: " + "".join(output)[-8000:])
    result.update(
        budget_seconds=wall_seconds,
        elapsed_seconds=time.monotonic() - started,
        deadline_exceeded=bool(result.get("deadline_exceeded", False)),
    )
    return result, output


def watchdog_probe(source: Path, record: Path, wall_seconds: float = 0.25) -> dict:
    name = "dcec-watchdog-" + uuid.uuid4().hex[:12]
    command = [*_run_prefix(source, record), "--name", name, IMAGE, PYTHON,
               "/source/dcec_isolated_record_worker.py", "hang"]
    process = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1)
    cleanup_started = None
    try:
        result, _ = _drive_worker(process, wall_seconds, lambda _: None, lambda: None)
    finally:
        cleanup_started = time.monotonic()
        _stop_process(process)
        docker("rm", "-f", name, check=False, timeout=30)
        cleanup_seconds = time.monotonic() - cleanup_started
    result.update(cleanup_seconds=cleanup_seconds)
    return result


def _gateway_config(profile: dict) -> dict:
    endpoint = urlsplit(str(profile["apibase"]))
    if endpoint.scheme != "https" or not endpoint.hostname:
        raise ValueError("isolated gateway requires a fixed HTTPS provider")
    key = profile["apikey"]
    headers = {"x-api-key": key} if key.startswith("sk-ant-") else {
        "Authorization": "Bearer " + key}
    tls, _ = production_tls_semantics(profile)
    return {"models": {"monitor": {
        "base": profile["apibase"], "headers": headers,
        "paths": ["/v1/messages"], "model": profile["model"], "tls": tls,
    }}, "telemetry": "http://127.0.0.1:9/v1/traces"}


def _collect_gateway_diagnostics(container: str, destination: Path) -> list[dict]:
    """Archive only the gateway's explicitly safe structured stage events."""
    completed = docker("logs", container, check=False, timeout=30)
    allowed = {
        "event", "timestamp", "thread", "stage", "status",
        "exception_type", "http_status",
    }
    records = []
    for line in (completed.stdout + "\n" + completed.stderr).splitlines():
        try:
            item = json.loads(line)
        except (TypeError, ValueError):
            continue
        if not isinstance(item, dict) or item.get("event") != "gateway_transport":
            continue
        records.append({key: item[key] for key in allowed if key in item})
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records),
        encoding="utf-8")
    return records


def run_record(source: Path, record: Path, profile: dict, dcec: bool, max_turns: int,
               wall_seconds: float, on_intervention, on_root_ready) -> dict:
    token = uuid.uuid4().hex[:12]
    volume, gateway, main = f"dcec-channel-{token}", f"dcec-gateway-{token}", f"dcec-main-{token}"
    docker("volume", "create", volume)
    with tempfile.TemporaryDirectory(prefix="dcec-gateway-") as temporary:
        gateway_root = Path(temporary)
        _, ca_path = production_tls_semantics(profile)
        (gateway_root / "config.json").write_text(
            json.dumps(_gateway_config(profile)), encoding="utf-8")
        shutil.copy2(TRANSPORT, gateway_root / "transport.py")
        if ca_path is not None:
            shutil.copy2(ca_path, gateway_root / "ca-bundle.pem")
        result = None
        cleanup_seconds = None
        gateway_diagnostics = []
        gateway_started = False
        try:
            docker("run", "-d", "--rm", "--name", gateway, "--network", "bridge",
                   "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
                   "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev",
                   "--mount", f"type=bind,src={RUNTIME.resolve()},dst=/opt/m4-runtime,readonly",
                   "--mount", f"type=bind,src={gateway_root.resolve()},dst=/gateway,readonly",
                   "--mount", f"type=volume,src={volume},dst=/run/model-channel",
                   IMAGE, PYTHON, "/gateway/transport.py", "gateway", "--config", "/gateway/config.json")
            gateway_started = True
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
                       "execute", "--dcec", "1" if dcec else "0", "--max-turns", str(max_turns),
                       "--wall-seconds", str(wall_seconds)]
            process = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1)
            result, _ = _drive_worker(
                process, wall_seconds, on_intervention, on_root_ready)
        finally:
            cleanup_started = time.monotonic()
            if "process" in locals():
                _stop_process(process)
            if gateway_started:
                gateway_diagnostics = _collect_gateway_diagnostics(
                    gateway, record / "monitor/audit/gateway_transport.jsonl")
            docker("rm", "-f", main, check=False, timeout=30)
            docker("rm", "-f", gateway, check=False, timeout=30)
            docker("volume", "rm", "-f", volume, check=False, timeout=30)
            cleanup_seconds = time.monotonic() - cleanup_started
        if result is None:
            raise RuntimeError("isolated record did not produce a result")
        result["cleanup_seconds"] = cleanup_seconds
        result["gateway_transport_diagnostic_events"] = len(gateway_diagnostics)
        return result
