"""UC-R5 research-only Harbor hooks and first-send authorization controller.

No import from the production Monitor is made here.  This module is loaded
only by an explicitly armed Harbor subprocess; without a separate, exact
authorization the executable entry refuses to launch.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import tarfile
import time
from typing import Any


FROZEN_PREREG_SHA256 = "657ebd27c48f248bc6bcceb66d95e5040fafe1d3f6ff7b972ad8fa1390d52ce0"
FROZEN_CANDIDATE = "232281d650d062bdc6a6030f40ccb904c1ac0851"
FROZEN_HARBOR_BASE = "459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: Path) -> str:
    return sha(path.read_bytes())


def frozen_task_tree_sha(root: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(root.rglob("*")):
        if item.is_symlink():
            raise RuntimeError("Symlink appeared in task asset")
        if not item.is_file() or ".git" in item.relative_to(root).parts:
            continue
        digest.update(item.relative_to(root).as_posix().encode() + b"\0" + item.read_bytes())
    return digest.hexdigest()


def save_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def tar_manifest(tar_path: Path) -> dict[str, Any]:
    """Hash every archived entry, including modes and symlink targets."""
    members: list[dict[str, Any]] = []
    with tarfile.open(tar_path, "r:*") as archive:
        for member in archive:
            path = member.name.removeprefix("./")
            if not path or path == ".":
                continue
            if path.startswith("/") or ".." in Path(path).parts:
                raise ValueError("Unsafe path in workspace archive")
            entry: dict[str, Any] = {
                "path": path, "mode": member.mode,
                "size": member.size,
                "type": ("file" if member.isfile() else
                         "directory" if member.isdir() else
                         "symlink" if member.issym() else
                         "hardlink" if member.islnk() else "other"),
            }
            if member.isfile():
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError(f"Missing archived bytes: {path}")
                digest = hashlib.sha256()
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
                entry["sha256"] = digest.hexdigest()
            elif member.issym() or member.islnk():
                entry["link_target"] = member.linkname
            members.append(entry)
    members.sort(key=lambda row: row["path"])
    return {"entries": members, "tar_sha256": file_sha(tar_path)}


def manifest_identity(manifest: dict[str, Any]) -> str:
    return sha(json.dumps(manifest["entries"], sort_keys=True, separators=(",", ":")).encode())


async def command(*argv: str) -> str:
    process = await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    if process.returncode:
        raise RuntimeError(f"Command failed ({process.returncode}): {argv[0]} {stderr.decode(errors='replace')[:400]}")
    return stdout.decode(errors="replace").strip()


class Bridge:
    def __init__(self, trial: Any, spec: dict[str, Any]):
        self.trial = trial
        self.spec = spec
        self.slot = spec["slot"]
        self.control = Path(spec["control_dir"])
        self.archive = Path(spec["archive_dir"])
        self.controller: asyncio.Task | None = None
        self.closed = False
        self.seen: set[str] = set()
        self.role_checked: set[str] = set()
        self.started = False
        self.capture: dict[str, Any] | None = None
        self.initial_container_id: str | None = None

    def receipt(self, name: str, payload: dict[str, Any]) -> None:
        save_json(self.archive / (name + ".json"), payload)

    async def container_id(self, service: str = "main") -> str:
        environment = self.trial.agent_environment
        result = await environment._run_docker_compose_command(["ps", "-q", service])
        container = result.stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{12,64}", container):
            raise RuntimeError("Cannot identify current trial main container")
        return container

    async def inspect(self, service: str = "main") -> dict[str, Any]:
        container = await self.container_id(service)
        raw = json.loads(await command("docker", "inspect", container))[0]
        mounts = [{"destination": m["Destination"], "type": m["Type"],
                   "source": m.get("Source"), "read_only": not m.get("RW", False)}
                  for m in raw.get("Mounts", [])]
        return {
            "container_id": container,
            "image": raw["Image"],
            "network_mode": raw["HostConfig"]["NetworkMode"],
            "command": raw["Config"].get("Cmd"),
            "mounts": mounts,
            "state": raw["State"]["Status"],
        }

    async def identity_gate(self) -> None:
        began = time.perf_counter_ns()
        if self.slot["candidate_commit"] != FROZEN_CANDIDATE:
            raise RuntimeError("Candidate identity mismatch")
        # Harbor trial_name has its own random suffix; the frozen runner's
        # opaque run identity is carried by the installed agent instead.
        if getattr(self.trial.agent, "run_id", None) != self.slot["run_id"]:
            raise RuntimeError("Agent/run identity mismatch")
        planned_job = (Path(self.slot["output"]["campaign_root"]) / "jobs" / self.slot["run_id"]).resolve()
        if not Path(self.trial.paths.trial_dir).resolve().is_relative_to(planned_job):
            raise RuntimeError("Trial output root differs from frozen slot")
        if sha(self.trial.task.instruction.encode()) != self.slot["task_identity"]["instruction_sha256"]:
            raise RuntimeError("Actual task instruction mismatch")
        task_dir = self.trial.task.task_dir
        if frozen_task_tree_sha(task_dir) != self.slot["task_identity"]["task_tree_sha256"]:
            raise RuntimeError("Actual Harbor task tree mismatch")
        if file_sha(task_dir / "task.toml") != self.slot["task_identity"]["task_toml_sha256"]:
            raise RuntimeError("Actual Harbor task config mismatch")
        from scripts.isolated_run_bundle import digest_tree
        bundle_source = Path(self.spec["generated_bundle_source"])
        if (digest_tree(bundle_source) != self.spec["generated_bundle_source_sha256"]
                or file_sha(bundle_source / "monitor_agent_core" / "models.local.json")
                != self.spec["generated_monitor_profile_sha256"]):
            raise RuntimeError("Generated deployment changed before agent start")
        actual = await self.inspect()
        gateway = await self.inspect("model-gateway")
        self.initial_container_id = actual["container_id"]
        expected = self.slot["image"]["id"]
        if actual["image"] != expected:
            raise RuntimeError("Actual image mismatch")
        if actual["network_mode"] != "none":
            raise RuntimeError("Task container network is not none")
        if actual["command"] != ["sh", "-c", "sleep infinity"]:
            raise RuntimeError("Task container keepalive command differs from frozen Harbor mode")
        destinations = {mount["destination"]: mount for mount in actual["mounts"]}
        if "/app" in destinations:
            raise RuntimeError("Unexpected external /app mount")
        for destination in ("/opt/genericagent-source", "/opt/m4-runtime"):
            if destination not in destinations or not destinations[destination]["read_only"]:
                raise RuntimeError(f"Missing read-only deployment mount: {destination}")
        forbidden = ("/tests", "/solution", "checkpoint", "guarded_worker", "scripted", "prereg")
        for mount in actual["mounts"]:
            if any(word in (mount["destination"] + " " + str(mount["source"])).lower() for word in forbidden):
                raise RuntimeError("Forbidden mount in actual container")
        if gateway["network_mode"] != "bridge":
            raise RuntimeError("Gateway network identity mismatch")
        gateway_destinations = {mount["destination"] for mount in gateway["mounts"]}
        if "/app" in gateway_destinations or "/bridge/control" not in gateway_destinations:
            raise RuntimeError("Gateway mount identity mismatch")
        self.receipt("agent_start_identity", {"trial_id": str(self.trial.id), "actual": actual,
                                               "gateway": gateway,
                                               "task_instruction_sha256": sha(self.trial.task.instruction.encode()),
                                               "gate_duration_ms": (time.perf_counter_ns() - began) / 1_000_000})

    async def _read_container_sha(self, command_text: str) -> str:
        result = await self.trial.agent_environment.exec(command_text, user="root", timeout_sec=30)
        if result.return_code:
            raise RuntimeError("Cannot read back deployed input")
        value = result.stdout.strip().split()[0]
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise RuntimeError("Invalid deployed input digest")
        return value

    async def verify_role_input(self, role: str) -> dict[str, Any]:
        expected = self.slot["task_identity"]
        if role == "task":
            run_id = self.slot["run_id"]
            observed = await self._read_container_sha(
                f"sha256sum /opt/genericagent/temp/{run_id}/input.txt")
            wanted = expected["actual_task_input_sha256"]
        elif role == "monitor":
            observed = await self._read_container_sha(
                "set -- /app/.monitor_original_task_*.txt; "
                "test \"$#\" -eq 1 && test -f \"$1\" && sha256sum \"$1\"")
            wanted = expected["monitor_original_task_sha256"]
        else:
            raise RuntimeError("Unknown model route")
        if observed != wanted:
            raise RuntimeError(f"{role} deployed input mismatch")
        return {"role": role, "observed_sha256": observed, "expected_sha256": wanted}

    async def process_pending(self, path: Path) -> None:
        began = time.perf_counter_ns()
        request = json.loads(path.read_text(encoding="utf-8"))
        request_id = request["request_id"]
        if request_id in self.seen:
            return
        self.seen.add(request_id)
        receipt: dict[str, Any] = dict(request)
        try:
            if self.closed or request["slot_id"] != self.slot["run_id"]:
                raise RuntimeError("Closed or cross-slot request")
            role = request["role"]
            if role not in ("monitor", "task"):
                raise RuntimeError("Unknown model route")
            if role == "monitor" and request.get("route_id") != "monitor":
                raise RuntimeError("Monitor route identity mismatch")
            if role == "task" and request.get("route_id") == "monitor":
                raise RuntimeError("Task route identity mismatch")
            current = await self.inspect()
            if current["container_id"] != self.initial_container_id:
                raise RuntimeError("Trial container replaced before model send")
            body = (self.control / f"{request_id}.request.json").read_bytes()
            if sha(body) != request["request_sha256"]:
                raise RuntimeError("Provider-ready bytes/hash mismatch")
            payload = json.loads(body)
            expected_model = self.slot["deployment"]["configured_monitor_model"] if role == "monitor" else self.spec["task_model"]
            if payload.get("model") != expected_model:
                raise RuntimeError("Configured model mismatch")
            if role not in self.role_checked:
                receipt["input_readback"] = await self.verify_role_input(role)
                self.role_checked.add(role)
            receipt["decision"] = "allow"
        except Exception as exc:
            receipt["decision"] = "deny"
            receipt["error_type"] = type(exc).__name__
            receipt["error"] = str(exc)
        receipt["gate_duration_ms"] = (time.perf_counter_ns() - began) / 1_000_000
        receipt["decision_time_ns"] = time.time_ns()
        self.receipt(f"first_send_{request_id}", receipt)
        save_json(self.control / f"{request_id}.permit.json", receipt)

    async def serve_gate(self) -> None:
        while not self.closed:
            for path in sorted(self.control.glob("*.pending.json")):
                await self.process_pending(path)
            await asyncio.sleep(0.02)

    async def agent_start(self, _event: Any) -> None:
        self.control.mkdir(parents=True, exist_ok=True)
        self.archive.mkdir(parents=True, exist_ok=True)
        await self.identity_gate()
        self.controller = asyncio.create_task(self.serve_gate())

    async def _capture_tar(self, destination: Path) -> dict[str, Any]:
        began = time.perf_counter_ns()
        container = await self.container_id()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as output:
            process = await asyncio.create_subprocess_exec(
                "docker", "cp", f"{container}:/app/.", "-",
                stdout=output, stderr=asyncio.subprocess.PIPE)
            _, stderr = await process.communicate()
        if process.returncode:
            raise RuntimeError("Workspace capture failed: " + stderr.decode(errors="replace")[:400])
        manifest = tar_manifest(destination)
        manifest["workspace_manifest_sha256"] = manifest_identity(manifest)
        manifest["capture_duration_ms"] = (time.perf_counter_ns() - began) / 1_000_000
        manifest["tar_bytes"] = destination.stat().st_size
        return manifest

    async def agent_end(self, _event: Any) -> None:
        self.closed = True
        save_json(self.control / "closed.json", {"slot_id": self.slot["run_id"], "time_ns": time.time_ns()})
        if self.controller:
            await self.controller
        for path in sorted(self.control.glob("*.pending.json")):
            await self.process_pending(path)
        sent = sorted(self.control.glob("*.request_sent.json"))
        connected = sorted(self.control.glob("*.connected.json"))
        send_status = ("started" if sent else "unknown_after_connection"
                       if connected else "not_started")
        self.receipt("inference_send_accounting", {
            "status": send_status, "request_sent_count": len(sent),
            "connection_count": len(connected),
            "roles_verified": sorted(self.role_checked),
        })
        environment = self.trial.agent_environment
        before = await self.container_id()
        await environment._run_docker_compose_command(["stop", "main"])
        await environment._run_docker_compose_command(["start", "main"])
        after = await self.container_id()
        if before != after:
            raise RuntimeError("Task container identity changed during writer termination")
        # The base main service is sleep-infinity; stop/start kills every old
        # process in this container without removing its writable layer.
        processes = await command("docker", "top", after)
        if any(marker in processes.lower() for marker in ("agentmain.py", "monitor_agent", "python3.12")):
            raise RuntimeError("Task or Monitor process survived writer termination")
        self.capture = await self._capture_tar(self.archive / "pre_verification_app.tar")
        git_result = await environment.exec(
            "git --no-optional-locks -C /app status --porcelain=v1 -uall", user="root", timeout_sec=30)
        self.receipt("pre_verification_capture", {
            "trial_id": str(self.trial.id), "container_id": after,
            "writer_termination": "docker-compose-stop-start-main",
            "processes_after_restart": processes,
            "git_status": git_result.stdout if git_result.return_code == 0 else None,
            "git_status_available": git_result.return_code == 0,
            "manifest": self.capture,
        })

    async def verification_start(self, _event: Any) -> None:
        began = time.perf_counter_ns()
        if self.capture is None:
            raise RuntimeError("No committed pre-verification capture")
        current = await self.inspect()
        previous = json.loads((self.archive / "pre_verification_capture.json").read_text(encoding="utf-8"))
        if current["container_id"] != previous["container_id"]:
            raise RuntimeError("Verifier environment replaced after capture")
        latest = await self._capture_tar(self.archive / "verification_boundary_app.tar")
        if latest["workspace_manifest_sha256"] != self.capture["workspace_manifest_sha256"]:
            raise RuntimeError("/app changed between capture and evaluator boundary")
        self.receipt("verification_release", {
            "trial_id": str(self.trial.id), "container_id": current["container_id"],
            "pre_verification_workspace_sha256": self.capture["workspace_manifest_sha256"],
            "boundary_workspace_sha256": latest["workspace_manifest_sha256"],
            "decision": "allow_original_evaluator",
            "verification_binding_duration_ms": (time.perf_counter_ns() - began) / 1_000_000,
        })

    async def trial_end(self, event: Any) -> None:
        verifier_result = getattr(event.result, "verifier_result", None)
        self.receipt("trial_end_binding", {
            "trial_id": str(self.trial.id),
            "captured_workspace_sha256": (
                self.capture["workspace_manifest_sha256"] if self.capture else None),
            "verification_released": (self.archive / "verification_release.json").exists(),
            "verifier_result_sha256": (
                sha(verifier_result.model_dump_json().encode())
                if verifier_result is not None else None),
            "exception_type": (getattr(getattr(event.result, "exception_info", None),
                                        "exception_type", None)),
        })


def install_trial_hooks() -> None:
    """Called only from a separately armed Harbor process bootstrap."""
    from harbor.trial.hooks import TrialEvent
    from harbor.trial.trial import Trial

    spec_path = os.environ.get("UC_R5_BRIDGE_SPEC")
    if not spec_path:
        raise RuntimeError("Missing UC-R5 bridge specification")
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    if spec.get("execution_authorized") is not True:
        raise RuntimeError("UC-R5 execution is not authorized")
    from method_discovery.uc_r5_execution_entry import load_authorized_slot
    authorization_path = Path(spec["authorization_path"])
    if file_sha(authorization_path) != spec.get("authorization_sha256"):
        raise RuntimeError("UC-R5 authorization bytes changed")
    selected, _ = load_authorized_slot(spec["slot"]["run_id"], authorization_path)
    if selected != spec["slot"]:
        raise RuntimeError("UC-R5 slot differs from authorization")
    original = Trial.create.__func__

    async def create(cls, config):
        trial = await original(cls, config)
        bridge = Bridge(trial, spec)
        trial.add_hook(TrialEvent.AGENT_START, bridge.agent_start)
        trial.add_hook(TrialEvent.AGENT_END, bridge.agent_end)
        trial.add_hook(TrialEvent.VERIFICATION_START, bridge.verification_start)
        trial.add_hook(TrialEvent.END, bridge.trial_end)
        return trial

    Trial.create = classmethod(create)
