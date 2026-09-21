"""Run the single authorized frozen DCEC-v1 CLAW-SWE generalization task."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "long_context_bench"
GA_ROOT = ROOT / "GenericAgent-main"
RUNTIME = ROOT / "bench_runtime" / "m2"
RUNTIME_LINUX = RUNTIME / "linux"
MANIFEST = (
    ROOT / "method_discovery" / "runs" / "dcec_v1_generalization_20260921"
    / "claw_swe_sphinx8551_manifest.json"
)
RUN_ID = "dcec-v1-generalization-claw-swe-sphinx8551-r1"
INSTANCE_ID = "sphinx-doc__sphinx-8551"
CAMPAIGN_ROOT = BENCH / "output" / "dcec_v1_generalization_20260921"
M3_ROOT = CAMPAIGN_ROOT / "claw_swe"
LOCKS = CAMPAIGN_ROOT / "claw_swe_method_locks.jsonl"
BUNDLE_ROOT = CAMPAIGN_ROOT / "isolated_bundles" / RUN_ID
RESULT_PATH = CAMPAIGN_ROOT / "launch_result.json"
GATEWAY_LOG = CAMPAIGN_ROOT / "gateway_transport.log"
MECHANISM_COMMIT = "746a695adac4325d6440941d384d543d1364fef9"
EXPECTED_GA_HASH = "641e6e21bbe6dc5562e4d7832fbc90d2046f9e63b7cbec3595424e661eb14cea"

MECHANISM_HASHES = {
    "monitor_agent_core/agent.py": "953c56b45c56d88577488e5c2c1b5491513d45e528a577490310ec584ca3e52d",
    "monitor_agent_core/working_context.py": "01e583d1c8cc11cc4385186f73d491dc1bf6b1bd0c1221ded35e2c1fc685a848",
    "monitor_agent_core/provider.py": "58e70a6a040591d5dc701d9ee0767e820cc6a604a8d42181b2a72c2e24187ee2",
    "monitor_agent_core/loop.py": "62dd73063c197495bc043381b74b4c00689d9321160dbda858f7ca1fac1f9548",
    "monitor_agent_core/workspace.py": "52272d83626aa561e7fe0aa2e4fc04d90707d8320f20ffffefef0ad1a990f40d",
    "monitor_agent_core/handoff_validation.py": "2a0c521d636b29067d62a04cf8e965d3310f0e3a7b0ac63f1061ad2a6f5d42e3",
    "monitor_agent_core/actions.py": "9b26d28a5d1adfe98a24afda0819bc26c7ca4ce072ab22cf8cc2a635b9637ea3",
    "monitor_agent_core/process_runner.py": "cebc138ff0a31fa952d37e585a33e587908cd0da2c0fb07ad62c4e1ce2793ec7",
}

DCEC_ENV = {
    "GA_RUN_ISOLATION": "no-network-unix-inference-v1",
    "GA_BASELINE_CONDITION": "original",
    "GA_EXPERIMENT_ID": "dcec-v1-generalization-claw-swe-sphinx8551-r1",
    "GA_CONDITION_ID": "dcec-v1",
    "GA_LLM_CONFIG_NAME": "native_claude_cc_vibe",
    "GA_MAX_TURNS": "300",
    "GA_MONITOR_ENABLED": "1",
    "GA_MONITOR_CONFIG": "claude_monitor_opus48",
    "GA_MONITOR_EXPECTED_MODEL": "claude-opus-4-8",
    "GA_PROVIDER_MAX_RETRIES": "8",
    "GA_MONITOR_DCEC": "1",
    "GA_MONITOR_DCEC_WORKING_CHARS": "4000",
    "GA_PMA_ENABLED": "0",
    "GA_MONITOR_GROUNDED_CONTEXT": "0",
    "GA_MONITOR_HANDOFF_VALIDATION": "0",
    "GA_MONITOR_ADVICE_REVISION": "0",
    "GA_MONITOR_FEEDBACK_FOCUS": "0",
    "GA_MONITOR_INQUIRY": "0",
    "GA_MONITOR_TOOL_FEEDBACK": "0",
    "GA_MONITOR_ACTIVE_WORKING_CONTEXT": "0",
    "GA_MONITOR_LIVE_AWARENESS": "0",
    "GA_MONITOR_DECISION_CONTEXT": "0",
    "GA_MONITOR_INDEPENDENT_C": "0",
    "GA_MONITOR_PMA_MEMORY": "0",
    "GA_MONITOR_ROOT_DECISION_CONTRACT": "0",
    "GA_MONITOR_ROOT_SIMPLE_CHECK": "0",
    "GA_MONITOR_ROOT_CAPTURE_REQUIRED": "0",
    "GA_MONITOR_TASK_MODEL": "0",
    "GA_MONITOR_HYBRID_CONTROL": "0",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def docker(*args: str, check: bool = True, timeout: int = 180) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=timeout
    )
    if check and result.returncode:
        raise RuntimeError(
            f"docker {' '.join(args)} failed ({result.returncode}): "
            f"{(result.stderr or result.stdout).strip()}"
        )
    return result


def verify_frozen_identity(manifest: dict) -> None:
    if manifest.get("execution_authorized") is not True:
        raise RuntimeError("generalization execution is not authorized")
    if manifest.get("mechanism_implementation") != MECHANISM_COMMIT:
        raise RuntimeError("DCEC-v1 mechanism commit mismatch")
    for relative, expected in MECHANISM_HASHES.items():
        actual = sha256(GA_ROOT / relative)
        if actual != expected:
            raise RuntimeError(f"frozen mechanism source changed: {relative}")
    registry = BENCH / "tasks" / "benchmark_v1_final_120.jsonl"
    if sha256(registry) != manifest["task_registry_sha256"]:
        raise RuntimeError("frozen benchmark registry changed")
    rows = [json.loads(line) for line in registry.read_text(encoding="utf-8").splitlines()]
    if rows[0].get("global_task_id") != f"claw_swe:{INSTANCE_ID}":
        raise RuntimeError("selection rule no longer resolves to the frozen task")
    if (M3_ROOT / "runs" / RUN_ID).exists() or RESULT_PATH.exists():
        raise RuntimeError("immutable generalization output already exists")


def python_home() -> str:
    homes = sorted((RUNTIME_LINUX / "python").glob("cpython-3.12.*-linux-x86_64-gnu"))
    if len(homes) != 1:
        raise RuntimeError(f"expected one Python 3.12 runtime, found {homes}")
    return homes[0].name


def install_isolated_adapter(m3, source_snapshot: Path, volume: str):
    original = m3.configure_m2_for_lock

    def configure(lock):
        module = original(lock)
        base = module.M2GenericAgentAdapter

        class IsolatedDCECAdapter(base):
            def container_run_args(self, instance_id):
                host_temp = self.temp_root / instance_id
                host_temp.mkdir(parents=True, exist_ok=True)
                host_memory = self.memory_root / instance_id
                if host_memory.exists():
                    shutil.rmtree(host_memory)
                shutil.copytree(source_snapshot / "memory", host_memory)
                host_artifacts = self.artifacts_root / instance_id
                host_artifacts.mkdir(parents=True, exist_ok=True)
                args = ["--network", "none", "--cap-drop", "ALL",
                        "--security-opt", "no-new-privileges:true"]
                args += module._mount(module.RUNTIME_HOST, module.CONTAINER_RUNTIME, "ro")
                args += module._mount(source_snapshot, module.CONTAINER_GA, "ro")
                args += module._mount(host_temp, f"{module.CONTAINER_GA}/temp", "rw")
                args += module._mount(host_memory, f"{module.CONTAINER_GA}/memory", "rw")
                args += module._mount(host_artifacts, "/opt/m2-artifacts", "rw")
                args += ["--mount", f"type=volume,src={volume},dst=/run/model-channel,readonly"]
                return args

            def post_container_start(self, workspace):
                py = f"{module.CONTAINER_RUNTIME}/python/{python_home()}/bin/python3.12"
                check = docker(
                    "exec", workspace.container_name, "bash", "-lc",
                    "test -S /run/model-channel/gateway.sock && "
                    "test \"$(ls /sys/class/net)\" = lo && "
                    "test ! -S /var/run/docker.sock && "
                    "test ! -f /opt/genericagent/mykey.py && "
                    "test ! -d /opt/genericagent/tests",
                )
                if check.returncode:
                    raise RuntimeError("CLAW-SWE task isolation check failed")
                docker(
                    "exec", "-d", workspace.container_name, py,
                    f"{module.CONTAINER_GA}/isolated_transport.py", "local",
                )
                for _ in range(50):
                    ready = docker(
                        "exec", workspace.container_name, py, "-c",
                        "import socket;s=socket.create_connection(('127.0.0.1',18765),1);s.close()",
                        check=False,
                    )
                    if ready.returncode == 0:
                        return
                    time.sleep(0.1)
                raise RuntimeError("local isolated inference transport did not become ready")

            def build_exec_command(self, agent_id, container_name, instance_id):
                command = super().build_exec_command(agent_id, container_name, instance_id)
                cleaned = []
                index = 0
                while index < len(command):
                    if (command[index] == "-e" and index + 1 < len(command)
                            and command[index + 1].split("=", 1)[0].endswith("_API_KEY")):
                        index += 2
                        continue
                    if (command[index] == "-e" and index + 1 < len(command)
                            and command[index + 1].startswith("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=")):
                        cleaned += ["-e", "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:18765/v1/traces"]
                        index += 2
                        continue
                    cleaned.append(command[index])
                    index += 1
                container_index = cleaned.index(container_name)
                environment = dict(DCEC_ENV)
                environment.update({
                    "GA_MONITOR_ARTIFACT_DIR": "/opt/m2-artifacts/monitor",
                    "GA_RESEARCH_EVENT_PATH": "/opt/m2-artifacts/research_events.jsonl",
                    "GA_TASK_WORKSPACE_DIR": "/testbed",
                    "GA_INLINE_LONG_PROMPT": "1",
                })
                additions = []
                for name, value in environment.items():
                    additions += ["-e", f"{name}={value}"]
                return cleaned[:container_index] + additions + cleaned[container_index:]

        module.M2GenericAgentAdapter = IsolatedDCECAdapter
        return module

    m3.configure_m2_for_lock = configure


def execute() -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    verify_frozen_identity(manifest)
    os.environ.update(DCEC_ENV)
    os.environ["GA_METHOD_EXPECTED_SOURCE_SHA256"] = EXPECTED_GA_HASH
    os.environ["CLAW_SWE_M3_ROOT"] = str(M3_ROOT)
    os.environ["CLAW_SWE_M3_LOCKS"] = str(LOCKS)
    sys.path.insert(0, str(BENCH))
    from scripts import run_claw_swe_m3 as m3
    from scripts.isolated_run_bundle import build_bundle

    m3.M3_ROOT = M3_ROOT
    m3.LOCKS = LOCKS
    m3.READINESS = M3_ROOT / "readiness.jsonl"
    m3.BATCH_LEDGER = M3_ROOT / "batch_ledger.jsonl"
    m3.COLLECTOR_NAME = "dcec-v1-generalization-claw-swe-otel"
    m3.COLLECTOR_PORT = 15328
    M3_ROOT.mkdir(parents=True, exist_ok=True)

    readiness = m3.scan("all", False, False, [INSTANCE_ID])
    if len(readiness) != 1 or readiness[0]["status"] != "ready":
        raise RuntimeError(f"frozen CLAW-SWE task is not ready: {readiness}")

    source_snapshot, _ = build_bundle(
        BUNDLE_ROOT, GA_ROOT, RUNTIME_LINUX, python_home(),
        "native_claude_cc_vibe", "claude_monitor_opus48", m3.COLLECTOR_PORT,
        monitor_profile_path=ROOT / "monitor_config" / "models.local.json",
    )
    token = hashlib.sha256(RUN_ID.encode()).hexdigest()[:12]
    volume = f"dcec-v1-generalization-{token}"
    gateway = f"dcec-v1-gateway-{token}"
    docker("volume", "create", volume)
    gateway_started = False
    run_finished = False
    evaluated = False
    error = None
    try:
        gateway_root = BUNDLE_ROOT / "gateway"
        py = f"/opt/m2-runtime/python/{python_home()}/bin/python3.12"
        docker(
            "run", "-d", "--rm", "--name", gateway, "--network", "bridge",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
            "--read-only", "--add-host", "host.docker.internal:host-gateway",
            "--mount", f"type=bind,src={RUNTIME_LINUX.resolve()},dst=/opt/m2-runtime,readonly",
            "--mount", f"type=bind,src={gateway_root.resolve()},dst=/gateway,readonly",
            "--mount", f"type=volume,src={volume},dst=/run/model-channel",
            "debian:bookworm-slim", py, "/gateway/transport.py", "gateway",
            "--config", "/gateway/config.json",
        )
        gateway_started = True
        for _ in range(60):
            probe = docker(
                "exec", gateway, py, "-c",
                "import socket;s=socket.socket(socket.AF_UNIX);s.connect('/run/model-channel/gateway.sock');s.close()",
                check=False,
            )
            if probe.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("isolated inference gateway did not become ready")

        install_isolated_adapter(m3, source_snapshot, volume)
        m3.execute(INSTANCE_ID, "run", RUN_ID, 7200, 0)
        run_finished = True
        m3.execute(INSTANCE_ID, "evaluate", RUN_ID, 7200, 0)
        evaluated = True
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        m3.stop_collector()
        if gateway_started:
            logs = docker("logs", gateway, check=False, timeout=60)
            GATEWAY_LOG.parent.mkdir(parents=True, exist_ok=True)
            GATEWAY_LOG.write_text(logs.stdout or logs.stderr or "", encoding="utf-8")
        docker("rm", "-f", gateway, check=False, timeout=60)
        docker("volume", "rm", "-f", volume, check=False, timeout=60)

    result = {
        "schema_version": "dcec-v1-generalization-launch/1",
        "run_id": RUN_ID,
        "task_id": f"claw_swe:{INSTANCE_ID}",
        "mechanism_implementation": MECHANISM_COMMIT,
        "run_finished": run_finished,
        "native_evaluation_finished": evaluated,
        "error": error,
        "retry_count": 0,
        "ordinary_control": False,
        "task_agent_profile": "native_claude_cc_vibe / claude-opus-4-6",
        "supervisor_profile": "claude_monitor_opus48 / claude-opus-4-8",
        "task_network_mode": "none",
    }
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if error:
        raise RuntimeError(error)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("the frozen runner only supports --execute")
    print(json.dumps(execute(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
