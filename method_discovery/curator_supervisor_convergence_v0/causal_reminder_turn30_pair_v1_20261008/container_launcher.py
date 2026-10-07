"""Authorized C-then-T container launcher for the exact turn-30 checkpoint.

The parent never imports the Task Agent. Each arm uses a separate Docker
Compose project, task container, gateway volume, Python process, and /app.
No Docker command is run merely by importing or certifying this module.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from .continuation_adapter import TASK_IMAGE, canonical_sha, digest, workspace_identity
from .execution_control import ArmResult
from .native_evaluator_adapter import NativeEvaluator, verify_native_identity
from .pair_harness import (CHECKPOINT, EXPECTED, HERE, REMINDER,
                           REPO, _read_json, build_pair_requests, checkpoint_binding)
from method_discovery.curator_supervisor_convergence_v0.causal_reminder_turn30_20261007 import (
    materialize as checkpoint_materialize,
)


FROZEN_BUNDLE = Path(r"E:\LongContext\long_context_bench\output\crs_rhr_rer_fyne_mechanism_gate\isolated_bundles\crs-rhr-rer-v0-fyne-bji-high-budget-r1")
FROZEN_SOURCE_SNAPSHOT = "209340005e5a037a69a34d7b6ebfb33ad0bf1f0d55b51db929b2edf9a0205228"
FROZEN_GATEWAY_TRANSPORT = "0b7c4e010e01339e8e0853061f48f8f1fe9e4c382588d3058d3a0613d5a46e98"
FROZEN_GATEWAY_CONFIG_SHA = "0f97125ba596969f2ce9d858acc666a100b8ebf1f91f8d87c8391e1a9ef2c6a3"
GATEWAY_IMAGE = "sha256:88200866dfff7ea7f5cbcb6ec7c8a701889efe6fe859fe64d6990e4b07ea4171"
M4_RUNTIME = Path(r"E:\LongContext\bench_runtime\m2\linux")
PYTHON = "/opt/m4-runtime/python/cpython-3.12.12-linux-x86_64-gnu/bin/python3.12"
SITE_PACKAGES = "/opt/m4-runtime/ga-env/lib/python3.12/site-packages"


def digest_tree(root: Path) -> str:
    d = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or "temp" in relative.parts or path.suffix == ".pyc":
            continue
        if path.is_file():
            d.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
            d.update(path.read_bytes())
    return d.hexdigest()


def validate_frozen_execution_environment() -> dict:
    checkpoint_binding()
    source = FROZEN_BUNDLE / "source"
    gateway = FROZEN_BUNDLE / "gateway"
    identity = _read_json(FROZEN_BUNDLE / "isolation_identity.json")
    gateway_config = _read_json(gateway / "config.json")
    image = subprocess.check_output(["docker", "image", "inspect", TASK_IMAGE,
                                     "--format", "{{.Id}}"], text=True).strip()
    gateway_image = subprocess.check_output(["docker", "image", "inspect", GATEWAY_IMAGE,
                                             "--format", "{{.Id}}"], text=True).strip()
    if (image != TASK_IMAGE or gateway_image != GATEWAY_IMAGE
            or digest_tree(source) != FROZEN_SOURCE_SNAPSHOT
            or identity["snapshot_sha256"] != FROZEN_SOURCE_SNAPSHOT
            or identity["profile"] != "no-network-unix-inference-v1"
            or digest((gateway / "transport.py").read_bytes()) != FROZEN_GATEWAY_TRANSPORT
            or digest((gateway / "config.json").read_bytes()) != FROZEN_GATEWAY_CONFIG_SHA
            or gateway_config["models"]["claude-opus-4-8"]["model"] != "claude-opus-4-8"
            or gateway_config["models"]["claude-opus-4-8"]["paths"] != ["/v1/messages"]
            or not M4_RUNTIME.is_dir()):
        raise RuntimeError("Frozen task image/source/isolation transport identity mismatch")
    verify_native_identity()
    return {"task_image": image, "gateway_image": gateway_image,
            "source_snapshot_sha256": FROZEN_SOURCE_SNAPSHOT,
            "gateway_transport_sha256": FROZEN_GATEWAY_TRANSPORT,
            "gateway_config_sha256": FROZEN_GATEWAY_CONFIG_SHA,
            "task_code_root": "/app", "task_network_mode": "none"}


def compose_spec(workspace: Path, stage: Path, raw: Path, source: Path, *, project: str) -> dict:
    if not project.startswith("causal-turn30-"):
        raise RuntimeError("Unexpected isolated Compose project")
    gateway = FROZEN_BUNDLE / "gateway"
    for path in (workspace, stage, raw, source, gateway, M4_RUNTIME):
        if not path.exists():
            raise RuntimeError(f"Compose input absent: {path}")
    return {"services": {
        "model-gateway": {
            "image": GATEWAY_IMAGE, "network_mode": "bridge",
            "cap_drop": ["ALL"], "security_opt": ["no-new-privileges:true"],
            "read_only": True,
            "environment": {"SSL_CERT_FILE": SITE_PACKAGES + "/certifi/cacert.pem"},
            "volumes": [f"{M4_RUNTIME.as_posix()}:/opt/m4-runtime:ro",
                        f"{gateway.as_posix()}:/gateway:ro", "model-channel:/run/model-channel"],
            "entrypoint": [PYTHON, "/gateway/transport.py", "gateway", "--config",
                           "/gateway/config.json"], "command": [],
            "healthcheck": {"test": ["CMD", PYTHON, "-c",
                "import socket; s=socket.socket(socket.AF_UNIX); s.connect('/run/model-channel/gateway.sock'); s.close()"],
                "interval": "1s", "timeout": "3s", "retries": 30}},
        "main": {
            "image": TASK_IMAGE, "network_mode": "none", "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges:true"], "working_dir": "/app",
            "tmpfs": ["/tests"],
            "depends_on": {"model-gateway": {"condition": "service_healthy"}},
            "volumes": ["model-channel:/run/model-channel:ro",
                        f"{workspace.as_posix()}:/app",
                        f"{source.as_posix()}:/opt/genericagent",
                        f"{M4_RUNTIME.as_posix()}:/opt/m4-runtime:ro",
                        f"{stage.as_posix()}:/opt/causal-stage:ro",
                        f"{raw.as_posix()}:/logs/agent"],
            "environment": {"PYTHONPATH": SITE_PACKAGES + ":/opt/genericagent:/opt/causal-stage",
                            "GA_LANG": "en", "GA_PMA_ENABLED": "0", "GA_MONITOR_ENABLED": "0"},
            "entrypoint": [PYTHON, "/opt/causal-stage/arm_child.py", "--authorized-child"],
            "command": []}},
            "volumes": {"model-channel": {}}}


def zero_model_container_command(workspace: Path, stage: Path, source: Path) -> list[str]:
    """No gateway/network/provider: validate deployed request build in /app."""
    return ["docker", "run", "--rm", "--network", "none",
            "--mount", f"type=bind,src={workspace.resolve().as_posix()},dst=/app",
            "--mount", f"type=bind,src={stage.resolve().as_posix()},dst=/opt/causal-stage,readonly",
            "--mount", f"type=bind,src={source.resolve().as_posix()},dst=/opt/genericagent",
            "--mount", f"type=bind,src={M4_RUNTIME.resolve().as_posix()},dst=/opt/m4-runtime,readonly",
            "--env", "GA_LANG=en", "--env",
            "PYTHONPATH=" + SITE_PACKAGES + ":/opt/genericagent:/opt/causal-stage",
            "--workdir", "/app", TASK_IMAGE, PYTHON,
            "/opt/causal-stage/arm_child.py", "--validate-only"]


def prepare_arm_stage(arm: str, destination: Path, runtime: dict,
                      control: dict, treatment: dict) -> dict:
    if arm not in ("control", "treatment") or destination.exists():
        raise RuntimeError("Arm stage invalid or already exists")
    destination.mkdir(parents=True, exist_ok=False)
    expected = control if arm == "control" else treatment
    staged = copy.deepcopy(runtime)
    if arm == "treatment":
        staged["turn30_next_prompt"] += "\n\n" + REMINDER
    if staged["turn30_next_prompt"] != expected["messages"][-1]["content"][-1]["text"]:
        raise RuntimeError("Staged continuation text differs from frozen request")
    for name in ("arm_child.py", "continuation_adapter.py"):
        shutil.copy2(HERE / name, destination / name)
    runtime_file = destination / "runtime_checkpoint.json"
    runtime_file.write_text(json.dumps(staged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (destination / "expected_request.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    task_source = checkpoint_materialize.TASK
    task_bytes = task_source.read_bytes()
    if digest(task_bytes) != "cae5f11a98aa573cf93629b8fb0becc18f395c5bdad25e09b8927d06f0725080":
        raise RuntimeError("Historical public task source identity mismatch")
    (destination / "original_task.txt").write_bytes(task_bytes)
    permit = {"authorized_child": True,
              "expected_request_sha256": canonical_sha(expected),
              "runtime_state_file_sha256": digest(runtime_file.read_bytes()),
              "original_task_sha256": digest(task_bytes),
              "task_image": TASK_IMAGE, "turn_offset": 30, "max_additional_turns": 270}
    (destination / "launch_permit.json").write_text(json.dumps(permit, indent=2) + "\n",
                                                    encoding="utf-8")
    return {"expected_request_sha256": canonical_sha(expected),
            "runtime_checkpoint_sha256": digest(runtime_file.read_bytes()),
            "original_task_sha256": digest(task_bytes),
            "files": sorted(path.name for path in destination.iterdir())}


class ContainerPairRuntime:
    def __init__(self, output_root: Path):
        validate_frozen_execution_environment()
        if output_root.exists():
            raise RuntimeError("Fresh causal output root required")
        if output_root.resolve().is_relative_to(REPO.resolve()):
            raise RuntimeError("Causal raw output root must be outside the research Git checkout")
        state, control, treatment, _ = build_pair_requests()
        output_root.mkdir(parents=True, exist_ok=False)
        self.output_root = output_root
        self.arm_roots = {}
        for arm in ("control", "treatment"):
            root = output_root / arm
            root.mkdir()
            source_copy = root / "production_source"
            shutil.copytree(FROZEN_BUNDLE / "source", source_copy,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "temp"))
            if digest_tree(source_copy) != FROZEN_SOURCE_SNAPSHOT:
                raise RuntimeError("Clean runtime-source copy identity mismatch")
            workspace = root / "workspace"
            source = Path(_read_json(HERE / "CLONE_MANIFEST.json")["arms"][arm]["workspace_path"])
            shutil.copytree(source, workspace)
            if workspace_identity(workspace) != {
                "ordinary_file_count": 2472, "workspace_sha256": EXPECTED["workspace_tree_sha256"]}:
                raise RuntimeError("Fresh arm workspace does not match checkpoint")
            raw = root / "raw"
            raw.mkdir()
            stage = root / "stage"
            prepare_arm_stage(arm, stage, state, control, treatment)
            self.arm_roots[arm] = root
        self.evaluator = NativeEvaluator(output_root / "native_evaluation")

    def execute_arm(self, arm: str) -> ArmResult:
        root = self.arm_roots[arm]
        workspace, stage, raw = (root / "workspace", root / "stage", root / "raw")
        project = "causal-turn30-" + arm + "-" + self.output_root.name.lower().replace("_", "-")[-20:]
        compose = compose_spec(workspace, stage, raw, root / "production_source", project=project)
        compose_file = root / "compose.json"
        compose_file.write_text(json.dumps(compose, indent=2) + "\n", encoding="utf-8")
        base = ["docker", "compose", "-p", project, "-f", str(compose_file)]
        with (raw / "container_stdout.log").open("wb") as stdout, (
                raw / "container_stderr.log").open("wb") as stderr:
            try:
                run = subprocess.run(base + ["up", "--abort-on-container-exit",
                                             "--exit-code-from", "main"],
                                     stdout=stdout, stderr=stderr, timeout=10000, check=False)
            finally:
                subprocess.run(base + ["down", "-v", "--remove-orphans"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=120, check=False)
        result_file = raw / "arm_result.json"
        if run.returncode or not result_file.is_file():
            accepted, last_turn = partial_task_counts(raw / "task_raw_events.jsonl")
            return ArmResult(arm, "infrastructure_failure", last_turn, accepted,
                             str(workspace), str(raw), "child/container did not return a valid result")
        result = _read_json(result_file)
        if result["first_provider_request_sha256"] != canonical_sha(
                _read_json(stage / "expected_request.json")):
            return ArmResult(arm, "infrastructure_failure", result["termination_turn"],
                             result["accepted_task_responses"], str(workspace), str(raw),
                             "first provider request identity mismatch")
        return ArmResult(arm, result["terminal_reason"], result["termination_turn"],
                         result["accepted_task_responses"], str(workspace), str(raw))

    def evaluate_workspace(self, neutral_workspace: str) -> dict:
        return self.evaluator(neutral_workspace)


def partial_task_counts(path: Path) -> tuple[int, int]:
    """Mechanical partial accounting when a child exits without a final result."""
    accepted, last_turn = 0, 30
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                break  # an interrupted final write is preserved, not repaired
            if row.get("kind") == "production_chat_result":
                payload = row.get("payload", {})
                if "raw" in payload and not str(payload.get("content") or "").startswith("!!!Error:"):
                    accepted += 1
            if row.get("kind") == "task_turn":
                last_turn = max(last_turn, int(row["payload"]["turn"]))
    return accepted, last_turn
