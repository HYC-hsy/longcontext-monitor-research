"""Host-only launcher for the frozen three-arm synthetic invoice check.

No PMA, snapshot, full financial Task, or verifier is started. Each arm gets a
fresh original Task image container, a separate writable /app bind, and a
separate gateway/Unix channel. The provider configuration is gateway-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid


ROOT = Path(__file__).resolve().parent
PARENT_RUN = Path(
    r"E:\LongContext\_pma_task_recheck_snapshot_20261121\live-02"
    r"\01-financial-document-processor-r1\runs\pma-155bb23ee8ea4b19")
IMAGE = "alexgshaw/financial-document-processor:20251031"
ARMS = ("none", "general", "targeted")
PYTHON = "/opt/m4-runtime/python/cpython-3.12.12-linux-x86_64-gnu/bin/python3.12"
RUNTIME = Path(r"E:\LongContext\bench_runtime\m2\linux")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mount(source: Path, destination: str, readonly: bool = False) -> str:
    text = f"type=bind,src={source.resolve(strict=True).as_posix()},dst={destination}"
    return text + (",readonly" if readonly else "")


def docker(*args: str, timeout: float | None = 60) -> str:
    result = subprocess.run(["docker", *args], capture_output=True,
                            encoding="utf-8", errors="replace", timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"docker {args[0]} returned {result.returncode}; "
                           "private stderr retained only in the local process")
    return result.stdout.strip()


def checked_plan() -> dict:
    design = json.loads((ROOT / "design.json").read_text(encoding="utf-8"))
    seed = json.loads((ROOT / "request_seed.json").read_text(encoding="utf-8-sig"))
    if design["task_turns_max"] != 4 or tuple(a["name"] for a in design["arms"]) != ARMS:
        raise RuntimeError("frozen three-arm design changed")
    if seed["task_model"] != "claude-opus-4-8" or seed["temperature"] != 1:
        raise RuntimeError("Task model no longer matches original financial run")
    source = PARENT_RUN / "bundle/source"
    profile = source / "mykey.json"
    if sha(profile).lower() != seed["task_profile_sha256"].lower():
        raise RuntimeError("staged Task model profile hash differs")
    gateway = PARENT_RUN / "bundle/gateway"
    compose = json.loads((PARENT_RUN / "bundle/isolation.compose.json").read_text(
        encoding="utf-8"))
    service = compose["services"]["model-gateway"]
    if service.get("image") != "debian:bookworm-slim" or not service.get("entrypoint"):
        raise RuntimeError("original model gateway identity unavailable")
    if not (gateway / "config.json").is_file() or not (gateway / "transport.py").is_file():
        raise RuntimeError("original gateway bundle missing")
    if not RUNTIME.is_dir() or not (source / "isolated_transport.py").is_file():
        raise RuntimeError("original Task runtime missing")
    fixture = {p.relative_to(ROOT / "fixture").as_posix(): sha(p)
               for p in (ROOT / "fixture").rglob("*") if p.is_file()}
    if len(fixture) != 4:
        raise RuntimeError("synthetic fixture must have three sources and one CSV")
    for arm in ARMS:
        workspace = ROOT / "workspaces" / arm
        for rel, digest in fixture.items():
            if sha(workspace / rel) != digest:
                raise RuntimeError("arm workspace differs before its first run")
        preflight = ROOT / "preflight" / arm / "preflight.json"
        if not preflight.is_file():
            raise RuntimeError("zero-model native Task preflight missing")
        observed = json.loads(preflight.read_text(encoding="utf-8"))
        if observed["model"]["model"] != seed["task_model"] or len(observed["file_receipts"]) != 4:
            raise RuntimeError("zero-model native Task preflight failed")
    return {"schema": "synthetic-invoice-run-plan-v1", "arms": list(ARMS),
            "task_model": seed["task_model"], "temperature": seed["temperature"],
            "thinking_type": seed["thinking_type"], "max_tokens": seed["max_tokens"],
            "api_mode": seed["api_mode"], "stream": seed["stream"],
            "task_profile_sha256": sha(profile),
            "task_image_id": json.loads(docker("image", "inspect", IMAGE))[0]["Id"],
            "source_dir": str(source), "gateway_image": service["image"],
            "gateway_config_sha256": sha(gateway / "config.json"),
            "fixture_sha256": fixture, "max_turns_per_arm": 4,
            "max_logical_task_turns_total": 12, "manager": "not_run",
            "native_verifier": "not_run"}


def run_one(arm: str, plan: dict) -> dict:
    if arm not in ARMS:
        raise ValueError("unplanned arm")
    output = ROOT / "runs" / arm
    if output.exists():
        raise FileExistsError("arm already has output; no automatic rerun")
    output.mkdir(parents=True)
    agent_log = output / "agent"
    agent_log.mkdir()
    token = uuid.uuid4().hex[:12]
    volume = "lc-syninv-channel-" + token
    gateway_name = "lc-syninv-gateway-" + token
    task_name = "lc-syninv-task-" + token
    source = PARENT_RUN / "bundle/source"
    gateway_dir = PARENT_RUN / "bundle/gateway"
    service = json.loads((PARENT_RUN / "bundle/isolation.compose.json").read_text(
        encoding="utf-8"))["services"]["model-gateway"]
    made = []
    try:
        docker("volume", "create", volume)
        made.append(("volume", volume))
        docker("run", "-d", "--name", gateway_name, "--network", "bridge",
               "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
               "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev",
               "--mount", mount(RUNTIME, "/opt/m4-runtime", True),
               "--mount", mount(gateway_dir, "/gateway", True),
               "--mount", f"type=volume,src={volume},dst=/run/model-channel",
               "--entrypoint", service["entrypoint"][0], service["image"],
               *service["entrypoint"][1:])
        made.append(("container", gateway_name))
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                docker("exec", gateway_name, PYTHON, "-c",
                       "import socket;s=socket.socket(socket.AF_UNIX);"
                       "s.connect('/run/model-channel/gateway.sock');s.close()",
                       timeout=5)
                break
            except RuntimeError:
                time.sleep(.5)
        else:
            raise RuntimeError("model gateway did not become ready")
        docker("run", "-d", "--name", task_name, "--network", "none",
               "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
               "--workdir", "/app", "--env", "GA_LANG=en",
               "--env", "GA_LLM_CONFIG_NAME=native_claude_cc_vibe_opus48",
               "--env", "GA_PMA_UPSTREAM_ENABLED=0",
               "--env", "GA_PMA_ENABLED=0", "--env", "GA_MONITOR_ENABLED=0",
               "--env", "GA_STATEFUL_MEMORY_ENABLED=0", "--env", "GA_POS_ENABLED=0",
               "--env", "GA_EXPERIMENT_RUNTIME_POLICY=v1",
               "--env", "GA_EXPERIMENT_TASK_TURNS=4",
               "--env", "GA_TASK_DEADLINE_EPOCH=uncapped",
               "--env", f"GA_BENCH_RUN_ID=synthetic-{arm}-{token}",
               "--env", "GA_BENCH_TASK_ID=synthetic-invoice",
               "--env", "PYTHONPATH=/opt/genericagent:"
                        "/opt/m4-runtime/ga-env/lib/python3.12/site-packages",
               "--mount", mount(ROOT / "workspaces" / arm, "/app"),
               "--mount", mount(source, "/opt/genericagent-source", True),
               "--mount", mount(ROOT / "request_seed.json", "/opt/request_seed.json", True),
               "--mount", mount(ROOT / "synthetic_entry.py", "/opt/synthetic_entry.py", True),
               "--mount", mount(agent_log, "/logs/agent"),
               "--mount", mount(RUNTIME, "/opt/m4-runtime", True),
               "--mount", f"type=volume,src={volume},dst=/run/model-channel,readonly",
               "--entrypoint", "sleep", IMAGE, "infinity")
        made.append(("container", task_name))
        docker("exec", task_name, "sh", "-c",
               "cp -a /opt/genericagent-source /opt/genericagent")
        docker("exec", "-d", task_name, PYTHON,
               "/opt/genericagent/isolated_transport.py", "local")
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                docker("exec", task_name, PYTHON, "-c",
                       "import socket;s=socket.create_connection(('127.0.0.1',18765),1);s.close()",
                       timeout=5)
                break
            except RuntimeError:
                time.sleep(.25)
        else:
            raise RuntimeError("Task local model relay did not become ready")
        docker("exec", task_name, PYTHON, "/opt/synthetic_entry.py",
               "--seed", "/opt/request_seed.json", "--arm", arm,
               "--output", "/logs/agent/result.json", timeout=None)
        result = agent_log / "result.json"
        if not result.is_file():
            raise RuntimeError("Task branch has no bound result file")
        return {"arm": arm, "result_sha256": sha(result),
                "result_path": str(result), "status": "completed"}
    finally:
        cleanup = []
        for kind, name in reversed(made):
            args = ("rm", "-f", name) if kind == "container" else ("volume", "rm", "-f", name)
            result = subprocess.run(["docker", *args], capture_output=True, timeout=60)
            cleanup.append({"kind": kind, "name": name, "removed": result.returncode == 0})
        (output / "cleanup.json").write_text(json.dumps(cleanup, indent=2),
                                              encoding="utf-8")
        if any(not row["removed"] for row in cleanup):
            raise RuntimeError("synthetic arm cleanup incomplete; stop queue")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("plan", "run"))
    args = parser.parse_args()
    plan = checked_plan()
    if args.command == "plan":
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    for arm in ARMS:
        print(json.dumps(run_one(arm, plan), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
