"""Zero-network regression for the UC-R5 research execution bridge."""
from __future__ import annotations

import asyncio
import http.client
import http.server
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import threading
import time
from types import SimpleNamespace
from uuid import uuid4

import pytest

from method_discovery.uc_r5_bridge_gateway import gate_resolver, digest, install
from method_discovery.uc_r5_execution_bridge import Bridge, frozen_task_tree_sha, manifest_identity, tar_manifest
from method_discovery.uc_r5_execution_entry import bridge_source_hash, load_authorized_slot, overlay_bundle


def _resolved(path, body, config, route_id=None):
    # No socket, provider, or usable credential exists in this resolver.
    payload = json.loads(body)
    route = {"model": payload["model"]}
    return "https://invalid.example/v1/messages", {}, json.dumps(payload).encode(), route


def _request(model="claude-opus-4-8"):
    return json.dumps({"model": model, "messages": [{"role": "user", "content": "x"}]}).encode()


def test_no_permit_blocks_upstream_without_network(tmp_path):
    calls = []

    def original(*args):
        calls.append("resolve")
        return _resolved(*args)

    resolve = gate_resolver(original, tmp_path, "offline-slot", 0.04)
    with pytest.raises(TimeoutError):
        resolve("/v1/messages", _request(), {}, "monitor")
    assert calls == ["resolve"]
    assert not list(tmp_path.glob("*.request_sent.json"))


def test_monitor_first_then_task_independent_byte_identity(tmp_path):
    resolve = gate_resolver(_resolved, tmp_path, "offline-slot", 1.0)
    outputs = {}
    source = _request()

    def invoke(role):
        outputs[role] = resolve("/v1/messages", source, {}, "monitor" if role == "monitor" else None)

    for role in ("monitor", "task"):
        thread = threading.Thread(target=invoke, args=(role,))
        thread.start()
        deadline = time.monotonic() + 1.0
        while not list(tmp_path.glob("*.pending.json")) and time.monotonic() < deadline:
            time.sleep(0.005)
        pending = next(iter(sorted(tmp_path.glob("*.pending.json"))))
        request = json.loads(pending.read_text(encoding="utf-8"))
        assert request["role"] == role
        assert (tmp_path / f"{request['request_id']}.request.json").read_bytes() == outputs.get(role, (None, None, _resolved("", source, {})[2]))[2]
        permit = dict(request, decision="allow")
        (tmp_path / f"{request['request_id']}.permit.json").write_text(json.dumps(permit), encoding="utf-8")
        thread.join(timeout=1)
        assert not thread.is_alive()
        assert outputs[role] == _resolved("/v1/messages", source, {})
        pending.unlink()


