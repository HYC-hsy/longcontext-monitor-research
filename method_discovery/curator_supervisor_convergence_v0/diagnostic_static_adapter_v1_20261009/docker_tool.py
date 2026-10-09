"""Offline tool port: bounded commands in the frozen image, never a provider."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import codecs
from pathlib import Path
import subprocess
import threading
import time
import uuid

from .adapter import save_json
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
        for name in ("home", "tmp", "build_cache", "output"):
            path = self.private / ".static_runtime" / name
            path.mkdir(parents=True, exist_ok=True)
            if path.is_symlink():
                raise RuntimeError("Symlinked runtime scratch")
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
                "--tmpfs", "/tests:ro,noexec,nosuid,size=1m",
                "--mount", f"type=bind,source={self.app},destination=/app,readonly",
                "--mount", f"type=bind,source={self.evidence},destination=/logs/agent/monitor/task_evidence,readonly",
                "--mount", f"type=bind,source={self.private},destination=/logs/agent/monitor/monitor_private",
                "--mount", f"type=bind,source={self.private / '.static_runtime' / 'home'},destination=/home/monitor",
                "--mount", f"type=bind,source={self.private / '.static_runtime' / 'tmp'},destination=/tmp",
                "--mount", f"type=bind,source={self.private / '.static_runtime' / 'build_cache'},destination=/cache",
                "--mount", f"type=bind,source={self.private / '.static_runtime' / 'output'},destination=/output",
                "--env", "HOME=/home/monitor", "--env", "TMPDIR=/tmp",
                "--env", "GOCACHE=/cache/go", "--env", "GOMODCACHE=/cache/gomod",
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
                if args.get("code"):
                    raise ValueError("Use session_id alone for read/cancel")
                return self._read_session(session, args.get("wait_seconds", 1), args.get("cancel", False))
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
            raise ValueError("cancel requires a new-session identifier")
        code = args.get("code")
        kind = args.get("type", "python")
        timeout = args.get("timeout", 60)
        wait_seconds = args.get("wait_seconds", 1)
        if not isinstance(code, str) or not code.strip() or kind not in {"python", "bash"}:
            raise ValueError("Invalid new code_run request")
        if type(timeout) is not int or not 1 <= timeout <= 300:
            raise ValueError("New code_run timeout must be in [1, 300]")
        self._validate_wait(wait_seconds)
        session = "static-" + uuid.uuid4().hex
        directory = self.private / "audit" / "commands" / session
        directory.mkdir(parents=True)
        script = directory / ("script.py" if kind == "python" else "script.sh")
        script.write_text(code, encoding="utf-8")
        output = directory / "output.log"
        command = self._docker_args(session, script, kind)
        with output.open("wb") as stream:
            process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT,
                                       stdin=subprocess.DEVNULL)
        entry = {"process": process, "output": output, "cursor": 0,
                 "started": time.monotonic(), "timeout": timeout,
                 "done": threading.Event(), "cancel": threading.Event(), "reason": None}
        self.new_sessions[session] = entry
        threading.Thread(target=self._watch_session, args=(session, entry), daemon=True).start()
        return self._read_session(session, wait_seconds, False)

    @staticmethod
    def _validate_wait(value):
        if type(value) not in (int, float) or not 0 <= value <= 5:
            raise ValueError("wait_seconds must be in [0, 5]")

    def _watch_session(self, session: str, entry: dict):
        process = entry["process"]
        try:
            while process.poll() is None:
                if entry["cancel"].is_set() or time.monotonic() - entry["started"] >= entry["timeout"]:
                    entry["reason"] = "cancelled" if entry["cancel"].is_set() else "timeout"
                    cleanup = subprocess.run(["docker", "rm", "-f", session],
                                             capture_output=True, timeout=10, check=False)
                    if cleanup.returncode != 0 and process.poll() is None:
                        entry["reason"] = "cleanup_error"
                    break
                time.sleep(0.05)
            process.wait(timeout=12)
        except Exception:
            entry["reason"] = "cleanup_error"
            try: subprocess.run(["docker", "rm", "-f", session],
                                capture_output=True, timeout=10, check=False)
            except Exception: pass
        finally:
            save_json(entry["output"].with_name("result.json"), {
                "exit_code": process.poll(), "reason": entry["reason"],
                "duration_seconds": time.monotonic() - entry["started"]})
            entry["done"].set()

    def _read_session(self, session: str, wait_seconds=1, cancel=False):
        self._validate_wait(wait_seconds)
        if type(cancel) is not bool:
            raise ValueError("cancel must be boolean")
        entry = self.new_sessions[session]
        if cancel:
            entry["cancel"].set()
        entry["done"].wait(wait_seconds)
        finished = entry["done"].is_set()
        output = entry["output"]
        with output.open("rb") as stream:
            stream.seek(entry["cursor"])
            raw = stream.read(12000)
        end = entry["cursor"] + len(raw) >= output.stat().st_size
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        text = decoder.decode(raw, final=finished and end)
        buffered, _ = decoder.getstate()
        entry["cursor"] += len(raw) - len(buffered)
        unread = max(0, output.stat().st_size - entry["cursor"])
        exit_code = entry["process"].poll() if finished else None
        return {"status": ("success" if exit_code == 0 and not entry["reason"] else "error") if finished else "running",
                "session_id": session, "stdout": text, "exit_code": exit_code,
                "reason": entry["reason"], "unread_bytes": unread,
                "output_path": f"monitor/audit/commands/{session}/output.log",
                "next_read": {"session_id": session} if not finished or unread else None,
                "historical": False}

    def close(self):
        for entry in self.new_sessions.values():
            if not entry["done"].is_set():
                entry["cancel"].set()
        for entry in self.new_sessions.values():
            entry["done"].wait(12)
        if any(not entry["done"].is_set() for entry in self.new_sessions.values()):
            raise RuntimeError("Analysis container cleanup unconfirmed")
