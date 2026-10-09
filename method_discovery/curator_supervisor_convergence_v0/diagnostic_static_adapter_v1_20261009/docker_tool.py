"""Offline tool port: bounded commands in the frozen image, never a provider."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time
import uuid

from .adapter import LIMITS, save_json
from method_discovery.curator_supervisor_convergence_v0.diagnostic_flex_preflight_v0_20261009.freeze_inputs import REPO


IMAGE = "sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1"


def _workspace_class():
    source = REPO / "GenericAgent-main/monitor_agent_core/workspace.py"
    spec = importlib.util.spec_from_file_location("static_diagnostic_workspace", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MonitorWorkspace


class DockerToolPort:
    def __init__(self, fixture: Path):
        self.fixture = Path(fixture).resolve(strict=True)
        self.app = self.fixture / "app"
        self.evidence = self.fixture / "task_evidence"
        self.private = self.fixture / "monitor_private"
        for directory in (self.app, self.evidence, self.private):
            if not directory.is_dir() or directory.is_symlink():
                raise RuntimeError("Incomplete or symlinked fixture mount")
        self.workspace = _workspace_class()(self.evidence, self.private,
                                             task_mounts={"workspace": self.app})
        self.new_sessions: dict[str, dict] = {}
        self.historical = json.loads((self.fixture / "RESEARCH_ONLY_MANIFEST.json").read_text(
            encoding="utf-8"))["outputs"]["historical_completed_outputs"]

    def _docker_args(self, session: str, script: Path, kind: str) -> list[str]:
        interpreter = {"python": "/usr/bin/python3", "bash": "/bin/bash"}[kind]
        virtual_script = "/logs/agent/monitor/monitor_private/" + script.relative_to(self.private).as_posix()
        return ["docker", "run", "--rm", "--name", session, "--network", "none",
                "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--tmpfs", "/tmp:rw,nosuid,size=512m", "--tmpfs", "/tests:ro,noexec,nosuid,size=1m",
                "--mount", f"type=bind,source={self.app},destination=/app,readonly",
                "--mount", f"type=bind,source={self.evidence},destination=/logs/agent/monitor/task_evidence,readonly",
                "--mount", f"type=bind,source={self.private},destination=/logs/agent/monitor/monitor_private",
                "--env", "HOME=/tmp", "--env", "GOCACHE=/tmp/go-cache",
                "--entrypoint", interpreter, IMAGE, virtual_script]

    def execute(self, name: str, args: dict) -> dict:
        if name == "file_read":
            return self.workspace.read_text(args["path"], **{key: value for key, value in args.items()
                                                              if key != "path"})
        if name == "file_write":
            cap = 16000 if args["path"] == "monitor/reference.md" else None
            return self.workspace.write_text(args["path"], args["content"],
                                             args.get("mode", "replace"), max_chars=cap)
        if name == "file_patch":
            cap = 16000 if args["path"] == "monitor/reference.md" else None
            return self.workspace.patch_text(args["path"], args["old_text"],
                                             args["new_text"], max_chars=cap)
        if name != "code_run":
            raise ValueError("Not an ordinary offline tool")
        if "session_id" in args:
            session = args["session_id"]
            if session in self.new_sessions:
                return dict(self.new_sessions[session])
            if session in self.historical:
                receipt = self.historical[session]
                output = self.private / "audit" / "commands" / session / "output.log"
                if hashlib.sha256(output.read_bytes()).hexdigest() != receipt["sha256"]:
                    raise RuntimeError("Historical receipt bytes changed")
                return {"status": "historical_completed", "session_id": session,
                        "output_path": f"monitor/audit/commands/{session}/output.log",
                        "sha256": receipt["sha256"], "historical": True}
            return {"status": "unavailable", "session_id": session,
                    "reason": "No cutoff-certified resumable session or complete historical output"}
        if args.get("cancel"):
            return {"status": "unavailable", "reason": "No active session identified"}
        code = args.get("code")
        kind = args.get("type", "python")
        timeout = args.get("timeout", 60)
        if not isinstance(code, str) or not code.strip() or kind not in {"python", "bash"}:
            raise ValueError("Invalid new code_run request")
        if type(timeout) is not int or not 1 <= timeout <= LIMITS["new_code_run_seconds"]:
            raise ValueError("New code_run timeout exceeds frozen 60-second cap")
        session = "static-" + uuid.uuid4().hex
        directory = self.private / "audit" / "commands" / session
        directory.mkdir(parents=True)
        script = directory / ("script.py" if kind == "python" else "script.sh")
        script.write_text(code, encoding="utf-8")
        output = directory / "output.log"
        command = self._docker_args(session, script, kind)
        started = time.monotonic()
        status, exit_code = "error", None
        try:
            with output.open("wb") as stream:
                completed = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                           timeout=timeout + 5, check=False)
            exit_code = completed.returncode
            status = "success" if exit_code == 0 else "error"
        except subprocess.TimeoutExpired:
            status = "cancelled_timeout"
            cleanup = subprocess.run(["docker", "rm", "-f", session], stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, timeout=10, check=False)
            if cleanup.returncode != 0:
                raise RuntimeError("Timed-out diagnostic container could not be confirmed removed")
        receipt = {"status": status, "session_id": session, "exit_code": exit_code,
                   "output_path": f"monitor/audit/commands/{session}/output.log",
                   "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                   "wait_seconds": time.monotonic() - started, "historical": False}
        save_json(directory / "result.json", receipt)
        self.new_sessions[session] = receipt
        return dict(receipt)