def test_mismatched_and_closed_permits_fail(tmp_path):
    resolve = gate_resolver(_resolved, tmp_path, "offline-slot", 0.4)
    failure = []

    def invoke():
        try:
            resolve("/v1/messages", _request(), {}, "monitor")
        except Exception as exc:
            failure.append(type(exc).__name__)

    thread = threading.Thread(target=invoke)
    thread.start()
    deadline = time.monotonic() + 1
    while not list(tmp_path.glob("*.pending.json")) and time.monotonic() < deadline:
        time.sleep(0.005)
    pending = json.loads(next(tmp_path.glob("*.pending.json")).read_text(encoding="utf-8"))
    wrong = dict(pending, decision="allow", slot_id="another-slot")
    (tmp_path / f"{pending['request_id']}.permit.json").write_text(json.dumps(wrong), encoding="utf-8")
    thread.join(timeout=1)
    assert failure == ["ValueError"]
    (tmp_path / "closed.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="closed"):
        resolve("/v1/messages", _request(), {}, "monitor")


def test_gateway_real_handler_preserves_request_and_stream_with_fake_upstream(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parent.parent / "long_context_bench/adapters/isolated_transport.py"
    spec = importlib.util.spec_from_file_location("uc_r5_frozen_transport_offline", path)
    assert spec and spec.loader
    transport = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(transport)
    original = transport._resolve_request
    expected = original("/v1/messages", _request(), {
        "models": {"monitor": {"base": "https://invalid.example", "headers": {"x-api-key": "fake-only"},
                               "paths": ["/v1/messages"], "model": "claude-opus-4-8"}},
        "telemetry": "http://invalid.example/v1/traces"}, "monitor")
    transport.create_tls_context = lambda _route: None
    upstream = []

    class FakeResponse:
        status = 200

        def __init__(self):
            self.chunks = iter((b"first", b"second", b""))

        def getheader(self, name, default=None):
            return "application/json" if name.lower() == "content-type" else default

        def read1(self, _size):
            return next(self.chunks)

    class FakeConnection:
        def __init__(self, *_args, **_kwargs):
            pass

        def connect(self):
            pass

        def request(self, method, target, body, headers):
            upstream.append((method, target, body, headers))

        def getresponse(self):
            return FakeResponse()

        def close(self):
            pass

    monkeypatch.setattr(transport.http.client, "HTTPSConnection", FakeConnection)
    install(transport, tmp_path, "offline-slot", 1.0)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), transport.Handler)
    server.mode = "gateway"
    server.config = {
        "models": {"monitor": {"base": "https://invalid.example", "headers": {"x-api-key": "fake-only"},
                               "paths": ["/v1/messages"], "model": "claude-opus-4-8"}},
        "telemetry": "http://invalid.example/v1/traces",
    }
    server.socket_path = "unused"
    runner = threading.Thread(target=server.serve_forever, daemon=True)
    runner.start()
    done = threading.Event()

    def permits():
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not done.is_set():
            for pending_path in tmp_path.glob("*.pending.json"):
                pending = json.loads(pending_path.read_text(encoding="utf-8"))
                permit = dict(pending, decision="allow")
                (tmp_path / f"{pending['request_id']}.permit.json").write_text(
                    json.dumps(permit), encoding="utf-8")
                return
            time.sleep(0.005)

    permit_thread = threading.Thread(target=permits, daemon=True)
    permit_thread.start()
    try:
        client = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=3)
        client.request("POST", "/v1/messages", body=_request(), headers={"x-model-route": "monitor"})
        response = client.getresponse()
        assert response.status == 200
        assert response.read() == b"firstsecond"
        assert len(upstream) == 1
        assert upstream[0][2] == expected[2]
        assert upstream[0][3]["x-api-key"] == "fake-only"
        assert len(list(tmp_path.glob("*.request_sent.json"))) == 1
        client.close()
    finally:
        done.set()
        server.shutdown()
        server.server_close()
        runner.join(timeout=2)


def test_gateway_send_position_closes_without_calling_upstream(tmp_path):
    sent = []

    class FakeHTTPS:
        def request(self, *args, **kwargs):
            sent.append((args, kwargs))

    fake = SimpleNamespace(_resolve_request=_resolved,
                           emit_transport_event=lambda *_args, **_kwargs: None,
                           http=SimpleNamespace(client=SimpleNamespace(HTTPSConnection=FakeHTTPS)))
    install(fake, tmp_path, "offline-slot", 0.01)
    (tmp_path / "closed.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="closed"):
        FakeHTTPS().request("POST", "/v1/messages", body=b"x", headers={})
    assert sent == []


def test_workspace_tar_manifest_files_modes_symlink(tmp_path):
    tar_path = tmp_path / "app.tar"
    with tarfile.open(tar_path, "w") as archive:
        content = b"before evaluation\n"
        info = tarfile.TarInfo("./source.py")
        info.mode = 0o755
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))
        link = tarfile.TarInfo("./link")
        link.type = tarfile.SYMTYPE
        link.linkname = "source.py"
        archive.addfile(link)
    manifest = tar_manifest(tar_path)
    assert manifest["entries"][0]["link_target"] == "source.py"
    assert manifest["entries"][1]["sha256"] == digest(b"before evaluation\n")
    assert manifest["entries"][1]["mode"] == 0o755
    before = manifest_identity(manifest)
    with tarfile.open(tar_path, "w") as archive:
        info = tarfile.TarInfo("./source.py")
        info.size = 5
        archive.addfile(info, io.BytesIO(b"after"))
    assert manifest_identity(tar_manifest(tar_path)) != before


