#!/usr/bin/env python3
"""M2 proof: run GenericAgent on one CLAW-SWE/SWE-bench Verified instance."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLAW_ROOT = Path(os.environ.get("CLAW_SWE_ROOT", r"E:\LongContext\Ref_Benchmark\CLAW-SWE-Bench"))
GA_HOST = Path(os.environ.get("GA_HOST_ROOT", r"E:\LongContext\GenericAgent-main"))
RUNTIME_ROOT = Path(os.environ.get("M2_RUNTIME_ROOT", r"E:\LongContext\bench_runtime\m2"))
RUNTIME_HOST = RUNTIME_ROOT / "linux"
WORK_ROOT = ROOT / "output" / "m2_claw_swe"
HOST_ENV_PYTHON = RUNTIME_ROOT / "host-env" / "python.exe"
DOCKER_DIR = Path(os.environ.get("DOCKER_CLI_DIR", r"E:\Docker\Desktop\resources\bin"))
INSTANCE_ID = "sphinx-doc__sphinx-8551"
DATASET_NAME = "princeton-nlp/SWE-bench_Verified"
DATASET_REVISION = "c104f840cc67f8b6eec6f759ebc8b2693d585d4a"
INSTANCE_SHA256 = "17680b0dcaa151dbd9f5d9dbc4f4f5d7f8d4f7ae8f88fc537953094ae17b7578"
CLAW_COMMIT = "fcece5f4c0817430ce953b52c80c931a40cd9b83"
GA_SOURCE_SHA256 = "a76afac3cd0bbd0148725f188b8527c83254f4a00310448ac624c81625c1d474"
IMAGE_TAG = "swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-8551:latest"
IMAGE_DIGEST = "sha256:77f476927410992943a8d2744aea86b3e0c50d8773b61e56ebba9dd0fd4b9db1"
IMAGE_REF = f"swebench/sweb.eval.x86_64.sphinx-doc_1776_sphinx-8551@{IMAGE_DIGEST}"
CONTAINER_GA = "/opt/genericagent"
CONTAINER_RUNTIME = "/opt/m2-runtime"
OTEL_PORT = 14318


def _run_checked(cmd: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(cmd)}\n{result.stderr.strip()}")
    return result.stdout.strip()


def validate_claw_checkout() -> dict:
    if not (CLAW_ROOT / ".git").exists():
        raise RuntimeError(f"CLAW-SWE checkout missing: {CLAW_ROOT}")
    git = ["git", "-c", f"safe.directory={CLAW_ROOT.resolve()}", "-C", str(CLAW_ROOT)]
    head = _run_checked(git + ["rev-parse", "HEAD"])
    if head != CLAW_COMMIT:
        raise RuntimeError(f"CLAW-SWE commit mismatch: expected {CLAW_COMMIT}, got {head}")
    status = _run_checked(git + ["status", "--porcelain", "--untracked-files=all"])
    if status:
        raise RuntimeError(f"CLAW-SWE checkout is dirty:\n{status}")
    return {"commit": head, "clean": True}


def _ga_source_hash() -> str:
    files = []
    for path in GA_HOST.rglob("*.py"):
        rel = path.relative_to(GA_HOST)
        if any(part in {"temp", "memory", "__pycache__", ".git"} for part in rel.parts):
            continue
        files.append(path)
    files.append(GA_HOST / "pyproject.toml")
    digest = hashlib.sha256()
    for path in sorted(files, key=lambda item: item.relative_to(GA_HOST).as_posix()):
        rel = path.relative_to(GA_HOST).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(rel).to_bytes(4, "big"))
        digest.update(rel)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def validate_ga_source() -> dict:
    actual = _ga_source_hash()
    method_expected = os.environ.get("GA_METHOD_EXPECTED_SOURCE_SHA256", "").strip().lower()
    expected = method_expected or GA_SOURCE_SHA256
    if len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
        raise RuntimeError("GA_METHOD_EXPECTED_SOURCE_SHA256 must be a 64-character SHA-256")
    if actual != expected:
        raise RuntimeError(f"GenericAgent source mismatch: expected {expected}, got {actual}")
    return {
        "source_sha256": actual,
        "expected_source_sha256": expected,
        "source_contract": "explicit_method_experiment" if method_expected else "frozen_m11",
        "file_set": "python+pyproject excluding temp/memory/cache",
    }


def _bootstrap() -> None:
    validate_claw_checkout()
    os.environ["PATH"] = str(DOCKER_DIR) + os.pathsep + os.environ.get("PATH", "")
    os.environ.setdefault("HF_HOME", str(WORK_ROOT / "hf-cache"))
    if str(CLAW_ROOT) not in sys.path:
        sys.path.insert(0, str(CLAW_ROOT))


_bootstrap()

from claw_swebench import config as claw_config  # noqa: E402
from claw_swebench.claws.generic import (  # noqa: E402
    FORWARDED_ENV_VARS,
    ROUND_END,
    GenericAgentAdapter,
    _parse_usage_text,
)
from datasets import load_dataset  # noqa: E402
from claw_swebench.orchestrator import run_one_instance  # noqa: E402
from claw_swebench.prediction import format_prediction  # noqa: E402
from claw_swebench.types import AgentResult  # noqa: E402
from claw_swebench.workspace import SWEBenchWorkspace  # noqa: E402


def require_utf8_mode(enabled: int | None = None) -> None:
    if (sys.flags.utf8_mode if enabled is None else enabled) == 0:
        raise RuntimeError("M2 runner requires Python UTF-8 mode; invoke it with `python -X utf8`")


def _canonical_sha256(value: dict) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_instance(instance: dict) -> dict:
    if instance.get("instance_id") != INSTANCE_ID:
        raise RuntimeError(f"unexpected instance: {instance.get('instance_id')}")
    actual = _canonical_sha256(instance)
    if actual != INSTANCE_SHA256:
        raise RuntimeError(f"instance data mismatch: expected {INSTANCE_SHA256}, got {actual}")
    return {"dataset": DATASET_NAME, "revision": DATASET_REVISION,
            "instance_id": INSTANCE_ID, "instance_sha256": actual}


def write_pinned_eval_dataset(instance: dict) -> Path:
    validate_instance(instance)
    path = WORK_ROOT / "pinned_dataset.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([instance], ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def validate_image() -> dict:
    result = subprocess.run(
        ["docker", "image", "inspect", IMAGE_TAG], capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode:
        raise RuntimeError(f"pinned SWE image is not local: {IMAGE_TAG}")
    info = json.loads(result.stdout)[0]
    image_id = info.get("Id")
    repo_digests = sorted(info.get("RepoDigests") or [])
    if image_id != IMAGE_DIGEST:
        raise RuntimeError(f"SWE image ID mismatch: expected {IMAGE_DIGEST}, got {image_id}")
    expected_repo_digest = IMAGE_REF
    if expected_repo_digest not in repo_digests:
        raise RuntimeError(f"SWE RepoDigest mismatch: expected {expected_repo_digest}, got {repo_digests}")
    return {"tag": IMAGE_TAG, "immutable_ref": IMAGE_REF, "image_id": image_id,
            "repo_digests": repo_digests}


def resolve_model_identity(llm_no: int) -> dict:
    if llm_no < 0:
        raise RuntimeError("llm_no must be non-negative")
    python_bin = f"{CONTAINER_RUNTIME}/python/{_python_home().name}/bin/python3.12"
    site_packages = f"{CONTAINER_RUNTIME}/ga-env/lib/python3.12/site-packages"
    resolver = (
        "import hashlib,json,pathlib;from agentmain import GenericAgent;"
        "a=GenericAgent();count=len(a.llmclients);requested=int(__import__('os').environ['M2_LLM_NO']);"
        "assert requested<count,f'llm_no {requested} out of range 0..{count-1}';a.next_llm(requested);"
        "b=a.llmclient.backend;cfg=pathlib.Path('/opt/genericagent/mykey.py').read_bytes();"
        "print('M2_IDENTITY='+json.dumps({'requested_llm_no':requested,'effective_llm_no':a.llm_no,"
        "'model':b.model.lower(),'backend_type':type(b).__name__,'backend_name':b.name,"
        "'available_models':count,'config_sha256':hashlib.sha256(cfg).hexdigest()},sort_keys=True))"
    )
    cmd = [
        "docker", "run", "--rm", "-v", f"{RUNTIME_HOST.resolve()}:{CONTAINER_RUNTIME}:ro",
        "-v", f"{GA_HOST.resolve()}:{CONTAINER_GA}:ro", "-e", f"M2_LLM_NO={llm_no}",
        "-e", f"PYTHONPATH={site_packages}:{CONTAINER_GA}", "debian:bookworm-slim",
        python_bin, "-c", resolver,
    ]
    output = _run_checked(cmd)
    marker = next((line for line in output.splitlines() if line.startswith("M2_IDENTITY=")), None)
    if not marker:
        raise RuntimeError("GA model resolver did not emit identity")
    identity = json.loads(marker.split("=", 1)[1])
    if not identity.get("model"):
        raise RuntimeError("GA model resolver returned an empty model")
    return identity


def observed_models_from_otel(path: Path, run_id: str) -> set[str]:
    models = set()
    if not path.exists():
        return models
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if run_id not in line:
            continue
        payload = json.loads(line)
        for resource in payload.get("resourceSpans", []):
            for scope in resource.get("scopeSpans", []):
                for span in scope.get("spans", []):
                    attrs = {item["key"]: item.get("value", {}) for item in span.get("attributes", [])}
                    if attrs.get("benchmark.run.id", {}).get("stringValue") != run_id:
                        continue
                    model = attrs.get("gen_ai.request.model", {}).get("stringValue")
                    if model:
                        models.add(model.lower())
    return models


def _python_home() -> Path:
    matches = sorted((RUNTIME_HOST / "python").glob("cpython-3.12.*-linux-x86_64-gnu"))
    if len(matches) != 1:
        raise RuntimeError(f"expected one managed Python 3.12 runtime, found {len(matches)}")
    return matches[0]


def _mount(source: Path, target: str, mode: str) -> list[str]:
    return ["-v", f"{source.resolve()}:{target}:{mode}"]


def pin_workspace_image() -> None:
    SWEBenchWorkspace._resolve_image = staticmethod(lambda _instance_id: IMAGE_REF)


def usage_from_otel(path: Path, run_id: str) -> dict:
    totals = {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}
    if not path.exists():
        return totals
    names = {
        "gen_ai.usage.input_tokens": "input",
        "gen_ai.usage.output_tokens": "output",
        "ga.usage.cache_read_input_tokens": "cacheRead",
        "ga.usage.cache_creation_input_tokens": "cacheWrite",
    }
    seen = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if run_id not in line:
            continue
        payload = json.loads(line)
        for resource in payload.get("resourceSpans", []):
            for scope in resource.get("scopeSpans", []):
                for span in scope.get("spans", []):
                    if span.get("spanId") in seen:
                        continue
                    attrs = {item["key"]: item.get("value", {}) for item in span.get("attributes", [])}
                    if attrs.get("benchmark.run.id", {}).get("stringValue") != run_id:
                        continue
                    seen.add(span.get("spanId"))
                    for source, target in names.items():
                        totals[target] += int(attrs.get(source, {}).get("intValue", 0))
    return totals


class M2GenericAgentAdapter(GenericAgentAdapter):
    """Windows-host compatibility overlay; CLAW workspace remains unchanged."""

    def __init__(self, run_id: str, model_identity: dict, timeout: int = 3600):
        max_turns = int(os.environ.get("GA_MAX_TURNS", "300"))
        super().__init__(model=model_identity["model"], timeout=timeout, max_turns=max_turns,
                         llm_no=model_identity["effective_llm_no"])
        self.run_id = run_id
        self.model_identity = model_identity
        self.temp_root = WORK_ROOT / "work" / run_id / "temp"
        self.memory_root = WORK_ROOT / "work" / run_id / "memory"
        self.artifacts_root = WORK_ROOT / "runs" / run_id

    def container_run_args(self, instance_id: str) -> list[str]:
        host_temp = self.temp_root / instance_id
        host_temp.mkdir(parents=True, exist_ok=True)
        host_memory = self.memory_root / instance_id
        if host_memory.exists():
            shutil.rmtree(host_memory)
        shutil.copytree(GA_HOST / "memory", host_memory)
        host_artifacts = self.artifacts_root / instance_id
        host_artifacts.mkdir(parents=True, exist_ok=True)
        args = []
        args += _mount(RUNTIME_HOST, CONTAINER_RUNTIME, "ro")
        args += _mount(GA_HOST, CONTAINER_GA, "ro")
        args += _mount(host_temp, f"{CONTAINER_GA}/temp", "rw")
        args += _mount(host_memory, f"{CONTAINER_GA}/memory", "rw")
        args += _mount(host_artifacts, "/opt/m2-artifacts", "rw")
        return args

    def build_exec_command(self, agent_id: str, container_name: str, instance_id: str) -> list[str]:
        python_bin = f"{CONTAINER_RUNTIME}/python/{_python_home().name}/bin/python3.12"
        site_packages = f"{CONTAINER_RUNTIME}/ga-env/lib/python3.12/site-packages"
        cmd = [
            "docker", "exec", "-w", "/testbed",
            "-e", f"PYTHONPATH={site_packages}:{CONTAINER_GA}",
            "-e", "GA_LANG=en",
            "-e", "GA_OTEL_ENABLED=1",
            "-e", "GA_OTEL_CAPTURE_CONTENT=0",
            "-e", f"GA_BENCH_RUN_ID={self.run_id}",
            "-e", f"GA_BENCH_TASK_ID={instance_id}",
            "-e", "GA_BENCH_EXPECTED_TURNS=1",
            "-e", "GA_OTEL_ARTIFACT_DIR=/opt/m2-artifacts",
            "-e", "OTEL_SERVICE_NAME=genericagent-claw-swe",
            "-e", (
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="
                f"http://host.docker.internal:{OTEL_PORT}/v1/traces"
            ),
        ]
        for name in FORWARDED_ENV_VARS:
            value = os.environ.get(name)
            if value:
                cmd += ["-e", f"{name}={value}"]
        for name in (
            "GA_LLM_CONFIG_NAME", "GA_MAX_TURNS", "GA_M0_MONITOR_ENABLED",
            "GA_M0_MONITOR_CONFIG", "GA_M0_MAX_INSPECTIONS",
            "GA_M0_RECENT_TRAJECTORY_TURNS",
            "GA_M1_WORKSPACE_ENABLED",
        ):
            value = os.environ.get(name)
            if value:
                cmd += ["-e", f"{name}={value}"]
        if os.environ.get("GA_M0_MONITOR_ENABLED") == "1":
            cmd += ["-e", "GA_M0_MONITOR_ARTIFACT_DIR=/opt/m2-artifacts/m0_monitor"]
        elif os.environ.get("GA_M1_WORKSPACE_ENABLED") == "1":
            raise ValueError("GA_M1_WORKSPACE_ENABLED requires GA_M0_MONITOR_ENABLED")
        cmd += [
            container_name, python_bin, f"{CONTAINER_GA}/agentmain.py",
            "--task", agent_id, "--llm_no", str(self.llm_no),
            "--nobg", "--verbose", "--no-user-tools",
        ]
        return cmd

    def send_task(self, prompt, agent_id, container_name, artifact_dir=None, instance_id=None):
        instance_id = instance_id or agent_id
        host_temp = self.temp_root / instance_id / agent_id
        host_temp.mkdir(parents=True, exist_ok=True)
        for stale in host_temp.glob("output*.txt"):
            stale.unlink()
        reply = host_temp / "reply.txt"
        if reply.exists():
            reply.unlink()
        (host_temp / "input.txt").write_text(prompt, encoding="utf-8")
        artifact_dir = Path(artifact_dir) if artifact_dir else None
        cmd = self.build_exec_command(agent_id, container_name, instance_id)
        started = time.time()
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output_path = host_temp / "output.txt"
        sentinel_seen = False
        timed_out = False
        try:
            while time.time() < started + self.timeout:
                if proc.poll() is not None:
                    break
                if output_path.exists() and ROUND_END in output_path.read_text(encoding="utf-8", errors="replace"):
                    sentinel_seen = True
                    break
                time.sleep(2)
            else:
                timed_out = True
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    proc.kill()
            stdout, stderr = proc.communicate(timeout=10)
        if artifact_dir:
            (artifact_dir / "agent_stdout.log").write_text(stdout or "", encoding="utf-8")
            (artifact_dir / "agent_stderr.log").write_text(stderr or "", encoding="utf-8")
        reason = "timeout" if timed_out else ("stop" if sentinel_seen else "error")
        usage = usage_from_otel(WORK_ROOT / "otel" / "traces.jsonl", self.run_id)
        if not any(usage.values()):
            usage = _parse_usage_text((stdout or "") + (output_path.read_text(encoding="utf-8", errors="replace") if output_path.exists() else ""))
        return AgentResult(
            success=reason == "stop", timeout=timed_out, exit_code=0 if sentinel_seen else (proc.returncode or 0),
            finish_reason=reason, stdout_path=artifact_dir / "agent_stdout.log" if artifact_dir else None,
            stderr_path=artifact_dir / "agent_stderr.log" if artifact_dir else None,
            session_id=None, duration_seconds=round(time.time() - started, 1),
            usage=usage,
        )

    def backup_session(self, agent_id: str, dest: Path) -> None:
        for instance_dir in self.temp_root.glob("*"):
            source = instance_dir / agent_id
            if source.exists():
                for name in ("output.txt", "stdout.log", "stderr.log", "input.txt"):
                    path = source / name
                    if path.exists():
                        shutil.copy2(path, dest / name)


def load_instance() -> dict:
    cached = WORK_ROOT / "instance.json"
    if cached.exists():
        instance = json.loads(cached.read_text(encoding="utf-8"))
        validate_instance(instance)
        return instance
    dataset = load_dataset(DATASET_NAME, split="test", revision=DATASET_REVISION)
    rows = [dict(row) for row in dataset if row["instance_id"] == INSTANCE_ID]
    if len(rows) != 1:
        raise RuntimeError(f"expected one instance, got {len(rows)}")
    validate_instance(rows[0])
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(rows[0], ensure_ascii=False, indent=2), encoding="utf-8")
    return rows[0]


def collect_reproducibility_identity(llm_no: int | None = None) -> dict:
    instance = load_instance()
    write_pinned_eval_dataset(instance)
    identity = {
        "schema_version": "m2-reproducibility-manifest/1",
        "claw_swe": validate_claw_checkout(),
        "generic_agent": validate_ga_source(),
        "dataset": validate_instance(instance),
        "image": validate_image(),
        "runtime": {"host_root": str(RUNTIME_ROOT.resolve()), "container_root": CONTAINER_RUNTIME},
    }
    if llm_no is not None:
        identity["model"] = resolve_model_identity(llm_no)
    return identity


def write_run_manifest(run_id: str, kind: str, identity: dict) -> Path:
    run_dir = WORK_ROOT / "runs" / run_id
    manifest = run_dir / "immutable_manifest.json"
    if manifest.exists():
        raise RuntimeError(f"run manifest already exists; choose a new run ID: {manifest}")
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {"run_id": run_id, "kind": kind, **identity}
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def validate_run_manifest(run_id: str) -> dict:
    run_dir = WORK_ROOT / "runs" / run_id
    manifest_path = run_dir / "immutable_manifest.json"
    predictions_path = run_dir / "predictions.jsonl"
    if not manifest_path.exists() or not predictions_path.exists():
        raise RuntimeError("evaluate requires immutable_manifest.json and predictions.jsonl for the run")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("run_id") != run_id:
        raise RuntimeError("manifest run_id does not match requested run")
    model = manifest.get("model")
    llm_no = model.get("requested_llm_no") if model else None
    current = collect_reproducibility_identity(llm_no)
    for key, value in current.items():
        if manifest.get(key) != value:
            raise RuntimeError(f"manifest identity mismatch for {key}")
    predictions = [json.loads(line) for line in predictions_path.read_text(encoding="utf-8").splitlines() if line]
    if len(predictions) != 1 or predictions[0].get("instance_id") != INSTANCE_ID:
        raise RuntimeError("prediction must contain exactly the pinned instance")
    if model and predictions[0].get("model_name_or_path") != model["model"]:
        raise RuntimeError("prediction model does not match resolved manifest model")
    if not model and predictions[0].get("model_name_or_path") != "m2-controlled-empty-patch":
        raise RuntimeError("controlled-failure prediction has an unexpected model label")
    return manifest


def preflight(run_id: str) -> dict:
    instance = load_instance()
    identity = collect_reproducibility_identity(0)
    pin_workspace_image()
    adapter = M2GenericAgentAdapter(run_id, identity["model"], timeout=30)
    workspace = SWEBenchWorkspace(INSTANCE_ID, adapter)
    checks = {"claw_commit": True, "ga_source": True, "dataset_revision_and_hash": True,
              "image_digest": True, "model_resolved": True}
    try:
        name = workspace.start()
        workspace.prepare_instance(instance["base_commit"])
        checks["base_commit"] = workspace.run_in_container("git rev-parse HEAD").stdout.strip() == instance["base_commit"]
        checks["python"] = workspace.run_in_container(
            f"{CONTAINER_RUNTIME}/python/{_python_home().name}/bin/python3.12 --version"
        ).exit_code == 0
        checks["ga_import"] = workspace.run_in_container(
            f"{CONTAINER_RUNTIME}/python/{_python_home().name}/bin/python3.12 -c \"import sys;"
            "sys.path[:0]=['/opt/m2-runtime/ga-env/lib/python3.12/site-packages','/opt/genericagent'];"
            "import agentmain\""
        ).exit_code == 0
        scan = workspace.run_in_container(
            "find /testbed /root /tmp -type f \\( -iname 'gold.patch' -o "
            "-iname 'reference.patch' -o -iname 'solution.patch' -o -iname 'test.patch' \\) 2>/dev/null"
        )
        checks["no_solution_artifacts"] = not scan.stdout.strip()
        checks["container_name"] = name
    finally:
        workspace.cleanup()
    checks["cleaned_up"] = subprocess.run(
        ["docker", "container", "inspect", f"generic-swe-{INSTANCE_ID}"], capture_output=True
    ).returncode != 0
    report = WORK_ROOT / "runs" / run_id / "preflight.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(checks, indent=2), encoding="utf-8")
    return checks


def write_controlled_failure(run_id: str) -> Path:
    identity = collect_reproducibility_identity()
    write_run_manifest(run_id, "controlled_failure", identity)
    path = WORK_ROOT / "runs" / run_id / "predictions.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    pred = format_prediction(INSTANCE_ID, "", "m2-controlled-empty-patch")
    path.write_text(json.dumps(pred) + "\n", encoding="utf-8")
    return path


def eval_dir_name(run_id: str) -> str:
    return f"{run_id}-{INSTANCE_SHA256[:12]}"


def build_eval_command(run_id: str) -> list[str]:
    work_mount = f"{WORK_ROOT.resolve()}:/work"
    runtime_mount = f"{RUNTIME_HOST.resolve()}:/opt/m2-runtime:ro"
    eval_dir = eval_dir_name(run_id)
    return [
        "docker", "run", "--rm", "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "-v", runtime_mount, "-v", work_mount, "-w", f"/work/eval/{eval_dir}",
        "-e", "HF_HOME=/work/hf-cache", "debian:bookworm-slim",
        "/opt/m2-runtime/eval-env/bin/python", "-m", "swebench.harness.run_evaluation",
        "-d", "/work/pinned_dataset.json", "-i", INSTANCE_ID,
        "-p", f"/work/runs/{run_id}/predictions.jsonl", "--max_workers", "1",
        "-t", "1800", "--cache_level", "instance", "--clean", "false",
        "-id", run_id, "-n", "swebench", "--report_dir", f"/work/eval/{eval_dir}",
    ]


def run_agent(run_id: str, timeout: int, llm_no: int):
    identity = collect_reproducibility_identity(llm_no)
    manifest_path = write_run_manifest(run_id, "formal_agent_run", identity)
    manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    pin_workspace_image()
    model_identity = identity["model"]
    model_name = model_identity["model"]
    claw_config.ARTIFACTS_ROOT = WORK_ROOT / "runs"
    record = run_one_instance(
        load_instance(), M2GenericAgentAdapter(run_id, model_identity, timeout), model_name, run_id
    )
    observed = observed_models_from_otel(WORK_ROOT / "otel" / "traces.jsonl", run_id)
    validation = {
        "run_id": run_id,
        "expected_model": model_name,
        "observed_models": sorted(observed),
        "model_match": observed == {model_name},
        "manifest_sha256": manifest_sha256,
        "manifest_unchanged": hashlib.sha256(manifest_path.read_bytes()).hexdigest() == manifest_sha256,
        "image_after_run": validate_image(),
    }
    validation_path = WORK_ROOT / "runs" / run_id / "identity_validation.json"
    validation_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    if not validation["model_match"]:
        raise RuntimeError(f"OTel model mismatch: expected {model_name}, observed {sorted(observed)}")
    if not validation["manifest_unchanged"]:
        raise RuntimeError("run manifest changed during execution")
    print(json.dumps({"instance_id": record.instance_id, "state": record.state.value,
                      "patch_empty": record.patch_empty, "error": record.error,
                      "model": model_name}, ensure_ascii=False))


def main() -> int:
    require_utf8_mode()
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("preflight", "controlled-failure", "run", "evaluate"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--llm-no", type=int, default=0)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.action == "preflight":
        result = preflight(args.run_id)
        print(json.dumps(result, indent=2))
        return 0 if all(v for k, v in result.items() if k != "container_name") else 1
    if args.action == "controlled-failure":
        print(write_controlled_failure(args.run_id))
        return 0
    if args.action == "evaluate":
        validate_run_manifest(args.run_id)
        run_dir = WORK_ROOT / "runs" / args.run_id
        eval_identity = {
            "run_id": args.run_id,
            "manifest_identity_valid": True,
            "manifest_sha256": hashlib.sha256((run_dir / "immutable_manifest.json").read_bytes()).hexdigest(),
            "predictions_sha256": hashlib.sha256((run_dir / "predictions.jsonl").read_bytes()).hexdigest(),
            "dataset_sha256": INSTANCE_SHA256,
            "image_digest": IMAGE_DIGEST,
        }
        (run_dir / "evaluation_identity_validation.json").write_text(
            json.dumps(eval_identity, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (WORK_ROOT / "eval" / eval_dir_name(args.run_id)).mkdir(parents=True, exist_ok=True)
        result = subprocess.run(build_eval_command(args.run_id)).returncode
        validate_image()
        return result
    run_agent(args.run_id, args.timeout, args.llm_no)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