def test_frozen_prereg_does_not_authorize_any_slot(tmp_path):
    with pytest.raises((RuntimeError, FileNotFoundError)):
        load_authorized_slot("25f65dbd77c41d3a039c91f5", tmp_path / "missing-authorization.json")
    false_authorization = tmp_path / "false.json"
    false_authorization.write_text(json.dumps({"execution_authorized": False}), encoding="utf-8")
    with pytest.raises(RuntimeError):
        load_authorized_slot("25f65dbd77c41d3a039c91f5", false_authorization)


def test_bridge_source_hash_uses_canonical_text_bytes(monkeypatch):
    # These are the only files included in the source hash; simulating a Git
    # CRLF checkout must not change the identity used by the addendum.
    from method_discovery import uc_r5_execution_entry as entry

    baseline = bridge_source_hash()
    original = Path.read_bytes

    def crlf_read(path):
        data = original(path)
        if path.suffix == ".py" and path.name.startswith("uc_r5_"):
            return data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        return data

    monkeypatch.setattr(Path, "read_bytes", crlf_read)
    assert entry.bridge_source_hash() == baseline


def test_harbor_cli_bootstrap_fails_before_original_cli_without_authorization():
    harbor_python = Path(r"E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe")
    if not harbor_python.exists():
        pytest.skip("Installed Harbor Python unavailable")
    repo = Path(__file__).resolve().parent.parent
    env = os.environ.copy()
    env.pop("UC_R5_BRIDGE_SPEC", None)
    env["PYTHONPATH"] = str(repo) + os.pathsep + env.get("PYTHONPATH", "")
    command = [str(harbor_python), str(repo / "method_discovery/uc_r5_bridge_harbor_cli.py"), "--help"]
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    assert result.returncode != 0
    assert "Missing UC-R5 bridge specification" in result.stderr


def test_five_condition_overlay_changes_gateway_only_not_deployed_profiles(tmp_path):
    repo = Path(__file__).resolve().parent.parent
    checklist = json.loads((repo / "method_discovery/runs/uc_r5_comparison_v1_20261003/SLOT_EXECUTION_CHECKLIST.json").read_text(encoding="utf-8"))
    slots = {}
    for row in checklist["proposed_slots"]:
        slots.setdefault(row["condition"], row)
    assert set(slots) == {"C0", "RP", "AP", "RB", "AB"}
    for condition, slot in slots.items():
        source = Path(slot["deployment"]["bundle_source"])
        if not source.exists():
            pytest.skip("Private offline bundle unavailable")
        monitor = source / "monitor_agent_core/models.local.json"
        task = source / "mykey.json"
        before = (digest(monitor.read_bytes()), digest(task.read_bytes()))
        folder = tmp_path / condition
        folder.mkdir()
        compose_path = folder / "isolation.compose.json"
        compose_path.write_text(json.dumps({"services": {"model-gateway": {
            "entrypoint": ["/frozen/python", "/gateway/transport.py", "gateway"],
            "volumes": ["/frozen/gateway:/gateway:ro"],
        }}}), encoding="utf-8")
        (folder / "isolation_identity.json").write_text(json.dumps({
            "snapshot_sha256": slot["deployment"]["bundle_snapshot_sha256"]}), encoding="utf-8")
        (folder / "gateway").mkdir()
        (folder / "gateway/transport.py").write_bytes(b"frozen test transport")
        spec_path = folder / "bridge_spec.json"
        spec_path.write_text("{}", encoding="utf-8")

        def original_build():
            return source, compose_path

        wrapped = overlay_bundle(original_build, repo / "method_discovery/uc_r5_bridge_gateway.py",
                                 folder / "control", slot, spec_path)
        assert wrapped() == (source, compose_path)
        after = (digest(monitor.read_bytes()), digest(task.read_bytes()))
        assert after == before
        compose = json.loads(compose_path.read_text(encoding="utf-8"))
        assert compose["services"]["model-gateway"]["entrypoint"][2:4] == ["--transport", "/gateway/transport.py"]


def test_actual_harbor_hook_emit_is_fail_closed():
    harbor_python = Path(r"E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe")
    if not harbor_python.exists():
        pytest.skip("Installed Harbor source unavailable")
    code = """
import asyncio
from types import SimpleNamespace
from harbor.trial.hooks import TrialEvent
from harbor.trial.trial import Trial
from harbor.models.trial.config import TrialConfig
from harbor.models.trial.result import TrialResult
from harbor.models.job.lock import TrialLock
from uuid import uuid4
events=[]
fake=SimpleNamespace(task=SimpleNamespace(name='offline'),
  config=TrialConfig.model_construct(trial_name='offline'),
  result=TrialResult.model_construct(id=uuid4()),
  _trial_lock=TrialLock.model_construct(), _hooks={event: [] for event in TrialEvent})
async def first(_): events.append('capture')
async def fail(_):
  events.append('stop')
  raise RuntimeError('capture failed')
async def forbidden(_): events.append('evaluation')
fake._hooks[TrialEvent.AGENT_END]=[first,fail]
fake._hooks[TrialEvent.VERIFICATION_START]=[forbidden]
try: asyncio.run(Trial._emit(fake, TrialEvent.AGENT_END))
except RuntimeError as exc: assert str(exc)=='capture failed'
else: raise AssertionError('hook failure swallowed')
assert events==['capture','stop']
print('HOOK_FAIL_CLOSED')
"""
    result = subprocess.run([str(harbor_python), "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "HOOK_FAIL_CLOSED" in result.stdout


def test_installed_harbor_single_step_never_evaluates_after_capture_failure():
    harbor_python = Path(r"E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe")
    if not harbor_python.exists():
        pytest.skip("Installed Harbor Python unavailable")
    code = """
import asyncio
from types import SimpleNamespace
from harbor.trial.hooks import TrialEvent
from harbor.trial.single_step import SingleStepTrial
from harbor.models.task.config import VerifierEnvironmentMode
import harbor.trial.single_step as ss
ss.resolve_task_verifier_mode=lambda _: VerifierEnvironmentMode.SHARED
events=[]
async def agent():
  events.append('agent')
  raise RuntimeError('capture failed')
async def collect(**_): events.append('artifact_collection')
async def verify(): events.append('evaluator')
async def noop(): pass
fake=SimpleNamespace(task=SimpleNamespace(config=SimpleNamespace(agent=SimpleNamespace(continue_until_timeout=False))),
  _run_agent=agent, _upload_agent_logs=noop, _collect_artifacts=collect,
  _run_verifier=verify, _stop_agent_environment=noop)
try: asyncio.run(SingleStepTrial._run(fake))
except RuntimeError as exc: assert str(exc)=='capture failed'
else: raise AssertionError('capture failure swallowed')
assert events==['agent']
print('EVALUATOR_BLOCKED')
"""
    result = subprocess.run([str(harbor_python), "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "EVALUATOR_BLOCKED" in result.stdout


def test_evaluator_binding_rejects_changed_workspace(tmp_path, monkeypatch):
    original = {"entries": [{"path": "marker", "sha256": digest(b"before")}]}
    changed = {"entries": [{"path": "marker", "sha256": digest(b"after")}]}
    original["workspace_manifest_sha256"] = manifest_identity(original)
    changed["workspace_manifest_sha256"] = manifest_identity(changed)
    archive = tmp_path / "archive"
    archive.mkdir()
    (archive / "pre_verification_capture.json").write_text(
        json.dumps({"container_id": "a" * 64}), encoding="utf-8")
    bridge = Bridge(SimpleNamespace(id="offline"), {
        "slot": {"run_id": "offline"}, "control_dir": str(tmp_path / "control"),
        "archive_dir": str(archive),
    })
    bridge.capture = original

    async def inspect():
        return {"container_id": "a" * 64}

    async def capture(_path):
        return changed

    monkeypatch.setattr(bridge, "inspect", inspect)
    monkeypatch.setattr(bridge, "_capture_tar", capture)
    with pytest.raises(RuntimeError, match="changed"):
        asyncio.run(bridge.verification_start(None))
    assert not (archive / "verification_release.json").exists()


def test_host_gate_validates_each_role_and_denies_cross_slot_or_input_error(tmp_path, monkeypatch):
    control = tmp_path / "control"
    control.mkdir()
    bridge = Bridge(SimpleNamespace(id="offline"), {
        "slot": {"run_id": "offline", "deployment": {"configured_monitor_model": "claude-opus-4-8"}},
        "task_model": "claude-opus-4-8", "control_dir": str(control),
        "archive_dir": str(tmp_path / "audit"),
    })
    bridge.initial_container_id = "a" * 64
    observed = []

    async def inspect():
        return {"container_id": "a" * 64}

    async def verify_role(role):
        observed.append(role)
        if role == "task":
            raise RuntimeError("task input changed")
        return {"role": role, "observed_sha256": "f" * 64}

    monkeypatch.setattr(bridge, "inspect", inspect)
    monkeypatch.setattr(bridge, "verify_role_input", verify_role)

    def pending(request_id, role, slot="offline"):
        body = _request()
        (control / f"{request_id}.request.json").write_bytes(body)
        path = control / f"{request_id}.pending.json"
        path.write_text(json.dumps({"slot_id": slot, "request_id": request_id,
                                    "role": role, "route_id": "monitor" if role == "monitor" else None,
                                    "request_sha256": digest(body)}), encoding="utf-8")
        return path

    asyncio.run(bridge.process_pending(pending("one", "monitor")))
    one = json.loads((control / "one.permit.json").read_text(encoding="utf-8"))
    assert one["decision"] == "allow"
    asyncio.run(bridge.process_pending(pending("two", "task")))
    two = json.loads((control / "two.permit.json").read_text(encoding="utf-8"))
    assert two["decision"] == "deny" and two["error"] == "task input changed"
    asyncio.run(bridge.process_pending(pending("three", "monitor", "other")))
    three = json.loads((control / "three.permit.json").read_text(encoding="utf-8"))
    assert three["decision"] == "deny"
    assert observed == ["monitor", "task"]


@pytest.mark.parametrize("fault", ["image", "network", "mount"])
def test_dynamic_trial_identity_fault_blocks_before_agent(tmp_path, monkeypatch, fault):
    repo = Path(__file__).resolve().parent.parent
    monkeypatch.syspath_prepend(str(repo / "long_context_bench"))
    from scripts.isolated_run_bundle import digest_tree

    source = tmp_path / "source"
    profile = source / "monitor_agent_core/models.local.json"
    profile.parent.mkdir(parents=True)
    profile.write_text("{}", encoding="utf-8")
    run_id = "offline-slot"
    job = tmp_path / "jobs" / run_id
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "task.toml").write_text("[task]\nname='offline'\n", encoding="utf-8")
    trial = SimpleNamespace(
        id="offline", agent=SimpleNamespace(run_id=run_id),
        paths=SimpleNamespace(trial_dir=job / "trial"),
        task=SimpleNamespace(instruction="Public task", task_dir=task_dir),
    )
    slot = {
        "run_id": run_id,
        "candidate_commit": "232281d650d062bdc6a6030f40ccb904c1ac0851",
        "output": {"campaign_root": str(tmp_path)},
        "task_identity": {"instruction_sha256": digest(b"Public task"),
                          "task_tree_sha256": frozen_task_tree_sha(task_dir),
                          "task_toml_sha256": digest((task_dir / "task.toml").read_bytes())},
        "image": {"id": "sha256:" + "a" * 64},
    }
    bridge = Bridge(trial, {
        "slot": slot, "control_dir": str(tmp_path / "control"),
        "archive_dir": str(tmp_path / "archive"),
        "generated_bundle_source": str(source),
        "generated_bundle_source_sha256": digest_tree(source),
        "generated_monitor_profile_sha256": digest(profile.read_bytes()),
    })
    actual = {"container_id": "b" * 64, "image": slot["image"]["id"],
              "network_mode": "none", "command": ["sh", "-c", "sleep infinity"], "mounts": [
                  {"destination": "/opt/genericagent-source", "source": "private-source", "read_only": True},
                  {"destination": "/opt/m4-runtime", "source": "private-runtime", "read_only": True},
              ]}
    if fault == "image":
        actual["image"] = "sha256:" + "c" * 64
    elif fault == "network":
        actual["network_mode"] = "bridge"
    else:
        actual["mounts"].append({"destination": "/tests", "source": "hidden", "read_only": True})

    async def inspect(service="main"):
        if service == "model-gateway":
            return {"network_mode": "bridge", "mounts": [
                {"destination": "/bridge/control", "source": "private", "read_only": False}],
                "container_id": "d" * 64}
        return actual

    monkeypatch.setattr(bridge, "inspect", inspect)
    with pytest.raises(RuntimeError):
        asyncio.run(bridge.identity_gate())
    assert not (tmp_path / "archive/agent_start_identity.json").exists()


def test_nonbenchmark_container_restart_kills_delayed_writer_and_preserves_capture(tmp_path):
    docker = subprocess.run(["docker", "info", "--format", "{{.OSType}}"],
                            capture_output=True, text=True)
    if docker.returncode or docker.stdout.strip() != "linux":
        pytest.skip("Linux Docker engine unavailable")
    name = "uc-r5-offline-" + uuid4().hex[:12]

    def docker_call(*args):
        result = subprocess.run(["docker", *args], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    try:
        container = docker_call("run", "-d", "--name", name, "--network", "none",
                                "debian:bookworm-slim", "sh", "-c", "mkdir -p /app; sleep infinity")
        docker_call("exec", name, "sh", "-c", "printf before > /app/source.py")
        docker_call("exec", name, "sh", "-c",
                    "(sleep 3; printf late > /app/source.py) </dev/null >/dev/null 2>&1 &")
        class FakeEnvironment:
            async def _run_docker_compose_command(self, args):
                if args == ["ps", "-q", "main"]:
                    return SimpleNamespace(stdout=container)
                if args == ["stop", "main"]:
                    docker_call("stop", "-t", "1", name)
                elif args == ["start", "main"]:
                    docker_call("start", name)
                else:
                    raise AssertionError(args)
                return SimpleNamespace(stdout="")

            async def exec(self, command_text, **_kwargs):
                assert command_text == "git -C /app status --porcelain=v1 -uall"
                return SimpleNamespace(return_code=128, stdout="")

        bridge = Bridge(SimpleNamespace(id="offline", agent_environment=FakeEnvironment()), {
            "slot": {"run_id": "offline"}, "control_dir": str(tmp_path / "control"),
            "archive_dir": str(tmp_path / "audit"),
        })
        asyncio.run(bridge.agent_end(None))
        manifest = bridge.capture
        assert manifest is not None
        assert next(row for row in manifest["entries"] if row["path"] == "source.py")["sha256"] == digest(b"before")
        # The delay belongs only to this synthetic writer regression, not to
        # the production capture or synchronization algorithm.
        time.sleep(3.5)
        assert docker_call("exec", name, "sh", "-c", "cat /app/source.py") == "before"
        asyncio.run(bridge.verification_start(None))
        release = json.loads((tmp_path / "audit/verification_release.json").read_text(encoding="utf-8"))
        assert release["pre_verification_workspace_sha256"] == manifest["workspace_manifest_sha256"]
        assert release["boundary_workspace_sha256"] == manifest["workspace_manifest_sha256"]
        docker_call("exec", name, "sh", "-c", "printf marker > /app/fake_evaluation_marker")
        assert not any(row["path"] == "fake_evaluation_marker" for row in manifest["entries"])
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True)
